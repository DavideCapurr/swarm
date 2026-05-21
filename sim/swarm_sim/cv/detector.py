"""Phase 7.D — YOLOv8 wrapper.

The wrapper is the seam between `CVPerception` and `ultralytics`. It
exists for three reasons:

1. *Lazy import.* `ultralytics` + `torch` are ~2 GB of wheels and pull
   CUDA on some systems. Importing them eagerly would tank `make setup`
   for the 99% of contributors who never opt into the `cv` extra. The
   import happens inside `_load_runtime()` and is gated by a clear
   error if the extra is missing.
2. *Deterministic predict.* YOLOv8 caches CUDA contexts and the random
   number generator state across calls. We seed `torch` + numpy
   explicitly before every predict and pass `verbose=False` so the
   stdout stays clean for tests that grep on it. The contract is
   "same image bytes + same model file + same conf-floor → same
   detection top-1".
3. *Fail-closed mapping.* The drone_day fire/person-aerial weights are
   placeholders today (see `manifest.json`). `predict` falls back to
   the AGPL COCO baseline + a class-name heuristic ("person" for
   `INTRUSION` / `HEAT_SPOT`; "fire", "smoke" if present else any
   ELEVATED detection for `SMOKE` / `FIRE`). The confidence still
   comes from the model — never from the scenario YAML.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from swarm_core.messages import AnomalyKind

from sim.swarm_sim.cv.weights import (
    AssetPlaceholder,
    AssetUnavailable,
    CVAssetError,
    ensure_asset,
    load_manifest,
)

logger = logging.getLogger("sim.cv")

_FIRE_WEIGHT = "yolov8n-fire.pt"
_PERSON_WEIGHT = "yolov8n-person-aerial.pt"
_BASELINE_WEIGHT = "yolov8n.pt"
_DEFAULT_CONF_FLOOR = 0.05
_TORCH_SEED = 0

# COCO baseline class-name heuristics. The Ultralytics yolov8n.pt model
# carries 80 COCO classes; we map AnomalyKind to a short candidate list.
# Phase 8.B will replace these with site-tuned thresholds.
_KIND_TO_COCO_CLASSES: dict[AnomalyKind, tuple[str, ...]] = {
    AnomalyKind.FIRE: ("fire", "smoke"),
    AnomalyKind.SMOKE: ("smoke", "fire"),
    AnomalyKind.HEAT_SPOT: ("person",),
    AnomalyKind.INTRUSION: ("person",),
    AnomalyKind.UNKNOWN: (),
}


class CVRuntimeUnavailable(CVAssetError):
    """`ultralytics`/`torch` is not importable in this environment."""


@dataclass(frozen=True)
class Detection:
    """The single top-1 detection used by `CVPerception`."""

    label: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


def _load_runtime() -> tuple[Any, Any]:
    """Import `ultralytics.YOLO` + `torch` lazily.

    Raises `CVRuntimeUnavailable` with an actionable hint when the
    `cv` extra has not been installed (`make setup-cv`).
    """

    try:
        import torch  # type: ignore[import-not-found]
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised by env tests
        raise CVRuntimeUnavailable(
            "ultralytics/torch not installed — run `make setup-cv` "
            "(opt-in extra; default `make setup` deliberately skips it)"
        ) from exc
    return YOLO, torch


class YOLODetector:
    """Thin wrapper that picks the right pretrained weight per AnomalyKind.

    The constructor is cheap — model loading is deferred to the first
    `predict()` call so smoke tests that only inspect manifests don't
    pay the 200 MB load cost.
    """

    def __init__(self, *, conf_floor: float = _DEFAULT_CONF_FLOOR) -> None:
        if not 0.0 <= conf_floor <= 1.0:
            raise CVAssetError(f"conf_floor must be in [0, 1]; got {conf_floor}")
        self._conf_floor = conf_floor
        self._models: dict[str, Any] = {}
        self._manifest = load_manifest()

    def _model_for(self, kind: AnomalyKind) -> tuple[Any, str]:
        """Return (loaded YOLO model, weight name).

        Falls back to the COCO baseline when the per-kind weight is still
        a drone_day placeholder.
        """

        wanted: str
        if kind in (AnomalyKind.FIRE, AnomalyKind.SMOKE):
            wanted = _FIRE_WEIGHT
        elif kind in (AnomalyKind.INTRUSION, AnomalyKind.HEAT_SPOT):
            wanted = _PERSON_WEIGHT
        else:
            wanted = _BASELINE_WEIGHT
        try:
            path = ensure_asset(wanted, manifest=self._manifest)
        except (AssetPlaceholder, AssetUnavailable) as exc:
            logger.info(
                "cv: %s unavailable (%s); falling back to %s",
                wanted, exc, _BASELINE_WEIGHT,
            )
            wanted = _BASELINE_WEIGHT
            path = ensure_asset(wanted, manifest=self._manifest)
        if wanted not in self._models:
            self._models[wanted] = self._load_yolo(path)
        return self._models[wanted], wanted

    def _load_yolo(self, weight_path: Path) -> Any:
        YOLO, torch = _load_runtime()
        torch.manual_seed(_TORCH_SEED)
        return YOLO(str(weight_path))

    def predict(self, frame_path: Path, kind: AnomalyKind) -> Detection:
        """Run inference on `frame_path` and return the top-1 detection.

        The frame is opened by `ultralytics` (which goes through OpenCV
        internally). The candidate label list per kind is documented in
        `_KIND_TO_COCO_CLASSES`; if no class matches, the top-1 detection
        of any class wins — confidence still comes from the real model
        output. If nothing detects at all, we return a zero-confidence
        placeholder so the seam stays honest (the autonomy baseline
        decides whether 0.0 is "below threshold").
        """

        if not frame_path.is_file():
            raise CVAssetError(f"frame {frame_path} does not exist")
        model, weight_name = self._model_for(kind)
        _, torch = _load_runtime()
        torch.manual_seed(_TORCH_SEED)
        results = model.predict(
            source=str(frame_path),
            conf=self._conf_floor,
            verbose=False,
            stream=False,
        )
        return self._pick(results, kind, weight_name)

    def _pick(self, results: Any, kind: AnomalyKind, weight_name: str) -> Detection:
        """Pick the most relevant detection from a YOLO `Results` iterable."""

        candidates = _KIND_TO_COCO_CLASSES.get(kind, ())
        best: Detection | None = None
        for r in results:
            names: dict[int, str] = r.names if hasattr(r, "names") else {}
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls.item()) if hasattr(box.cls, "item") else int(box.cls)
                label = names.get(cls_id, str(cls_id))
                conf = float(box.conf.item() if hasattr(box.conf, "item") else box.conf)
                xyxy_raw = box.xyxy[0]
                xyxy = tuple(float(v.item() if hasattr(v, "item") else v) for v in xyxy_raw)
                det = Detection(label=label, confidence=conf, bbox_xyxy=xyxy)  # type: ignore[arg-type]
                if candidates and label.lower() in candidates:
                    if best is None or det.confidence > best.confidence:
                        best = det
                elif best is None:
                    best = det
        if best is None:
            logger.info(
                "cv: %s emitted zero detections via %s (kind=%s)",
                weight_name, weight_name, kind.value,
            )
            return Detection(label="", confidence=0.0, bbox_xyxy=(0.0, 0.0, 0.0, 0.0))
        return best

"""Phase 7.D — CV baseline (pretrained, no fine-tuning).

This package replaces the deterministic-but-mock perception with real YOLOv8
inference on committed smoke fixtures (or, when cached, reference samples
from FLAME / D-Fire / VisDrone). The seam matches `MockPerception`
structurally: same `run()` + `on_anomaly` callback, same `IgnitionEvent`
schedule. Only `confidence` becomes a real model output.

Opt-in only:
- Install via `make setup-cv` (`uv sync --extra cv`). Default `make setup`
  does NOT install the extra (~2 GB of wheels) and the prod image does
  not carry it either.
- Enable per-scenario with `perception.cv_enabled: true` in the YAML
  (mirror of Phase 7.B's `autonomy_baseline` flag).

License posture (Ultralytics is AGPL-3.0): see
`docs/security/threat-model.md` §Supply chain + `docs/cv/phase-7d.md`.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

"""Phase 7.D — YOLOv8 detector smoke test.

Gated by `pytest.importorskip("ultralytics")` + marker `cv_baseline` so
the default `make test` (no `[cv]` extra) skips this file silently.
Run via `make test-cv` after `make setup-cv`.

The test is intentionally narrow: invoke the detector on the smallest
real input (one committed PNG fixture) and assert it returns a
`Detection` with a numeric confidence and a bbox tuple. The point is
that the seam wires through — ultralytics loads, torch runs, the
manifest provides the weight path, and a `Detection` flows back to
`CVPerception`. The smoke fixtures are 32x32 zero-pixel PNGs, so YOLO
will almost certainly emit `conf=0.0` from the zero-detection branch.
That IS the contract the test asserts.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.cv_baseline
ultralytics = pytest.importorskip("ultralytics")

from swarm_core.messages import AnomalyKind  # noqa: E402

from sim.swarm_sim.cv.detector import Detection, YOLODetector  # noqa: E402
from sim.swarm_sim.cv.weights import list_fixtures  # noqa: E402


def test_detector_returns_detection_on_real_frame() -> None:
    frames = list_fixtures("fire")
    assert frames, "no committed fire fixtures"
    detector = YOLODetector(conf_floor=0.0)
    det = detector.predict(frames[0], AnomalyKind.SMOKE)
    assert isinstance(det, Detection)
    assert 0.0 <= det.confidence <= 1.0
    assert len(det.bbox_xyxy) == 4
    assert all(isinstance(v, float) for v in det.bbox_xyxy)


def test_detector_is_deterministic_across_calls() -> None:
    """Same image + same model → same confidence (Phase 8.B-bis precondition)."""
    frames = list_fixtures("fire")
    assert frames
    detector = YOLODetector(conf_floor=0.0)
    a = detector.predict(frames[0], AnomalyKind.SMOKE)
    b = detector.predict(frames[0], AnomalyKind.SMOKE)
    assert a.confidence == b.confidence
    assert a.bbox_xyxy == b.bbox_xyxy
    assert a.label == b.label

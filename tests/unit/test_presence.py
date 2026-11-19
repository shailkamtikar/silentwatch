import numpy as np
import pytest

from silentwatch.presence.estimator import (
    MediaPipeFaceBackend,
    ModelMissingError,
    PresenceEstimator,
    PresenceObservation as Obs,
    PresenceState as P,
    PresenceTracker,
)

FACE, NONE = Obs(1, 0.9), Obs(0, 0.0)


def run(tracker, seq, dt=0.2, t0=0.0):
    out, t = [], t0
    for o in seq:
        out.append(tracker.update(o, t))
        t += dt
    return out


class FakeBackend:
    def __init__(self, scores):
        self.scores = scores

    def detect(self, bgr):
        return list(self.scores)


def test_becomes_present_after_consecutive_detections():
    st = run(PresenceTracker(3), [FACE] * 5)
    assert st[0] != P.PRESENT and st[1] != P.PRESENT and st[2] == P.PRESENT


def test_head_turn_stays_present_or_uncertain_not_absent():
    t = PresenceTracker(3, pending_s=3.0, lock_after_s=10.0)
    run(t, [FACE] * 5)
    st = run(t, [NONE] * 10, t0=1.0)  # 2 s without a face
    assert all(s in (P.PRESENT, P.UNCERTAIN) for s in st)


def test_pending_then_confirmed_at_configured_times():
    t = PresenceTracker(3, pending_s=3.0, lock_after_s=10.0)
    run(t, [FACE] * 5)            # last seen at t=0.8
    st = {}
    for k in range(1, 70):
        ts = 0.8 + k * 0.2
        st[round(ts - 0.8, 1)] = t.update(NONE, ts)
    assert st[2.8] != P.ABSENT_PENDING and st[3.0] == P.ABSENT_PENDING
    assert st[9.8] == P.ABSENT_PENDING and st[10.0] == P.ABSENT_CONFIRMED


def test_return_requires_consecutive_detections_hysteresis():
    t = PresenceTracker(3, pending_s=3.0, lock_after_s=10.0)
    run(t, [FACE] * 5)
    run(t, [NONE] * 40, t0=1.0)
    assert t.state == P.ABSENT_PENDING or t.state == P.ABSENT_CONFIRMED
    t.update(FACE, 9.0)
    assert t.state != P.PRESENT          # one detection (e.g. a false positive) is not enough
    t.update(FACE, 9.2)
    t.update(FACE, 9.4)
    assert t.state == P.PRESENT


def test_pause_does_not_count_as_absence():
    t = PresenceTracker(3, pending_s=3.0, lock_after_s=10.0)
    run(t, [FACE] * 5)
    t.pause(1.0)
    st = t.update(NONE, 60.0)             # camera was out for 59 s
    assert st in (P.PRESENT, P.UNCERTAIN)


def test_two_people_counted():
    est = PresenceEstimator(FakeBackend([0.9, 0.8]))
    assert est.observe(np.zeros((48, 64, 3), np.uint8)).face_count == 2


def test_confidence_threshold_applied():
    est = PresenceEstimator(FakeBackend([0.3, 0.45]), min_confidence=0.5)
    assert est.observe(np.zeros((8, 8, 3), np.uint8)).face_count == 0


def test_model_missing_is_actionable(tmp_path):
    with pytest.raises(ModelMissingError, match="download_models"):
        MediaPipeFaceBackend(tmp_path / "nope.tflite")


def test_invalid_timer_order_rejected():
    with pytest.raises(ValueError):
        PresenceTracker(3, pending_s=10.0, lock_after_s=3.0)


def test_real_model_finds_no_face_in_blank_frame():
    from silentwatch.presence.estimator import DEFAULT_FACE_MODEL

    if not DEFAULT_FACE_MODEL.exists():
        pytest.skip("model not downloaded")
    backend = MediaPipeFaceBackend()
    assert PresenceEstimator(backend).observe(np.zeros((480, 640, 3), np.uint8)).face_count == 0
    backend.close()

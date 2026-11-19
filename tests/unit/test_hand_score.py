import numpy as np
import pytest

from silentwatch.camera.hand_detector import (
    DEFAULT_HAND_MODEL,
    HandApproachTracker,
    HandBox,
    HandModelMissingError,
    MediaPipeHandBackend,
    score_from,
)


def box(area_side):
    s = area_side
    return HandBox(0.1, 0.1, 0.1 + s, 0.1 + s)


def feed(tr, sides, dt=0.1, t0=0.0):
    return [tr.update([box(s)] if s else [], t0 + i * dt) for i, s in enumerate(sides)]


def test_no_hand_scores_zero():
    assert all(r.score == 0 for r in feed(HandApproachTracker(), [0] * 20))


def test_approaching_hand_score_rises_and_is_clipped():
    tr = HandApproachTracker(approach_growth=0.35)
    sides = [0.10 + 0.04 * i for i in range(15)]        # hand grows steadily toward the lens
    res = feed(tr, sides)
    scores = [r.score for r in res]
    assert scores[-1] > scores[3] and 0.0 <= max(scores) <= 1.0
    assert tr.approaching(res[-1])


def test_hand_moving_away_score_falls():
    tr = HandApproachTracker()
    res = feed(tr, [0.4, 0.4, 0.4, 0.4, 0.4, 0.4] + [0.4 - 0.05 * i for i in range(1, 7)])
    assert res[-1].score < res[5].score


def test_small_distant_hand_is_not_approaching():
    tr = HandApproachTracker()
    res = feed(tr, [0.05 + 0.002 * i for i in range(20)])
    assert not tr.approaching(res[-1])


def test_score_is_monotone_in_growth_and_size():
    base = [score_from(0.2, then, 0.35).score for then in (0.2, 0.18, 0.15, 0.10, 0.05)]
    assert base == sorted(base)
    sizes = [score_from(a, a, 0.35).score for a in (0.05, 0.12, 0.2, 0.3, 0.45)]
    assert sizes == sorted(sizes) and sizes[-1] <= 1.0


def test_hand_filling_frame_is_high_even_without_motion():
    assert score_from(0.5, 0.5, 0.35).score == pytest.approx(1.0)


def test_model_missing_is_graceful(tmp_path):
    with pytest.raises(HandModelMissingError, match="download_models"):
        MediaPipeHandBackend(tmp_path / "nope.task")


def test_real_model_blank_frame_has_no_hands():
    if not DEFAULT_HAND_MODEL.exists():
        pytest.skip("model not downloaded")
    be = MediaPipeHandBackend()
    assert be.detect(np.zeros((480, 640, 3), np.uint8)) == []
    be.close()

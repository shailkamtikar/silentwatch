import numpy as np
import pytest

from silentwatch.camera.calibration import baseline_from_images
from silentwatch.camera.integrity import FeatureExtractor
from silentwatch.camera.obstruction import ObstructionClassifier, ObstructionState as S, log_obstruction
from silentwatch.config import default_config
from silentwatch.storage import Database, EventStore, EventType
from tests.fixtures import synthetic as syn

H, W = 96, 128
CFG = default_config().obstruction
DT = 0.2  # 5 fps


def normal(i):
    return syn.scene(seed=i % 3, h=H, w=W)


def finger(i):
    rng = np.random.default_rng(i)
    img = np.full((H, W, 3), (45, 90, 190), np.float32) + rng.normal(0, 1.0, (H, W, 3))
    return np.clip(img, 0, 255).astype(np.uint8)


def black_noise(i):
    rng = np.random.default_rng(i)
    return np.clip(rng.normal(0.4, 0.6, (H, W, 3)), 0, 255).astype(np.uint8)


def half_cover(i):
    img = normal(i).copy()
    img[:, : W // 2] = finger(i)[:, : W // 2]
    return img


def lights_off(i):
    return syn.dim(normal(i), 0.12)


@pytest.fixture
def baseline():
    return baseline_from_images([normal(i) for i in range(30)], "camera0", "640x480")


def run(clf, frames, t0=0.0):
    ex = FeatureExtractor()
    out = []
    for k, img in enumerate(frames):
        out.append(clf.update(ex.update(img), t0 + k * DT))
    return out


def seq(*parts):
    """parts: (function, seconds)"""
    frames, i = [], 0
    for fn, secs in parts:
        for _ in range(int(round(secs / DT))):
            frames.append(fn(i))
            i += 1
    return frames


def test_normal_scene_stays_normal(baseline):
    res = run(ObstructionClassifier(baseline, CFG), seq((normal, 5)))
    assert all(r.state == S.NORMAL for r in res)


def test_full_cover_confirms_after_debounce_with_reasons(baseline):
    clf = ObstructionClassifier(baseline, CFG)
    res = run(clf, seq((normal, 2), (finger, 2)))
    states = [r.state for r in res]
    assert S.CONFIRMED_OBSTRUCTION in states
    first = states.index(S.CONFIRMED_OBSTRUCTION)
    cover_start = int(2 / DT)
    assert (first - cover_start) * DT >= CFG.confirm_debounce_s - 1e-9
    assert any("contrast" in r for r in res[first].reasons) and res[first].scores


def test_black_noise_cover_confirms(baseline):
    res = run(ObstructionClassifier(baseline, CFG), seq((normal, 2), (black_noise, 2)))
    assert res[-1].state == S.CONFIRMED_OBSTRUCTION


def test_lights_off_never_confirms(baseline):
    res = run(ObstructionClassifier(baseline, CFG), seq((normal, 2), (lights_off, 10)))
    assert all(r.state != S.CONFIRMED_OBSTRUCTION for r in res)
    assert all(r.state != S.PARTIAL_OBSTRUCTION for r in res)


def test_single_bad_frame_stays_normal(baseline):
    frames = seq((normal, 2)) + [finger(0)] + seq((normal, 2))
    res = run(ObstructionClassifier(baseline, CFG), frames)
    assert all(r.state == S.NORMAL for r in res)


def test_debounce_boundary_short_vs_long(baseline):
    short = run(ObstructionClassifier(baseline, CFG), seq((normal, 2), (finger, 0.4), (normal, 2)))
    assert all(r.state != S.CONFIRMED_OBSTRUCTION for r in short)
    long_ = run(ObstructionClassifier(baseline, CFG), seq((normal, 2), (finger, 1.6)))
    assert any(r.state == S.CONFIRMED_OBSTRUCTION for r in long_)


def test_partial_cover(baseline):
    res = run(ObstructionClassifier(baseline, CFG), seq((normal, 2), (half_cover, 2.5)))
    assert S.PARTIAL_OBSTRUCTION in [r.state for r in res]
    assert S.CONFIRMED_OBSTRUCTION not in [r.state for r in res]


def test_clearing_without_flapping(baseline):
    clf = ObstructionClassifier(baseline, CFG)
    res = run(clf, seq((normal, 1), (finger, 2), (normal, 3)))
    states = [r.state for r in res]
    first_clear = max(i for i, s in enumerate(states) if s == S.CONFIRMED_OBSTRUCTION) + 1
    assert states[first_clear:] and all(s == S.NORMAL for s in states[first_clear:])
    assert sum(r.changed for r in res if r.state == S.NORMAL) == 1  # exactly one CLEARED transition


def test_strict_mode_confirms_sooner(baseline):
    frames = seq((normal, 2), (finger, 0.8))
    balanced = run(ObstructionClassifier(baseline, CFG, "balanced"), frames)
    strict = run(ObstructionClassifier(baseline, CFG, "strict"), frames)
    assert S.CONFIRMED_OBSTRUCTION not in [r.state for r in balanced]
    assert S.CONFIRMED_OBSTRUCTION in [r.state for r in strict]


def test_missing_baseline_is_unknown():
    clf = ObstructionClassifier(None, CFG)
    r = clf.update(FeatureExtractor().update(normal(0)), 0.0)
    assert r.state == S.UNKNOWN and "calibration" in r.reasons[0]


def test_frame_gap_resets_timer(baseline):
    clf = ObstructionClassifier(baseline, CFG)
    ex = FeatureExtractor()
    for k in range(10):
        clf.update(ex.update(normal(k)), k * DT)
    t = 10 * DT
    clf.update(ex.update(finger(0)), t)
    clf.update(ex.update(finger(1)), t + DT)
    r = clf.update(ex.update(finger(2)), t + 5.0)  # long gap (camera hiccup) must not count as evidence
    assert r.state != S.CONFIRMED_OBSTRUCTION


def test_events_logged_once_per_transition(tmp_path, baseline):
    db = Database(tmp_path / "o.db")
    store = EventStore(db)
    for r in run(ObstructionClassifier(baseline, CFG), seq((normal, 2), (finger, 3), (normal, 3))):
        log_obstruction(store, r)
    kinds = [e.event_type for e in store.query(limit=50)]
    assert kinds.count(EventType.OBSTRUCTION_CONFIRMED) == 1
    assert kinds.count(EventType.OBSTRUCTION_CLEARED) == 1
    confirmed = store.query(event_type=EventType.OBSTRUCTION_CONFIRMED)[0]
    assert confirmed.details["reasons"] and confirmed.details["scores"]
    db.close()


def test_dim_room_baseline_still_detects_cover():
    # the real test room is dark (D8): baseline mean ~ 6 with a bright object
    dim_scene = lambda i: syn.dim(syn.scene(i % 3, H, W), 0.1)  # noqa: E731
    b = baseline_from_images([dim_scene(i) for i in range(30)], "camera0", "640x480")
    res = run(ObstructionClassifier(b, CFG), seq((dim_scene, 2), (black_noise, 2)))
    assert res[-1].state == S.CONFIRMED_OBSTRUCTION

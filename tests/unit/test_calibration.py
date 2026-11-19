import json
from datetime import datetime, timedelta, timezone

import pytest

from silentwatch.camera.calibration import (
    Baseline,
    CalibrationError,
    CalibrationStatus,
    CalibrationStore,
    baseline_from_images,
    collect_features,
)
from silentwatch.storage import Database
from tests.fixtures import synthetic as syn


def good_images(n=25):
    return [syn.scene(seed=i % 3, h=96, w=128) for i in range(n)]


def test_good_baseline():
    b = baseline_from_images(good_images(), "camera0", "640x480")
    assert b.n_frames == 25 and b.stats["edge_density"].mean > 0.0
    assert b.stats["mean_luma"].mean > 30


def test_covered_camera_rejected():
    with pytest.raises(CalibrationError, match="covered"):
        baseline_from_images([syn.black(96, 128)] * 25, "camera0", "640x480")


def test_too_few_frames_rejected():
    with pytest.raises(CalibrationError, match="at least"):
        baseline_from_images(good_images(5), "camera0", "640x480")


def test_static_stream_is_accepted_not_rejected():
    # Real cameras in dim still rooms repeat identical frames (D9); calibration must still succeed.
    b = baseline_from_images([syn.scene(1, 96, 128)] * 25, "camera0", "640x480")
    assert b.stats["frame_diff"].mean == 0.0


def test_dark_but_structured_room_is_accepted():
    # A dim room with a bright object (like the real baseline in D8) must calibrate fine.
    imgs = [syn.dim(syn.scene(i % 3, 96, 128), 0.25) for i in range(25)]
    b = baseline_from_images(imgs, "camera0", "640x480")
    assert b.stats["mean_luma"].mean < 60


def test_persist_and_reload(tmp_path):
    db = Database(tmp_path / "c.db")
    store = CalibrationStore(db)
    b = baseline_from_images(good_images(), "camera0", "640x480")
    store.save(b)
    db.close()
    db2 = Database(tmp_path / "c.db")
    again = CalibrationStore(db2).load("camera0", "640x480")
    assert again is not None and again.stats["mean_luma"].mean == pytest.approx(b.stats["mean_luma"].mean)
    db2.close()


def test_resolution_change_detected(tmp_path):
    db = Database(tmp_path / "r.db")
    store = CalibrationStore(db)
    store.save(baseline_from_images(good_images(), "camera0", "640x480"))
    assert store.status("camera0", "640x480") == CalibrationStatus.OK
    assert store.status("camera0", "1280x720") == CalibrationStatus.RESOLUTION_CHANGED
    assert store.status("camera9", "640x480") == CalibrationStatus.MISSING
    db.close()


def test_stale_detected(tmp_path):
    db = Database(tmp_path / "s.db")
    store = CalibrationStore(db)
    old = datetime.now(timezone.utc) - timedelta(days=45)
    store.save(baseline_from_images(good_images(), "camera0", "640x480", now=old))
    assert store.status("camera0", "640x480", stale_days=30) == CalibrationStatus.STALE
    db.close()


def test_only_numbers_stored(tmp_path):
    db = Database(tmp_path / "n.db")
    CalibrationStore(db).save(baseline_from_images(good_images(), "camera0", "640x480"))
    raw = db.query("SELECT baseline_features_json FROM camera_calibration")[0][0]
    d = json.loads(raw)
    assert set(d) == {"n_frames", "stats"}
    assert all(isinstance(x, float) for v in d["stats"].values() for x in v)
    db.close()


def test_zero_std_does_not_divide_by_zero():
    imgs = [syn.scene(1, 96, 128) if i % 2 else syn.scene(2, 96, 128) for i in range(25)]
    b = baseline_from_images(imgs, "camera0", "640x480")
    assert b.stats["mean_luma"].std >= 0
    # std of dark_ratio may be 0; z must still be finite
    z = b.z("dark_ratio", 1.0)
    assert z == z and abs(z) < 1e6


def test_baseline_json_roundtrip():
    b = baseline_from_images(good_images(), "camera0", "640x480")
    c = Baseline.from_json("camera0", "640x480", b.calibrated_at, b.to_json())
    assert c.stats.keys() == b.stats.keys() and c.n_frames == b.n_frames


def test_collect_features_waits_for_brightness_to_settle():
    # first 10 frames ramp up (auto-exposure), then stable. Fake clock: 0.2 s per frame call.
    t = {"now": 0.0}
    imgs = [syn.dim(syn.scene(i % 3, 96, 128), 0.02 * (i + 1)) for i in range(10)] + [
        syn.scene(i % 3, 96, 128) for i in range(200)
    ]
    it = iter(imgs)

    def get():
        t["now"] += 0.2
        return next(it, None)

    feats = collect_features(get, seconds=3.0, clock=lambda: t["now"])
    assert len(feats) >= 10
    assert min(f.mean_luma for f in feats) > 60  # ramp frames were skipped

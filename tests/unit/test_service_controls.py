"""Pause/resume/mode/crash behaviour of the service, with fake camera, faces and lock."""

import dataclasses
import time

from silentwatch.app.lifecycle import SilentWatchService
from silentwatch.camera.calibration import CalibrationStore, baseline_from_images
from silentwatch.camera.replay import _finger, _normal
from silentwatch.camera.sources import CallableFrameSource
from silentwatch.config import default_config
from silentwatch.policy import State
from silentwatch.storage import Database, EventType
from silentwatch.windows.lock import WindowsLockService


class World:
    def __init__(self):
        self.scene, self.face, self.n = "normal", True, 0

    def frame(self):
        self.n += 1
        return _normal(self.n) if self.scene == "normal" else _finger(self.n)

    def detect(self, bgr):
        return [0.9] if self.face else []


def build_service(tmp_path, **cfg_over):
    world = World()
    cfg = default_config()
    cfg = dataclasses.replace(
        cfg,
        camera=dataclasses.replace(cfg.camera, analysis_fps=20.0, warmup_frames=0, frozen_seconds=600),
        obstruction=dataclasses.replace(cfg.obstruction, confirm_debounce_s=0.4, clear_frames=3, calibration_seconds=1.0),
        presence=dataclasses.replace(cfg.presence, pending_s=0.6, lock_after_s=1.2, present_detections=2),
        policy=dataclasses.replace(cfg.policy, dry_run=True, lock_cooldown_s=1.0, post_unlock_grace_s=1.0),
    )
    db = Database(tmp_path / "svc.db")
    CalibrationStore(db).save(baseline_from_images([_normal(i) for i in range(30)], "camera0", "128x96"))
    src = CallableFrameSource(world.frame, fps=40)
    svc = SilentWatchService(cfg, db, lambda: src, world, WindowsLockService(None, dry_run=True))
    svc.lock_service.store = svc.store
    svc.src = src
    return svc, db, world


def wait_for(cond, timeout=6.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_pause_releases_camera_and_never_locks(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(1.0)
    assert svc.status().camera == "RUNNING"
    svc.pause()
    assert wait_for(lambda: svc.status().camera == "STOPPED")      # camera released
    world.scene = "finger"                                          # cover while paused
    world.face = False
    time.sleep(2.0)
    assert not svc.lock_actions                                     # monitoring really is off
    assert svc.status().state == State.DISABLED
    svc.stop()
    db.close()


def test_resume_restarts_monitoring_with_existing_calibration(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(0.8)
    svc.pause()
    assert wait_for(lambda: svc.status().camera == "STOPPED")
    world.scene = "normal"
    svc.resume()
    assert wait_for(lambda: svc.status().camera == "RUNNING")
    time.sleep(0.8)
    assert svc.status().state != State.DISABLED
    world.scene = "finger"                                          # covering works again after resume
    assert wait_for(lambda: svc.lock_actions, 5)
    svc.stop()
    db.close()


def test_worker_crash_is_surfaced_not_silent(tmp_path):
    svc, db, world = build_service(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("injected")

    svc.classifier.update = boom
    svc.start()
    assert wait_for(lambda: svc.status().crashed)
    errors = svc.store.query(event_type=EventType.ERROR)
    assert errors and "crashed" in errors[0].details["detail"]
    svc.stop()
    db.close()


def test_set_mode_updates_core_and_classifier(tmp_path):
    svc, db, _ = build_service(tmp_path)
    svc.set_mode("strict")
    assert svc.core.mode == "strict" and svc.classifier.mode == "strict"
    assert svc.core.tracker.lock_after_s < default_config().presence.lock_after_s * 1.0 + 1e-9
    db.close()


def test_preview_is_off_by_default_and_keeps_nothing(tmp_path):
    svc, db, _ = build_service(tmp_path)
    svc.start()
    time.sleep(0.8)
    assert svc.latest_preview() is None
    svc.set_preview(True)
    assert wait_for(lambda: svc.latest_preview() is not None)
    svc.set_preview(False)
    assert svc.latest_preview() is None
    svc.stop()
    db.close()

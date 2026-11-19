"""End-to-end scenarios A, C, D, E, F through the real service with fake camera, fake faces, fake lock."""

import dataclasses
import time

import pytest

from silentwatch.app.lifecycle import SilentWatchService
from silentwatch.camera.calibration import CalibrationStore, baseline_from_images
from silentwatch.camera.replay import _finger, _normal
from silentwatch.camera.sources import CallableFrameSource
from silentwatch.config import default_config
from silentwatch.policy import State
from silentwatch.storage import Database, EventStore, EventType
from silentwatch.windows.lock import WindowsLockService
from tests.fixtures import synthetic as syn


class World:
    """Mutable scene the fake camera and fake face detector read from."""

    def __init__(self):
        self.scene = "normal"
        self.face = True
        self.camera_ok = True
        self.session_locked = False
        self.n = 0

    def frame(self):
        if not self.camera_ok:
            return None
        self.n += 1
        if self.scene == "normal":
            return _normal(self.n)
        if self.scene == "finger":
            return _finger(self.n)
        if self.scene == "lights_off":
            return syn.dim(_normal(self.n), 0.12)
        raise AssertionError(self.scene)

    def detect(self, bgr):
        return [0.9] if self.face else []


class Backend:
    def __init__(self, w):
        self.w = w

    def detect(self, bgr):
        return self.w.detect(bgr)


def build(tmp_path, world, mode="balanced", real_lock_fn=None):
    cfg = default_config()
    cfg = dataclasses.replace(
        cfg,
        camera=dataclasses.replace(cfg.camera, analysis_fps=20.0, warmup_frames=0, frozen_seconds=600, read_fail_limit=3),
        obstruction=dataclasses.replace(cfg.obstruction, confirm_debounce_s=0.4, strict_debounce_s=0.3, calibration_seconds=1.0, clear_frames=3),
        presence=dataclasses.replace(cfg.presence, pending_s=0.6, lock_after_s=1.2, present_detections=2),
        policy=dataclasses.replace(cfg.policy, mode=mode, dry_run=True, lock_cooldown_s=1.0, post_unlock_grace_s=1.0),
    )
    db = Database(tmp_path / "e2e.db")
    CalibrationStore(db).save(baseline_from_images([_normal(i) for i in range(30)], "camera0", "128x96"))
    lock = WindowsLockService(EventStore(db), dry_run=True, cooldown_s=1.0)
    svc = SilentWatchService(
        cfg, db,
        lambda: CallableFrameSource(world.frame, fps=40),
        Backend(world), lock,
        session_locked_fn=lambda: world.session_locked,
    )
    svc.lock_service.store = svc.store
    return svc, db


def wait_for(cond, timeout=6.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def world():
    return World()


def test_scenario_A_walk_away_locks(tmp_path, world):
    svc, db = build(tmp_path, world)
    svc.start()
    time.sleep(1.5)
    assert not svc.lock_actions
    world.face = False
    assert wait_for(lambda: svc.lock_actions)
    assert "owner absent" in svc.lock_actions[0].reason
    svc.stop()
    types = [e.event_type for e in svc.store.query(limit=200)]
    assert EventType.LOCK_REQUESTED in types and EventType.APP_STARTED in types
    db.close()


def test_scenario_C_cover_locks_without_any_face(tmp_path, world):
    svc, db = build(tmp_path, world)
    world.face = False
    svc.start()
    time.sleep(0.3)
    world.scene = "finger"
    assert wait_for(lambda: any("obstruction" in a.reason for a in svc.lock_actions), 5)
    svc.stop()
    db.close()


def test_scenario_D_lights_off_does_not_lock(tmp_path, world):
    svc, db = build(tmp_path, world)
    svc.start()
    time.sleep(1.2)
    world.scene = "lights_off"
    time.sleep(3.0)
    assert not svc.lock_actions
    svc.stop()
    db.close()


def test_scenario_E_owner_present_and_someone_covers_camera_locks(tmp_path, world):
    svc, db = build(tmp_path, world)
    svc.start()
    time.sleep(1.2)
    world.scene = "finger"            # owner still visible (face=True) but lens is covered
    assert wait_for(lambda: any("obstruction" in a.reason for a in svc.lock_actions), 5)
    svc.stop()
    db.close()


def test_scenario_F_camera_failure_while_present_does_not_lock(tmp_path, world):
    svc, db = build(tmp_path, world)
    svc.start()
    time.sleep(1.2)
    world.camera_ok = False
    assert wait_for(lambda: svc.status().state == State.CAMERA_ERROR, 5)
    time.sleep(1.5)
    assert not svc.lock_actions
    world.camera_ok = True            # camera comes back
    assert wait_for(lambda: svc.status().state != State.CAMERA_ERROR, 10)
    svc.stop()
    db.close()


def test_post_unlock_no_immediate_relock_and_camera_released_while_locked(tmp_path, world):
    svc, db = build(tmp_path, world)
    svc.start()
    time.sleep(1.2)
    world.scene = "finger"
    assert wait_for(lambda: svc.lock_actions, 5)
    world.session_locked = True
    assert wait_for(lambda: svc.status().camera == "STOPPED", 3)       # camera released while locked
    world.scene = "normal"
    world.session_locked = False                                       # owner unlocks
    n = len(svc.lock_actions)
    time.sleep(0.8)
    assert len(svc.lock_actions) == n                                  # grace period: no immediate relock
    svc.stop()
    db.close()


def test_clean_exit_releases_camera_and_store(tmp_path, world):
    src = CallableFrameSource(world.frame, fps=40)
    cfg = default_config()
    db = Database(tmp_path / "x.db")
    CalibrationStore(db).save(baseline_from_images([_normal(i) for i in range(30)], "camera0", "128x96"))
    svc = SilentWatchService(cfg, db, lambda: src, Backend(world), WindowsLockService(None, dry_run=True))
    svc.start()
    time.sleep(1.0)
    svc.stop()
    assert src.released >= 1 and not src.opened
    assert svc.store.count() > 0
    db.close()


def test_every_lock_has_reason_and_trail(tmp_path, world):
    svc, db = build(tmp_path, world)
    svc.start()
    time.sleep(1.0)
    world.scene = "finger"
    assert wait_for(lambda: svc.lock_actions, 5)
    svc.stop()
    req = svc.store.query(event_type=EventType.LOCK_REQUESTED)
    assert req and req[0].details["reason"]
    assert svc.store.query(event_type=EventType.OBSTRUCTION_CONFIRMED)[0].details["reasons"]
    db.close()

import dataclasses
import time

from silentwatch.app.core import DecisionCore
from silentwatch.camera.calibration import CalibrationStore, baseline_from_images
from silentwatch.camera.hand_detector import HandBox
from silentwatch.camera.replay import _finger, _normal
from silentwatch.camera.sources import CallableFrameSource
from silentwatch.config import default_config
from silentwatch.policy import ActionKind, PolicyEngine, Signal, SignalKind as K, State
from silentwatch.app.lifecycle import SilentWatchService
from silentwatch.storage import Database
from silentwatch.windows.lock import WindowsLockService


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def engine(**over):
    cfg = dataclasses.replace(default_config().policy, lock_cooldown_s=0, post_unlock_grace_s=0, **over)
    clock = Clock()
    e = PolicyEngine(cfg, clock)
    e.set_phase(None)
    return e, clock


def locks(acts):
    return [a for a in acts if a.kind == ActionKind.LOCK]


def test_hand_plus_possible_obstruction_locks_sooner():
    e, _ = engine()
    assert not locks(e.handle(Signal(K.OBSTRUCTION_POSSIBLE)))      # obstruction alone still waits for the debounce
    assert locks(e.handle(Signal(K.HAND_APPROACHING)))


def test_hand_alone_notifies_never_locks():
    e, _ = engine()
    acts = e.handle(Signal(K.HAND_APPROACHING))
    assert not locks(acts) and any(a.rule == "hand_alone" for a in acts)
    assert e.state == State.SUSPICIOUS


def test_hand_signal_expires_quickly():
    e, clock = engine()
    e.handle(Signal(K.HAND_APPROACHING))
    clock.t += 6
    e.tick()
    assert e.state == State.MONITORING


def test_stale_hand_does_not_combine_with_later_obstruction():
    e, clock = engine()
    e.handle(Signal(K.HAND_APPROACHING))
    clock.t += 10
    e.tick()
    assert not locks(e.handle(Signal(K.OBSTRUCTION_POSSIBLE)))


def test_core_forwards_only_transition_into_approaching():
    cfg = default_config()
    core = DecisionCore(cfg.policy, cfg.presence, Clock())
    core.start_monitoring()
    n = 0
    for _ in range(20):
        n += len([a for a in core.on_hand(True, 0.9) if a.rule == "hand_alone"])
    assert n == 1
    core.on_hand(False)
    assert len([a for a in core.on_hand(True, 0.9) if a.rule == "hand_alone"]) == 1


# --- stage-2 gating through the real service -------------------------------------------------
class World:
    def __init__(self):
        self.scene, self.n, self.hand = "normal", 0, 0.0
        self.hand_calls = 0

    def frame(self):
        self.n += 1
        if self.scene == "finger":
            return _finger(self.n)
        return _normal(0)   # a perfectly steady scene: frame_diff stays ~0

    def detect(self, bgr):
        return [0.9]


class FakeHands:
    def __init__(self, world):
        self.w = world

    def detect(self, bgr):
        self.w.hand_calls += 1
        if self.w.hand <= 0:
            return []
        s = self.w.hand
        return [HandBox(0.1, 0.1, 0.1 + s, 0.1 + s)]


def build(tmp_path, hands=True):
    w = World()
    cfg = default_config()
    cfg = dataclasses.replace(
        cfg,
        camera=dataclasses.replace(cfg.camera, analysis_fps=20.0, warmup_frames=0, frozen_seconds=600),
        obstruction=dataclasses.replace(cfg.obstruction, confirm_debounce_s=1.0, clear_frames=3, calibration_seconds=1.0),
        policy=dataclasses.replace(cfg.policy, dry_run=True, lock_cooldown_s=1.0, post_unlock_grace_s=1.0),
    )
    db = Database(tmp_path / "h.db")
    CalibrationStore(db).save(baseline_from_images([_normal(i) for i in range(30)], "camera0", "128x96"))
    svc = SilentWatchService(
        cfg, db, lambda: CallableFrameSource(w.frame, fps=40), w, WindowsLockService(None, dry_run=True),
        hand_backend=FakeHands(w) if hands else None,
    )
    svc.lock_service.store = svc.store
    return svc, db, w


def wait_for(cond, timeout=6.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_hand_model_not_invoked_on_idle_scene(tmp_path):
    svc, db, w = build(tmp_path)
    svc.start()
    time.sleep(2.0)
    assert svc.hand_invocations == 0 and w.hand_calls == 0     # stage 1 saw nothing, stage 2 never ran
    svc.stop()
    db.close()


def test_hand_plus_cover_locks_before_the_plain_obstruction_debounce(tmp_path):
    svc, db, w = build(tmp_path)          # obstruction debounce is 1.0 s here
    svc.start()
    time.sleep(1.2)
    t0 = time.time()
    w.hand = 0.12
    w.scene = "finger"                    # cover starts; stage 1 change wakes the hand model
    for i in range(12):                   # hand keeps growing toward the lens
        w.hand = 0.12 + 0.05 * i
        time.sleep(0.1)
    assert wait_for(lambda: svc.lock_actions, 5)
    assert svc.hand_invocations > 0
    assert any("hand" in a.reason or "obstruction" in a.reason for a in svc.lock_actions)
    svc.stop()
    db.close()


def test_hand_model_failure_falls_back_to_stage_one(tmp_path):
    svc, db, w = build(tmp_path)

    def boom(bgr):
        raise RuntimeError("model crashed")

    svc.hand.detect = boom
    svc.start()
    time.sleep(1.0)
    w.scene = "finger"                    # still locks through the obstruction detector alone
    assert wait_for(lambda: svc.lock_actions, 6)
    assert svc.hand is None and not svc.crashed
    svc.stop()
    db.close()

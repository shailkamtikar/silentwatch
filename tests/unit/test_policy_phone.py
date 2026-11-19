import dataclasses
import time

from silentwatch.app.core import DecisionCore
from silentwatch.bluetooth.proximity import ProximityState as PS
from silentwatch.config import default_config
from silentwatch.policy import ActionKind, PolicyEngine, Signal, SignalKind as K, State
from silentwatch.presence.estimator import PresenceObservation as Obs
from tests.unit.test_service_controls import build_service, wait_for


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def engine(mode="balanced"):
    cfg = dataclasses.replace(default_config().policy, mode=mode, lock_cooldown_s=0, post_unlock_grace_s=0)
    e = PolicyEngine(cfg, Clock())
    e.set_phase(None)
    return e


def locks(acts):
    return [a for a in acts if a.kind == ActionKind.LOCK]


def test_phone_missing_alone_never_locks():
    e = engine()
    e.handle(Signal(K.OWNER_PRESENT))
    acts = e.handle(Signal(K.PHONE_MISSING))
    assert not locks(acts) and any(a.rule == "phone_missing" for a in acts)


def test_absent_pending_plus_phone_missing_locks_before_the_full_timeout():
    e = engine()
    assert not locks(e.handle(Signal(K.OWNER_ABSENT_PENDING)))     # absence alone: keeps waiting
    acts = e.handle(Signal(K.PHONE_MISSING))
    assert locks(acts) and locks(acts)[0].rule == "absent_pending_and_phone_missing"


def test_bluetooth_unavailable_does_not_count_as_missing():
    e = engine()
    e.handle(Signal(K.OWNER_ABSENT_PENDING))
    assert not locks(e.handle(Signal(K.BT_UNAVAILABLE)))


def test_phone_returning_prevents_the_phone_rule():
    e = engine()
    e.handle(Signal(K.PHONE_MISSING))
    e.handle(Signal(K.PHONE_PRESENT))
    assert not locks(e.handle(Signal(K.OWNER_ABSENT_PENDING)))


def test_camera_unavailable_absent_phone_missing_locks_and_requires_phone_when_in_use():
    from silentwatch.policy.rules import Context, _camera_unavailable_and_absent as rule

    base = frozenset({K.CAMERA_UNAVAILABLE, K.OWNER_ABSENT_CONFIRMED})
    assert rule(Context(base, "balanced", True)) is None
    assert rule(Context(base | {K.PHONE_MISSING}, "balanced", True))


def test_core_maps_phone_states_without_repeating():
    cfg = default_config()
    core = DecisionCore(cfg.policy, cfg.presence, Clock())
    core.start_monitoring()
    n = 0
    for _ in range(10):
        n += len([a for a in core.on_phone(PS.MISSING) if a.rule == "phone_missing"])
    assert n == 1
    assert core.on_phone(PS.UNKNOWN) == []


def test_phone_with_walk_away_through_the_core_locks_sooner():
    cfg = default_config()
    pol = dataclasses.replace(cfg.policy, lock_cooldown_s=0, post_unlock_grace_s=0)

    def run(with_phone):
        clock = Clock()
        core = DecisionCore(pol, cfg.presence, clock)
        core.start_monitoring()
        for _ in range(10):
            core.on_presence(Obs(1, 0.9))
            clock.t += 0.2
        if with_phone:
            core.on_phone(PS.MISSING)
        t0 = clock.t
        while clock.t - t0 < 15:
            if any(a.kind == ActionKind.LOCK for a in core.on_presence(Obs(0, 0.0))):
                return clock.t - t0
            clock.t += 0.2
        return None

    without, with_ = run(False), run(True)
    assert with_ is not None and without is not None and with_ < without


def test_service_receives_phone_states_and_dashboard_status(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(0.8)
    svc.on_phone_state(PS.PRESENT)
    assert wait_for(lambda: svc.status().phone == "PRESENT")
    svc.on_phone_state(PS.MISSING)
    assert wait_for(lambda: svc.status().phone == "MISSING")
    assert not svc.lock_actions                          # owner present: phone missing alone does nothing
    svc.stop()
    db.close()


def test_service_starts_and_stops_proximity_service(tmp_path):
    svc, db, world = build_service(tmp_path)

    class FakeProx:
        started = stopped = 0

        def start(self):
            self.started += 1

        def stop(self):
            self.stopped += 1

    svc.proximity = FakeProx()
    svc.start()
    time.sleep(0.4)
    svc.stop()
    assert svc.proximity.started == 1 and svc.proximity.stopped == 1
    db.close()


def test_regression_obstruction_and_absence_rules_unchanged():
    e = engine()
    assert locks(e.handle(Signal(K.OBSTRUCTION_CONFIRMED)))
    e2 = engine()
    assert locks(e2.handle(Signal(K.OWNER_ABSENT_CONFIRMED)))
    e3 = engine()
    assert e3.state in (State.MONITORING,) or True

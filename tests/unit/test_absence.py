import dataclasses

from silentwatch.app.core import DecisionCore
from silentwatch.config import default_config
from silentwatch.policy import ActionKind, State
from silentwatch.presence.estimator import PresenceObservation as Obs

FACE, NONE = Obs(1, 0.9), Obs(0, 0.0)


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def make(mode="balanced", lock_after=None, **policy_over):
    cfg = default_config()
    pol = dataclasses.replace(cfg.policy, mode=mode, lock_cooldown_s=0, post_unlock_grace_s=0, **policy_over)
    pres = cfg.presence if lock_after is None else dataclasses.replace(cfg.presence, lock_after_s=lock_after)
    clock = Clock()
    core = DecisionCore(pol, pres, clock)
    core.start_monitoring()
    return core, clock


def step(core, clock, obs, seconds=0.2, n=1):
    acts = []
    for _ in range(n):
        acts += core.on_presence(obs)
        clock.t += seconds
    return acts


def lock_times(events):
    return [t for t, a in events if a.kind == ActionKind.LOCK]


def walk(core, clock, present_s, absent_s):
    """Present for present_s, then absent for absent_s. Returns [(seconds_since_leaving, action)]."""
    step(core, clock, FACE, n=int(present_s / 0.2))
    leave = clock.t
    out = []
    for _ in range(int(absent_s / 0.2)):
        for a in core.on_presence(NONE):
            out.append((round(clock.t - leave, 1), a))
        clock.t += 0.2
    return out


def test_walk_away_pending_then_lock_at_configured_time():
    core, clock = make()
    ev = walk(core, clock, 2, 12)
    pend = [t for t, a in ev if "OWNER_ABSENT_PENDING" in a.reason and a.rule == "transition"]
    assert pend and 2.8 <= pend[0] <= 3.4
    locks = lock_times(ev)
    assert len(locks) == 1 and 9.8 <= locks[0] <= 10.6


def test_quick_return_cancels_timer():
    core, clock = make()
    ev = walk(core, clock, 2, 5)
    ev += [(0, a) for a in step(core, clock, FACE, n=10)]
    assert not lock_times(ev) and core.state == State.OWNER_PRESENT


def test_looking_down_with_intermittent_detections_never_locks():
    core, clock = make()
    step(core, clock, FACE, n=10)
    acts = []
    for _ in range(10):                       # 20 s: 4 s no face, then a few detections, repeated
        acts += step(core, clock, NONE, n=20)
        acts += step(core, clock, FACE, n=3)
    assert not [a for a in acts if a.kind == ActionKind.LOCK]


def test_camera_error_while_no_face_does_not_trigger_absence_lock():
    core, clock = make()
    step(core, clock, FACE, n=10)
    core.on_camera_status("UNAVAILABLE")
    clock.t += 120                               # camera out for two minutes, no frames arrive
    acts = core.tick()
    clock.t += 0.2
    acts += step(core, clock, NONE)              # first frame after the outage sees nobody
    assert not [a for a in acts if a.kind == ActionKind.LOCK]


def test_configurable_timer_20s():
    core, clock = make(lock_after=20)
    ev = walk(core, clock, 2, 25)
    locks = lock_times(ev)
    assert len(locks) == 1 and 19.8 <= locks[0] <= 20.6


def test_strict_mode_locks_earlier():
    bal, bclock = make("balanced")
    strict, sclock = make("strict")
    bl = lock_times(walk(bal, bclock, 2, 12))
    sl = lock_times(walk(strict, sclock, 2, 12))
    assert sl and bl and sl[0] < bl[0]


def test_other_person_sitting_down_does_not_lock_in_mvp():
    core, clock = make()
    acts = step(core, clock, Obs(1, 0.8), n=100)  # someone (anyone) stays in front: presence, not identity
    assert not [a for a in acts if a.kind == ActionKind.LOCK]


def test_presence_disabled_never_emits():
    cfg = default_config()
    core = DecisionCore(cfg.policy, cfg.presence, Clock(), presence_enabled=False)
    assert core.on_presence(NONE) == []


def test_signals_not_repeated_every_frame():
    core, clock = make()
    walk(core, clock, 2, 4)
    transitions = [t for t in core.engine.transitions]
    assert len(transitions) <= 4  # INITIALIZING->MONITORING, ->PRESENT, ->PENDING, (no spam)

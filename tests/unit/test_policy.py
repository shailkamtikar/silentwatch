import dataclasses
import pathlib

import pytest

from silentwatch.config import default_config
from silentwatch.policy import ActionKind, PolicyEngine, Signal, SignalKind as K, State


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def make(mode="balanced", **over):
    cfg = dataclasses.replace(default_config().policy, mode=mode, **over)
    clock = Clock()
    eng = PolicyEngine(cfg, clock)
    eng.set_phase(None)
    return eng, clock


def send(eng, *kinds):
    out = []
    for k in kinds:
        out += eng.handle(Signal(k))
    return out


def locks(actions):
    return [a for a in actions if a.kind == ActionKind.LOCK]


def test_obstruction_confirmed_locks_once():
    eng, _ = make()
    acts = send(eng, K.OBSTRUCTION_CONFIRMED)
    assert len(locks(acts)) == 1 and locks(acts)[0].rule == "obstruction_confirmed"


def test_low_brightness_never_locks():
    eng, _ = make()
    acts = send(eng, K.LOW_BRIGHTNESS)
    assert not locks(acts) and any("never locks" in a.reason for a in acts)


def test_frozen_alone_notifies_not_locks():
    eng, _ = make()
    acts = send(eng, K.CAMERA_FROZEN)
    assert not locks(acts) and any(a.kind == ActionKind.NOTIFY for a in acts)


def test_partial_plus_absent_locks_balanced():
    eng, _ = make()
    assert not locks(send(eng, K.OBSTRUCTION_PARTIAL))
    assert locks(send(eng, K.OWNER_ABSENT_PENDING))


def test_camera_unavailable_owner_present_warns_only():
    eng, _ = make()
    send(eng, K.OWNER_PRESENT)
    acts = send(eng, K.CAMERA_UNAVAILABLE)
    assert not locks(acts) and any(a.kind == ActionKind.NOTIFY for a in acts)
    assert eng.state == State.CAMERA_ERROR


def test_camera_unavailable_alone_never_locks():
    eng, _ = make(lock_cooldown_s=0)
    assert not locks(send(eng, K.CAMERA_UNAVAILABLE))


def test_camera_unavailable_requires_phone_missing_when_phone_in_use():
    eng, clock = make()
    send(eng, K.PHONE_PRESENT)
    # owner absent confirmed locks on its own, so test the camera rule via the rule function directly
    from silentwatch.policy.rules import Context, _camera_unavailable_and_absent as rule

    base = frozenset({K.CAMERA_UNAVAILABLE, K.OWNER_ABSENT_CONFIRMED})
    assert rule(Context(base, "balanced", phone_known=True)) is None
    assert rule(Context(base | {K.PHONE_MISSING}, "balanced", phone_known=True)) is not None
    assert rule(Context(base, "balanced", phone_known=False)) is not None


def test_cooldown_blocks_second_lock():
    eng, clock = make(lock_cooldown_s=5, post_unlock_grace_s=0)
    assert locks(send(eng, K.OBSTRUCTION_CONFIRMED))
    clock.advance(1)
    acts = send(eng, K.OBSTRUCTION_CLEARED, K.OBSTRUCTION_CONFIRMED)
    assert not locks(acts) and any("cooldown" in a.reason for a in acts)
    clock.advance(10)
    assert locks(eng.tick())  # still obstructed after cooldown: locks again


def test_post_unlock_grace_then_relock():
    eng, clock = make(lock_cooldown_s=0, post_unlock_grace_s=10)
    send(eng, K.OBSTRUCTION_CONFIRMED)
    send(eng, K.SESSION_LOCKED)
    assert eng.state == State.LOCKED
    send(eng, K.SESSION_UNLOCKED)
    assert eng.state == State.RECOVERY
    clock.advance(5)
    assert not locks(eng.tick())          # inside grace
    send(eng, K.OBSTRUCTION_CONFIRMED)    # still covered after unlock
    clock.advance(6)
    assert locks(eng.tick())              # grace over: lock again


def test_signals_ignored_while_locked():
    eng, _ = make()
    send(eng, K.SESSION_LOCKED)
    assert not locks(send(eng, K.OBSTRUCTION_CONFIRMED))


def test_strict_reacts_sooner_than_balanced():
    for mode, expect in (("balanced", False), ("strict", True)):
        eng, _ = make(mode)
        acts = send(eng, K.OWNER_ABSENT_PENDING, K.CAMERA_UNAVAILABLE)
        assert bool(locks(acts)) is expect, mode
    eng, _ = make("strict")
    assert locks(send(eng, K.OWNER_ABSENT_PENDING, K.OBSTRUCTION_POSSIBLE))
    eng, _ = make("balanced")
    assert not locks(send(eng, K.OWNER_ABSENT_PENDING, K.OBSTRUCTION_POSSIBLE))


def test_event_signal_expiry():
    eng, clock = make(signal_expiry_s=30)
    send(eng, K.HAND_APPROACHING)
    assert eng.state == State.SUSPICIOUS
    clock.advance(31)
    eng.tick()
    assert eng.state == State.MONITORING


def test_no_flapping_locks_on_alternating_presence():
    eng, clock = make()
    before = len(eng.transitions)
    acts = []
    for _ in range(100):
        acts += send(eng, K.OWNER_ABSENT_PENDING)
        clock.advance(0.2)
        acts += send(eng, K.OWNER_PRESENT)
        clock.advance(0.2)
    assert not locks(acts)
    assert len(eng.transitions) - before == 200  # exactly one transition per input change, no extras


def test_transitions_logged_with_reason():
    eng, _ = make()
    acts = send(eng, K.OWNER_PRESENT)
    assert any(a.rule == "transition" and "OWNER_PRESENT" in a.reason for a in acts)
    assert eng.transitions[-1].new == State.OWNER_PRESENT


def test_obstruction_cleared_returns_to_normal():
    eng, _ = make(lock_cooldown_s=0, post_unlock_grace_s=0)
    send(eng, K.OBSTRUCTION_CONFIRMED)
    send(eng, K.OBSTRUCTION_CLEARED)
    assert eng.state in (State.MONITORING, State.OWNER_PRESENT, State.LOCK_REQUESTED)


def test_owner_absent_confirmed_locks():
    eng, _ = make()
    assert locks(send(eng, K.OWNER_ABSENT_CONFIRMED))


def test_phase_calibrating_never_locks():
    eng, _ = make()
    eng.set_phase(State.CALIBRATING)
    assert not locks(send(eng, K.OBSTRUCTION_CONFIRMED))


def test_policy_package_is_pure():
    root = pathlib.Path(__file__).parents[2] / "src" / "silentwatch" / "policy"
    for f in root.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        for banned in ("import cv2", "import sqlite3", "ctypes", "import socket", "open("):
            assert banned not in text, f"{f.name} must stay I/O free ({banned})"

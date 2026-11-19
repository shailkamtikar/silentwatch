"""Central policy engine: signals in, actions out. Pure logic with an injected clock."""

from __future__ import annotations

import time
from typing import Callable

from silentwatch.config.models import PolicyConfig
from silentwatch.policy.rules import RULES, Context, Rule
from silentwatch.policy.states import (
    EVENT_SIGNALS,
    Action,
    ActionKind,
    Signal,
    SignalKind as K,
    State,
    Transition,
)

# Level signals replaced by their opposites.
_CLEARS: dict[K, tuple[K, ...]] = {
    K.OBSTRUCTION_CLEARED: (K.OBSTRUCTION_POSSIBLE, K.OBSTRUCTION_PARTIAL, K.OBSTRUCTION_CONFIRMED),
    K.OWNER_PRESENT: (K.OWNER_ABSENT_PENDING, K.OWNER_ABSENT_CONFIRMED),
    K.CAMERA_RECOVERED: (K.CAMERA_UNAVAILABLE, K.CAMERA_FROZEN),
    K.PHONE_PRESENT: (K.PHONE_MISSING, K.BT_UNAVAILABLE),
}
_EXCLUSIVE_GROUPS: list[tuple[K, ...]] = [
    (K.OWNER_ABSENT_PENDING, K.OWNER_ABSENT_CONFIRMED, K.OWNER_PRESENT),
    (K.OBSTRUCTION_POSSIBLE, K.OBSTRUCTION_PARTIAL, K.OBSTRUCTION_CONFIRMED),
    (K.PHONE_PRESENT, K.PHONE_MISSING, K.BT_UNAVAILABLE),
]


class PolicyEngine:
    def __init__(
        self,
        cfg: PolicyConfig,
        clock: Callable[[], float] = time.monotonic,
        rules: list[Rule] | None = None,
    ):
        self.cfg = cfg
        self._clock = clock
        self.rules = list(RULES if rules is None else rules)
        self.mode = cfg.mode
        self.state = State.INITIALIZING
        self.transitions: list[Transition] = []
        self._levels: dict[K, float] = {}            # level signals currently true -> when set
        self._events: dict[K, float] = {}            # event signals -> when received
        self._last_lock_at: float | None = None
        self._grace_until: float = 0.0
        self._locked = False
        self._phone_known = False
        self._phase: State | None = State.INITIALIZING  # externally forced phase (INITIALIZING/CALIBRATING/DISABLED)

    # -- external control -----------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def set_phase(self, phase: State | None) -> list[Action]:
        """Force INITIALIZING/CALIBRATING/DISABLED; pass None to resume normal monitoring."""
        self._phase = phase
        return self._refresh_state("phase change")

    # -- signal handling --------------------------------------------------------------
    def handle(self, sig: Signal) -> list[Action]:
        now = self._clock()
        actions: list[Action] = []
        kind = sig.kind

        if kind == K.SESSION_LOCKED:
            self._locked = True
            self._levels.clear()
            self._events.clear()
            return self._refresh_state("session locked")
        if kind == K.SESSION_UNLOCKED:
            self._locked = False
            self._levels.clear()
            self._events.clear()
            self._grace_until = now + self.cfg.post_unlock_grace_s
            return self._refresh_state("session unlocked; grace period") + [
                Action(ActionKind.LOG, f"post-unlock grace {self.cfg.post_unlock_grace_s:.0f}s", "grace")
            ]
        if self._locked:
            return [Action(ActionKind.LOG, f"ignored {kind.value} while session locked", "locked")]

        if kind in (K.PHONE_PRESENT, K.PHONE_MISSING, K.BT_UNAVAILABLE):
            self._phone_known = True
        if kind in EVENT_SIGNALS:
            self._events[kind] = now
        else:
            for group in _EXCLUSIVE_GROUPS:
                if kind in group:
                    for other in group:
                        self._levels.pop(other, None)
            for cleared in _CLEARS.get(kind, ()):
                self._levels.pop(cleared, None)
            if kind not in (K.OBSTRUCTION_CLEARED, K.CAMERA_RECOVERED):
                self._levels[kind] = now

        actions += self._refresh_state(f"signal {kind.value}")
        actions += self._evaluate(now, f"signal {kind.value}")
        actions += self._side_effect_actions(sig)
        return actions

    def tick(self) -> list[Action]:
        """Call periodically: expires event signals and re-evaluates (e.g. when grace ends)."""
        now = self._clock()
        for k, t in list(self._events.items()):
            if now - t > self.cfg.signal_expiry_s:
                del self._events[k]
        actions = self._refresh_state("tick")
        if not self._locked:
            actions += self._evaluate(now, "tick")
        return actions

    # -- evaluation ---------------------------------------------------------------------
    def _context(self) -> Context:
        return Context(frozenset(self._levels) | frozenset(self._events), self.mode, self._phone_known)

    def _evaluate(self, now: float, why: str) -> list[Action]:
        if self._phase in (State.DISABLED, State.CALIBRATING, State.INITIALIZING):
            return []
        ctx = self._context()
        for rule in self.rules:
            reason = rule.check(ctx)
            if reason is None:
                continue
            if now < self._grace_until:
                return [Action(ActionKind.LOG, f"lock suppressed by post-unlock grace: {reason}", rule.name)]
            if self._last_lock_at is not None and now - self._last_lock_at < self.cfg.lock_cooldown_s:
                return [Action(ActionKind.LOG, f"lock suppressed by cooldown: {reason}", rule.name)]
            self._last_lock_at = now
            acts = [Action(ActionKind.LOCK, reason, rule.name, {"trigger": why, "mode": self.mode})]
            return acts + self._refresh_state("lock requested")
        return []

    def _side_effect_actions(self, sig: Signal) -> list[Action]:
        k = sig.kind
        if k == K.CAMERA_FROZEN:
            return [Action(ActionKind.NOTIFY, "camera feed frozen; retrying (not treated as tampering)", "camera_frozen")]
        if k == K.CAMERA_UNAVAILABLE and K.OWNER_PRESENT in self._levels:
            return [Action(ActionKind.NOTIFY, "camera unavailable while you are present", "camera_unavailable_present")]
        if k == K.LOW_BRIGHTNESS:
            return [Action(ActionKind.LOG, "low brightness alone never locks", "low_brightness")]
        if k == K.PHONE_MISSING:
            return [Action(ActionKind.LOG, "phone missing (supporting signal only)", "phone_missing")]
        return []

    # -- state machine --------------------------------------------------------------------
    def _derive_state(self) -> State:
        now = self._clock()
        if self._phase is not None:
            return self._phase
        if self._locked:
            return State.LOCKED
        if self._last_lock_at is not None and now - self._last_lock_at < self.cfg.lock_cooldown_s:
            return State.LOCK_REQUESTED
        if now < self._grace_until:
            return State.RECOVERY
        lv = set(self._levels) | set(self._events)
        if K.OBSTRUCTION_CONFIRMED in lv:
            return State.TAMPERING_CONFIRMED
        if K.CAMERA_UNAVAILABLE in lv:
            return State.CAMERA_ERROR
        if K.OWNER_ABSENT_CONFIRMED in lv:
            return State.OWNER_ABSENT
        if lv & {K.OBSTRUCTION_POSSIBLE, K.OBSTRUCTION_PARTIAL, K.HAND_APPROACHING}:
            return State.SUSPICIOUS
        if K.OWNER_ABSENT_PENDING in lv:
            return State.OWNER_ABSENT_PENDING
        if K.OWNER_PRESENT in lv:
            return State.OWNER_PRESENT
        return State.MONITORING

    def _refresh_state(self, reason: str) -> list[Action]:
        new = self._derive_state()
        if new == self.state:
            return []
        t = Transition(self._clock(), self.state, new, reason)
        self.transitions.append(t)
        self.state = new
        return [Action(ActionKind.LOG, f"state {t.old.value} -> {t.new.value} ({reason})", "transition")]

"""DecisionCore: turns raw detector outputs into policy signals and returns actions.

Pure orchestration (no threads, no I/O, injected clock) so every scenario can be tested deterministically.
"""

from __future__ import annotations

import time
from typing import Callable

from silentwatch.camera.obstruction import ObstructionResult, ObstructionState
from silentwatch.config.models import PolicyConfig, PresenceConfig
from silentwatch.policy import Action, PolicyEngine, Signal, SignalKind as K, State
from silentwatch.presence.estimator import PresenceObservation, PresenceState, PresenceTracker

_PRESENCE_SIGNAL = {
    PresenceState.PRESENT: K.OWNER_PRESENT,
    PresenceState.ABSENT_PENDING: K.OWNER_ABSENT_PENDING,
    PresenceState.ABSENT_CONFIRMED: K.OWNER_ABSENT_CONFIRMED,
}
_OBSTRUCTION_SIGNAL = {
    ObstructionState.POSSIBLE_OBSTRUCTION: K.OBSTRUCTION_POSSIBLE,
    ObstructionState.PARTIAL_OBSTRUCTION: K.OBSTRUCTION_PARTIAL,
    ObstructionState.CONFIRMED_OBSTRUCTION: K.OBSTRUCTION_CONFIRMED,
    ObstructionState.NORMAL: K.OBSTRUCTION_CLEARED,
}
_CAMERA_SIGNAL = {
    "UNAVAILABLE": K.CAMERA_UNAVAILABLE,
    "FROZEN": K.CAMERA_FROZEN,
    "RECOVERED": K.CAMERA_RECOVERED,
}


def tracker_for(presence: PresenceConfig, mode: str) -> PresenceTracker:
    """Strict mode locks after half the configured absence time (never earlier than the pending time)."""
    lock_after = presence.lock_after_s if mode != "strict" else max(presence.pending_s, presence.lock_after_s * 0.5)
    return PresenceTracker(presence.present_detections, presence.pending_s, lock_after)


class DecisionCore:
    def __init__(
        self,
        policy_cfg: PolicyConfig,
        presence_cfg: PresenceConfig,
        clock: Callable[[], float] = time.monotonic,
        presence_enabled: bool = True,
    ):
        self.clock = clock
        self.engine = PolicyEngine(policy_cfg, clock)
        self.presence_cfg = presence_cfg
        self.mode = policy_cfg.mode
        self.tracker = tracker_for(presence_cfg, self.mode)
        self.presence_enabled = presence_enabled
        self._last_presence_signal: K | None = None
        self._last_obstruction_signal: K | None = None
        self.camera_ok = True
        self._hand_signalled = False

    def start_monitoring(self) -> list[Action]:
        return self.engine.set_phase(None)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.engine.set_mode(mode)
        self.tracker = tracker_for(self.presence_cfg, mode)
        self._last_presence_signal = None

    # -- inputs ---------------------------------------------------------------------------
    def on_presence(self, obs: PresenceObservation, ts: float | None = None) -> list[Action]:
        if not self.presence_enabled:
            return []
        ts = self.clock() if ts is None else ts
        self.camera_ok = True
        state = self.tracker.update(obs, ts)
        sig = _PRESENCE_SIGNAL.get(state)
        if sig is None or sig == self._last_presence_signal:
            return self.engine.tick()
        self._last_presence_signal = sig
        return self.engine.handle(Signal(sig))

    def on_obstruction(self, result: ObstructionResult) -> list[Action]:
        sig = _OBSTRUCTION_SIGNAL.get(result.state)
        if sig is None or sig == self._last_obstruction_signal:
            return []
        self._last_obstruction_signal = sig
        return self.engine.handle(Signal(sig, detail={"reasons": result.reasons, "scores": result.scores}))

    def on_hand(self, approaching: bool, score: float = 0.0) -> list[Action]:
        """Hand evidence. Only the transition into 'approaching' is forwarded (signals are not repeated per frame)."""
        if not approaching:
            self._hand_signalled = False
            return []
        if self._hand_signalled:
            return []
        self._hand_signalled = True
        return self.engine.handle(Signal(K.HAND_APPROACHING, confidence=score))

    def on_camera_status(self, kind: str, detail: str = "", ts: float | None = None) -> list[Action]:
        sig = _CAMERA_SIGNAL.get(kind)
        if sig is None:
            return []
        ts = self.clock() if ts is None else ts
        if sig == K.CAMERA_UNAVAILABLE:
            self.camera_ok = False
            self.tracker.pause(ts)  # no camera is not the same as no owner
        return self.engine.handle(Signal(sig, detail={"detail": detail}))

    def on_session(self, locked: bool) -> list[Action]:
        if locked:
            self._last_presence_signal = None
            self._last_obstruction_signal = None
        return self.engine.handle(Signal(K.SESSION_LOCKED if locked else K.SESSION_UNLOCKED))

    def on_signal(self, sig: Signal) -> list[Action]:
        return self.engine.handle(sig)

    def tick(self) -> list[Action]:
        return self.engine.tick()

    @property
    def state(self) -> State:
        return self.engine.state

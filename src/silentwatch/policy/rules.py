"""Lock rules, table-driven (Book section 10.4). Each rule returns a reason string or None.

Rules are explicit and explainable on purpose; weighted scoring is deliberately deferred (Book section 21).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from silentwatch.policy.states import SignalKind as K


@dataclass(frozen=True)
class Context:
    """Snapshot of what is currently true. Built by the engine; rules never mutate it."""

    active: frozenset[K]
    mode: str
    phone_known: bool    # a phone signal has ever been seen (phone feature in use)

    def has(self, *kinds: K) -> bool:
        return any(k in self.active for k in kinds)

    @property
    def owner_absent_pending(self) -> bool:
        return K.OWNER_ABSENT_PENDING in self.active

    @property
    def owner_absent_confirmed(self) -> bool:
        return K.OWNER_ABSENT_CONFIRMED in self.active

    @property
    def owner_absent_any(self) -> bool:
        return self.owner_absent_pending or self.owner_absent_confirmed

    @property
    def strict(self) -> bool:
        return self.mode == "strict"


@dataclass(frozen=True)
class Rule:
    name: str
    check: Callable[[Context], str | None]


def _obstruction_confirmed(c: Context) -> str | None:
    return "camera obstruction confirmed" if c.has(K.OBSTRUCTION_CONFIRMED) else None


def _partial_and_absent(c: Context) -> str | None:
    if c.has(K.OBSTRUCTION_PARTIAL) and c.owner_absent_any:
        return "partial camera obstruction while owner absent"
    return None


def _possible_and_absent_strict(c: Context) -> str | None:
    if c.strict and c.has(K.OBSTRUCTION_POSSIBLE) and c.owner_absent_any:
        return "possible camera obstruction while owner absent (strict mode)"
    return None


def _hand_and_obstruction(c: Context) -> str | None:
    if c.has(K.HAND_APPROACHING) and c.has(K.OBSTRUCTION_POSSIBLE, K.OBSTRUCTION_PARTIAL):
        return "hand approaching the lens with a possible obstruction"
    return None


def _camera_unavailable_and_absent(c: Context) -> str | None:
    if not c.has(K.CAMERA_UNAVAILABLE):
        return None
    if c.strict and c.owner_absent_any:
        return "camera unavailable while owner absent (strict mode)"
    if c.owner_absent_confirmed:
        # With a phone in use, require it to be missing too (Book 10.4); otherwise absence + camera loss suffices.
        if not c.phone_known or c.has(K.PHONE_MISSING):
            return "camera unavailable while owner absent" + (" and phone missing" if c.phone_known else "")
    return None


def _owner_absent_confirmed(c: Context) -> str | None:
    return "owner absent beyond configured timeout" if c.owner_absent_confirmed else None


RULES: list[Rule] = [
    Rule("obstruction_confirmed", _obstruction_confirmed),
    Rule("partial_and_absent", _partial_and_absent),
    Rule("possible_and_absent_strict", _possible_and_absent_strict),
    Rule("hand_and_obstruction", _hand_and_obstruction),
    Rule("camera_unavailable_and_absent", _camera_unavailable_and_absent),
    Rule("owner_absent_confirmed", _owner_absent_confirmed),
]

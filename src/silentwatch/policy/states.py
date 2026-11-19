"""Policy vocabulary: states, signals, actions (Book sections 10.2-10.5). No I/O, no camera imports."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class State(str, enum.Enum):
    DISABLED = "DISABLED"
    INITIALIZING = "INITIALIZING"
    CALIBRATING = "CALIBRATING"
    MONITORING = "MONITORING"
    OWNER_PRESENT = "OWNER_PRESENT"
    OWNER_ABSENT_PENDING = "OWNER_ABSENT_PENDING"
    OWNER_ABSENT = "OWNER_ABSENT"
    SUSPICIOUS = "SUSPICIOUS"
    TAMPERING_CONFIRMED = "TAMPERING_CONFIRMED"
    LOCK_REQUESTED = "LOCK_REQUESTED"
    LOCKED = "LOCKED"
    CAMERA_ERROR = "CAMERA_ERROR"
    RECOVERY = "RECOVERY"


class SignalKind(str, enum.Enum):
    # persistent "level" signals: stay true until their opposite arrives
    OBSTRUCTION_POSSIBLE = "OBSTRUCTION_POSSIBLE"
    OBSTRUCTION_PARTIAL = "OBSTRUCTION_PARTIAL"
    OBSTRUCTION_CONFIRMED = "OBSTRUCTION_CONFIRMED"
    OBSTRUCTION_CLEARED = "OBSTRUCTION_CLEARED"
    OWNER_PRESENT = "OWNER_PRESENT"
    OWNER_ABSENT_PENDING = "OWNER_ABSENT_PENDING"
    OWNER_ABSENT_CONFIRMED = "OWNER_ABSENT_CONFIRMED"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    CAMERA_FROZEN = "CAMERA_FROZEN"
    CAMERA_RECOVERED = "CAMERA_RECOVERED"
    PHONE_PRESENT = "PHONE_PRESENT"
    PHONE_MISSING = "PHONE_MISSING"
    BT_UNAVAILABLE = "BT_UNAVAILABLE"
    SESSION_LOCKED = "SESSION_LOCKED"
    SESSION_UNLOCKED = "SESSION_UNLOCKED"
    # event signals: expire after policy.signal_expiry_s
    LOW_BRIGHTNESS = "LOW_BRIGHTNESS"
    HAND_APPROACHING = "HAND_APPROACHING"
    USB_STORAGE_ARRIVED = "USB_STORAGE_ARRIVED"


EVENT_SIGNALS = {SignalKind.LOW_BRIGHTNESS, SignalKind.HAND_APPROACHING, SignalKind.USB_STORAGE_ARRIVED}


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    confidence: float = 1.0
    detail: dict[str, Any] = field(default_factory=dict)


class ActionKind(str, enum.Enum):
    LOG = "LOG"
    NOTIFY = "NOTIFY"
    LOCK = "LOCK"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    reason: str
    rule: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Transition:
    at: float
    old: State
    new: State
    reason: str

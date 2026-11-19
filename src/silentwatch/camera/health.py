"""Camera health: frozen feed, read failures, format changes, timestamp gaps. Pure logic, no I/O."""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass

import cv2
import numpy as np


class HealthState(str, enum.Enum):
    OK = "OK"
    FROZEN = "FROZEN"
    UNAVAILABLE = "UNAVAILABLE"


class HealthEventKind(str, enum.Enum):
    FROZEN = "FROZEN"
    UNAVAILABLE = "UNAVAILABLE"
    RECOVERED = "RECOVERED"
    FORMAT_CHANGED = "FORMAT_CHANGED"
    GAP = "GAP"


@dataclass(frozen=True)
class HealthEvent:
    kind: HealthEventKind
    detail: str = ""


def _frame_hash(img: np.ndarray) -> bytes:
    small = cv2.resize(img, (64, 48), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
    return hashlib.blake2b(gray.tobytes(), digest_size=8).digest()


def _is_shutter_black(img: np.ndarray) -> bool:
    """A privacy shutter yields a valid, constant black frame. That is not a frozen camera."""
    return float(img.mean()) < 3.0 and float(img.std()) < 1.0


class CameraHealthMonitor:
    def __init__(
        self,
        frozen_frames: int = 10,
        read_fail_limit: int = 5,
        expected_interval_s: float = 0.2,
        frozen_seconds: float = 20.0,
    ):
        self.frozen_frames = frozen_frames
        self.frozen_seconds = frozen_seconds
        self.read_fail_limit = read_fail_limit
        self.expected_interval_s = expected_interval_s
        self.state = HealthState.OK
        self._fail_run = 0
        self._same_run = 0
        self._last_hash: bytes | None = None
        self._last_shape: tuple | None = None
        self._last_ts: float | None = None
        self._same_since: float | None = None

    def observe(self, ok: bool, image: np.ndarray | None, ts: float) -> list[HealthEvent]:
        """Feed one read result. Returns health events caused by it (usually empty)."""
        events: list[HealthEvent] = []
        if not ok or image is None:
            self._fail_run += 1
            if self._fail_run >= self.read_fail_limit and self.state != HealthState.UNAVAILABLE:
                self.state = HealthState.UNAVAILABLE
                events.append(HealthEvent(HealthEventKind.UNAVAILABLE, f"{self._fail_run} consecutive read failures"))
            return events

        self._fail_run = 0
        previous = self.state
        if self._last_ts is not None and ts - self._last_ts > 5 * self.expected_interval_s:
            events.append(HealthEvent(HealthEventKind.GAP, f"{ts - self._last_ts:.2f}s between frames"))
        self._last_ts = ts

        if self._last_shape is not None and image.shape != self._last_shape:
            events.append(HealthEvent(HealthEventKind.FORMAT_CHANGED, f"{self._last_shape} -> {image.shape}"))
            self._same_run = 0
            self._last_hash = None
        self._last_shape = image.shape

        h = _frame_hash(image)
        if self._last_hash is not None and h == self._last_hash and not _is_shutter_black(image):
            self._same_run += 1
        else:
            self._same_run = 0
            self._same_since = ts
        self._last_hash = h

        # A dim, static scene can deliver bit-identical frames for seconds (observed on the HP camera, D9),
        # so 'frozen' needs both a frame count and a minimum duration.
        same_for = ts - (self._same_since if self._same_since is not None else ts)
        if self._same_run + 1 >= self.frozen_frames and same_for >= self.frozen_seconds:
            if self.state != HealthState.FROZEN:
                self.state = HealthState.FROZEN
                events.append(HealthEvent(HealthEventKind.FROZEN, f"{self._same_run + 1} identical frames"))
        else:
            self.state = HealthState.OK

        if previous != HealthState.OK and self.state == HealthState.OK:
            events.append(HealthEvent(HealthEventKind.RECOVERED, f"was {previous.value}"))
        return events

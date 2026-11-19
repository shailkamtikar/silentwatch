"""Lock the real Windows session via LockWorkStation (never a fake overlay)."""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

from silentwatch.storage import EventStore, EventType, Severity

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LockResult:
    requested: bool          # API accepted the request (does not prove the lock has finished)
    dry_run: bool = False
    suppressed: bool = False  # blocked by cooldown
    win32_error: int | None = None
    reason: str = ""


def _win32_lock() -> tuple[bool, int | None]:
    """Call user32.LockWorkStation. Returns (ok, last_error)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.LockWorkStation.restype = ctypes.c_int
    ok = bool(user32.LockWorkStation())
    return ok, (None if ok else ctypes.get_last_error())


class WindowsLockService:
    def __init__(
        self,
        store: EventStore | None = None,
        dry_run: bool = True,
        cooldown_s: float = 5.0,
        lock_fn: Callable[[], tuple[bool, int | None]] = _win32_lock,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.store = store
        self.dry_run = dry_run
        self.cooldown_s = cooldown_s
        self._lock_fn = lock_fn
        self._clock = clock
        self._last_request: float | None = None
        self._mutex = threading.Lock()

    def _log(self, etype: EventType, sev: Severity, reason: str, details: dict, action: str | None = None) -> None:
        if self.store is not None:
            self.store.append(etype, sev, "lock_service", details={"reason": reason, **details}, action_taken=action)

    def lock(self, reason: str) -> LockResult:
        with self._mutex:
            now = self._clock()
            if self._last_request is not None and now - self._last_request < self.cooldown_s:
                self._log(EventType.LOCK_SUPPRESSED, Severity.INFO, reason, {"cooldown_s": self.cooldown_s})
                return LockResult(False, self.dry_run, True, None, reason)
            self._last_request = now

            if self.dry_run:
                self._log(EventType.LOCK_REQUESTED, Severity.CRITICAL, reason, {"dry_run": True})
                log.warning("DRY RUN: would lock Windows (%s)", reason)
                self._log(EventType.LOCK_RESULT, Severity.INFO, reason, {"dry_run": True}, "dry_run")
                return LockResult(True, True, False, None, reason)

            # The real lock is requested BEFORE anything touches the database, so a slow, locked or full
            # database can never delay or prevent it.
            try:
                ok, err = self._lock_fn()
            except Exception as exc:  # noqa: BLE001 - lock failure must never crash monitoring
                log.error("LockWorkStation raised %r", exc)
                self._log(EventType.LOCK_REQUESTED, Severity.CRITICAL, reason, {"dry_run": False})
                self._log(EventType.LOCK_RESULT, Severity.CRITICAL, reason, {"exception": repr(exc)}, "failed")
                return LockResult(False, False, False, None, reason)
            if not ok:
                log.error("LockWorkStation failed, error=%s", err)
            self._log(EventType.LOCK_REQUESTED, Severity.CRITICAL, reason, {"dry_run": False})
            self._log(
                EventType.LOCK_RESULT,
                Severity.INFO if ok else Severity.CRITICAL,
                reason,
                {"win32_error": err},
                "locked" if ok else "failed",
            )
            return LockResult(ok, False, False, err, reason)

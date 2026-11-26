"""Event log: security-relevant events, minimal data, no frames or personal info."""

from __future__ import annotations

import enum
import json
import logging
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from silentwatch.storage.database import Database

log = logging.getLogger(__name__)


class EventType(str, enum.Enum):
    APP_STARTED = "APP_STARTED"
    APP_STOPPED = "APP_STOPPED"
    STATE_CHANGED = "STATE_CHANGED"
    LOCK_REQUESTED = "LOCK_REQUESTED"
    LOCK_RESULT = "LOCK_RESULT"
    LOCK_SUPPRESSED = "LOCK_SUPPRESSED"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    CAMERA_FROZEN = "CAMERA_FROZEN"
    CAMERA_BUSY = "CAMERA_BUSY"
    CAMERA_RECOVERED = "CAMERA_RECOVERED"
    CAMERA_RETRY = "CAMERA_RETRY"
    CAMERA_FORMAT_CHANGED = "CAMERA_FORMAT_CHANGED"
    OBSTRUCTION_POSSIBLE = "OBSTRUCTION_POSSIBLE"
    OBSTRUCTION_PARTIAL = "OBSTRUCTION_PARTIAL"
    OBSTRUCTION_CONFIRMED = "OBSTRUCTION_CONFIRMED"
    OBSTRUCTION_CLEARED = "OBSTRUCTION_CLEARED"
    CALIBRATION_DONE = "CALIBRATION_DONE"
    CALIBRATION_REJECTED = "CALIBRATION_REJECTED"
    OWNER_ABSENT_PENDING = "OWNER_ABSENT_PENDING"
    OWNER_ABSENT_CONFIRMED = "OWNER_ABSENT_CONFIRMED"
    OWNER_PRESENT = "OWNER_PRESENT"
    HAND_APPROACHING = "HAND_APPROACHING"
    PHONE_PRESENT = "PHONE_PRESENT"
    PHONE_MISSING = "PHONE_MISSING"
    BT_UNAVAILABLE = "BT_UNAVAILABLE"
    USB_STORAGE_ARRIVED = "USB_STORAGE_ARRIVED"
    USB_STORAGE_REMOVED = "USB_STORAGE_REMOVED"
    SESSION_LOCKED = "SESSION_LOCKED"
    SESSION_UNLOCKED = "SESSION_UNLOCKED"
    SNAPSHOT_SAVED = "SNAPSHOT_SAVED"
    SETTINGS_CHANGED = "SETTINGS_CHANGED"
    DATA_DELETED = "DATA_DELETED"
    ERROR = "ERROR"


class Severity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Event:
    event_type: EventType
    severity: Severity
    source: str
    confidence: float | None = None
    details: dict[str, Any] | None = None
    action_taken: str | None = None
    timestamp_utc: str | None = None
    id: int | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class EventStore:
    """Append-only event log. Storage failures never raise out of append().

    With async_writes=True, append() only queues the event in memory and a background thread writes it, so a slow,
    locked or full database can never stall the monitoring/decision path (it retries until the database recovers).
    """

    def __init__(self, db: Database, fallback_size: int = 1000, async_writes: bool = False):
        self.db = db
        self._pending: deque[Event] = deque(maxlen=fallback_size)
        self._flush_lock = threading.Lock()
        self._async = async_writes
        self._cv = threading.Condition()
        self._closing = False
        self._writer: threading.Thread | None = None
        if async_writes:
            self._writer = threading.Thread(target=self._writer_loop, name="event-writer", daemon=True)
            self._writer.start()

    # -- async writer ---------------------------------------------------------------------
    def _flush_async(self) -> bool:
        """Write queued events one by one. Returns False if the database refused (events stay queued)."""
        while True:
            with self._cv:
                if not self._pending:
                    return True
                ev = self._pending.popleft()
            try:
                self._insert(ev)
            except sqlite3.Error as exc:
                with self._cv:
                    self._pending.appendleft(ev)
                log.error("Event store write failed (%r); %d event(s) held in memory", exc, len(self._pending))
                return False

    def _writer_loop(self) -> None:
        while True:
            with self._cv:
                while not self._pending and not self._closing:
                    self._cv.wait(0.5)
                if self._closing and not self._pending:
                    return
            if not self._flush_async():
                time.sleep(0.3)          # database busy/full: retry shortly
                with self._cv:
                    if self._closing:
                        return

    def flush(self, timeout: float = 2.0) -> bool:
        """Wait (bounded) until everything queued has been written. True if the queue drained."""
        if not self._async:
            with self._flush_lock:
                self._flush()
            return not self._pending
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._cv:
                if not self._pending:
                    return True
                self._cv.notify()
            time.sleep(0.01)
        return not self._pending

    def close(self, timeout: float = 3.0) -> None:
        """Flush (bounded), stop the writer. Later appends fall back to synchronous writes."""
        if self._async:
            self.flush(timeout)
            with self._cv:
                self._closing = True
                self._cv.notify_all()
            if self._writer is not None:
                self._writer.join(timeout)
            self._async = False

    def append(
        self,
        event_type: EventType,
        severity: Severity = Severity.INFO,
        source: str = "app",
        confidence: float | None = None,
        details: dict[str, Any] | None = None,
        action_taken: str | None = None,
        timestamp_utc: str | None = None,
    ) -> None:
        ev = Event(event_type, severity, source, confidence, details, action_taken, timestamp_utc or _now_iso())
        if self._async:
            with self._cv:
                self._pending.append(ev)
                self._cv.notify()
            return
        with self._flush_lock:
            self._pending.append(ev)
            self._flush()

    def _insert(self, ev: Event) -> None:
        self.db.execute(
            "INSERT INTO events (timestamp_utc, event_type, severity, confidence, source, details_json, action_taken)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                ev.timestamp_utc,
                ev.event_type.value,
                ev.severity.value,
                ev.confidence,
                ev.source,
                json.dumps(ev.details, separators=(",", ":")) if ev.details is not None else None,
                ev.action_taken,
            ),
        )

    def _flush(self) -> None:
        while self._pending:
            ev = self._pending[0]
            try:
                self._insert(ev)
            except sqlite3.Error as exc:
                log.error("Event store write failed (%r); %d event(s) held in memory", exc, len(self._pending))
                return
            self._pending.popleft()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @staticmethod
    def _row(r: tuple) -> Event:
        return Event(
            id=r[0],
            timestamp_utc=r[1],
            event_type=EventType(r[2]),
            severity=Severity(r[3]),
            confidence=r[4],
            source=r[5],
            details=json.loads(r[6]) if r[6] else None,
            action_taken=r[7],
        )

    _COLS = "id, timestamp_utc, event_type, severity, confidence, source, details_json, action_taken"

    def recent(self, n: int = 50) -> list[Event]:
        self._settle()
        rows = self.db.query(f"SELECT {self._COLS} FROM events ORDER BY id DESC LIMIT ?", (n,))
        return [self._row(r) for r in rows]

    def query(
        self,
        event_type: EventType | None = None,
        since: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Event]:
        self._settle()
        clauses, params = [], []
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type.value)
        if since is not None:
            clauses.append("timestamp_utc >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.db.query(
            f"SELECT {self._COLS} FROM events {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        return [self._row(r) for r in rows]

    def _settle(self) -> None:
        if self._async:
            self.flush(1.0)

    def count(self) -> int:
        self._settle()
        return self.db.query("SELECT COUNT(*) FROM events")[0][0]

    def purge_older_than(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="milliseconds")
        cur = self.db.execute("DELETE FROM events WHERE timestamp_utc < ?", (cutoff,))
        return cur.rowcount

    def delete_all(self) -> None:
        self.db.execute("DELETE FROM events")

"""Event log: security-relevant events, minimal data, no frames or personal info."""

from __future__ import annotations

import enum
import json
import logging
import sqlite3
import threading
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
    """Append-only event log. Storage failures never raise out of append()."""

    def __init__(self, db: Database, fallback_size: int = 1000):
        self.db = db
        self._pending: deque[Event] = deque(maxlen=fallback_size)
        self._flush_lock = threading.Lock()

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
        rows = self.db.query(f"SELECT {self._COLS} FROM events ORDER BY id DESC LIMIT ?", (n,))
        return [self._row(r) for r in rows]

    def query(
        self,
        event_type: EventType | None = None,
        since: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Event]:
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

    def count(self) -> int:
        return self.db.query("SELECT COUNT(*) FROM events")[0][0]

    def purge_older_than(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="milliseconds")
        cur = self.db.execute("DELETE FROM events WHERE timestamp_utc < ?", (cutoff,))
        return cur.rowcount

    def delete_all(self) -> None:
        self.db.execute("DELETE FROM events")

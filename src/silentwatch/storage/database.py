"""SQLite connection management: WAL, schema versioning, corruption recovery."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# Each migration upgrades from (index) to (index + 1). Keep these append-only.
MIGRATIONS: list[str] = [
    # v0 -> v1
    """
    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp_utc TEXT NOT NULL,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        confidence REAL,
        source TEXT NOT NULL,
        details_json TEXT,
        action_taken TEXT
    );
    CREATE INDEX idx_events_ts ON events(timestamp_utc);
    CREATE INDEX idx_events_type ON events(event_type);
    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE camera_calibration (
        camera_id TEXT NOT NULL,
        resolution TEXT NOT NULL,
        baseline_features_json TEXT NOT NULL,
        calibrated_at TEXT NOT NULL,
        PRIMARY KEY (camera_id, resolution)
    );
    """,
    # v1 -> v2
    """
    CREATE TABLE device_enrollment (
        device_id TEXT PRIMARY KEY,
        device_type TEXT NOT NULL,
        friendly_name TEXT NOT NULL,
        public_key_or_protected_token TEXT,
        created_at TEXT NOT NULL,
        last_seen_at TEXT
    );
    """,
]
SCHEMA_VERSION = len(MIGRATIONS)


class Database:
    """Thread-safe wrapper around one SQLite file."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._conn = self._open()

    # -- opening / recovery -------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=2)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA user_version").fetchone()
        except sqlite3.DatabaseError:
            conn.close()  # release the file handle so it can be moved aside (Windows)
            raise
        return conn

    def _open(self) -> sqlite3.Connection:
        try:
            conn = self._connect()
        except sqlite3.DatabaseError as exc:
            log.error("Database %s unreadable (%r); moving aside and recreating", self.path, exc)
            self._quarantine()
            conn = self._connect()
        self._migrate(conn)
        return conn

    def _quarantine(self) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(self.path) + suffix)
            if p.exists():
                try:
                    target = p.with_name(f"{p.name}.{stamp}.corrupt") if suffix == "" else p
                    if suffix == "":
                        p.replace(target)
                    else:
                        p.unlink()
                except OSError as exc:
                    log.error("Could not quarantine %s: %r", p, exc)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for v in range(version, SCHEMA_VERSION):
            with conn:
                conn.executescript("BEGIN;" + MIGRATIONS[v])
                conn.execute(f"PRAGMA user_version = {v + 1}")
            log.info("Database migrated to schema v%d", v + 1)

    # -- access --------------------------------------------------------------
    @property
    def version(self) -> int:
        with self._lock:
            return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            with self._conn:
                return self._conn.execute(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def transaction(self, fn: Callable[[sqlite3.Connection], object]) -> object:
        with self._lock:
            with self._conn:
                return fn(self._conn)

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

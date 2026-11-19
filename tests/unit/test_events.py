import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest

from silentwatch.storage import SCHEMA_VERSION, Database, EventStore, EventType, Severity


@pytest.fixture
def store(tmp_path):
    db = Database(tmp_path / "t.db")
    yield EventStore(db)
    db.close()


def test_schema_created(tmp_path):
    db = Database(tmp_path / "x.db")
    tables = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"events", "settings", "camera_calibration", "device_enrollment"} <= tables
    assert db.version == SCHEMA_VERSION
    db.close()


def test_append_and_recent(store):
    for i in range(3):
        store.append(EventType.LOCK_REQUESTED, Severity.CRITICAL, "test", 0.9, {"i": i}, "lock")
    rows = store.recent(3)
    assert [r.details["i"] for r in rows] == [2, 1, 0]
    assert rows[0].action_taken == "lock" and rows[0].confidence == 0.9


def test_query_filter(store):
    store.append(EventType.LOCK_RESULT)
    store.append(EventType.ERROR)
    assert [e.event_type for e in store.query(event_type=EventType.LOCK_RESULT)] == [EventType.LOCK_RESULT]


def test_sql_injection_stored_as_text(store):
    evil = "'; DROP TABLE events;--"
    store.append(EventType.ERROR, details={"x": evil}, source=evil)
    assert store.count() == 1
    assert store.recent(1)[0].details["x"] == evil


def test_retention_purge(store):
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    store.append(EventType.ERROR, timestamp_utc=old)
    store.append(EventType.ERROR)
    assert store.purge_older_than(30) == 1
    assert store.count() == 1


def test_delete_all(store):
    store.append(EventType.ERROR)
    store.delete_all()
    assert store.count() == 0
    store.append(EventType.ERROR)  # schema intact
    assert store.count() == 1


def test_concurrent_writes(tmp_path):
    db = Database(tmp_path / "c.db")
    st = EventStore(db)

    def work():
        for _ in range(1000):
            st.append(EventType.STATE_CHANGED)

    ts = [threading.Thread(target=work) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert st.count() == 2000
    db.close()


def test_corrupt_db_recovered(tmp_path):
    p = tmp_path / "bad.db"
    p.write_bytes(b"this is not a sqlite database" * 50)
    db = Database(p)
    st = EventStore(db)
    st.append(EventType.ERROR)
    assert st.count() == 1
    assert list(tmp_path.glob("*.corrupt"))
    db.close()


def test_storage_failure_never_raises(store, monkeypatch):
    def boom(*a, **k):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(store.db, "execute", boom)
    store.append(EventType.ERROR)  # must not raise
    assert store.pending_count == 1
    monkeypatch.undo()
    store.append(EventType.ERROR)  # flushes the backlog
    assert store.pending_count == 0 and store.count() == 2


def test_migration_from_v0_and_v1(tmp_path):
    p = tmp_path / "m.db"
    conn = sqlite3.connect(p)
    conn.execute("PRAGMA user_version = 0")
    conn.close()
    db = Database(p)
    assert db.version == SCHEMA_VERSION
    db.close()


def test_migration_keeps_data(tmp_path):
    from silentwatch.storage.database import MIGRATIONS

    p = tmp_path / "keep.db"
    conn = sqlite3.connect(p)
    conn.executescript(MIGRATIONS[0])
    conn.execute("PRAGMA user_version = 1")
    conn.execute(
        "INSERT INTO events (timestamp_utc, event_type, severity, source) VALUES ('2026-01-01T00:00:00+00:00','ERROR','INFO','t')"
    )
    conn.commit()
    conn.close()
    db = Database(p)
    assert db.version == 2
    assert EventStore(db).count() == 1
    db.close()

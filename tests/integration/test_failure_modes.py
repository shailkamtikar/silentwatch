"""Failure-mode and security tests (Book 18.4 and the 16 failure table) that need no human or hardware."""

import json
import pathlib
import random
import re
import sqlite3
import subprocess
import sys
import time

from silentwatch.camera.calibration import CalibrationStore
from silentwatch.config import default_config, load_config
from silentwatch.storage import Database, EventStore, EventType
from silentwatch.windows.lock import WindowsLockService
from tests.unit.test_service_controls import build_service, wait_for

SRC = pathlib.Path(__file__).parents[2] / "src" / "silentwatch"


def test_process_killed_mid_write_leaves_a_valid_database(tmp_path):
    db_path = tmp_path / "k.db"
    code = (
        "import sys, time\n"
        "from silentwatch.storage import Database, EventStore, EventType\n"
        f"db = Database(r'{db_path}')\n"
        "st = EventStore(db)\n"
        "print('ready', flush=True)\n"
        "i = 0\n"
        "while True:\n"
        "    st.append(EventType.STATE_CHANGED, details={'i': i}); i += 1\n"
    )
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "ready"
    time.sleep(1.0)
    p.kill()                                   # hard kill: no cleanup, like a crash or an attacker's taskkill /F
    p.wait()
    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()
    db = Database(db_path)                      # restarts cleanly and keeps its data
    n = EventStore(db).count()
    assert n > 10
    db.close()


def test_locked_database_never_delays_the_real_lock(tmp_path):
    svc, db, world = build_service(tmp_path)
    fired = []
    svc.lock_service = WindowsLockService(svc.store, dry_run=False, cooldown_s=1.0, lock_fn=lambda: (fired.append(time.time()) or True, None))
    svc.start()
    time.sleep(1.0)
    holder = sqlite3.connect(db.path, timeout=0.1, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")           # another process holds the write lock for the whole test
    t0 = time.time()
    world.scene = "finger"
    assert wait_for(lambda: fired, 5)
    assert fired[0] - t0 < 2.0, "lock was delayed by the locked database"
    holder.execute("ROLLBACK")
    holder.close()
    svc.stop()
    db.close()


def test_monitoring_survives_a_locked_database(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(0.8)
    holder = sqlite3.connect(db.path, timeout=0.1, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    world.scene = "finger"
    assert wait_for(lambda: svc.lock_actions, 8)   # decisions still happen while events cannot be written
    holder.execute("ROLLBACK")
    holder.close()
    assert not svc.crashed
    svc.stop()
    db.close()


def test_corrupted_calibration_row_triggers_recalibration_not_a_crash(tmp_path):
    import dataclasses

    svc, db, world = build_service(tmp_path)
    svc.cfg = dataclasses.replace(svc.cfg, obstruction=dataclasses.replace(svc.cfg.obstruction, calibration_seconds=2.0))
    db.execute("UPDATE camera_calibration SET baseline_features_json = '{not json'")
    svc.start()
    assert wait_for(lambda: svc.classifier.baseline is not None, 12)      # recalibrated from live frames
    assert not svc.crashed
    errors = svc.store.query(event_type=EventType.ERROR)
    assert any("calibration" in (e.details or {}).get("detail", "") for e in errors)
    svc.stop()
    db.close()


def test_rejected_calibration_is_retried_until_it_succeeds(tmp_path):
    import dataclasses

    svc, db, world = build_service(tmp_path)
    svc.cfg = dataclasses.replace(svc.cfg, obstruction=dataclasses.replace(svc.cfg.obstruction, calibration_seconds=2.0))
    svc.CAL_RETRY_S = 0.5
    db.execute("DELETE FROM camera_calibration")
    world.scene = "finger"                       # lens covered at start-up: calibration must be refused
    svc.start()
    assert wait_for(lambda: svc.store.query(event_type=EventType.CALIBRATION_REJECTED), 10)
    assert svc.classifier.baseline is None
    world.scene = "normal"                       # uncovered: the retry now succeeds
    assert wait_for(lambda: svc.classifier.baseline is not None, 12)
    world.scene = "finger"
    assert wait_for(lambda: svc.lock_actions, 8)  # and obstruction detection works from then on
    svc.stop()
    db.close()


def test_transient_iteration_error_does_not_stop_monitoring(tmp_path):
    svc, db, world = build_service(tmp_path)
    real = svc.classifier.update
    calls = {"n": 0}

    def flaky(f, ts):
        calls["n"] += 1
        if calls["n"] in (5, 6, 7):
            raise RuntimeError("transient")
        return real(f, ts)

    svc.classifier.update = flaky
    svc.start()
    time.sleep(1.5)
    assert not svc.crashed and svc.status().frames > 10
    world.scene = "finger"
    assert wait_for(lambda: svc.lock_actions, 6)
    svc.stop()
    db.close()


def test_tampered_settings_never_crash_or_weaken_safety(tmp_path):
    rnd = random.Random(1234)
    bad_values = [None, True, -1, 10**18, 1e308, "x" * 10_000, [], {}, {"a": {"b": 1}}, float("nan")]
    for i in range(60):
        data = {}
        for sec in ("camera", "obstruction", "presence", "policy", "privacy", "nope", "../../etc"):
            if rnd.random() < 0.7:
                data[sec] = {k: rnd.choice(bad_values) for k in ("width", "confirm_debounce_s", "lock_after_s", "mode", "snapshots", "dry_run", "zzz")}
        p = tmp_path / f"s{i}.json"
        try:
            p.write_text(json.dumps(data, allow_nan=True), encoding="utf-8")
        except (TypeError, ValueError):
            continue
        cfg = load_config(p)                                    # must never raise
        assert cfg.obstruction.confirm_debounce_s >= 0.2         # safety floor holds
        assert cfg.privacy.snapshots is False or data.get("privacy", {}).get("snapshots") is True


def test_garbage_and_oversized_settings_files(tmp_path):
    for payload in (b"\x00\xff\xfe", b"[1,2,3]", b'{"policy": "x"}', b"{" * 100_000):
        p = tmp_path / "g.json"
        p.write_bytes(payload)
        assert load_config(p) == default_config()


def test_no_network_code_in_the_product():
    banned = re.compile(r"^\s*(import|from)\s+(socket|requests|urllib|http\.client|httpx|aiohttp|ftplib|smtplib|websockets?)\b", re.M)
    for f in SRC.rglob("*.py"):
        assert not banned.search(f.read_text(encoding="utf-8")), f"network import in {f}"


def test_no_elevation_or_credentials_requested():
    text = "\n".join(f.read_text(encoding="utf-8") for f in SRC.rglob("*.py"))
    for marker in ("runas", "ShellExecute", "requireAdministrator", "SeDebugPrivilege", "AdjustTokenPrivileges"):
        assert marker not in text


def test_storage_full_does_not_stop_decisions(tmp_path, monkeypatch):
    svc, db, world = build_service(tmp_path)

    def full(*a, **k):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(svc.store.db, "execute", full)
    svc.start()
    time.sleep(0.8)
    world.scene = "finger"
    assert wait_for(lambda: svc.lock_actions, 6)
    assert not svc.crashed
    monkeypatch.undo()
    svc.stop()
    db.close()

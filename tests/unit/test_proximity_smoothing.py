import asyncio
import time

import pytest

from silentwatch.bluetooth.enrollment import TYPE_BLE_UUID, TYPE_PAIRED, EnrolledDevice, EnrollmentStore
from silentwatch.bluetooth.proximity import (
    BleAdvertSource,
    BluetoothProximityService,
    PairedConnectionSource,
    ProximitySmoother,
    ProximityState as S,
    Reading,
)
from silentwatch.storage import Database, EventStore, EventType

YES, NO, OFF = Reading(True, True, -50), Reading(True, False), Reading(False)


def feed(sm, readings, t0=0.0, dt=1.0):
    return [sm.update(r, t0 + i * dt) for i, r in enumerate(readings)]


def test_present_needs_consecutive_readings():
    st = feed(ProximitySmoother(60, 2), [YES, YES])
    assert st == [S.UNKNOWN, S.PRESENT]


def test_missing_only_after_window():
    sm = ProximitySmoother(missing_after_s=60)
    feed(sm, [YES, YES])
    st = feed(sm, [NO] * 70, t0=2.0)
    assert st[56] == S.PRESENT and st[-1] == S.MISSING      # 58 s without sight is still present
    assert st[57] in (S.PRESENT, S.MISSING)                 # flips at ~60 s


def test_brief_dropout_does_not_flip():
    sm = ProximitySmoother(60)
    feed(sm, [YES, YES])
    st = feed(sm, [NO] * 10 + [YES], t0=2.0)                # 10 s of interference
    assert S.MISSING not in st and st[-1] == S.PRESENT


def test_unavailable_is_not_missing_and_outage_does_not_count():
    sm = ProximitySmoother(60)
    feed(sm, [YES, YES])
    assert sm.update(OFF, 100.0) == S.UNAVAILABLE
    assert sm.update(NO, 400.0) == S.UNAVAILABLE or sm.state != S.MISSING
    assert sm.update(NO, 401.0) != S.MISSING                # outage time is not absence time
    assert sm.update(NO, 465.0) == S.MISSING                # a full window of *observed* absence is needed


def test_phone_returns_after_missing():
    sm = ProximitySmoother(10)
    feed(sm, [YES, YES])
    feed(sm, [NO] * 15, t0=2.0)
    assert sm.state == S.MISSING
    assert feed(sm, [YES, YES], t0=20.0) == [S.MISSING, S.PRESENT]


class FakeSource:
    def __init__(self):
        self.reading = YES
        self.calls = 0

    async def poll(self):
        self.calls += 1
        return self.reading


def test_service_emits_states_and_logs_events(tmp_path):
    db = Database(tmp_path / "b.db")
    store = EventStore(db)
    src, seen = FakeSource(), []
    svc = BluetoothProximityService(src, ProximitySmoother(0.4, 2), seen.append, store, poll_interval_s=0.05)
    svc.start()
    time.sleep(0.5)
    assert seen and seen[0] == S.PRESENT
    src.reading = NO
    time.sleep(1.0)
    src.reading = OFF
    time.sleep(0.4)
    svc.stop()
    assert S.MISSING in seen and seen[-1] == S.UNAVAILABLE
    kinds = [e.event_type for e in store.query(limit=20)]
    assert EventType.PHONE_PRESENT in kinds and EventType.PHONE_MISSING in kinds and EventType.BT_UNAVAILABLE in kinds
    db.close()


def test_service_survives_source_crash_and_callback_crash(tmp_path):
    class Crashy:
        async def poll(self):
            raise RuntimeError("radio exploded")

    seen = []

    def cb(s):
        seen.append(s)
        raise RuntimeError("cb")

    svc = BluetoothProximityService(Crashy(), ProximitySmoother(1, 2), cb, None, poll_interval_s=0.05)
    svc.start()
    time.sleep(0.4)
    svc.stop()
    assert seen == [S.UNAVAILABLE]


def test_enrollment_roundtrip_and_unenroll(tmp_path):
    db = Database(tmp_path / "e.db")
    store = EnrollmentStore(db)
    assert store.load() is None
    store.save(EnrolledDevice("service-uuid-1", TYPE_BLE_UUID, "My phone"))
    d = store.load()
    assert d.device_id == "service-uuid-1" and d.friendly_name == "My phone"
    cols = [r[1] for r in db.query("PRAGMA table_info(device_enrollment)")]
    assert "public_key_or_protected_token" in cols
    assert db.query("SELECT public_key_or_protected_token FROM device_enrollment")[0][0] is None   # no secrets stored
    assert store.delete() == 1 and store.load() is None
    db.close()


def test_enrollment_rejects_unknown_type(tmp_path):
    db = Database(tmp_path / "e2.db")
    with pytest.raises(ValueError):
        EnrollmentStore(db).save(EnrolledDevice("x", "carrier-pigeon", "n"))
    db.close()


def test_real_sources_degrade_gracefully_without_a_device():
    r = asyncio.run(PairedConnectionSource("not-a-real-device-id").poll())
    assert r.available is False and r.present is False
    r2 = asyncio.run(BleAdvertSource("0000feed-0000-1000-8000-00805f9b34fb", scan_s=1.0).poll())
    assert r2.present is False          # nothing advertises that UUID (available may be True or False)

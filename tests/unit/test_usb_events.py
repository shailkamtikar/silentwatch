import ctypes
import dataclasses
import struct
import time

from silentwatch.config import default_config
from silentwatch.policy import ActionKind, PolicyEngine, Signal, SignalKind as K
from silentwatch.storage import EventType
from silentwatch.windows.usb_monitor import (
    BUS_TYPE_USB,
    DBT_DEVICEARRIVAL,
    DBT_DEVICEREMOVECOMPLETE,
    DBT_DEVTYP_VOLUME,
    WM_DEVICECHANGE,
    UsbMonitor,
    bus_type_of,
    classify,
    drive_letters,
)
from tests.unit.test_service_controls import build_service, wait_for


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def engine(mode="balanced"):
    cfg = dataclasses.replace(default_config().policy, mode=mode, lock_cooldown_s=0, post_unlock_grace_s=0)
    e = PolicyEngine(cfg, Clock())
    e.set_phase(None)
    return e


def locks(acts):
    return [a for a in acts if a.kind == ActionKind.LOCK]


def broadcast(mon, wparam, letter="E", devtype=DBT_DEVTYP_VOLUME):
    import win32gui

    mask = 1 << (ord(letter) - ord("A"))
    buf = ctypes.create_string_buffer(struct.pack("<IIIIH2x", 20, devtype, 0, mask, 0))
    win32gui.SendMessage(mon.hwnd, WM_DEVICECHANGE, wparam, ctypes.addressof(buf))


def test_drive_letters():
    assert drive_letters(0b101) == ["A", "C"]


def test_classification_uses_bus_type():
    assert classify("E", lambda l: BUS_TYPE_USB) == "usb"
    assert classify("E", lambda l: 17) == "nvme"
    assert classify("E", lambda l: None) == "unknown"


def test_real_system_drive_is_not_usb():
    bus = bus_type_of("C")
    assert bus is None or bus != BUS_TYPE_USB


def test_monitor_reports_usb_arrival_and_removal_only():
    got = []
    mon = UsbMonitor(got.append, bus_fn=lambda letter: BUS_TYPE_USB if letter == "E" else 17)
    assert mon.start(), mon.error
    broadcast(mon, DBT_DEVICEARRIVAL, "E")            # USB stick
    broadcast(mon, DBT_DEVICEARRIVAL, "D")            # internal disk: ignored
    broadcast(mon, DBT_DEVICEARRIVAL, "E", devtype=5)  # not a volume (e.g. HID/interface): ignored
    broadcast(mon, DBT_DEVICEREMOVECOMPLETE, "E")
    mon.stop()
    assert got == ["ARRIVED", "REMOVED"]


def test_monitor_survives_garbage_and_callback_errors():
    def cb(kind):
        raise RuntimeError("boom")

    mon = UsbMonitor(cb, bus_fn=lambda l: BUS_TYPE_USB)
    assert mon.start()
    broadcast(mon, DBT_DEVICEARRIVAL, "E")
    broadcast(mon, 0x1234, "E")
    broadcast(mon, DBT_DEVICEARRIVAL, "E")
    mon.stop()


def test_usb_while_owner_present_only_logs():
    e = engine()
    e.handle(Signal(K.OWNER_PRESENT))
    acts = e.handle(Signal(K.USB_STORAGE_ARRIVED))
    assert not locks(acts) and any(a.rule == "usb_logged" for a in acts)


def test_usb_while_owner_absent_locks_in_both_modes():
    for mode in ("balanced", "strict"):
        e = engine(mode)
        e.handle(Signal(K.OWNER_ABSENT_PENDING))
        assert locks(e.handle(Signal(K.USB_STORAGE_ARRIVED))), mode


def test_hid_or_unrelated_signals_do_not_lock():
    e = engine()
    e.handle(Signal(K.OWNER_ABSENT_PENDING))
    assert not locks(e.handle(Signal(K.LOW_BRIGHTNESS)))


def test_service_logs_usb_without_identifying_details(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(0.8)
    svc.on_usb_event("ARRIVED")
    svc.on_usb_event("REMOVED")
    assert wait_for(lambda: svc.store.query(event_type=EventType.USB_STORAGE_REMOVED))
    ev = svc.store.query(event_type=EventType.USB_STORAGE_ARRIVED)[0]
    assert ev.details == {"class": "usb_storage"}          # no serial, letter, label or contents
    assert not svc.lock_actions                            # owner present: logged only
    svc.stop()
    db.close()


def test_service_starts_and_stops_usb_monitor(tmp_path):
    svc, db, world = build_service(tmp_path)

    class Fake:
        started = stopped = 0

        def start(self):
            self.started += 1

        def stop(self):
            self.stopped += 1

    svc.usb = Fake()
    svc.start()
    time.sleep(0.3)
    svc.stop()
    assert (svc.usb.started, svc.usb.stopped) == (1, 1)
    db.close()

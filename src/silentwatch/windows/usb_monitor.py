"""USB storage arrival/removal monitoring (log + risk signal; no blocking, no content reading).

Volume arrivals are broadcast to top-level windows with WM_DEVICECHANGE, so this uses a hidden top-level window.
Only the device *class* is reported: never serial numbers, labels or file listings.
"""

from __future__ import annotations

import ctypes
import logging
import struct
import threading
from typing import Callable

log = logging.getLogger(__name__)

WM_DEVICECHANGE = 0x0219
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVTYP_VOLUME = 0x00000002

BUS_TYPE_USB = 7
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
_BUS_NAMES = {7: "usb", 17: "nvme", 11: "sata", 3: "ata", 12: "sd", 13: "mmc", 1: "scsi"}


def drive_letters(unitmask: int) -> list[str]:
    return [chr(ord("A") + i) for i in range(26) if unitmask & (1 << i)]


def bus_type_of(letter: str) -> int | None:
    """Storage bus type of a drive letter (7 = USB). Needs no admin rights (zero-access handle). None if unknown."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = ctypes.c_void_p
    h = k32.CreateFileW(f"\\\\.\\{letter}:", 0, 3, None, 3, 0, None)
    if h in (None, ctypes.c_void_p(-1).value):
        return None
    try:
        query = struct.pack("<IIB3x", 0, 0, 0)            # StorageDeviceProperty, PropertyStandardQuery
        out = ctypes.create_string_buffer(1024)
        returned = ctypes.c_ulong(0)
        ok = k32.DeviceIoControl(
            ctypes.c_void_p(h), IOCTL_STORAGE_QUERY_PROPERTY, query, len(query), out, len(out), ctypes.byref(returned), None
        )
        if not ok or returned.value < 32:
            return None
        return struct.unpack_from("<I", out.raw, 28)[0]
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


def classify(letter: str, bus_fn: Callable[[str], int | None] = bus_type_of) -> str:
    bus = bus_fn(letter)
    return _BUS_NAMES.get(bus, "unknown") if bus is not None else "unknown"


class UsbMonitor:
    """Calls on_event('ARRIVED' | 'REMOVED') for USB storage volumes only."""

    def __init__(self, on_event: Callable[[str], None], bus_fn: Callable[[str], int | None] = bus_type_of):
        self._on_event = on_event
        self._bus_fn = bus_fn
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self.hwnd: int | None = None
        self.error: str | None = None

    def start(self, timeout: float = 5.0) -> bool:
        self._thread = threading.Thread(target=self._run, name="usb-monitor", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self.hwnd is not None

    def stop(self) -> None:
        if self.hwnd:
            import win32con
            import win32gui

            try:
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:  # noqa: BLE001
                pass
        if self._thread is not None:
            self._thread.join(3)
        self._thread = None
        self.hwnd = None

    def _handle(self, wparam: int, lparam: int) -> None:
        if wparam not in (DBT_DEVICEARRIVAL, DBT_DEVICEREMOVECOMPLETE) or not lparam:
            return
        hdr = ctypes.string_at(lparam, 20)
        _size, devtype, _res, unitmask, _flags = struct.unpack("<IIIIH2x", hdr)
        if devtype != DBT_DEVTYP_VOLUME:
            return
        for letter in drive_letters(unitmask):
            # On removal the volume is already gone and cannot be queried; report removal of any removable volume class.
            if wparam == DBT_DEVICEARRIVAL:
                if classify(letter, self._bus_fn) == "usb":
                    self._on_event("ARRIVED")
            else:
                self._on_event("REMOVED")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        import win32con
        import win32gui

        try:
            if msg == WM_DEVICECHANGE:
                self._handle(wparam, lparam)
            elif msg == win32con.WM_CLOSE:
                win32gui.DestroyWindow(hwnd)
                return 0
            elif msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
        except Exception:  # noqa: BLE001
            log.exception("usb event handler failed")
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _run(self) -> None:
        try:
            import win32api
            import win32gui

            cls = win32gui.WNDCLASS()
            cls.hInstance = win32api.GetModuleHandle(None)
            cls.lpszClassName = f"SilentWatchUsbWnd{id(self)}"
            cls.lpfnWndProc = self._wnd_proc
            atom = win32gui.RegisterClass(cls)
            self.hwnd = win32gui.CreateWindow(atom, "SilentWatchUsb", 0, 0, 0, 0, 0, 0, 0, cls.hInstance, None)
            self._ready.set()
            win32gui.PumpMessages()
        except Exception as exc:  # noqa: BLE001
            self.error = repr(exc)
            log.error("usb monitor failed: %r", exc)
            self._ready.set()

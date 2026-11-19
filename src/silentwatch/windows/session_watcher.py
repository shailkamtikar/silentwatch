"""Event-driven Windows session/power notifications (lock, unlock, logon, logoff, sleep, resume)."""

from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)

WM_WTSSESSION_CHANGE = 0x02B1
WM_POWERBROADCAST = 0x0218
_WTS_EVENTS = {5: "LOGON", 6: "LOGOFF", 7: "LOCK", 8: "UNLOCK", 3: "REMOTE_CONNECT", 4: "REMOTE_DISCONNECT"}
_POWER_EVENTS = {4: "SUSPEND", 7: "RESUME", 18: "RESUME"}   # PBT_APMSUSPEND, RESUMESUSPEND, RESUMEAUTOMATIC


class SessionWatcher:
    """Hidden window on its own thread that receives WTS session and power notifications. No admin needed."""

    def __init__(self, on_event: Callable[[str], None]):
        self._on_event = on_event
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self.hwnd: int | None = None
        self.error: str | None = None

    def start(self, timeout: float = 5.0) -> bool:
        self._thread = threading.Thread(target=self._run, name="session-watcher", daemon=True)
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

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        import win32con
        import win32gui

        try:
            if msg == WM_WTSSESSION_CHANGE and wparam in _WTS_EVENTS:
                self._on_event(_WTS_EVENTS[wparam])
            elif msg == WM_POWERBROADCAST and wparam in _POWER_EVENTS:
                self._on_event(_POWER_EVENTS[wparam])
            elif msg == win32con.WM_CLOSE:
                win32gui.DestroyWindow(hwnd)
                return 0
            elif msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
        except Exception:  # noqa: BLE001 - a callback must never break the message loop
            log.exception("session event handler failed")
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _run(self) -> None:
        try:
            import win32api
            import win32gui
            import win32ts

            cls = win32gui.WNDCLASS()
            cls.hInstance = win32api.GetModuleHandle(None)
            cls.lpszClassName = f"SilentWatchSessionWnd{id(self)}"
            cls.lpfnWndProc = self._wnd_proc
            atom = win32gui.RegisterClass(cls)
            hwnd = win32gui.CreateWindow(atom, "SilentWatchSession", 0, 0, 0, 0, 0, 0, 0, cls.hInstance, None)
            try:
                win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
            except Exception as exc:  # noqa: BLE001 - polling still works without it
                log.warning("WTS registration failed: %r", exc)
            self.hwnd = hwnd
            self._ready.set()
            win32gui.PumpMessages()
            try:
                win32ts.WTSUnRegisterSessionNotification(hwnd)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            self.error = repr(exc)
            log.error("session watcher failed: %r", exc)
            self._ready.set()

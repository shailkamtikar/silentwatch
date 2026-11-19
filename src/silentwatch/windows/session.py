"""Windows session state helpers (polling fallback; event-driven version arrives in M5.4)."""

from __future__ import annotations

import ctypes
import logging

log = logging.getLogger(__name__)

_DESKTOP_SWITCHDESKTOP = 0x0100


def is_workstation_locked() -> bool:
    """True while the secure (lock-screen) desktop has the input focus.

    OpenInputDesktop fails when the calling process cannot open the active input desktop, which is the case
    on the Winlogon/lock desktop. This needs no admin rights. Returns False if the state cannot be determined.
    """
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.OpenInputDesktop.restype = ctypes.c_void_p
        h = user32.OpenInputDesktop(0, False, _DESKTOP_SWITCHDESKTOP)
        if not h:
            return True
        user32.CloseDesktop(ctypes.c_void_p(h))
        return False
    except Exception as exc:  # noqa: BLE001
        log.debug("session state unknown: %r", exc)
        return False

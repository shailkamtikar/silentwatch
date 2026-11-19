"""Single-instance guard (named mutex) so two copies never fight over the camera."""

from __future__ import annotations

import ctypes

ERROR_ALREADY_EXISTS = 183


class InstanceLock:
    def __init__(self, handle: int):
        self._handle = handle

    def release(self) -> None:
        if self._handle:
            ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(self._handle))
            self._handle = 0


def acquire(name: str = "Local\\SilentWatch.SingleInstance") -> InstanceLock | None:
    """Return a lock if we are the only instance, otherwise None."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    handle = k32.CreateMutexW(None, False, name)
    if not handle:
        return None
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        k32.CloseHandle(ctypes.c_void_p(handle))
        return None
    return InstanceLock(handle)

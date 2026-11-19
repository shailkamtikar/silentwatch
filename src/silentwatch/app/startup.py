"""Optional 'start with Windows' using the per-user Startup folder (no admin, easy to remove)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

LAUNCHER = "SilentWatch.cmd"


def startup_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _command() -> str:
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    pyw = exe.with_name("pythonw.exe")           # no console window
    return f'"{pyw if pyw.exists() else exe}" -m silentwatch'


def is_enabled(directory: Path | None = None) -> bool:
    return ((directory or startup_dir()) / LAUNCHER).exists()


def enable(directory: Path | None = None, command: str | None = None) -> Path:
    d = directory or startup_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / LAUNCHER
    p.write_text(f'@echo off\r\nstart "" /min {command or _command()}\r\n', encoding="ascii")
    return p


def disable(directory: Path | None = None) -> bool:
    p = (directory or startup_dir()) / LAUNCHER
    if p.exists():
        p.unlink()
        return True
    return False

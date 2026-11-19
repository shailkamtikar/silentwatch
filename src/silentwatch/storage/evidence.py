"""Opt-in evidence snapshots: encrypted at rest (Windows DPAPI), auto-expiring, size-capped.

Snapshots are labelled for what they are ("last frame before obstruction"), never "intruder": the person who
covers the lens may never have been in view (Book section 5.6).
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

import cv2
import numpy as np

log = logging.getLogger(__name__)

SUFFIX = ".swe"


class EvidenceError(Exception):
    pass


class Protector(Protocol):
    def protect(self, data: bytes) -> bytes: ...

    def unprotect(self, data: bytes) -> bytes: ...


class DpapiProtector:
    """Windows Data Protection API: only the same Windows user account on this machine can decrypt."""

    def protect(self, data: bytes) -> bytes:
        import win32crypt

        return win32crypt.CryptProtectData(data, "SILENTWATCH evidence", None, None, None, 0)

    def unprotect(self, data: bytes) -> bytes:
        import win32crypt

        try:
            return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
        except Exception as exc:  # noqa: BLE001 - wrong user, corrupted or tampered file
            raise EvidenceError(f"cannot decrypt snapshot: {exc}") from exc


class EvidenceStore:
    def __init__(
        self,
        directory: Path | str,
        retention_days: int = 7,
        max_bytes: int = 50 * 1024 * 1024,
        protector: Protector | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.dir = Path(directory)
        self.retention_days = retention_days
        self.max_bytes = max_bytes
        self.protector = protector or DpapiProtector()
        self._clock = clock

    def save(self, image: np.ndarray, label: str) -> Path:
        ok, buf = cv2.imencode(".png", image)
        if not ok:
            raise EvidenceError("could not encode snapshot")
        blob = self.protector.protect(buf.tobytes())
        self.dir.mkdir(parents=True, exist_ok=True)          # created lazily: never exists unless snapshots are used
        stamp = datetime.fromtimestamp(self._clock(), timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        name = f"{stamp}_{re.sub(r'[^a-z0-9_]', '', label.lower())}{SUFFIX}"
        path = self.dir / name
        path.write_bytes(blob)
        self.purge()
        return path

    def load(self, path: Path | str) -> np.ndarray:
        try:
            raw = self.protector.unprotect(Path(path).read_bytes())
        except OSError as exc:
            raise EvidenceError(f"cannot read snapshot: {exc}") from exc
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise EvidenceError("snapshot is corrupted")
        return img

    def files(self) -> list[Path]:
        return sorted(self.dir.glob(f"*{SUFFIX}")) if self.dir.exists() else []

    def purge(self) -> int:
        """Delete snapshots older than the retention period, then oldest-first until under the size cap."""
        removed = 0
        now = self._clock()
        cutoff = now - self.retention_days * 86400
        files = self.files()
        for f in list(files):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    files.remove(f)
                    removed += 1
            except OSError:
                pass
        files.sort(key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        while len(files) > 1 and total > self.max_bytes:   # the newest snapshot is always kept
            f = files.pop(0)
            try:
                total -= f.stat().st_size
                f.unlink()
                removed += 1
            except OSError:
                pass
        return removed

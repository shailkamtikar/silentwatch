"""Retention and 'delete everything' helpers."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from silentwatch.config import app_data_dir

log = logging.getLogger(__name__)


def delete_all_local_data(root: Path | None = None) -> list[str]:
    """Remove the whole SilentWatch data directory (db, settings, evidence). Returns removed names."""
    base = root or app_data_dir()
    removed: list[str] = []
    if not base.exists():
        return removed
    for child in list(base.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed.append(child.name)
        except OSError as exc:
            log.error("Could not delete %s: %r", child, exc)
    return removed

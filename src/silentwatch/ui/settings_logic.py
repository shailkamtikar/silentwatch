"""Qt-free logic for settings, first-run consent and data deletion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from silentwatch.config import Config, app_data_dir, user_settings_path
from silentwatch.config.loader import update_settings
from silentwatch.storage.retention import delete_all_local_data

CONSENT_TEXT = (
    "SILENTWATCH uses your laptop's camera to detect whether the lens is covered and whether someone is in "
    "front of the laptop, and locks Windows when your rules say so.\n\n"
    "- Everything is processed on this laptop. Nothing is uploaded.\n"
    "- Camera frames are analysed in memory and not saved. Snapshots are off unless you turn them on.\n"
    "- It never uses the microphone and never sees or stores your Windows sign-in details.\n"
    "- Presence detection is not identity verification and can be fooled (for example by a photo). It is a "
    "convenience layer on top of your Windows sign-in, not a replacement for it.\n"
    "- It cannot protect a laptop from someone who can stop the app or reach your files directly.\n\n"
    "The camera indicator light will be on whenever monitoring is active. You can pause at any time from the "
    "tray icon."
)


@dataclass(frozen=True)
class Field:
    section: str
    key: str
    label: str
    kind: str                    # "choice" | "bool" | "int" | "float"
    choices: tuple[str, ...] = ()
    live: bool = False           # applies without restart


FIELDS: tuple[Field, ...] = (
    Field("policy", "mode", "Mode", "choice", ("balanced", "strict"), live=True),
    Field("policy", "dry_run", "Dry-run (decide but do not really lock)", "bool"),
    Field("presence", "pending_s", "Seconds without a face before 'absent pending'", "float"),
    Field("presence", "lock_after_s", "Seconds of absence before locking", "float"),
    Field("obstruction", "confirm_debounce_s", "Seconds a cover must persist before locking", "float"),
    Field("privacy", "retention_days", "Keep the event log for (days)", "int"),
    Field("privacy", "snapshots", "Save evidence snapshots (off by default)", "bool"),
    Field("hand", "enabled", "Hand-approach early warning", "bool"),
)


def apply_form(values: dict[str, object], path: Path | None = None) -> tuple[Config, dict[str, str]]:
    """values keyed "section.key". Returns (new config, inline errors keyed the same way)."""
    changes: dict[str, dict[str, object]] = {}
    for k, v in values.items():
        section, key = k.split(".", 1)
        changes.setdefault(section, {})[key] = v
    return update_settings(changes, path)


def startup_gate(cfg: Config, ask_consent: Callable[[], bool], path: Path | None = None) -> bool:
    """True if monitoring may start. Without consent the camera is never opened."""
    if cfg.privacy.consent_given:
        return True
    if not ask_consent():
        return False
    _, errors = update_settings({"privacy": {"consent_given": True}}, path)
    return not errors


def erase_everything(close_database: Callable[[], None], root: Path | None = None) -> list[str]:
    """Close the DB then delete the whole data directory (db, settings, evidence). Returns removed names."""
    close_database()
    return delete_all_local_data(root or app_data_dir())


def settings_file() -> Path:
    return user_settings_path()

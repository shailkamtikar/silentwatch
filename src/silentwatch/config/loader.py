"""Load defaults (TOML) merged with validated user overrides (JSON)."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import tomllib
from pathlib import Path
from typing import Any

from silentwatch.config.models import SECTIONS, Config

log = logging.getLogger(__name__)

DEFAULT_TOML = Path(__file__).with_name("default.toml")


def app_data_dir() -> Path:
    """Per-user data directory. SILENTWATCH_HOME overrides it (used by tests)."""
    override = os.environ.get("SILENTWATCH_HOME")
    if override:
        return Path(override)
    return Path(os.environ.get("APPDATA", Path.home())) / "SilentWatch"


def user_settings_path() -> Path:
    return app_data_dir() / "settings.json"


def _type_ok(default: Any, value: Any) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def _load_defaults() -> dict[str, dict[str, Any]]:
    with DEFAULT_TOML.open("rb") as fh:
        return tomllib.load(fh)


def _read_overrides(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings root must be an object")
        return data
    except (OSError, ValueError) as exc:
        log.error("Ignoring unreadable settings file %s: %r", path, exc)
        return {}


def load_config(user_path: Path | None = None) -> Config:
    """Defaults from TOML; each valid user override applied individually, invalid ones skipped."""
    defaults = _load_defaults()
    overrides = _read_overrides(user_path if user_path is not None else user_settings_path())
    sections: dict[str, Any] = {}
    for name, cls in SECTIONS.items():
        values = dict(defaults[name])
        obj = cls(**values)
        user_section = overrides.get(name)
        if isinstance(user_section, dict):
            for key, val in user_section.items():
                if key not in values:
                    log.warning("Unknown setting %s.%s ignored", name, key)
                    continue
                if not _type_ok(values[key], val):
                    log.error("Setting %s.%s has wrong type, using default", name, key)
                    continue
                try:
                    candidate = dataclasses.replace(obj, **{key: val})
                except ValueError as exc:
                    log.error("Setting %s.%s rejected: %s", name, key, exc)
                    continue
                obj = candidate
                values[key] = val
        elif user_section is not None:
            log.error("Settings section %s must be an object, ignored", name)
        sections[name] = obj
    return Config(**sections)


def default_config() -> Config:
    """Pure defaults, ignoring any user settings file."""
    defaults = _load_defaults()
    return Config(**{n: c(**defaults[n]) for n, c in SECTIONS.items()})


def save_overrides(overrides: dict[str, dict[str, Any]], path: Path | None = None) -> Path:
    """Persist user overrides (validated first by loading them back)."""
    target = path or user_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
    os.replace(tmp, target)
    return target

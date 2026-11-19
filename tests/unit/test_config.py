import dataclasses
import json
import logging

import pytest

from silentwatch.config import default_config, load_config, save_overrides


def _write(tmp_path, data):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    return p


def test_defaults(tmp_path):
    cfg = load_config(tmp_path / "missing.json")
    assert cfg.policy.mode == "balanced"
    assert cfg.privacy.snapshots is False
    assert cfg.camera.width == 640 and cfg.camera.analysis_fps == 5.0
    assert cfg.presence.pending_s == 3.0 and cfg.presence.lock_after_s == 10.0
    assert cfg.policy.dry_run is True


def test_override_applied(tmp_path):
    cfg = load_config(_write(tmp_path, {"presence": {"lock_after_s": 20}}))
    assert cfg.presence.lock_after_s == 20
    assert cfg.presence.pending_s == 3.0


def test_out_of_range_rejected(tmp_path, caplog):
    with caplog.at_level(logging.ERROR):
        cfg = load_config(_write(tmp_path, {"presence": {"lock_after_s": -5}}))
    assert cfg.presence.lock_after_s == 10.0
    assert "rejected" in caplog.text


def test_wrong_type(tmp_path):
    cfg = load_config(_write(tmp_path, {"camera": {"analysis_fps": "fast"}}))
    assert cfg.camera.analysis_fps == 5.0


def test_unknown_key_ignored(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        cfg = load_config(_write(tmp_path, {"camera": {"nonsense": 1}}))
    assert cfg == default_config()
    assert "Unknown" in caplog.text


def test_corrupt_json_falls_back(tmp_path):
    cfg = load_config(_write(tmp_path, "{bad"))
    assert cfg == default_config()


def test_missing_settings_dir(tmp_path):
    assert load_config(tmp_path / "nope" / "settings.json") == default_config()


def test_immutable():
    cfg = default_config()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.policy.mode = "strict"  # type: ignore[misc]


def test_debounce_safety_floor(tmp_path):
    cfg = load_config(_write(tmp_path, {"obstruction": {"confirm_debounce_s": 0}}))
    assert cfg.obstruction.confirm_debounce_s == 1.0


def test_bool_is_not_int(tmp_path):
    cfg = load_config(_write(tmp_path, {"camera": {"width": True}}))
    assert cfg.camera.width == 640


def test_invalid_mode(tmp_path):
    cfg = load_config(_write(tmp_path, {"policy": {"mode": "yolo"}}))
    assert cfg.policy.mode == "balanced"


def test_section_must_be_object(tmp_path):
    cfg = load_config(_write(tmp_path, {"policy": 5}))
    assert cfg == default_config()


def test_save_roundtrip(tmp_path):
    p = save_overrides({"policy": {"mode": "strict"}}, tmp_path / "s" / "settings.json")
    assert load_config(p).policy.mode == "strict"

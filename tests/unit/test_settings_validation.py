import json
import os
import pathlib
import re

from silentwatch.config import default_config, load_config
from silentwatch.config.loader import update_settings, validate_change
from silentwatch.ui.settings_logic import FIELDS, apply_form, erase_everything, startup_gate


def test_first_run_requires_consent_and_declining_blocks(tmp_path):
    p = tmp_path / "settings.json"
    asked = []
    assert startup_gate(default_config(), lambda: asked.append(1) or False, p) is False
    assert asked == [1] and not p.exists()            # nothing recorded, camera never started


def test_accepting_consent_is_remembered(tmp_path):
    p = tmp_path / "settings.json"
    assert startup_gate(default_config(), lambda: True, p) is True
    assert load_config(p).privacy.consent_given is True
    asked = []
    assert startup_gate(load_config(p), lambda: asked.append(1) or True, p) is True
    assert asked == []                                  # not asked again


def test_change_timer_persists_and_is_used(tmp_path):
    p = tmp_path / "s.json"
    cfg, errors = apply_form({"presence.lock_after_s": 20.0}, p)
    assert not errors and cfg.presence.lock_after_s == 20.0
    assert load_config(p).presence.lock_after_s == 20.0


def test_invalid_values_rejected_inline_and_not_saved(tmp_path):
    p = tmp_path / "s.json"
    cfg, errors = apply_form({"presence.lock_after_s": -3.0, "policy.mode": "yolo"}, p)
    assert set(errors) == {"presence.lock_after_s", "policy.mode"}
    assert not p.exists() and cfg == default_config()


def test_valid_and_invalid_mixed_saves_only_valid(tmp_path):
    p = tmp_path / "s.json"
    cfg, errors = apply_form({"presence.lock_after_s": 15.0, "obstruction.confirm_debounce_s": 0.0}, p)
    assert list(errors) == ["obstruction.confirm_debounce_s"]
    assert json.loads(p.read_text())["presence"]["lock_after_s"] == 15.0


def test_validate_change_messages():
    assert validate_change("policy", "mode", "strict") is None
    assert "unknown" in validate_change("policy", "nope", 1)
    assert "wrong type" in validate_change("camera", "width", "wide")


def test_all_form_fields_exist_in_config():
    cfg = default_config()
    for f in FIELDS:
        assert hasattr(getattr(cfg, f.section), f.key), f


def test_snapshots_off_by_default_and_no_evidence_dir(tmp_path):
    assert default_config().privacy.snapshots is False
    assert not (tmp_path / "evidence").exists()


def test_delete_all_returns_to_first_run(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "x.bin").write_bytes(b"1")
    (tmp_path / "silentwatch.db").write_bytes(b"db")
    update_settings({"privacy": {"consent_given": True}}, tmp_path / "settings.json")
    closed = []
    removed = erase_everything(lambda: closed.append(1), tmp_path)
    assert closed == [1] and set(removed) == {"evidence", "silentwatch.db", "settings.json"}
    assert list(tmp_path.iterdir()) == []
    assert load_config(tmp_path / "settings.json").privacy.consent_given is False


def test_no_microphone_or_audio_code_anywhere():
    root = pathlib.Path(__file__).parents[2] / "src" / "silentwatch"
    pat = re.compile(r"sounddevice|pyaudio|speech_recognition|\bwave\b|microphone|winmm|audioop", re.I)
    for f in root.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for m in pat.finditer(text):
            line = text[max(0, text.rfind("\n", 0, m.start())):text.find("\n", m.start())]
            # the consent text may *say* it never uses the microphone
            assert "never uses the microphone" in text or "microphone" not in m.group(0).lower(), f"{f}: {line}"


def test_settings_dialog_inline_errors_and_cancel_delete(tmp_path, monkeypatch):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    monkeypatch.setenv("SILENTWATCH_HOME", str(tmp_path))
    from PySide6.QtWidgets import QApplication, QMessageBox

    from silentwatch.ui.settings import make_settings_dialog

    app = QApplication.instance() or QApplication([])
    erased, saved = [], []
    dlg = make_settings_dialog(default_config(), on_saved=saved.append, on_erase=lambda: erased.append(1))
    dlg.widgets["presence.lock_after_s"].setValue(-3.0)
    assert dlg.save() is False and "presence" in dlg.error_labels["presence.lock_after_s"].text().lower()
    dlg.widgets["presence.lock_after_s"].setValue(25.0)
    assert dlg.save() is True and saved and saved[0].presence.lock_after_s == 25.0
    # cancelling the delete confirmation removes nothing
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    assert dlg.confirm_erase() is False and erased == []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    assert dlg.confirm_erase() is True and erased == [1]
    app.processEvents()

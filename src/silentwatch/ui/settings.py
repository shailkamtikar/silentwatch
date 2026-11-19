"""Qt dialogs: first-run consent and the settings page (with delete-all and test-lock)."""

from __future__ import annotations

from typing import Callable

from silentwatch.config import Config, load_config
from silentwatch.ui.settings_logic import CONSENT_TEXT, FIELDS, apply_form


def ask_consent_qt() -> bool:
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox()
    box.setWindowTitle("SILENTWATCH - camera use")
    box.setIcon(QMessageBox.Icon.Information)
    box.setText("Before SILENTWATCH starts")
    box.setInformativeText(CONSENT_TEXT)
    accept = box.addButton("I understand, start monitoring", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Decline", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is accept


def make_settings_dialog(
    cfg: Config,
    on_saved: Callable[[Config], None] | None = None,
    on_erase: Callable[[], None] | None = None,
    on_test_lock: Callable[[], None] | None = None,
):
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
        QPushButton, QSpinBox, QVBoxLayout,
    )

    class SettingsDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("SILENTWATCH settings")
            self.cfg = cfg
            self.widgets: dict[str, object] = {}
            self.error_labels: dict[str, QLabel] = {}
            form = QFormLayout()
            for f in FIELDS:
                key = f"{f.section}.{f.key}"
                current = getattr(getattr(cfg, f.section), f.key)
                if f.kind == "choice":
                    w = QComboBox()
                    w.addItems(list(f.choices))
                    w.setCurrentText(str(current))
                elif f.kind == "bool":
                    w = QCheckBox()
                    w.setChecked(bool(current))
                elif f.kind == "int":
                    w = QSpinBox()
                    w.setRange(-100000, 100000)      # range limits come from validation, so bad input is reported inline
                    w.setValue(int(current))
                else:
                    w = QDoubleSpinBox()
                    w.setRange(-100000.0, 100000.0)
                    w.setDecimals(1)
                    w.setValue(float(current))
                err = QLabel("")
                err.setStyleSheet("color: #c02020;")
                self.widgets[key] = w
                self.error_labels[key] = err
                col = QVBoxLayout()
                col.addWidget(w)
                col.addWidget(err)
                suffix = "" if f.live else "  (applies after restart)"
                form.addRow(f.label + suffix, col)

            self.btn_save = QPushButton("Save")
            self.btn_save.clicked.connect(self.save)
            self.btn_erase = QPushButton("Delete all local data...")
            self.btn_erase.clicked.connect(self.confirm_erase)
            self.btn_lock = QPushButton("Test lock now...")
            self.btn_lock.clicked.connect(self.confirm_test_lock)
            row = QHBoxLayout()
            for b in (self.btn_save, self.btn_lock, self.btn_erase):
                row.addWidget(b)
            lay = QVBoxLayout(self)
            lay.addLayout(form)
            lay.addLayout(row)

        def values(self) -> dict[str, object]:
            out: dict[str, object] = {}
            for key, w in self.widgets.items():
                if isinstance(w, QComboBox):
                    out[key] = w.currentText()
                elif isinstance(w, QCheckBox):
                    out[key] = w.isChecked()
                else:
                    out[key] = w.value()
            return out

        def save(self) -> bool:
            new_cfg, errors = apply_form(self.values())
            for key, lbl in self.error_labels.items():
                lbl.setText(errors.get(key, ""))
            if errors:
                return False
            self.cfg = new_cfg
            if on_saved:
                on_saved(new_cfg)
            return True

        def confirm_erase(self) -> bool:
            r = QMessageBox.question(
                self, "Delete all local data",
                "This permanently deletes the event log, calibration, settings and any snapshots stored by "
                "SILENTWATCH on this laptop. It cannot be undone, and SILENTWATCH will close.\n\nDelete everything?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return False
            if on_erase:
                on_erase()
            return True

        def confirm_test_lock(self) -> bool:
            r = QMessageBox.question(
                self, "Test lock",
                "This will really lock Windows in a moment. Save your work first. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return False
            if on_test_lock:
                on_test_lock()
            return True

    return SettingsDialog()

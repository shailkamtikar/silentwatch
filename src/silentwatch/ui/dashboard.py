"""Dashboard: what the system sees right now, and why it acted. Preview is OFF by default."""

from __future__ import annotations

import numpy as np

from silentwatch.app.lifecycle import ServiceStatus, SilentWatchService
from silentwatch.app.tray import IconKind, icon_kind, tooltip
from silentwatch.policy import State
from silentwatch.storage import EventType
from silentwatch.ui.history import HistoryModel, make_table_model, why_text

_BANNER_COLORS = {
    IconKind.MONITORING: "#2e9e4f", IconKind.WARNING: "#e0b020", IconKind.ALERT: "#d03030",
    IconKind.PAUSED: "#8a8a8a", IconKind.CAMERA_ERROR: "#e07a20", IconKind.LOCKED: "#2a4b8d", IconKind.ERROR: "#8a2be2",
}


def structure_loss_percent(scores: dict | None) -> int:
    """0 = scene looks like the baseline, 100 = all structure lost (what an obstruction looks like)."""
    if not scores:
        return 0
    ratio = min(scores.get("contrast_ratio", 1.0), scores.get("edge_ratio", 1.0), 1.0)
    return int(round(100 * (1.0 - max(0.0, ratio))))


def numpy_to_qimage(bgr: np.ndarray):
    from PySide6.QtGui import QImage

    h, w = bgr.shape[:2]
    return QImage(bgr.data, w, h, 3 * w, QImage.Format.Format_BGR888).copy()


def make_dashboard(service: SilentWatchService):
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSplitter, QTableView,
        QTextEdit, QVBoxLayout, QWidget,
    )

    class Dashboard(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("SILENTWATCH dashboard")
            self.resize(900, 640)
            self.service = service
            self.history = HistoryModel(service.store)
            self.table_model = make_table_model(self.history)

            self.banner = QLabel("...")
            self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.banner.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px; color: white;")
            self.lbl_obstruction = QLabel()
            self.lbl_presence = QLabel()
            self.lbl_countdown = QLabel()
            self.lbl_hand = QLabel()
            self.lbl_phone = QLabel()
            self.bar = QProgressBar()
            self.bar.setRange(0, 100)
            self.bar.setFormat("Scene structure lost: %p%")
            self.chk_preview = QCheckBox("Show live camera preview (off by default; nothing is saved)")
            self.chk_preview.toggled.connect(self._toggle_preview)
            self.preview = QLabel("Preview off")
            self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview.setMinimumHeight(200)

            self.cmb_filter = QComboBox()
            self.cmb_filter.addItem("All events", None)
            for t in (EventType.LOCK_REQUESTED, EventType.OBSTRUCTION_CONFIRMED, EventType.OWNER_ABSENT_CONFIRMED,
                      EventType.CAMERA_UNAVAILABLE, EventType.STATE_CHANGED, EventType.ERROR):
                self.cmb_filter.addItem(t.value, t)
            self.cmb_filter.currentIndexChanged.connect(self._filter_changed)
            self.btn_refresh = QPushButton("Refresh")
            self.btn_refresh.clicked.connect(self.reload_history)
            self.lbl_empty = QLabel("No events yet. Events appear here as SILENTWATCH monitors.")
            self.table = QTableView()
            self.table.setModel(self.table_model)
            self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
            self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
            self.table.horizontalHeader().setStretchLastSection(True)
            self.table.clicked.connect(self._show_why)
            self.why = QTextEdit()
            self.why.setReadOnly(True)
            self.why.setPlaceholderText("Select an event to see why it happened.")

            top = QVBoxLayout()
            top.addWidget(self.banner)
            for w in (self.lbl_obstruction, self.lbl_presence, self.lbl_countdown, self.lbl_hand, self.lbl_phone, self.bar, self.chk_preview, self.preview):
                top.addWidget(w)
            row = QHBoxLayout()
            row.addWidget(self.cmb_filter)
            row.addWidget(self.btn_refresh)
            bottom = QVBoxLayout()
            bottom.addLayout(row)
            bottom.addWidget(self.lbl_empty)
            bottom.addWidget(self.table)
            bottom.addWidget(self.why)
            top_w, bottom_w = QWidget(), QWidget()
            top_w.setLayout(top)
            bottom_w.setLayout(bottom)
            split = QSplitter(Qt.Orientation.Vertical)
            split.addWidget(top_w)
            split.addWidget(bottom_w)
            lay = QVBoxLayout(self)
            lay.addWidget(split)

            self.status_timer = QTimer(self)
            self.status_timer.timeout.connect(self.refresh_status)
            self.preview_timer = QTimer(self)
            self.preview_timer.timeout.connect(self._draw_preview)

        # -- updates --------------------------------------------------------------------
        def refresh_status(self) -> ServiceStatus:
            s = self.service.status()
            kind = icon_kind(s)
            self.banner.setText(tooltip(s).replace("SILENTWATCH: ", ""))
            self.banner.setStyleSheet(f"font-size: 18px; font-weight: bold; padding: 8px; color: white; background: {_BANNER_COLORS[kind]};")
            self.lbl_obstruction.setText(f"Camera view: {s.obstruction.value.replace('_', ' ').title()}")
            self.lbl_presence.setText(f"Presence: {s.presence.replace('_', ' ').title()}   (camera {s.camera.lower()})")
            self.lbl_countdown.setText(
                f"Locking in {s.lock_in_s:.0f}s unless someone returns" if s.lock_in_s is not None else "No lock pending"
            )
            self.lbl_hand.setText(f"Hand near camera: {s.hand_score * 100:.0f}% (early warning only)")
            self.lbl_phone.setText(f"Phone: {s.phone.title()} (supporting signal only)")
            self.bar.setValue(structure_loss_percent(s.scores))
            return s

        def reload_history(self) -> None:
            self.table_model.reload()
            self.lbl_empty.setVisible(self.history.is_empty)
            self.table.setVisible(not self.history.is_empty)

        def _filter_changed(self) -> None:
            self.history.event_type = self.cmb_filter.currentData()
            self.history.page = 0
            self.reload_history()

        def _show_why(self, index) -> None:
            if 0 <= index.row() < len(self.history.rows):
                self.why.setPlainText(why_text(self.history.rows[index.row()]))

        def _toggle_preview(self, on: bool) -> None:
            self.service.set_preview(on)
            if on and self.isVisible():
                self.preview_timer.start(100)       # <= 10 Hz
            else:
                self.preview_timer.stop()
                self.preview.setPixmap(QPixmap())
                self.preview.setText("Preview off")

        def _draw_preview(self) -> None:
            img = self.service.latest_preview()
            if img is None:
                return
            pm = QPixmap.fromImage(numpy_to_qimage(img)).scaledToWidth(480)
            self.preview.setPixmap(pm)

        # -- window lifecycle: nothing runs while the dashboard is closed --------------------
        def showEvent(self, e) -> None:
            super().showEvent(e)
            self.refresh_status()
            self.reload_history()
            self.status_timer.start(500)
            if self.chk_preview.isChecked():
                self.service.set_preview(True)
                self.preview_timer.start(100)

        def hideEvent(self, e) -> None:
            super().hideEvent(e)
            self.status_timer.stop()
            self.preview_timer.stop()
            self.service.set_preview(False)

    return Dashboard()

"""System tray application: always-visible monitoring indicator and controls (Book section 14)."""

from __future__ import annotations

import enum
from typing import Callable

from silentwatch.app.lifecycle import ServiceStatus, SilentWatchService
from silentwatch.policy import State


class IconKind(str, enum.Enum):
    MONITORING = "monitoring"      # green
    WARNING = "warning"            # yellow: pending absence / suspicious
    ALERT = "alert"                # red: tampering or lock requested
    PAUSED = "paused"              # grey
    CAMERA_ERROR = "camera_error"  # orange
    LOCKED = "locked"              # dark blue
    ERROR = "error"                # purple: worker crashed


_COLORS = {
    IconKind.MONITORING: "#2e9e4f",
    IconKind.WARNING: "#e0b020",
    IconKind.ALERT: "#d03030",
    IconKind.PAUSED: "#8a8a8a",
    IconKind.CAMERA_ERROR: "#e07a20",
    IconKind.LOCKED: "#2a4b8d",
    IconKind.ERROR: "#8a2be2",
}


def icon_kind(s: ServiceStatus) -> IconKind:
    """Pure mapping from service status to the icon, so it can be tested without a display."""
    if s.crashed:
        return IconKind.ERROR
    if s.paused or s.state == State.DISABLED:
        return IconKind.PAUSED
    if s.state == State.LOCKED:
        return IconKind.LOCKED
    if s.state in (State.TAMPERING_CONFIRMED, State.LOCK_REQUESTED):
        return IconKind.ALERT
    if s.state == State.CAMERA_ERROR:
        return IconKind.CAMERA_ERROR
    if s.state in (State.SUSPICIOUS, State.OWNER_ABSENT_PENDING, State.OWNER_ABSENT):
        return IconKind.WARNING
    return IconKind.MONITORING


def tooltip(s: ServiceStatus) -> str:
    if s.crashed:
        return "SILENTWATCH: monitor stopped unexpectedly (see event log)"
    if s.paused:
        return "SILENTWATCH: paused - camera off"
    base = f"SILENTWATCH: {s.state.value.replace('_', ' ').title()} - camera on"
    if s.lock_in_s is not None:
        base += f" - locking in {s.lock_in_s:.0f}s"
    return base


def make_icon(kind: IconKind):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(_COLORS[kind]))
    p.setPen(QColor("#202020"))
    p.drawEllipse(3, 3, 26, 26)
    p.end()
    return QIcon(pm)


class TrayApp:
    def __init__(
        self,
        service: SilentWatchService,
        open_dashboard: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        open_settings: Callable[[], None] | None = None,
    ):
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QAction, QActionGroup
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon

        self.service = service
        self._open_dashboard = open_dashboard
        self._on_quit = on_quit
        self.tray = QSystemTrayIcon()
        self.menu = QMenu()

        self.act_dashboard = QAction("Open dashboard")
        self.act_dashboard.triggered.connect(lambda: self._open_dashboard and self._open_dashboard())
        self.act_pause = QAction("Pause monitoring")
        self.act_pause.triggered.connect(self.toggle_pause)
        self.act_calibrate = QAction("Recalibrate camera")
        self.act_calibrate.triggered.connect(self.service.request_calibration)
        self.act_settings = QAction("Settings...")
        self.act_settings.triggered.connect(lambda: open_settings and open_settings())

        mode_menu = self.menu.addMenu("Mode")
        group = QActionGroup(mode_menu)
        self.mode_actions = {}
        for name in ("balanced", "strict"):
            a = QAction(name.capitalize(), mode_menu, checkable=True)
            a.setChecked(self.service.core.mode == name)
            a.triggered.connect(lambda _=False, n=name: self.service.set_mode(n))
            group.addAction(a)
            mode_menu.addAction(a)
            self.mode_actions[name] = a

        self.act_quit = QAction("Quit SILENTWATCH")
        self.act_quit.triggered.connect(self.quit)
        for a in (self.act_dashboard, self.act_pause, self.act_calibrate, self.act_settings):
            self.menu.insertAction(mode_menu.menuAction(), a)
        self.menu.addSeparator()
        self.menu.addAction(self.act_quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda reason: self._open_dashboard and reason == QSystemTrayIcon.ActivationReason.DoubleClick and self._open_dashboard())

        self._icons = {k: make_icon(k) for k in IconKind}
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.last_kind: IconKind | None = None

    def show(self) -> None:
        self.refresh()
        self.tray.show()
        self.timer.start(500)

    def refresh(self) -> IconKind:
        s = self.service.status()
        kind = icon_kind(s)
        if kind != self.last_kind:
            self.tray.setIcon(self._icons[kind])
            self.last_kind = kind
        self.tray.setToolTip(tooltip(s))
        self.act_pause.setText("Resume monitoring" if s.paused else "Pause monitoring")
        return kind

    def toggle_pause(self) -> None:
        if self.service.status().paused:
            self.service.resume()
        else:
            self.service.pause()
        self.refresh()

    def quit(self) -> None:
        self.timer.stop()
        self.tray.hide()
        if self._on_quit:
            self._on_quit()

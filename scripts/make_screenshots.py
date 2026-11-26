"""Render the README screenshots from the real UI code driven by SYNTHETIC scenes (no camera, no personal images).

    python scripts/make_screenshots.py

Writes PNGs to docs/images/. The scenes are generated test patterns, never frames from a real room.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
os.environ["SILENTWATCH_HOME"] = tempfile.mkdtemp(prefix="swshots")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from silentwatch.app.lifecycle import SilentWatchService  # noqa: E402
from silentwatch.app.tray import IconKind, make_icon  # noqa: E402
from silentwatch.camera.calibration import CalibrationStore, baseline_from_images  # noqa: E402
from silentwatch.camera.integrity import FeatureExtractor  # noqa: E402
from silentwatch.camera.obstruction import ObstructionClassifier, ObstructionState  # noqa: E402
from silentwatch.camera.sources import CallableFrameSource  # noqa: E402
from silentwatch.config import app_data_dir, default_config  # noqa: E402
from silentwatch.storage import Database  # noqa: E402
from silentwatch.testing import synthetic as syn  # noqa: E402
from silentwatch.ui.dashboard import make_dashboard, structure_loss_percent  # noqa: E402
from silentwatch.ui.settings import make_settings_dialog  # noqa: E402
from silentwatch.ui.settings_logic import CONSENT_TEXT  # noqa: E402
from silentwatch.windows.lock import WindowsLockService  # noqa: E402

OUT = Path(__file__).parents[1] / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 640, 480


def normal(i: int) -> np.ndarray:
    return syn.scene(seed=i % 3, h=H, w=W)


def finger(i: int) -> np.ndarray:
    rng = np.random.default_rng(i)
    return np.clip(np.full((H, W, 3), (45, 90, 190), np.float32) + rng.normal(0, 1.0, (H, W, 3)), 0, 255).astype(np.uint8)


class World:
    def __init__(self):
        self.scene, self.n = "normal", 0

    def frame(self):
        self.n += 1
        return finger(self.n) if self.scene == "finger" else normal(self.n)

    def detect(self, bgr):
        return [0.9]


def pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.03)


def dashboards(app) -> None:
    world = World()
    cfg = default_config()
    cfg = dataclasses.replace(
        cfg,
        camera=dataclasses.replace(cfg.camera, analysis_fps=8.0, warmup_frames=0, frozen_seconds=600),
        obstruction=dataclasses.replace(cfg.obstruction, confirm_debounce_s=1.0, clear_frames=3, calibration_seconds=1.0),
        policy=dataclasses.replace(cfg.policy, dry_run=True, lock_cooldown_s=1.0, post_unlock_grace_s=1.0),
    )
    db = Database(app_data_dir() / "shots.db")
    CalibrationStore(db).save(baseline_from_images([normal(i) for i in range(30)], "camera0", f"{W}x{H}"))
    svc = SilentWatchService(cfg, db, lambda: CallableFrameSource(world.frame, fps=12), world, WindowsLockService(None, dry_run=True))
    svc.lock_service.store = svc.store
    svc.start()
    dash = make_dashboard(svc)
    dash.resize(1000, 900)
    dash.show()
    dash.chk_preview.setChecked(True)
    pump(app, 3.5)
    dash.refresh_status()
    dash.grab().save(str(OUT / "dashboard-monitoring.png"))

    world.scene = "finger"
    t0 = time.time()
    while not svc.lock_actions and time.time() - t0 < 8:
        pump(app, 0.1)
    pump(app, 1.5)
    dash.refresh_status()
    dash.reload_history()
    for row, ev in enumerate(dash.history.rows):
        if ev.event_type.value == "LOCK_REQUESTED":
            dash.table.selectRow(row)
            dash._show_why(dash.table_model.index(row, 0))
            break
    pump(app, 0.3)
    dash.grab().save(str(OUT / "dashboard-lock-why.png"))
    dash.hide()
    svc.stop()
    db.close()


def tray_icons(app) -> None:
    items = [
        (IconKind.MONITORING, "Monitoring"), (IconKind.WARNING, "Absent / suspicious"), (IconKind.ALERT, "Tamper / lock"),
        (IconKind.PAUSED, "Paused (camera off)"), (IconKind.CAMERA_ERROR, "Camera problem"),
        (IconKind.LOCKED, "Windows locked"), (IconKind.ERROR, "Monitor crashed"),
    ]
    cell_w, cell_h = 190, 96
    pm = QPixmap(cell_w * len(items), cell_h)
    pm.fill(QColor("#1f2430"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor("#e8ecf4"))
    f = QFont()
    f.setPointSize(10)
    p.setFont(f)
    for i, (kind, label) in enumerate(items):
        x = i * cell_w
        p.drawPixmap(x + cell_w // 2 - 24, 10, make_icon(kind).pixmap(48, 48))
        p.drawText(x, 66, cell_w, 24, Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    pm.save(str(OUT / "tray-icons.png"))


def dialogs(app) -> None:
    box = QMessageBox()
    box.setWindowTitle("SILENTWATCH - camera use")
    box.setIcon(QMessageBox.Icon.Information)
    box.setText("Before SILENTWATCH starts")
    box.setInformativeText(CONSENT_TEXT)
    box.addButton("I understand, start monitoring", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Decline", QMessageBox.ButtonRole.RejectRole)
    box.show()
    pump(app, 0.4)
    box.grab().save(str(OUT / "consent.png"))
    box.close()

    dlg = make_settings_dialog(default_config())
    dlg.resize(560, dlg.sizeHint().height())
    dlg.show()
    pump(app, 0.3)
    dlg.grab().save(str(OUT / "settings.png"))
    dlg.close()


def before_after() -> None:
    """Left: normal scene. Right: lens covered. Numbers come from the real classifier on these exact frames."""
    base = baseline_from_images([normal(i) for i in range(30)], "demo", f"{W}x{H}")
    cfg = default_config().obstruction
    clf, ex = ObstructionClassifier(base, cfg), FeatureExtractor()
    dt, res_normal, res_cover, confirm_at = 0.2, None, None, None
    for k in range(15):
        res_normal = clf.update(ex.update(normal(k)), k * dt)
    t_cover = 15 * dt
    for k in range(15, 40):
        res_cover = clf.update(ex.update(finger(k)), k * dt)
        if confirm_at is None and res_cover.state == ObstructionState.CONFIRMED_OBSTRUCTION:
            confirm_at = k * dt - t_cover
    assert confirm_at is not None, "classifier did not confirm the synthetic cover"

    def panel(img, title, subtitle, color, lines):
        im = img.copy()
        cv2.rectangle(im, (0, 0), (W, 70), (30, 36, 48), -1)
        cv2.putText(im, title, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
        cv2.putText(im, subtitle, (16, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 225, 235), 1, cv2.LINE_AA)
        cv2.rectangle(im, (0, H - 40 * len(lines) - 14), (W, H), (30, 36, 48), -1)
        for i, text in enumerate(lines):
            cv2.putText(im, text, (16, H - 40 * len(lines) + 28 * i + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 238, 245), 1, cv2.LINE_AA)
        return im

    left = panel(normal(1), "NORMAL", "synthetic test scene", (110, 220, 130),
                 [f"scene structure lost: {structure_loss_percent(res_normal.scores)}%", "state: NORMAL  ->  no action"])
    right = panel(finger(1), "LENS COVERED", f"confirmed after {confirm_at:.1f} s (debounce)", (80, 90, 240),
                  [f"scene structure lost: {structure_loss_percent(res_cover.scores)}%", "state: CONFIRMED_OBSTRUCTION -> lock",
                   "no face was ever needed"])
    gap = np.full((H, 12, 3), (24, 28, 38), np.uint8)
    cv2.imwrite(str(OUT / "obstruction-before-after.png"), np.hstack([left, gap, right]))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    f = app.font()
    f.setFamily("Segoe UI")
    f.setPointSize(10)
    app.setFont(f)
    before_after()
    tray_icons(app)
    dialogs(app)
    dashboards(app)
    for p in sorted(OUT.glob("*.png")):
        print(f"{p.name}: {p.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

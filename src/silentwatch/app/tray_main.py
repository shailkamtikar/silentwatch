"""Launch the tray application (the normal way to run SILENTWATCH)."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys

from silentwatch import __version__


def run_tray(args: argparse.Namespace) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

    from silentwatch.app.lifecycle import SilentWatchService
    from silentwatch.app.tray import TrayApp
    from silentwatch.camera.sources import CvFrameSource
    from silentwatch.config import app_data_dir, load_config
    from silentwatch.presence.estimator import DEFAULT_FACE_MODEL, MediaPipeFaceBackend, ModelMissingError
    from silentwatch.storage import Database
    from silentwatch.windows import single_instance
    from silentwatch.windows.lock import WindowsLockService

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)

    guard = single_instance.acquire()
    if guard is None:
        QMessageBox.information(None, "SILENTWATCH", "SILENTWATCH is already running (see the system tray).")
        return 0

    cfg = load_config()
    from silentwatch.ui.settings import ask_consent_qt, make_settings_dialog
    from silentwatch.ui.settings_logic import erase_everything, startup_gate

    if not startup_gate(cfg, ask_consent_qt):
        guard.release()
        return 0          # declined: the camera is never opened
    cfg = load_config()
    policy = dataclasses.replace(cfg.policy, dry_run=not args.live, mode=args.mode or cfg.policy.mode)
    cfg = dataclasses.replace(cfg, policy=policy)
    logging.basicConfig(level=getattr(logging, cfg.logging.level), format="%(asctime)s %(levelname)s %(message)s")

    backend = None
    if cfg.presence.enabled and not args.no_presence:
        try:
            backend = MediaPipeFaceBackend(DEFAULT_FACE_MODEL, cfg.presence.min_confidence)
        except ModelMissingError as exc:
            logging.warning("presence disabled: %s", exc)

    hands = None
    if cfg.hand.enabled:
        try:
            from silentwatch.camera.hand_detector import HandModelMissingError, MediaPipeHandBackend

            hands = MediaPipeHandBackend()
        except HandModelMissingError as exc:
            logging.warning("hand detection disabled: %s", exc)

    db = Database(app_data_dir() / "silentwatch.db")
    c = cfg.camera
    svc = SilentWatchService(
        cfg, db, lambda: CvFrameSource(c.index, c.width, c.height, c.backend), backend,
        WindowsLockService(None, dry_run=policy.dry_run, cooldown_s=policy.lock_cooldown_s),
        hand_backend=hands,
    )
    svc.lock_service.store = svc.store
    if cfg.bluetooth.enabled:
        from silentwatch.bluetooth.enrollment import EnrollmentStore, make_source
        from silentwatch.bluetooth.proximity import BluetoothProximityService, ProximitySmoother

        enrolled = EnrollmentStore(db).load()
        if enrolled is None:
            logging.warning("bluetooth.enabled is true but no phone is enrolled (python -m silentwatch.tools.enroll_phone)")
        else:
            svc.proximity = BluetoothProximityService(
                make_source(enrolled), ProximitySmoother(cfg.bluetooth.missing_after_s), svc.on_phone_state, svc.store
            )

    dash: dict = {"w": None}

    def open_dashboard() -> None:
        from silentwatch.ui.dashboard import make_dashboard

        if dash["w"] is None:
            dash["w"] = make_dashboard(svc)
        dash["w"].show()
        dash["w"].raise_()
        dash["w"].activateWindow()

    def quit_app() -> None:
        if dash["w"] is not None:
            dash["w"].close()
        svc.stop()
        db.close()
        guard.release()
        app.quit()

    def open_settings() -> None:
        def erased() -> None:
            erase_everything(lambda: (svc.stop(), db.close()))
            guard.release()
            app.quit()

        def test_lock() -> None:
            WindowsLockService(svc.store, dry_run=False, cooldown_s=0).lock("manual test lock from settings")

        dlg = make_settings_dialog(load_config(), on_saved=lambda c: svc.set_mode(c.policy.mode), on_erase=erased, on_test_lock=test_lock)
        dash["settings"] = dlg
        dlg.show()

    from silentwatch.app import startup
    from silentwatch.windows.session_watcher import SessionWatcher

    watcher = SessionWatcher(svc.on_session_event)
    watcher.start()
    tray = TrayApp(
        svc, open_dashboard=open_dashboard, on_quit=lambda: (watcher.stop(), quit_app()), open_settings=open_settings,
        startup=(startup.is_enabled, lambda on: startup.enable() if on else startup.disable()),
    )
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.warning("no system tray available on this desktop")
    svc.start()
    tray.show()
    if args.seconds:
        QTimer.singleShot(int(args.seconds * 1000), tray.quit)
    print(f"SILENTWATCH {__version__} running in the tray | mode={policy.mode} | "
          f"{'LIVE (real lock)' if args.live else 'DRY-RUN (no real lock)'}", flush=True)
    return app.exec()

"""Command-line entry point."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
import time

from silentwatch import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="silentwatch", description="SILENTWATCH laptop protection")
    p.add_argument("--version", action="store_true", help="print version and exit")
    p.add_argument("--headless", action="store_true", help="run the monitoring service in the console (default: system tray app)")
    p.add_argument("--live", action="store_true", help="REALLY lock Windows (default is dry-run: decisions are logged only)")
    p.add_argument("--mode", choices=["strict", "balanced"], help="override policy mode")
    p.add_argument("--no-presence", action="store_true", help="disable face presence detection")
    p.add_argument("--seconds", type=float, default=0.0, help="stop after N seconds (0 = until Ctrl+C)")
    return p


def run_headless(args: argparse.Namespace) -> int:
    from silentwatch.app.lifecycle import SilentWatchService
    from silentwatch.camera.sources import CvFrameSource
    from silentwatch.config import app_data_dir, load_config
    from silentwatch.presence.estimator import DEFAULT_FACE_MODEL, MediaPipeFaceBackend, ModelMissingError
    from silentwatch.storage import Database
    from silentwatch.windows.lock import WindowsLockService

    cfg = load_config()
    policy = dataclasses.replace(cfg.policy, dry_run=not args.live, mode=args.mode or cfg.policy.mode)
    cfg = dataclasses.replace(cfg, policy=policy)
    logging.basicConfig(level=getattr(logging, cfg.logging.level), format="%(asctime)s %(levelname)s %(message)s")

    backend = None
    if cfg.presence.enabled and not args.no_presence:
        try:
            backend = MediaPipeFaceBackend(DEFAULT_FACE_MODEL, cfg.presence.min_confidence)
        except ModelMissingError as exc:
            print(f"presence disabled: {exc}", file=sys.stderr)

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
        cfg,
        db,
        lambda: CvFrameSource(c.index, c.width, c.height, c.backend),
        backend,
        WindowsLockService(None, dry_run=policy.dry_run, cooldown_s=policy.lock_cooldown_s),
        on_status_line=lambda s: print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True),
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
    print(f"SILENTWATCH {__version__} headless | mode={policy.mode} | {'LIVE (real lock)' if args.live else 'DRY-RUN (no real lock)'} | Ctrl+C to stop")
    svc.start()
    try:
        end = time.monotonic() + args.seconds if args.seconds else None
        while end is None or time.monotonic() < end:
            time.sleep(2.0)
            s = svc.status()
            print(f"  state={s.state.value} obstruction={s.obstruction.value} presence={s.presence} camera={s.camera} frames={s.frames}", flush=True)
    except KeyboardInterrupt:
        print("stopping...")
    finally:
        svc.stop()
        db.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.headless:
        return run_headless(args)
    from silentwatch.app.tray_main import run_tray

    return run_tray(args)

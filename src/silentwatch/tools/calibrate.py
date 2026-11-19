"""Calibrate the obstruction detector for the current camera and room.

    python -m silentwatch.tools.calibrate

Keep the laptop in its normal position, lens uncovered, normal lighting. Stores numbers only.
"""

from __future__ import annotations

import time

from silentwatch.camera.calibration import (
    CalibrationError,
    CalibrationStore,
    collect_features,
    compute_baseline,
    log_result,
)
from silentwatch.camera.capture import CameraCaptureService
from silentwatch.camera.sources import CvFrameSource
from silentwatch.config import app_data_dir, load_config
from silentwatch.storage import Database, EventStore


def run(db: Database, store: EventStore | None = None) -> int:
    cfg = load_config()
    c = cfg.camera
    svc = CameraCaptureService(
        lambda: CvFrameSource(c.index, c.width, c.height, c.backend),
        c.analysis_fps, c.warmup_frames, c.queue_size, c.frozen_frames, c.read_fail_limit, c.frozen_seconds, c.frozen_reopen_interval_s,
    )
    resolution = f"{c.width}x{c.height}"
    with svc:
        print(f"Calibrating for {cfg.obstruction.calibration_seconds:.0f}s - keep the lens uncovered...")
        feats = collect_features(
            lambda: (lambda f: f.image if f else None)(svc.get(timeout=0.5)),
            cfg.obstruction.calibration_seconds,
            time.monotonic,
        )
    try:
        baseline = compute_baseline(feats, f"camera{c.index}", resolution)
    except CalibrationError as exc:
        print(f"Calibration rejected: {exc}")
        log_result(store, False, str(exc))
        return 1
    CalibrationStore(db).save(baseline)
    log_result(store, True, f"{baseline.n_frames} frames")
    print(f"Calibration saved ({baseline.n_frames} frames). mean luma {baseline.stats['mean_luma'].mean:.1f}")
    return 0


def main() -> int:
    db = Database(app_data_dir() / "silentwatch.db")
    try:
        return run(db, EventStore(db))
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

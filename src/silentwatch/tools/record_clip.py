"""Record a labelled test clip from the real camera for tuning.

    python -m silentwatch.tools.record_clip --scenario normal --seconds 30
    python -m silentwatch.tools.record_clip --scenario hand_fast --seconds 12 --cover-at 5

Frames are stored at 128x96 in data/clips/ (git-ignored: it contains your room). A 'normal' clip is needed
as the baseline for evaluation. A countdown tells you when to start covering.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from silentwatch.camera.capture import CameraCaptureService
from silentwatch.camera.replay import save_clip
from silentwatch.camera.sources import CvFrameSource
from silentwatch.config import load_config

EXPECT_CONFIRM = {"hand_fast", "hand_slow", "finger", "cloth", "paper", "shutter"}
OUT = Path("data/clips")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--cover-at", type=float, default=None, help="seconds into the clip when you cover the lens")
    ap.add_argument("--take", type=int, default=1)
    args = ap.parse_args(argv)
    c = load_config().camera
    svc = CameraCaptureService(
        lambda: CvFrameSource(c.index, c.width, c.height, c.backend),
        c.analysis_fps, c.warmup_frames, c.queue_size, c.frozen_frames, c.read_fail_limit, c.frozen_seconds, c.frozen_reopen_interval_s,
    )
    frames: list[np.ndarray] = []
    with svc:
        print("Starting in 3 s (camera warms up)...")
        time.sleep(3)
        t0 = time.monotonic()
        while time.monotonic() - t0 < args.seconds:
            f = svc.get(timeout=0.5)
            if f is not None:
                frames.append(cv2.resize(f.image, (128, 96), interpolation=cv2.INTER_AREA))
            if args.cover_at is not None and abs((time.monotonic() - t0) - args.cover_at) < 0.1:
                print(">>> COVER NOW")
    meta = {
        "scenario": args.scenario,
        "description": f"recorded take {args.take}",
        "expect_confirm": args.scenario in EXPECT_CONFIRM,
        "cover_at": args.cover_at,
    }
    path = OUT / args.scenario / f"take{args.take}.npz"
    save_clip(path, np.stack(frames), meta)
    print(f"Saved {len(frames)} frames to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

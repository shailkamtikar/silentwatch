"""Print live camera features (numbers only, nothing saved).

    python -m silentwatch.tools.feature_probe --seconds 10
"""

from __future__ import annotations

import argparse
import time

from silentwatch.camera.capture import CameraCaptureService
from silentwatch.camera.integrity import FeatureExtractor
from silentwatch.camera.sources import CvFrameSource
from silentwatch.config import load_config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args(argv)
    cfg = load_config().camera
    svc = CameraCaptureService(
        lambda: CvFrameSource(cfg.index, cfg.width, cfg.height, cfg.backend),
        cfg.analysis_fps, cfg.warmup_frames, cfg.queue_size, cfg.frozen_frames, cfg.read_fail_limit,
    )
    ex = FeatureExtractor()
    end = time.monotonic() + args.seconds
    print("t   mean  dark  std   flat  edge   lap    ent  struct diff")
    with svc:
        while time.monotonic() < end:
            fr = svc.get(timeout=1.0)
            if fr is None:
                continue
            f = ex.update(fr.image)
            print(f"{fr.index:<3d} {f.mean_luma:5.1f} {f.dark_ratio:4.2f} {f.std_luma:5.1f} {f.tile_flat_ratio:4.2f} "
                  f"{f.edge_density:5.3f} {f.laplacian_var:6.1f} {f.entropy:4.2f} {f.structure_ratio:5.2f} {f.frame_diff:5.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

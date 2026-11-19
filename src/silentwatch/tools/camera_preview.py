"""Show the live camera with a visible 'camera in use' banner. Press q to quit. Saves nothing."""

from __future__ import annotations

import cv2

from silentwatch.camera.capture import CameraCaptureService
from silentwatch.camera.sources import CvFrameSource
from silentwatch.config import load_config


def main() -> int:
    cfg = load_config().camera
    svc = CameraCaptureService(
        lambda: CvFrameSource(cfg.index, cfg.width, cfg.height, cfg.backend),
        cfg.analysis_fps,
        cfg.warmup_frames,
        cfg.queue_size,
    )
    with svc:
        while True:
            f = svc.get(timeout=1.0)
            if f is None:
                if svc.error:
                    print("Camera error:", svc.error)
                    return 1
                continue
            img = f.image.copy()
            cv2.putText(img, "SILENTWATCH: CAMERA IN USE (q to quit)", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("SILENTWATCH preview", img)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

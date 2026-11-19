"""Probe the default webcam: backends, supported resolutions, first-frame time. Saves nothing."""

import sys
import time

import cv2

RES = [(640, 480), (1280, 720), (1920, 1080)]
BACKENDS = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF}


def probe(name, backend, index=0):
    t0 = time.monotonic()
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        print(f"{name}: could not open camera {index}")
        return False
    ok = False
    for w, h in RES:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        try:
            got, frame = cap.read()
        except cv2.error as exc:
            print(f"{name}: requested {w}x{h} -> OpenCV error: {str(exc).splitlines()[0][:80]}")
            continue
        if got:
            ok = True
            print(f"{name}: requested {w}x{h} -> frame {frame.shape[1]}x{frame.shape[0]}, "
                  f"first-frame {time.monotonic() - t0:.2f}s, mean luma {frame.mean():.1f}")
        else:
            print(f"{name}: requested {w}x{h} -> no frame")
    cap.release()
    return ok


if __name__ == "__main__":
    results = [probe(n, b) for n, b in BACKENDS.items()]
    sys.exit(0 if any(results) else 1)

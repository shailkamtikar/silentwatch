# Decisions

## D1. Python version
Python 3.12 (venv). 3.11 is also installed; 3.12 is pinned because every planned dependency resolved and imported on it (M0.3).

## D2. Single OpenCV package
`pip` resolved `opencv-python`, `opencv-contrib-python` (a MediaPipe dependency) and both provide `cv2`. Only **`opencv-contrib-python`** is installed. Never install plain `opencv-python` alongside it. Verified with `pip list` in the spike venv (M0.3, T0.3-04).

## D3. Dependencies verified together (spike venv)
opencv-contrib-python 5.1.0.95, mediapipe 1.2.3, bleak (winrt backend), PySide6-Essentials 6.12.0, pywin32. `pip check` clean. Full PySide6 meta-package is not used (pulls WebEngine/Pdf add-ons).

## D4. Camera backend: DirectShow (`cv2.CAP_DSHOW`)
Measured on the HP True Vision FHD Camera (M0.3 / M2.1 probe):

| Backend | 640x480 first frame | Notes |
|---|---|---|
| DSHOW | ~1.2 s | 720p and 1080p also work |
| MSMF | ~14.7 s | OpenCV assertion error when switching to 1280x720 |

DSHOW is the default. **Finding:** the first frame after opening is nearly black (mean luma 0.1) because of auto-exposure warm-up. Capture, calibration and obstruction analysis must discard the first frames (`warmup_frames` in config) so a normal start is never mistaken for a covered lens.

## D5. Default configuration location
`default.toml` lives inside the package (`src/silentwatch/config/default.toml`) so it is bundled by setuptools and PyInstaller. (The playbook mentioned a root `config/` folder.)

## D6. Phone proximity method
Decided in M7.1 (see below once recorded).

## D7. Real-camera capture measurement (M2.1)
On the HP camera via DSHOW at 640x480: first emitted frame ~2.3 s after start (15 warm-up frames discarded), ~4.6 frames/s emitted at the 5 fps analysis rate, five start/stop cycles all succeeded and released the device. The first emitted frame still had mean luma ~6 (very dark), so exposure may need more than 15 frames to settle; calibration (M3.2) therefore also waits for brightness to stabilise instead of trusting a fixed frame count.

## D8. Real-camera feature sanity values and low-light behaviour (M3.1)
Measured with `python -m silentwatch.tools.feature_probe` on the HP camera in the evening room at the time of testing (numbers only, nothing saved):

| Condition | mean luma | dark ratio | std | tile flat | edge density | structure ratio |
|---|---|---|---|---|---|---|
| Real scene, dim room with one lit object | 5.9 | 0.97 | 36 | 0.75 | 0.018 | 0.54 |

Findings:
- In a dim room the camera uses long auto-exposure and delivers only ~4 unique frames/s (15 unique frames in 120 reads at ~30 Hz). Consecutive reads are often bit-identical. Frozen detection therefore works on the emitted (5 fps) stream with a 10-frame threshold, never on raw reads.
- A realistic baseline can be very dark (mean ~6) yet still structured. Calibration must not reject dark-but-structured baselines; it rejects only baselines that are already featureless (covered lens).
- Darkness alone is not a feature the classifier trusts; structure collapse (std, edge density, tile flatness, structure ratio) is.

## D9. Frozen-feed detection is duration-based (found in M3.2 real-camera run)
First version flagged `FROZEN` after 10 identical emitted frames (2 s) and re-opened the camera. On the real HP camera in a dim, static room this produced false FROZEN events about every 5 s and kept resetting the stream (calibration got 7 frames instead of 25). Fix: FROZEN now needs both `frozen_frames` identical frames **and** `frozen_seconds` (default 20 s) of identical frames, and a FROZEN event re-opens the device at most once per `frozen_reopen_interval_s` (default 300 s); otherwise it only warns. Policy still treats FROZEN alone as a warning, never as tampering.

## D10. Calibration accepts static streams (M3.2)
The playbook asked calibration to reject frozen streams. On the real camera a still, dim room produced bit-identical frames for the whole 5 s window, so a "frozen" check rejected a perfectly healthy camera. Calibration now rejects only too few frames and covered/featureless scenes. A real run on the HP camera saved a baseline from 22 frames (mean luma 5.9).

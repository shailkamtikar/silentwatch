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

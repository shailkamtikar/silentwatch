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

## D11. Presence via MediaPipe Face Detector (M4.2)
`mediapipe 1.2.3` with `blaze_face_short_range.tflite` (Google model storage, 229,746 bytes, SHA-256 pinned in `scripts/download_models.ps1` and `models/README.md`; recorded on first verified download). Detection costs ~2.5 ms per frame on this laptop's CPU. A corrupted model file is detected by hash and re-downloaded (tested). A live run in the dim test room saw 0 faces in 45 frames and correctly progressed to `OWNER_ABSENT_PENDING`; detection of a real face needs a person in view (see `docs/manual-verification.md`). Presence is not identity: a photo can be detected as a face (documented limit).

## D12. Lock requests are latched per condition (M4.3)
Early scripted tests showed that, with cooldown 0, a persisting condition (e.g. absence confirmed) issued a LOCK on every frame. The engine now latches: one LOCK per continuous condition; the latch re-arms when no rule triggers any more, on SESSION_UNLOCKED, or when `on_lock_result(False)` reports that Windows rejected the request (so a failed lock is retried).

## D13. Live end-to-end dry run (M4.4)
`python -m silentwatch --headless --seconds 30` on the HP camera (dry-run, temporary data dir): started, calibrated automatically (MISSING -> 6 frames wait -> baseline), then with nobody in view went `OWNER_ABSENT_PENDING` at ~9 s after start and issued a dry-run lock for "owner absent beyond configured timeout" at ~19 s after start, i.e. 10 s after the last (non-)detection as configured. A static dim scene produced a FROZEN warning after ~18 s of identical frames and one device re-open; defaults were raised to `frozen_seconds = 60` and `frozen_reopen_interval_s = 600` to make that rarer. All 8 scripted end-to-end scenarios (A, C, D, E, F, post-unlock, clean exit, audit trail) pass with fake camera/face/lock.

## D14. Hand-approach evidence (M6.1)
`hand_landmarker.task` (Google model storage, 7,819,105 bytes, SHA-256 pinned). On a blank 640x480 frame it costs ~8.5 ms (CPU), so it is only run when stage 1 flags a change (M6.2). The score combines relative bounding-box growth over 0.5 s with absolute size; it is monotone and clipped to 0..1. It is early-warning evidence only: policy never locks on it alone.

## D15. Two-stage pipeline cost (M6.2)
Live on the HP camera (idle dim room, dry-run, face + obstruction analysis at 5 fps, 20 s window after calibration): process CPU 7.0 % of one core without the hand model and 6.2 % with it enabled; 89 frames analysed in both runs and **0** hand-model invocations, because stage 1 saw no change. (The difference is measurement noise.) Stage 2 wakes on `frame_diff >= 4`, a non-NORMAL obstruction state, or for 2 s after a hand was last seen. A hand signal alone only notifies; with a possible/partial obstruction it locks before the plain debounce expires. A failing hand model disables itself and monitoring continues on stage 1.

## D16. Phone proximity: feasibility spike result (M7.1, 20 Nov 2026)
Measured on this laptop (MediaTek Bluetooth adapter) with the paired Android phone (identifiers not recorded here):

| Method | Result |
|---|---|
| BLE advertisement scan (Bleak, 20 s, phone nearby, screen on) | 13 distinct addresses; only 2 carried a name, and neither was the phone. The phone cannot be recognised by name. Android phones use rotating random (private) addresses, so an address cannot identify it for long. One strong unnamed device (RSSI about -43 dBm, manufacturer id 224) is a candidate but is not a stable identity |
| Paired-device connection state (WinRT `BluetoothDevice.ConnectionStatus`) | The phone is paired but reported **DISCONNECTED** while idle: Windows only shows CONNECTED while a profile (audio, Phone Link, tethering) holds a link, so a disconnect cannot be read as "phone left" |

Decision: implement the proximity service behind a `ProximitySource` abstraction with smoothing, enrollment and policy rules (M7.2, M7.3), and support two sources: (1) **paired-connection** (usable only when the phone keeps a live connection, e.g. connected to the laptop for Phone Link), and (2) **BLE advertisement by service UUID**, which gives a stable identity only if the phone runs a small advertiser app (for example the free "nRF Connect" app's Advertiser with a custom service UUID). Without one of these the phone feature reports `BT_UNAVAILABLE` and has no effect on any decision: the core product does not depend on it. Windows' own Dynamic Lock (Settings > Accounts > Sign-in options) is also available for walk-away locking with the same phone.

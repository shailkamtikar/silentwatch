# Manual verification log

Automated tests never call the real `LockWorkStation`, never cover your lens and never use Bluetooth/USB hardware. Items below need a human at the laptop. Status: `PENDING` until you run and tick them.

| Milestone | Test ID | What to do | Status |
|---|---|---|---|
| M1.3 | T1.3-05 | Save work, run `python -m silentwatch.tools.lock_test --delay 5`; real Windows lock screen must appear and PIN unlock must work | PENDING |
| M1.3 | T1.3-06 | After unlocking, rerun with `--dry-run` and confirm `LOCK_REQUESTED`/`LOCK_RESULT` are printed | PENDING |
| M2.2 | T2.2-07 | Point camera at a still scene for 10 minutes with the app running; no `CAMERA_FROZEN` event | PENDING |
| M2.2 | T2.2 live | Disable camera in Device Manager during a run: `CAMERA_UNAVAILABLE` within ~2 s | PENDING |
| M2.3 | T2.3-03 | Device Manager: disable then enable the camera while a run is active; recovery within ~35 s | PENDING |
| M2.3 | T2.3-04..07 | Windows Camera app / Meet / Hello / privacy toggle matrix in `docs/testing.md` | PENDING |
| M3.1 | T3.1-09 | Run `python -m silentwatch.tools.feature_probe --seconds 10` three times: normal, hand covering lens, lights off; paste the numbers into `docs/testing.md` | PENDING |
| M3.2 | T3.2-07 | Calibrate in your normal desk lighting with the screen on: `python -m silentwatch.tools.calibrate`. (An automated run in the dim test room already succeeded with 22 frames.) | PARTIAL |
| M3.3 | live dry-run | After calibrating, cover the lens with your hand: console/dashboard shows CONFIRMED_OBSTRUCTION with reasons; switch the room light off with the screen on: no CONFIRMED (see M4.4 for the full run) | PENDING |
| M3.4 | T3.4-01..07 | Record real clips and evaluate: `python -m silentwatch.tools.record_clip --scenario normal --seconds 40`, then `hand_fast`, `hand_slow`, `finger`, `cloth`, `paper`, `lights_off`, `partial`, `translucent` (use `--cover-at`), then `python -m silentwatch.tools.evaluate --write-docs`. Add 30 minutes of normal use. Tune `Thresholds` in `obstruction.py` only with these results | PENDING |
| M4.2 | T4.2-01..06 | Sit in front of the camera: face_count >= 1 and state PRESENT; turn your head / look down 2 s: not absent; second person: count 2; low light result noted | PENDING |
| M4.3 | live dry-run | `--dry-run`: stand up and leave the frame; log shows pending then `LOCK (dry-run)` at the configured time (full run in M4.4) | PENDING |
| M4.4 | T4.4-01..05 | LIVE scenarios with the real lock: run `python -m silentwatch --headless --live` with work saved. A: walk away; C: cover lens with hand; D: lights off; E: sit and have someone cover the lens; F: disable camera in Device Manager. (Automated dry-run of the whole pipeline on the real camera already passed.) | PENDING |
| M4.4 | T4.4-09 | 30-minute soak with `--headless` (dry-run): 0 false lock decisions, memory stable | PENDING |

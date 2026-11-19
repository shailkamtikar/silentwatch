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
| M5.1 | T5.1-01..03,05 | Run `python -m silentwatch` (or `pythonw -m silentwatch`): tray icon appears with tooltip; Pause turns the camera LED off; Resume restores; Quit exits. (Automated: the tray launched and exited cleanly with the real camera in dry-run; icon logic and pause/resume are unit-tested.) | PARTIAL |
| M5.1 | T5.1-08 | Confirm no UAC prompt appears when starting the app (nothing requests elevation) | PENDING |
| M5.2 | T5.2-01 | Open the dashboard from the tray; enable the preview; wave a hand: image is smooth and the "scene structure lost" bar reacts. Take a screenshot for the demo (avoid showing private surroundings; do not commit it) | PENDING |
| M5.3 | T5.3-01,08,09 | First launch shows the consent dialog and the camera stays off until you accept; Settings > "Test lock now" really locks (save work); Windows Settings > Privacy > Microphone shows SILENTWATCH never used the microphone | PENDING |
| M5.4 | T5.4-01..05 | With the tray app running: Win+L then sign in (camera LED off while locked, monitoring resumes ~after the grace period); sleep/wake; enable "Start with Windows" in the tray menu, sign out/in, app starts; disable it and check `shell:startup` is clean. (Automated: synthetic WTS/power messages, 20 lock/unlock cycles with the fake camera.) | PENDING |
| M6.1 | T6.1-01..04 | Move your hand toward the lens: hand score rises; away: falls; no hand: ~0; dim light: no crash | PENDING |
| M6.2 | T6.2-05 | Live `--live`: move your hand quickly toward the lens and cover it: lock happens, event log shows both the hand and obstruction evidence | PENDING |
| M7.1 | T7.1-03..05,07 | Screen-off / pocket / Battery-Saver / 20-minute address-rotation checks with the phone (run `python scripts/ble_scan.py`); install an advertiser app on the phone and confirm its UUID is seen | PENDING |
| M7.2 | T7.2-02..06 | After enrolling (`python -m silentwatch.tools.enroll_phone ...`): phone beside laptop = PRESENT; phone in another room for the configured window = MISSING; Bluetooth toggled off = BT_UNAVAILABLE (not MISSING); laptop sleep/wake recovers (matrix in Book 18.3) | PENDING |
| M7.3 | T7.3-06 | Live with an enrolled phone: walk away carrying the phone vs. leaving it: lock is sooner when the phone is also missing; with Bluetooth off the app shows BT_UNAVAILABLE and does not treat it as theft | PENDING |
| M8.1 | T8.1-01..04 | `bluetooth`/`usb.enabled = true` in settings; plug a USB stick while seated (logged, no lock); remove it; plug it while away from the desk (lock). Plug a mouse/keyboard: ignored. (Automated: synthetic WM_DEVICECHANGE, bus-type classification of the real system drive) | PENDING |
| M8.2 | T8.2-07 | Turn "Save evidence snapshots" on, trigger an obstruction, then sign in as a different Windows user and try to open `%APPDATA%\SilentWatch\evidence\*.swe` with the app: it must fail to decrypt | PENDING |
| M9.1 | T9.1-02 | Reboot with "Start with Windows" on: app returns to the tray and monitoring resumes | PENDING |
| M9.1 | T9.1-03,04 | Settings > Privacy & security > Camera: turn camera access off while running (expect CAMERA_UNAVAILABLE, no crash), turn on (recovers); disable/enable the camera in Device Manager (needs admin) | PENDING |

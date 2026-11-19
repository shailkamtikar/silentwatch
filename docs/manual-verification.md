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

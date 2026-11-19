# Manual verification log

Automated tests never call the real `LockWorkStation`, never cover your lens and never use Bluetooth/USB hardware. Items below need a human at the laptop. Status: `PENDING` until you run and tick them.

| Milestone | Test ID | What to do | Status |
|---|---|---|---|
| M1.3 | T1.3-05 | Save work, run `python -m silentwatch.tools.lock_test --delay 5`; real Windows lock screen must appear and PIN unlock must work | PENDING |
| M1.3 | T1.3-06 | After unlocking, rerun with `--dry-run` and confirm `LOCK_REQUESTED`/`LOCK_RESULT` are printed | PENDING |

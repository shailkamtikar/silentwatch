# Testing

Test IDs follow `T<phase>.<milestone>-NN`, matching `docs/PLAYBOOK.md`.

Run all automated tests:

```powershell
python -m pytest -q
```

## Manual verification status

Items that need a human at the laptop (physical lock, covering the lens, walking away, Bluetooth, USB, battery) are tracked in `docs/manual-verification.md`. Automated tests never call the real `LockWorkStation`.

## Camera contention matrix (M2.3)

| Scenario | Result | Status |
|---|---|---|
| Two OpenCV/DSHOW processes on the HP camera at once | Second client opened in 0.4 s and read 10/10 frames while the first kept reading (Windows 11 camera frame server allows sharing) | Observed (automated probe) |
| Windows Camera app open first, then SILENTWATCH | Needs manual run | PENDING |
| SILENTWATCH first, then Meet/Zoom/Teams | Needs manual run | PENDING |
| Windows Hello sign-in while running | Needs manual run (also see M5.4: camera is released while locked) | PENDING |
| Camera privacy toggle off | Needs manual run: expect `CAMERA_UNAVAILABLE`, retries with backoff, no crash | PENDING |
| Disable/enable camera in Device Manager (admin) | Needs manual run: expect recovery within ~35 s | PENDING |

Camera failures never produce tamper locks by themselves; the capture service retries with 1,2,4,...,30 s backoff and reports UNAVAILABLE/FROZEN/RECOVERED events.

## Feature extractor real-data note (M3.1, T3.1-09)
See decision D8 in `docs/decisions.md`: first real-camera feature values were recorded. Covered-lens and lights-off values still need to be recorded by a human (see `docs/manual-verification.md`).

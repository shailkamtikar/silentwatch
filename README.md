# SILENTWATCH

Privacy-first Windows 11 laptop protection: local webcam analysis (camera-obstruction detection, owner presence), optional phone proximity, USB and hand-approach signals, and locking the **real** Windows session. Everything runs on the laptop; no cloud, no network code.

**Status:** working prototype (all planned milestones through 9.2 implemented; see `docs/PLAYBOOK.md`). It is a defensive utility, **not** a guaranteed anti-theft system. Read `docs/threat-model.md` before relying on it.

## What it does

- Locks Windows when the camera lens is covered (even if no face was ever seen), when you leave and stay away, when the camera is disabled while you are away, or when USB storage is plugged in while you are away (optional).
- Never locks because of darkness, a frozen camera feed, a missing phone, or a nearby hand *alone*.
- Explains every decision: the dashboard's "why" panel shows the evidence behind each lock.

## Quick start (development)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e . -r requirements-dev.txt -r requirements.txt
.\scripts\download_models.ps1          # face and hand models, SHA-256 verified
python -m pytest -q
```

## Running

```powershell
python -m silentwatch --headless                 # console, DRY-RUN: decisions are logged, nothing is locked
python -m silentwatch --headless --live          # really locks Windows (save your work first)
python -m silentwatch                            # tray app (first run shows the consent screen)
python -m silentwatch.tools.calibrate            # (re)calibrate the camera for this room
python -m silentwatch.tools.lock_test --dry-run  # check the lock path
```

The default is dry-run until you pass `--live` or turn dry-run off in Settings. Calibration runs automatically on first start (keep the lens uncovered).

## Layout

`src/silentwatch/` — `camera/` (capture, health, features, calibration, classifier, hand), `presence/`, `policy/` (pure decision engine), `app/` (service, tray), `ui/`, `windows/` (lock, session, USB), `bluetooth/`, `storage/`, `tools/`. Tests in `tests/`, docs in `docs/`.

## Limitations

Cannot stop an attacker who controls the session or the machine, cannot tell a photo from a person, cannot distinguish total darkness from a black cover, and thresholds need calibration per camera and room. Presence detection is not identity verification. Phone proximity needs a live Bluetooth connection or a phone-side advertiser app (see `docs/decisions.md`, D16). Motion/snatch detection is not available (no sensor).

## Licence

MIT (see `LICENSE`). Third-party models and libraries keep their own licences; an inventory is part of milestone 9.4.

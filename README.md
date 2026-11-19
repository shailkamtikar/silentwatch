# SILENTWATCH

Privacy-first Windows 11 laptop protection: local webcam analysis (camera-obstruction detection, owner presence), optional phone proximity, and locking the real Windows session. Everything runs locally; no cloud services.

**Status:** prototype under development. It is a defensive utility, not a guaranteed anti-theft system. See `docs/SILENTWATCH_Knowledge_Book.md` (requirements) and `docs/PLAYBOOK.md` (build plan).

## Quick start (development)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e . -r requirements-dev.txt
python -m pytest -q
```

## Limitations

Cannot stop an attacker who has control of the machine, cannot tell a photo from a person, and thresholds need calibration per camera. Presence detection is not identity verification.

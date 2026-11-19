# Testing

Test IDs follow `T<phase>.<milestone>-NN`, matching `docs/PLAYBOOK.md`.

Run all automated tests:

```powershell
python -m pytest -q
```

## Manual verification status

Items that need a human at the laptop (physical lock, covering the lens, walking away, Bluetooth, USB, battery) are tracked in `docs/manual-verification.md`. Automated tests never call the real `LockWorkStation`.

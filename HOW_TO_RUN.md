# How to run SILENTWATCH yourself (no Claude needed)

SILENTWATCH is a **desktop app, not a web server**. There is no URL to open. "Showing it locally" means: start it, then use its **tray icon** (bottom-right of the taskbar, maybe under the ^ arrow) and its **dashboard window**.

All commands are for **PowerShell** on this laptop. Folder: `C:\Users\HP\projects\silentwatch`

---

## A. One-time setup (only if `.venv` is missing or something is broken)

```powershell
cd C:\Users\HP\projects\silentwatch
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e . -r requirements-dev.txt -r requirements.txt
.\scripts\download_models.ps1
python -m pytest -q
```

- If `Activate.ps1` is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.
- The last line should end with `268 passed` (takes about 2 minutes).
- `download_models.ps1` fetches two small model files into `models\` (face and hand detection) and checks their SHA-256.

---

## B. Every time: start it

Open PowerShell and go to the project, then activate the environment:

```powershell
cd C:\Users\HP\projects\silentwatch
.\.venv\Scripts\Activate.ps1
```

Pick ONE of these:

### 1. Safe test mode in the console (recommended first)
Decisions are printed, **nothing is really locked**:

```powershell
python -m silentwatch --headless
```

You will see lines like `state=OWNER_PRESENT ...` every 2 seconds, and `LOCK: ... (dry-run)` when it *would* lock. Stop with **Ctrl+C**. The first run calibrates for ~5 seconds: keep the lens uncovered.

### 2. The tray app (the normal way)

```powershell
python -m silentwatch
```

- First launch shows a **consent screen**. Click "I understand, start monitoring".
- A coloured circle appears in the tray: green = monitoring, yellow = someone absent/suspicious, red = tamper/lock, grey = paused, orange = camera problem, purple = monitor crashed.
- **Right-click it**: Open dashboard, Pause/Resume (turns the camera off), Recalibrate camera, Settings, Mode (Balanced/Strict), Start with Windows, Quit.
- **Double-click it** (or "Open dashboard") to show the **dashboard**: current state, "scene structure lost" bar, optional live preview (tick the box; off by default and never saved), and the event history with a "why" panel for each lock.
- It starts in **dry-run**: it logs "would lock" but does not lock Windows. Turn dry-run off in **Settings** when you want real locking.

For no console window at all, use `pythonw -m silentwatch` instead of `python -m silentwatch`.

### 3. REAL locking (save your work first!)

```powershell
python -m silentwatch --headless --live
```

or `python -m silentwatch --live` for the tray version. Windows really locks (lock screen, sign in with your normal PIN/password). To stop it: Ctrl+C, or tray > Quit.

---

## C. Handy commands

| What | Command |
|---|---|
| Recalibrate the camera (lens uncovered, normal lighting) | `python -m silentwatch.tools.calibrate` |
| Try one real lock in 5 s | `python -m silentwatch.tools.lock_test --delay 5` |
| Same, without locking | `python -m silentwatch.tools.lock_test --dry-run` |
| See raw camera numbers for 10 s (nothing saved) | `python -m silentwatch.tools.feature_probe --seconds 10` |
| Show the camera with a "camera in use" banner (q quits) | `python -m silentwatch.tools.camera_preview` |
| Score the cover-detector on test scenarios | `python -m silentwatch.tools.evaluate` |
| Enrol a phone (optional, see docs/decisions.md D16) | `python -m silentwatch.tools.enroll_phone --paired S24` |
| Version | `python -m silentwatch --version` |

Command-line options: `--mode strict|balanced`, `--no-presence` (skip face detection), `--seconds N` (stop after N seconds), `--live`.

---

## D. Where things are stored

`%APPDATA%\SilentWatch\` holds the event log (`silentwatch.db`), your settings (`settings.json`) and, only if you turned snapshots on, `evidence\`. Delete the whole folder (or use Settings > "Delete all local data") to reset everything, including the consent screen. Nothing is ever uploaded.

---

## E. If something goes wrong

| Problem | Fix |
|---|---|
| Tray icon is **orange** / "camera unavailable" | Close other apps using the webcam (Zoom, Teams, Camera app), check Settings > Privacy & security > Camera is on, and make sure the camera shutter/F-key switch is open. It retries by itself. |
| `presence disabled: Face model not found` | Run `.\scripts\download_models.ps1` |
| Nothing happens when I cover the lens | Check it calibrated (`python -m silentwatch.tools.calibrate`), and that you are not paused (grey icon). In dry-run it only *says* it would lock. |
| "SILENTWATCH is already running" | It is already in the tray (maybe hidden under ^). Quit it from there, or: `Get-Process python* \| Stop-Process` |
| It locked and I cannot get back | Sign in normally; it waits ~10 s after unlock before it can lock again. |
| Camera light stays on after a crash | `Get-Process python*, pythonw* \| Stop-Process` |
| Tests fail after a Windows/Python update | Redo section A (recreate `.venv`). |
| Want to see what it decided | Dashboard > event history, or open `%APPDATA%\SilentWatch\silentwatch.db` with any SQLite viewer. |

---

## F. Get the code back from GitHub

```powershell
git clone https://github.com/shailkamtikar/silentwatch.git
cd silentwatch
git checkout phase-9-release     # latest work (phases 0-8 are also on main)
```
then redo section A.

Docs: `docs/PLAYBOOK.md` (build plan), `docs/decisions.md` (why things are the way they are), `docs/threat-model.md` (what it can and cannot protect), `docs/manual-verification.md` (checks still waiting for you).

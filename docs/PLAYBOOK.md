# SILENTWATCH — Phase-Wise Development Playbook

**Repository:** https://github.com/shailkamtikar/silentwatch.git (checked: it exists and is currently empty)
**Source of truth for requirements:** `SILENTWATCH_Knowledge_Book.md` (referred to below as "the Book")
**Target machine (audited 19 Nov 2026):** Windows 11 Home 10.0.26300, Python 3.12.10 (3.11 also present), AMD Ryzen 7 7840HS, 15.3 GB RAM, HP True Vision FHD Camera (USB), MediaTek Bluetooth adapter, Android phone "Shail's S24 FE" already paired. No motion sensor and no Windows presence sensor found.
**Scope decision:** laptop-snatch / motion detection is **out of scope** (no sensor; dropped by the owner). Everything else in the Book's MVP and should-have tiers is in scope.

---

## 0. How to use this playbook

1. Work strictly in order. A milestone may start only when every milestone in its **Requires** line is `DONE` and tagged.
2. For each milestone: implement the Tasks → run the Test Cases → tick the Verification Checklist → only then run the Git Checkpoint.
3. Fill the **Status** column of each test table (`PASS` / `FAIL` / `N/A`) in a copy of this file or in `docs/testing.md`. A milestone is DONE only when every row is `PASS` or an explicit, justified `N/A`.
4. Every Git push is a stable checkpoint. Never push a red test suite.
5. Each phase ends with a **Phase Completion Checkpoint** (go / no-go) and is merged into `main` only on GO.

### 0.1 Missing information (identified, with the default this playbook assumes)

The instructions say to flag gaps instead of silently assuming. These are the open items. Each has a default so you can start; reply if any default is wrong.

| # | Missing information | Default assumed | Where it matters |
|---|---|---|---|
| 1 | Demo / judging date and audience | Unknown. Plan targets a working demo after Phase 4, polished demo after Phase 5 | Phase ordering, Phase 9 |
| 2 | Default Git branch | `main` (repo is empty, so GitHub's default applies) | Phase 0 |
| 3 | Licence for your own code | MIT (change before first public release if you prefer otherwise) | M0.1, M9.4 |
| 4 | UI framework | PySide6 (install **PySide6-Essentials** only, not the full meta-package, to avoid the heavy WebEngine/Pdf add-ons the dry run pulled in) | Phase 5 |
| 5 | Does the S24 FE advertise a usable BLE beacon? | Unknown. Phase 7 starts with a feasibility spike and chooses between BLE advertisement scanning and paired-device connection state | Phase 7 |
| 6 | Webcam sharing with Windows Hello / video calls | Unknown on this laptop. Tested explicitly in M2.3 | Phase 2 |
| 7 | Competition / institution rules about disclosing AI assistance | Not provided. Check them yourself; the playbook only controls what appears in Git history | Git rules |
| 9 | Second test machine | Your old Windows 11 Home laptop, available for the Milestone 9.3 clean-machine test (its specs are not yet recorded) | M9.3 |
| 8 | Team size | Assumed solo (affects rollback: force-push is acceptable only on your own feature branches) | Rollback |

### 0.2 Global Git conventions (apply to every milestone)

**Branching:** `main` is always releasable. One branch per phase: `phase-0-setup`, `phase-1-foundation`, `phase-2-camera`, `phase-3-obstruction`, `phase-4-policy-presence`, `phase-5-ui-privacy`, `phase-6-hand`, `phase-7-ble`, `phase-8-extras`, `phase-9-release`. Milestones are commits (and tags) on the phase branch. At the Phase Completion Checkpoint the branch is merged to `main` with `--no-ff` and tagged `phase-N-complete`.

**Commit messages:** Conventional style: `feat(camera): add capture service (M2.1)`.

**Authorship — no co-author trailers.** Every commit must have only your identity (`Shail Kamtikar <shailkamtikar@gmail.com>`, already your global Git identity). Do not add `Co-Authored-By:` lines or any other trailer, and do not paste generated trailers into commit messages or PR descriptions. A `commit-msg` hook that blocks such trailers is set up in M0.1, and each Git checkpoint below can be audited with:

```powershell
git log --format=%B | Select-String -Pattern "co-authored-by" -CaseSensitive:$false
git shortlog -sne --all
```
Both must show only you (the first must print nothing). No commit was created by the assistant while preparing this playbook.

**Tags:** `m<phase>.<n>` after each milestone push, e.g. `m2.1`. Phase merges get `phase-N-complete`.

**Never commit (global list; each milestone adds specifics):**
`.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.db` / `*.sqlite*` (event stores), `data/` (recorded camera clips, evidence snapshots, face images), `%APPDATA%` settings, `.env` or any secrets, `dist/`, `build/`, downloaded model weights (`models/*.task`, `models/*.onnx`, `models/*.tflite`; commit only `models/README.md` and the download script with SHA-256 hashes), editor folders, large binaries.

**Standard rollback ladder (used in every milestone's Rollback section):**
1. *Not pushed yet:* `git restore .` (discard edits) or `git reset --hard HEAD` (drop the uncommitted state).
2. *Pushed, safe for any case:* `git revert <bad-commit-hash>` then `git push origin <branch>`. This adds a new commit and rewrites no history.
3. *Pushed to your own phase branch, solo project, you want the branch exactly at the last good milestone:* `git reset --hard <previous-tag>` then `git push --force-with-lease origin <branch>`. Never force-push `main`.
4. *Already merged to `main`:* use option 2 only.
5. Find the previous good point with `git tag --sort=creatordate` and `git log --oneline -n 15`.

### 0.3 Dependency map (what must exist before what)

```
Phase 0 ─► Phase 1 (config, events, lock) ─► Phase 2 (camera) ─► Phase 3 (obstruction)
                                                              └──────────────┐
Phase 1 ─► Phase 4.1 (policy core, no camera needed) ───────────────────────┤
Phase 2 ─► Phase 4.2 (presence)                                              ▼
Phase 3 + 4.1 + 4.2 ─► 4.3 ─► 4.4 headless end-to-end  =  FIRST DEMOABLE BUILD
4.4 ─► Phase 5 (UI, privacy, session)  =  POLISHED DEMO
4.4 ─► Phase 6 (hand)      4.4 ─► Phase 7 (BLE)      4.4 ─► Phase 8 (USB, evidence)
5 + 6 + 7 + 8 ─► Phase 9 (hardening, packaging, release)
```
Phases 6, 7 and 8 are independent of each other; do them in any order after Phase 4.4, but only after Phase 5 if you want them visible in the UI.

### 0.4 Technology rules

No library enters the project before the milestone that needs it. Each milestone's guidance states why it is needed. Libraries are added to `requirements.txt` only in that milestone, and `requirements-lock.txt` (from `pip freeze`) is refreshed at each phase checkpoint.

---

# PHASE 0 — Project Setup & Baseline

**Branch:** `phase-0-setup`

## Milestone 0.1 — Repository, identity guard, ignore rules, first push

**1. Milestone Name:** Initialise the Git repository, connect it to GitHub, and make the first safe push.

**2. Objective:** Create a clean repository whose history contains only your authorship, that cannot accidentally capture secrets or camera data, and that is connected to `origin`. This is the rollback base for the whole project.

**3. Tasks to Complete**
- [ ] `git init` in `C:\Users\HP\projects\silentwatch`, set default branch `main`.
- [ ] Set repo-local identity to your name and email.
- [ ] Add `origin` = `https://github.com/shailkamtikar/silentwatch.git`.
- [ ] Create `.gitignore` (global never-commit list above).
- [ ] Create `LICENSE` (MIT, your name, 2026) and a short `README.md` stub (what it is, status "prototype").
- [ ] Move `SILENTWATCH_Knowledge_Book.md` and this playbook into `docs/`.
- [ ] Install the `commit-msg` hook that rejects `Co-authored-by:` trailers.
- [ ] First commit on `main`, push, then create `phase-0-setup`.

**4. Files / Modules Affected:** `.gitignore`, `LICENSE`, `README.md`, `docs/SILENTWATCH_Knowledge_Book.md`, `docs/PLAYBOOK.md`, `.git/hooks/commit-msg` (local only, not versioned).

**5. Implementation Guidance**
- PowerShell:
  ```powershell
  git init -b main
  git config user.name "Shail Kamtikar"
  git config user.email "shailkamtikar@gmail.com"
  git remote add origin https://github.com/shailkamtikar/silentwatch.git
  ```
- Hook (`.git/hooks/commit-msg`, plain `sh`, Git for Windows runs it):
  ```sh
  #!/bin/sh
  if grep -qi '^co-authored-by:' "$1"; then
    echo "Blocked: remove Co-authored-by trailer"; exit 1
  fi
  ```
- Authenticate pushes with the already-logged-in `gh` account (`gh auth status` shows `shailkamtikar`). No token goes into any file.
- Hooks are not versioned; re-create it after any fresh clone.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T0.1-01 | Remote connected | Repo initialised | `git remote -v` | `origin` fetch/push = the silentwatch URL | ☐ |
| T0.1-02 | Ignore rules work (negative) | `.gitignore` present | Create `.venv/x`, `data/clip.mp4`, `a.db`, `.env`; `git status` | None of them listed as untracked | ☐ |
| T0.1-03 | Identity correct | Config set | `git log -1 --format="%an <%ae>"` after commit | `Shail Kamtikar <shailkamtikar@gmail.com>` | ☐ |
| T0.1-04 | Hook blocks trailer (negative) | Hook installed | `git commit --allow-empty -m "x" -m "Co-Authored-By: Foo <a@b.c>"` | Commit rejected with "Blocked" message | ☐ |
| T0.1-05 | Hook allows normal commit | Hook installed | `git commit --allow-empty -m "chore: test"` then `git reset --soft HEAD~1` | Commit succeeds | ☐ |
| T0.1-06 | Push works | Commit exists | `git push -u origin main` | Branch visible on GitHub | ☐ |
| T0.1-07 | Edge: secrets scan | Files staged | `git diff --cached --name-only`, search for `.env`, `*.db` | Nothing sensitive staged | ☐ |

**7. Verification Checklist**
- [ ] `git ls-remote origin` lists `refs/heads/main`.
- [ ] GitHub page shows README, LICENSE, `docs/`.
- [ ] Contributors graph shows only you.
- [ ] `phase-0-setup` branch exists locally and remotely.

**8. Completion Criteria:** All T0.1 rows PASS; `main` pushed; no ignored item tracked.

**9. Git Checkpoint**
```powershell
git status
git add .
git commit -m "chore: initialise repository, licence, ignore rules, docs (M0.1)"
git push -u origin main
git switch -c phase-0-setup
git tag -a m0.1 -m "M0.1 repo baseline"
git push origin phase-0-setup m0.1
```
*Do not commit:* `.env`, `*.db`, `data/`, `.venv/`, anything outside the list in 0.2.

**10. Rollback / Recovery:** This is the first commit, so there is nothing earlier to return to. If a bad file was pushed: remove it with `git rm --cached <file>`, add it to `.gitignore`, commit, push. If a **secret** was pushed, revoke the secret first (rewriting history does not un-leak it), then clean history with the standard ladder only on this still-solo repo.

---

## Milestone 0.2 — Python project skeleton and test harness

**Requires:** M0.1.

**1. Milestone Name:** Virtual environment, package skeleton, and a passing test run.

**2. Objective:** A reproducible environment where `python -m pytest` runs green on an empty but correctly structured `src/silentwatch` package, so every later milestone has a place to land and a way to be tested.

**3. Tasks to Complete**
- [ ] Create `.venv` with Python 3.12 (`py -3.12 -m venv .venv`).
- [ ] Create `pyproject.toml` (src layout, name `silentwatch`, `requires-python = ">=3.11,<3.13"`).
- [ ] Create package folders from Book §12 that are needed now: `src/silentwatch/{__init__,main}.py`, `config/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`, `docs/`.
- [ ] Add `requirements.txt` (runtime: empty for now) and `requirements-dev.txt` (`pytest`).
- [ ] Add a smoke test and a `python -m silentwatch --version` entry point.
- [ ] Add `docs/testing.md` with the test-ID convention (`T<phase>.<n>-NN`).

**4. Files / Modules Affected:** `pyproject.toml`, `requirements*.txt`, `src/silentwatch/__init__.py`, `src/silentwatch/__main__.py`, `src/silentwatch/main.py`, `tests/unit/test_smoke.py`, `docs/testing.md`.

**5. Implementation Guidance**
- Python 3.12 is already installed; the Book recommends 3.11 or 3.12 and asks for pinning. A venv keeps the global interpreter untouched (it currently has numpy, onnxruntime, pillow).
- `pytest` is required for the Book's testing plan (§18) and is the only dependency added now.
- Install the package editable: `pip install -e .` so tests import `silentwatch` exactly as the app does.
- Version string lives in one place (`__init__.__version__ = "0.0.1"`).
- Commands:
  ```powershell
  py -3.12 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install -U pip
  pip install -e . -r requirements-dev.txt
  python -m pytest -q
  ```

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T0.2-01 | Package imports | venv active, editable install | `python -c "import silentwatch; print(silentwatch.__version__)"` | Prints `0.0.1` | ☐ |
| T0.2-02 | Entry point | Same | `python -m silentwatch --version` | Prints version, exit code 0 | ☐ |
| T0.2-03 | Test suite runs | Same | `python -m pytest -q` | 1+ passed, 0 failed | ☐ |
| T0.2-04 | Wrong interpreter (negative) | Global Python | `py -3.12 -c "import silentwatch"` outside venv | `ModuleNotFoundError` (proves isolation) | ☐ |
| T0.2-05 | Fresh clone reproducibility | Clone to a temp folder | Create venv, `pip install -e . -r requirements-dev.txt`, run pytest | Passes without manual steps | ☐ |
| T0.2-06 | Dependency health | venv active | `pip check` | "No broken requirements found" | ☐ |
| T0.2-07 | Edge: ignore | After running | `git status` | No `.venv`, `.pytest_cache`, `__pycache__` listed | ☐ |

**7. Verification Checklist**
- [ ] T0.2-01..07 PASS.
- [ ] `requirements-dev.txt` lists only what is used.
- [ ] README has a "Quick start" with the exact commands above.

**8. Completion Criteria:** A fresh clone reaches a green `pytest` using only the README.

**9. Git Checkpoint**
```powershell
git status
git add .
git commit -m "chore: python skeleton, pytest harness, test-ID convention (M0.2)"
git push origin phase-0-setup
git tag -a m0.2 -m "M0.2 skeleton"; git push origin m0.2
```
*Do not commit:* `.venv/`, caches, `*.egg-info/`.

**10. Rollback / Recovery:** `git revert <hash>` or `git reset --hard m0.1; git push --force-with-lease origin phase-0-setup`. Delete and re-create `.venv` if the environment is corrupted (it is disposable).

---

## Milestone 0.3 — Hardware audit and dependency compatibility spike

**Requires:** M0.2.

**1. Milestone Name:** Book Phase 0 audit, plus proof that every planned library installs and imports together.

**2. Objective:** Turn the earlier manual audit into a repeatable script and verify, before writing real code, that OpenCV, MediaPipe, Bleak, PySide6 and pywin32 coexist on Python 3.12. Finding a conflict now is cheap; finding it in Phase 5 is not.

**3. Tasks to Complete**
- [ ] `scripts/audit_hardware.ps1`: OS build, CPU, RAM, camera device, Bluetooth adapter, paired phone, sensors, presence-sensing registry key, battery, privacy setting. Output to `docs/hardware-baseline.md`.
- [ ] `scripts/smoke_imports.py`: import and print version of `cv2`, `mediapipe`, `bleak`, `PySide6.QtWidgets`, `win32api`, `sqlite3`.
- [ ] Install candidates in a **throwaway** venv (`.venv-spike`, git-ignored), run the smoke script, record results.
- [ ] Decide the single OpenCV package (see guidance) and write the decision to `docs/decisions.md`.
- [ ] Add webcam facts: supported resolutions/FPS found via a 10-line OpenCV probe.

**4. Files / Modules Affected:** `scripts/audit_hardware.ps1`, `scripts/smoke_imports.py`, `scripts/probe_camera.py`, `docs/hardware-baseline.md`, `docs/decisions.md`, `.gitignore` (add `.venv-spike/`).

**5. Implementation Guidance**
- The pip dry run resolved `mediapipe 1.2.3`, `opencv-python 5.1.0.95` **and** `opencv-contrib-python 5.1.0.95` together. Two OpenCV wheels both provide `cv2` and can overwrite each other. Install only `opencv-contrib-python` (MediaPipe depends on it) and do not install plain `opencv-python`; record this in `decisions.md`.
- `pywin32` is justified for the Phase 5/8 Windows notifications (session lock/unlock, device arrival) which `ctypes` can do but with more boilerplate. `LockWorkStation` itself will use `ctypes`.
- `bleak` pulls the `winrt-*` packages it needs; do not install them separately.
- Model files are **not** bundled with pip wheels in every case; note which MediaPipe tasks need a downloaded `.task` file (needed for Phase 4.2 and 6.1).
- Run from the spike venv:
  ```powershell
  py -3.12 -m venv .venv-spike
  .\.venv-spike\Scripts\python -m pip install opencv-contrib-python mediapipe bleak PySide6-Essentials pywin32
  .\.venv-spike\Scripts\python scripts\smoke_imports.py
  .\.venv-spike\Scripts\python -m pip check
  ```

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T0.3-01 | Audit script output | Windows 11 | Run `audit_hardware.ps1` | `hardware-baseline.md` lists camera, BT adapter, phone, no sensors | ☐ |
| T0.3-02 | All libs import | Spike venv | `smoke_imports.py` | Each prints a version; exit 0 | ☐ |
| T0.3-03 | No dependency conflicts | Spike venv | `pip check` | No broken requirements | ☐ |
| T0.3-04 | Single `cv2` (negative) | Spike venv | `pip list \| findstr opencv` | Only `opencv-contrib-python` present | ☐ |
| T0.3-05 | Camera probe | Webcam free, shutter open | `probe_camera.py` | Reports ≥ 640x480 supported, frame returned | ☐ |
| T0.3-06 | Camera shutter/blocked (failure) | Cover lens or disable camera in privacy settings | Run probe | Reports a clear failure, no crash/hang | ☐ |
| T0.3-07 | Missing optional hardware | Sensor class empty | Run audit | Marks "not available" rather than erroring | ☐ |
| T0.3-08 | Edge: script idempotent | Run twice | Compare outputs | Same content aside from timestamp | ☐ |

**7. Verification Checklist**
- [ ] `docs/hardware-baseline.md` committed with real values from your laptop.
- [ ] `decisions.md` records OpenCV package choice and Python 3.12 pin.
- [ ] `.venv-spike` is untracked and can be deleted.

**8. Completion Criteria:** All libraries import together on your machine, the camera yields a frame, and decisions are documented.

**9. Git Checkpoint**
```powershell
git status
git add .
git commit -m "docs(baseline): hardware audit, dependency spike, decisions (M0.3)"
git push origin phase-0-setup
git tag -a m0.3 -m "M0.3 baseline audit"; git push origin m0.3
```
*Do not commit:* `.venv-spike/`, captured frames from the probe, your serial numbers or Bluetooth MAC addresses in the audit output (redact them).

**10. Rollback / Recovery:** `git revert <hash>`; audit docs have no runtime impact, so rollback is low risk.

---

## Phase 0 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 0.1, 0.2, 0.3 ☐ |
| Tests passed | T0.1-01..07, T0.2-01..07, T0.3-01..08 ☐ |
| Known issues | (list, e.g. "camera shutter test not possible, no physical shutter") |
| Git commit / hash | `________` tag `phase-0-complete` |
| Overall verification | Fresh clone → venv → pytest green; audit documented; authorship check clean |
| **Go / No-Go for Phase 1** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-0-setup -m "merge: phase 0 complete"
git push origin main
git tag -a phase-0-complete -m "Phase 0 done"; git push origin phase-0-complete
```

---

# PHASE 1 — Foundation: Config, Event Store, Windows Lock

**Branch:** `phase-1-foundation` (create from updated `main`). Order inside the phase: config → events → lock, because lock actions must be logged.

## Milestone 1.1 — Configuration system

**Requires:** Phase 0 complete.

**1. Milestone Name:** Typed, validated configuration with safe defaults.

**2. Objective:** All thresholds and timers from the Book ("make all automatic locking thresholds configurable") live in one validated config object, so later modules never hard-code numbers.

**3. Tasks to Complete**
- [ ] `config/default.toml` with sections `[camera]`, `[obstruction]`, `[presence]`, `[policy]`, `[privacy]`, `[logging]`.
- [ ] Python dataclasses mirroring those sections with range validation.
- [ ] Loader: defaults (read with stdlib `tomllib`) merged with user overrides from `%APPDATA%\SilentWatch\settings.json`.
- [ ] Reject invalid values with a clear error and fall back to defaults.
- [ ] Defaults per Book: 640x480, 5 FPS analysis, absence-pending 3 s, lock-after-absence 10 s, obstruction debounce 1.0 s, mode `balanced`, snapshots **off**.

**4. Files / Modules Affected:** `config/default.toml`, `src/silentwatch/config/{__init__,models,loader}.py`, `tests/unit/test_config.py`.

**5. Implementation Guidance**
- `tomllib` is stdlib in 3.11+, so no new dependency. User overrides use JSON because the stdlib can write JSON but not TOML.
- Validate with plain dataclass `__post_init__` checks; do not add pydantic (not needed, one more dependency to license-audit).
- Config object is immutable (`frozen=True`); changes produce a new object.
- Policy code will receive the config by injection, never read files itself (needed for testability).

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T1.1-01 | Defaults load | No user file | `load_config()` | Values match `default.toml`; mode `balanced`; snapshots off | ☐ |
| T1.1-02 | Override applied | User JSON sets `absence_lock_s=20` | Load | Value 20, others default | ☐ |
| T1.1-03 | Out-of-range rejected | `absence_lock_s=-5` | Load | Error logged, default used | ☐ |
| T1.1-04 | Wrong type | `fps="fast"` | Load | Error logged, default used | ☐ |
| T1.1-05 | Unknown key | Extra key in JSON | Load | Ignored with warning, no crash | ☐ |
| T1.1-06 | Corrupt JSON (failure) | File contains `{bad` | Load | Defaults used, app continues, event noted | ☐ |
| T1.1-07 | Missing settings dir (edge) | `%APPDATA%\SilentWatch` absent | Load | Directory created or defaults used silently | ☐ |
| T1.1-08 | Immutability | Loaded config | Try assigning a field | `FrozenInstanceError` | ☐ |
| T1.1-09 | Safety bound | `obstruction_debounce_s=0` | Load | Rejected (must be ≥ 0.2 s) so a single frame can never lock | ☐ |

**7. Verification Checklist**
- [ ] `pytest tests/unit/test_config.py -q` all green.
- [ ] No magic numbers duplicated outside `default.toml`.
- [ ] Your real `settings.json` is not in the repo.

**8. Completion Criteria:** Config loads, validates, falls back safely; ≥ 9 tests pass.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(config): typed validated configuration with defaults (M1.1)"
git push origin phase-1-foundation
git tag -a m1.1 -m "M1.1 config"; git push origin m1.1
```
*Do not commit:* any `settings.json` from `%APPDATA%`.

**10. Rollback / Recovery:** `git revert <hash>`, or `git reset --hard phase-0-complete` on the phase branch then `git push --force-with-lease origin phase-1-foundation`.

---

## Milestone 1.2 — SQLite event store

**Requires:** M1.1.

**1. Milestone Name:** Local, minimal, schema-versioned event log.

**2. Objective:** Persist security-relevant events (Book §13) so every lock has an explainable reason and the UI can later show history.

**3. Tasks to Complete**
- [ ] `events` table: `id, timestamp_utc, event_type, severity, confidence, source, details_json, action_taken`.
- [ ] Also create `settings` and `camera_calibration` tables now (empty) so migrations stay simple later.
- [ ] Schema version via `PRAGMA user_version`; forward migration function.
- [ ] API: `append(event)`, `recent(n)`, `query(type, since)`, `purge_older_than(days)`, `delete_all()`.
- [ ] Database at `%APPDATA%\SilentWatch\silentwatch.db`; WAL mode; single writer thread or lock.
- [ ] Never store frames or personal data in `details_json`.

**4. Files / Modules Affected:** `src/silentwatch/storage/{database,events,retention}.py`, `tests/unit/test_events.py`, `tests/integration/test_db_concurrency.py`.

**5. Implementation Guidance**
- `sqlite3` is stdlib (Book: SQLite is sufficient). Use parameterised queries only; never format SQL with strings.
- Event types are an `Enum` (`OWNER_ABSENT_CONFIRMED`, `OBSTRUCTION_CONFIRMED`, `CAMERA_UNAVAILABLE`, `LOCK_REQUESTED`, `LOCK_RESULT`, …) so typos are impossible.
- Timestamps in UTC ISO-8601; UI converts to local time.
- Database errors must never crash the monitoring loop: catch, log to the file logger, keep a bounded in-memory fallback queue.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T1.2-01 | Create schema | No DB | Open store | Tables exist; `user_version` = 1 | ☐ |
| T1.2-02 | Append + read | Open store | Append 3 events, `recent(3)` | Returned in newest-first order, fields intact | ☐ |
| T1.2-03 | Query filter | Mixed events | `query(type=LOCK_RESULT)` | Only that type | ☐ |
| T1.2-04 | SQL injection (security) | Open store | Append event with `'; DROP TABLE events;--` in details | Stored as text, table intact | ☐ |
| T1.2-05 | Retention purge | Events 40 days old and today | `purge_older_than(30)` | Old gone, new kept | ☐ |
| T1.2-06 | Delete all | Events exist | `delete_all()` | Zero rows, schema intact | ☐ |
| T1.2-07 | Concurrent writes (integration) | Two threads | 1000 appends each | All 2000 stored, no "database is locked" crash | ☐ |
| T1.2-08 | Corrupted DB (failure) | Truncate DB file | Open store | Corrupt file renamed to `.corrupt`, new DB created, event logged | ☐ |
| T1.2-09 | Disk full (failure) | Simulate `OperationalError` | Append | No exception escapes; fallback queue holds event | ☐ |
| T1.2-10 | Migration (schema validation) | DB with version 0 | Open | Migrated to current; data kept | ☐ |

**7. Verification Checklist**
- [ ] Open the DB with a SQLite viewer and confirm columns match Book §13.
- [ ] No frame data or names in any `details_json` produced by tests.
- [ ] M1.1 tests still pass (regression).

**8. Completion Criteria:** All tests PASS and the monitoring-loop contract "storage failure never crashes the app" is proven.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(storage): sqlite event store with retention and migrations (M1.2)"
git push origin phase-1-foundation
git tag -a m1.2 -m "M1.2 events"; git push origin m1.2
```
*Do not commit:* `*.db`, `*.db-wal`, `*.db-shm`, `*.corrupt`.

**10. Rollback / Recovery:** `git revert <hash>` or reset to `m1.1`. Local DB files are disposable in development; delete `%APPDATA%\SilentWatch\silentwatch.db` if a migration experiment corrupts it.

---

## Milestone 1.3 — Windows lock service (real lock)

**Requires:** M1.1, M1.2.

**1. Milestone Name:** Call the real `LockWorkStation` safely, with dry-run and logging.

**2. Objective:** Prove the project's core action: lock the real Windows session (Book Phase 1, §8.1). Provide a dry-run mode so tests and development never lock the machine unexpectedly.

**3. Tasks to Complete**
- [ ] `WindowsLockService.lock(reason)`; returns a result object (`requested=True/False`, `win32_error`).
- [ ] Uses `ctypes.windll.user32.LockWorkStation()`; checks return value and `GetLastError`.
- [ ] `dry_run` flag from config; in dry run, log the event but do not call the API.
- [ ] Minimum interval between lock requests (cooldown, default 5 s) to prevent lock loops.
- [ ] Logs `LOCK_REQUESTED` and `LOCK_RESULT` events with the reason.
- [ ] CLI: `python -m silentwatch.tools.lock_test --delay 5` and `--dry-run`.

**4. Files / Modules Affected:** `src/silentwatch/windows/lock.py`, `src/silentwatch/tools/lock_test.py`, `tests/unit/test_lock.py`.

**5. Implementation Guidance**
- `ctypes` is stdlib; no new dependency. Wrap the DLL call behind an injected callable so unit tests can fake it.
- A successful return means the lock was *requested*, not that every state change finished (Book §8.1). Never claim more.
- Do **not** build any fake overlay or full-screen window as a lock (Book §14 rule 12).
- Save all work before the manual test; the real lock will interrupt your session. Unlock with your normal Windows sign-in.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T1.3-01 | Unit: API called | Fake DLL returns 1 | `lock("test")` | Fake called once; result `requested=True` | ☐ |
| T1.3-02 | Unit: API failure | Fake returns 0, error 5 | `lock("test")` | `requested=False`, error recorded, no exception | ☐ |
| T1.3-03 | Dry-run (negative) | `dry_run=true` | `lock("test")` | DLL never called; event logged as dry-run | ☐ |
| T1.3-04 | Cooldown | Two calls within 1 s | Call twice | Second suppressed, logged as `LOCK_SUPPRESSED` | ☐ |
| T1.3-05 | Real lock (manual integration) | Work saved | `lock_test --delay 5` | Windows lock screen appears; unlock with PIN works | ☐ |
| T1.3-06 | Event trail | After T1.3-05 | `recent(5)` | `LOCK_REQUESTED` + `LOCK_RESULT` with reason | ☐ |
| T1.3-07 | Edge: already locked | Screen locked (run from scheduled task) | Call | No crash; result logged | ☐ |
| T1.3-08 | Security: no credentials | Code review | Search source for `password`, `pin` | No handling of credentials | ☐ |
| T1.3-09 | Regression | Earlier tests | `pytest -q` | M1.1/M1.2 still green | ☐ |

**7. Verification Checklist**
- [ ] The *real* Windows lock screen appears, not a custom window.
- [ ] Unlock needs normal Windows authentication.
- [ ] Event log shows the reason string.
- [ ] Default config has `dry_run = false` only for the lock tool; the main app default for development is `dry_run = true` until M4.4.

**8. Completion Criteria:** Manual real lock verified once on your laptop and logged; all automated tests PASS.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(windows): real LockWorkStation service with dry-run and cooldown (M1.3)"
git push origin phase-1-foundation
git tag -a m1.3 -m "M1.3 lock"; git push origin m1.3
```
*Do not commit:* test event databases.

**10. Rollback / Recovery:** `git revert <hash>`. If a lock loop ever trapped you in development, sign in normally; the 5 s cooldown and dry-run default exist so this cannot spin.

---

## Phase 1 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 1.1, 1.2, 1.3 ☐ |
| Tests passed | T1.1-01..09, T1.2-01..10, T1.3-01..09 ☐ |
| Known issues | |
| Git commit / hash | `________` tag `phase-1-complete` |
| Overall verification | Config → store → real lock works end to end; coverage of storage failure paths |
| **Go / No-Go for Phase 2** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-1-foundation -m "merge: phase 1 complete"
git push origin main
git tag -a phase-1-complete -m "Phase 1 done"; git push origin phase-1-complete
```

---

# PHASE 2 — Camera Capture & Health

**Branch:** `phase-2-camera` (from updated `main`). Book reference: §8.2, §5.2-F, Roadmap Phase 2.

## Milestone 2.1 — Camera capture service and preview tool

**Requires:** Phase 1 complete.

**1. Milestone Name:** Open the HP webcam, deliver timestamped frames, release it cleanly.

**2. Objective:** A `CameraCaptureService` that runs on its own thread, produces frames at a modest rate, and can be started and stopped without leaving the camera locked.

**3. Tasks to Complete**
- [ ] Add `opencv-contrib-python` to `requirements.txt` (single OpenCV package, per M0.3 decision).
- [ ] Benchmark `cv2.CAP_DSHOW` vs `cv2.CAP_MSMF` on your camera (time-to-first-frame, stability); record the winner in `docs/decisions.md`.
- [ ] `Frame` dataclass: `image (BGR ndarray)`, `monotonic_ts`, `index`, `width`, `height`.
- [ ] Capture thread with bounded queue (drop oldest) and target 640x480, analysis FPS from config.
- [ ] `start()`, `stop()` (releases device, joins thread), context manager support.
- [ ] `tools/camera_preview.py`: shows live window and a visible "camera in use" text; `q` quits.

**4. Files / Modules Affected:** `src/silentwatch/camera/capture.py`, `src/silentwatch/camera/frame.py`, `src/silentwatch/tools/camera_preview.py`, `tests/unit/test_capture.py`, `docs/decisions.md`, `requirements.txt`.

**5. Implementation Guidance**
- OpenCV is the Book's first-prototype capture layer; deterministic and enough for obstruction analysis.
- Abstract the source behind a `FrameSource` protocol (`read() -> (ok, ndarray)`), so Phases 3-4 can replay recorded clips and tests need no camera.
- Request 640x480 once; verify actual size from the first frame (webcams may ignore requests).
- Only **one** capture handle in the process (Book §15).
- Use `time.monotonic()` for timestamps, not wall-clock.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T2.1-01 | Start/stop | Camera free | Start, run 5 s, stop | Frames received; camera LED off after stop | ☐ |
| T2.1-02 | Frame metadata | Running | Read 10 frames | Increasing index and monotonic timestamps | ☐ |
| T2.1-03 | Rate limiting | FPS config 5 | Count frames in 10 s | ≈ 50 (±15 %) | ☐ |
| T2.1-04 | Resource release (edge) | Start/stop 20 times | Loop | No handle leak; last start still works | ☐ |
| T2.1-05 | No camera (failure) | Index 99 / device disabled | Start | Clear error object, no hang, no traceback to user | ☐ |
| T2.1-06 | Queue overflow | Slow consumer | Consume 1 fps | Memory flat; oldest frames dropped | ☐ |
| T2.1-07 | Fake source (unit) | `FrameSource` stub | Run service | Works without hardware (CI-friendly) | ☐ |
| T2.1-08 | Double start (validation) | Running | `start()` again | Idempotent or clear error | ☐ |
| T2.1-09 | Privacy | Preview tool | Run | On-screen "camera in use" indicator visible | ☐ |

**7. Verification Checklist**
- [ ] Task Manager shows no growing memory over 5 minutes of preview.
- [ ] Windows camera privacy indicator turns on and off with start/stop.
- [ ] Backend decision recorded with measured numbers.

**8. Completion Criteria:** Stable start/stop cycles on real hardware plus hardware-free unit tests.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(camera): capture service with frame source abstraction (M2.1)"
git push origin phase-2-camera
git tag -a m2.1 -m "M2.1 capture"; git push origin m2.1
```
*Do not commit:* captured frames, screenshots of your room/face.

**10. Rollback / Recovery:** `git revert <hash>` or reset to `phase-1-complete`. If the camera stays "in use" after a crash, close Python processes (`Get-Process python | Stop-Process`) and replug/disable-enable the camera in Device Manager.

---

## Milestone 2.2 — Camera health monitor

**Requires:** M2.1.

**1. Milestone Name:** Detect frozen feed, read failures, timestamp gaps and format changes.

**2. Objective:** Produce `CAMERA_UNAVAILABLE` and `CAMERA_FROZEN` signals (Book §5.2-F), clearly separated from tampering.

**3. Tasks to Complete**
- [ ] `CameraHealthMonitor` consuming frames/read results, emitting health states: `OK`, `FROZEN`, `UNAVAILABLE`, `FORMAT_CHANGED`.
- [ ] Frozen = N consecutive identical frame hashes (config, default 10 frames) *and* sensor noise absent.
- [ ] Unavailable = M consecutive read failures (default 5) or device-removed.
- [ ] Timestamp gap detection (frame interval > 5× expected).
- [ ] Emits events into the event store; never decides to lock (policy does).

**4. Files / Modules Affected:** `src/silentwatch/camera/health.py`, `tests/unit/test_health.py`, `tests/fixtures/` (synthetic frames).

**5. Implementation Guidance**
- Hash a downscaled grayscale frame (e.g. 64x48) with `hashlib.blake2b` for speed. Identical hashes alone can occur with a perfectly static scene on some cameras; real webcams add noise, but test this on your camera and record the result.
- Keep the monitor pure (inputs → state), with an injected clock.
- A privacy-shutter black frame is *valid* video, not a failure; do not label it `UNAVAILABLE`.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T2.2-01 | Healthy stream | Varying synthetic frames | Feed 100 | State `OK` | ☐ |
| T2.2-02 | Frozen | Identical frame ×10 | Feed | `FROZEN` after threshold, not before | ☐ |
| T2.2-03 | Unavailable | 5 failed reads | Feed | `UNAVAILABLE` | ☐ |
| T2.2-04 | Recovery | After UNAVAILABLE | Feed good frames | Back to `OK`, recovery event | ☐ |
| T2.2-05 | Resolution change | 640x480 then 320x240 | Feed | `FORMAT_CHANGED` | ☐ |
| T2.2-06 | Timestamp gap | 3 s pause | Feed | Gap flagged, not mistaken for freeze | ☐ |
| T2.2-07 | Static real scene (edge) | Real camera, nothing moving, 60 s | Run | No false `FROZEN` (record result) | ☐ |
| T2.2-08 | Black frame (edge) | Lens covered | Run | State stays `OK` (obstruction is Phase 3's job) | ☐ |
| T2.2-09 | Event logging | Any state change | Check store | One event per transition, no spam | ☐ |

**7. Verification Checklist**
- [ ] Unplug/disable the camera in Device Manager during a run: `UNAVAILABLE` appears within ~2 s.
- [ ] Re-enable: recovery event within the backoff time (see M2.3).
- [ ] Regression: M2.1 tests green.

**8. Completion Criteria:** Health states are correct on synthetic and real data, with measured false-freeze rate (target 0 in a 10-minute static test).

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(camera): health monitor for freeze, loss, format change (M2.2)"
git push origin phase-2-camera
git tag -a m2.2 -m "M2.2 health"; git push origin m2.2
```
*Do not commit:* recordings.

**10. Rollback / Recovery:** `git revert <hash>` / reset to `m2.1`.

---

## Milestone 2.3 — Reconnect with backoff and camera-contention matrix

**Requires:** M2.1, M2.2.

**1. Milestone Name:** Recover automatically from camera loss and document how other apps interfere.

**2. Objective:** Bounded re-initialisation (Book scenario F) and a measured contention matrix (Book Roadmap Phase 2; this settles missing-info item 6).

**3. Tasks to Complete**
- [ ] Reconnect loop: backoff 1 s, 2 s, 4 s … capped at 30 s, resets on success.
- [ ] Emit `CAMERA_RECOVERED` / `CAMERA_RETRY_EXHAUSTED` (never exceeds configured retries before settling to slow polling).
- [ ] Contention test matrix executed by hand and recorded in `docs/testing.md`: Windows Camera app, Windows Hello sign-in, Teams/Zoom/Meet-in-browser, Task Manager view.
- [ ] Decide a **camera ownership strategy**: if another app holds the camera, enter a `CAMERA_BUSY` state (not tampering), show a warning, retry slowly.

**4. Files / Modules Affected:** `src/silentwatch/camera/capture.py`, `src/silentwatch/camera/reconnect.py`, `docs/testing.md`, `tests/unit/test_reconnect.py`.

**5. Implementation Guidance**
- Backoff is deterministic and testable with an injected clock.
- On Windows, a second process often fails to open the device or gets black/stale frames; record exactly which on your camera.
- Always release before retry to avoid leaking handles.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T2.3-01 | Backoff schedule | Fake source always failing | Run clock | Waits 1,2,4,8,16,30,30 s | ☐ |
| T2.3-02 | Recovery resets backoff | Failure then success | Run | Next failure starts at 1 s again | ☐ |
| T2.3-03 | Real disable/enable | Device Manager toggle | Disable, wait, enable | App recovers automatically within 35 s | ☐ |
| T2.3-04 | Windows Camera app open | App running first | Start SILENTWATCH | `CAMERA_BUSY`, no crash, no false lock event | ☐ |
| T2.3-05 | SILENTWATCH first, then call app | Ours running | Open Meet/Zoom | Documented outcome (one of: shared, blocked, frozen) | ☐ |
| T2.3-06 | Windows Hello | Sign out/in | Observe | Documented outcome; app recovers after unlock | ☐ |
| T2.3-07 | Privacy toggle off | Settings → Camera access off | Start | Clear message, state `UNAVAILABLE`, no crash | ☐ |
| T2.3-08 | Stop during retry (edge) | Retrying | `stop()` | Thread exits within 1 s | ☐ |

**7. Verification Checklist**
- [ ] The contention table in `docs/testing.md` is filled with real observations.
- [ ] No thread or handle leaks after 10 minutes of disable/enable cycling.

**8. Completion Criteria:** Auto-recovery proven; behaviour with other camera apps documented; no false "tampering" from contention.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(camera): reconnect backoff and contention handling (M2.3)"
git push origin phase-2-camera
git tag -a m2.3 -m "M2.3 reconnect"; git push origin m2.3
```

**10. Rollback / Recovery:** `git revert <hash>` / reset to `m2.2`.

---

## Phase 2 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 2.1, 2.2, 2.3 ☐ |
| Tests passed | T2.1-01..09, T2.2-01..09, T2.3-01..08 ☐ |
| Known issues | (e.g. which apps hold the camera exclusively) |
| Git commit / hash | `________` tag `phase-2-complete` |
| Overall verification | 30-minute soak: no leak, no crash, correct states under unplug/disable |
| **Go / No-Go for Phase 3** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-2-camera -m "merge: phase 2 complete"
git push origin main
git tag -a phase-2-complete -m "Phase 2 done"; git push origin phase-2-complete
```

---

# PHASE 3 — Camera Obstruction Detection (the signature feature)

**Branch:** `phase-3-obstruction`. Book reference: §5, §21 ("prove a calibrated classical-vision detector first"). No machine-learning model in this phase.

## Milestone 3.1 — Feature extractor

**Requires:** Phase 2 complete (needs `Frame` and `FrameSource`; hardware only for the manual test).

**1. Milestone Name:** Pure functions that turn a frame into numeric image features.

**2. Objective:** Compute the Book's detection signals (§5.2 A-D) deterministically from a frame.

**3. Tasks to Complete**
- [ ] `FrameFeatures` dataclass: `mean_luma, median_luma, dark_pixel_ratio, global_variance, tile_variance_low_ratio, edge_density, laplacian_variance, entropy, frame_diff`.
- [ ] Downscale to ≤ 160x120 grayscale before computing (cost control).
- [ ] Tile grid 4x4 for local-variance map.
- [ ] Edge density via Canny with fixed thresholds applied to a normalised image.
- [ ] `frame_diff` = mean absolute difference vs previous analysed frame.
- [ ] Synthetic frame generators for tests (uniform black, uniform gray, noise, checkerboard, gradient, blurred).

**4. Files / Modules Affected:** `src/silentwatch/camera/integrity.py`, `tests/unit/test_features.py`, `tests/fixtures/synthetic.py`.

**5. Implementation Guidance**
- Use only OpenCV + numpy (already present). No SciPy/scikit-image.
- Keep functions side-effect free and fast (< 5 ms per frame at 160x120; test it).
- Normalise to 0..1 where possible; the classifier compares against calibration, not absolute values (Book §5.4).
- Expected behaviours: black frame → low mean, ~zero variance, ~zero edges; finger/cloth → low edges/variance, maybe not dark; dark room → low mean but still some noise/texture.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T3.1-01 | Black frame | Synthetic zeros | Extract | mean≈0, dark_ratio≈1, edges≈0, variance≈0 | ☐ |
| T3.1-02 | Checkerboard | Synthetic | Extract | High edge density, high entropy-ish | ☐ |
| T3.1-03 | Uniform mid-gray | Synthetic 128 | Extract | Low variance/edges, dark_ratio 0 (not dark but featureless) | ☐ |
| T3.1-04 | Blur reduces sharpness | Checkerboard vs Gaussian blur | Extract both | Laplacian variance lower for blurred | ☐ |
| T3.1-05 | Frame diff | Same frame twice vs two different | Extract | ≈0 vs clearly > 0 | ☐ |
| T3.1-06 | Dim textured scene (edge) | Checkerboard × 0.1 brightness | Extract | Mean low but edge density > uniform black | ☐ |
| T3.1-07 | Invalid input (failure) | `None`, empty array, 1-channel | Extract | Clear `ValueError`, no crash | ☐ |
| T3.1-08 | Performance | 1000 frames 640x480 | Time | Average < 5 ms/frame after downscale | ☐ |
| T3.1-09 | Real-camera smoke | Camera running | Print features for normal / covered | Plausible, recorded in docs | ☐ |
| T3.1-10 | Determinism | Same input twice | Extract | Identical outputs | ☐ |

**7. Verification Checklist**
- [ ] Hand/lights-off sample values are written into `docs/testing.md` (first real data).
- [ ] No feature relies on a single absolute threshold.

**8. Completion Criteria:** All features tested on synthetic data, speed target met, real-camera sanity values recorded.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(obstruction): frame feature extractor (M3.1)"
git push origin phase-3-obstruction
git tag -a m3.1 -m "M3.1 features"; git push origin m3.1
```

**10. Rollback / Recovery:** `git revert <hash>` / reset to `phase-2-complete`.

---

## Milestone 3.2 — Calibration and baseline storage

**Requires:** M3.1, M1.2.

**1. Milestone Name:** Learn what "normal" looks like on this camera in this room.

**2. Objective:** Capture a short baseline and store per-feature mean and standard deviation in `camera_calibration` (Book §5.4). Store numbers only, never frames.

**3. Tasks to Complete**
- [ ] `CalibrationRunner`: collect 5 s of frames, compute per-feature mean/std/min/max.
- [ ] Reject bad calibration: camera covered, too dark, frozen, too few frames.
- [ ] Persist to `camera_calibration(camera_id, resolution, baseline_features_json, calibrated_at)`.
- [ ] Invalidate when resolution or camera id changes; staleness warning after N days (config).
- [ ] CLI: `python -m silentwatch.tools.calibrate`.

**4. Files / Modules Affected:** `src/silentwatch/camera/calibration.py`, `src/silentwatch/storage/database.py` (use existing table), `src/silentwatch/tools/calibrate.py`, `tests/unit/test_calibration.py`.

**5. Implementation Guidance**
- Calibration success criteria: ≥ 20 frames, mean luma ≥ configured minimum, edge density above a floor, no freeze. If the user calibrates in the dark, refuse with a clear reason, otherwise later logic is poisoned.
- Store std as well as mean so the classifier can use z-scores; guard against zero std with a floor.
- Offer multiple profiles later (day/night) but ship one now.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T3.2-01 | Good baseline | Synthetic varied frames | Calibrate | Baseline stored with mean/std | ☐ |
| T3.2-02 | Covered camera (negative) | Black frames | Calibrate | Rejected: "camera appears covered" | ☐ |
| T3.2-03 | Too few frames | 5 frames only | Calibrate | Rejected | ☐ |
| T3.2-04 | Frozen camera | Identical frames | Calibrate | Rejected | ☐ |
| T3.2-05 | Persist and reload | After T3.2-01 | Restart store, load | Same values | ☐ |
| T3.2-06 | Resolution change (edge) | Calibrated at 640x480, now 1280x720 | Load | Marked invalid, recalibration requested | ☐ |
| T3.2-07 | Real desk calibration | Normal lighting | Run CLI | Succeeds; values saved | ☐ |
| T3.2-08 | No image data stored (privacy) | After calibration | Inspect DB | Only numbers present | ☐ |
| T3.2-09 | Zero std guard | Constant-feature input | Calibrate | No divide-by-zero, floor applied | ☐ |

**7. Verification Checklist**
- [ ] Open the DB and read the JSON: numeric only.
- [ ] Running calibration twice in the same conditions gives similar baselines (within a sensible spread; record it).

**8. Completion Criteria:** Baseline reliably created, rejected when invalid, and persisted.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(obstruction): calibration runner and baseline storage (M3.2)"
git push origin phase-3-obstruction
git tag -a m3.2 -m "M3.2 calibration"; git push origin m3.2
```
*Do not commit:* `*.db`, any calibration capture frames.

**10. Rollback / Recovery:** `git revert <hash>` / reset to `m3.1`; delete stale local calibration rows if schema changed.

---

## Milestone 3.3 — Explainable obstruction classifier with temporal debounce

**Requires:** M3.1, M3.2.

**1. Milestone Name:** Rule-based `NORMAL / POSSIBLE / PARTIAL / CONFIRMED_OBSTRUCTION` output.

**2. Objective:** Combine features against the baseline, require persistence, and explain every decision. Darkness alone must never confirm obstruction (Book §22). This emits events only; **no locking yet**.

**3. Tasks to Complete**
- [ ] Score each feature as a deviation from baseline (z-score or ratio).
- [ ] Rule set (starting point, tuned in M3.4): confirmed requires texture/edge/variance collapse **and** (dark *or* near-uniform) sustained for the debounce window; brightness-only drop → `POSSIBLE` at most.
- [ ] Partial: a large tile fraction lost structure while other tiles remain normal.
- [ ] State output includes `reasons: list[str]` and `feature_scores`.
- [ ] Hysteresis: separate enter/exit thresholds; clear after K normal frames.
- [ ] Debounce windows from config (default 1.0 s confirmed, strict 0.5 s).
- [ ] Emit `OBSTRUCTION_POSSIBLE / PARTIAL / CONFIRMED / CLEARED` events (deduplicated).

**4. Files / Modules Affected:** `src/silentwatch/camera/obstruction.py`, `tests/unit/test_obstruction.py`, config sections `[obstruction]`.

**5. Implementation Guidance**
- Explainability is a requirement (Book §10.3 "user can inspect why a lock occurred"); store the reasons string in the event.
- Pure and clock-injected for deterministic tests with scripted feature sequences.
- Handle auto-exposure: webcams brighten after covering ends; give "clearing" a short grace to avoid flapping.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T3.3-01 | Normal scene | Baseline-like features | Feed 5 s | `NORMAL`, no events | ☐ |
| T3.3-02 | Full cover | Black/featureless sequence | Feed 2 s | `CONFIRMED` after debounce, with reasons | ☐ |
| T3.3-03 | Lights off | Dark but textured/noisy features | Feed 10 s | Never `CONFIRMED`; at most `POSSIBLE` | ☐ |
| T3.3-04 | Single bad frame | One anomalous frame | Feed | Stays `NORMAL` | ☐ |
| T3.3-05 | Debounce boundary | Cover for 0.4 s vs 1.2 s | Feed | 0.4 s → no confirm, 1.2 s → confirm | ☐ |
| T3.3-06 | Partial cover | Half tiles featureless | Feed | `PARTIAL_OBSTRUCTION` | ☐ |
| T3.3-07 | Clearing | After confirmed, normal frames | Feed | `CLEARED` after K frames, no flapping | ☐ |
| T3.3-08 | Strict mode | `strict` config | Cover 0.6 s | Confirms sooner than balanced | ☐ |
| T3.3-09 | Missing baseline (failure) | No calibration | Classify | `UNKNOWN`, calibration requested | ☐ |
| T3.3-10 | Explainability | Any confirmed event | Read event | Contains reasons and scores | ☐ |
| T3.3-11 | Regression | Earlier suites | `pytest -q` | All green | ☐ |

**7. Verification Checklist**
- [ ] Live run with `--dry-run`: cover the lens with your hand; console prints `CONFIRMED` with reasons; no lock.
- [ ] Lights off in the room: no `CONFIRMED`.

**8. Completion Criteria:** Rule set passes synthetic and first live checks; every output is explainable.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(obstruction): explainable classifier with debounce and hysteresis (M3.3)"
git push origin phase-3-obstruction
git tag -a m3.3 -m "M3.3 classifier"; git push origin m3.3
```

**10. Rollback / Recovery:** `git revert <hash>` / reset to `m3.2`.

---

## Milestone 3.4 — Test-clip recorder, replay harness, threshold tuning

**Requires:** M3.3.

**1. Milestone Name:** Measure and tune the detector with a labelled test set (Book §18.1).

**2. Objective:** Turn "it seems to work" into numbers: detection latency, false-positive and false-negative rates per scenario, then tune thresholds.

**3. Tasks to Complete**
- [ ] `tools/record_clip.py --scenario hand_fast`: records 10-15 s of frames to `data/clips/<scenario>/<n>.npz` (git-ignored) plus a committed `tests/fixtures/clips_manifest.json` with labels and expected outcomes.
- [ ] Scenarios: normal, dim, lights_off, screen_brightness_change, hand_fast, hand_slow, finger, cloth, paper, partial, translucent, shutter_if_available.
- [ ] `tools/evaluate.py`: replays clips through the classifier, writes a results table to `docs/obstruction-results.md`.
- [ ] Tune thresholds; commit **only** the numbers in `config/default.toml`.
- [ ] Record ≥ 3 takes per covering scenario and 30 minutes of normal desk use.

**4. Files / Modules Affected:** `src/silentwatch/tools/{record_clip,evaluate}.py`, `tests/fixtures/clips_manifest.json`, `docs/obstruction-results.md`, `config/default.toml`, `data/` (ignored).

**5. Implementation Guidance**
- Recorded clips contain your face and room, so they are **never committed** (Book §14).
- Replay uses the `FrameSource` abstraction from M2.1.
- Suggested starting targets (adjust honestly, do not tune to hide failures): ≥ 95 % of opaque covers confirmed within 1.5 s; 0 false locks in 30 minutes of normal use; lights-off never confirmed.
- Document failures (e.g. translucent material) as known limits per Book §5.5.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T3.4-01 | Recorder output | Camera on | Record `hand_fast` | Clip file + manifest entry | ☐ |
| T3.4-02 | Replay determinism | Same clip twice | Evaluate | Identical results | ☐ |
| T3.4-03 | Opaque covers | hand/finger/cloth/paper clips | Evaluate | ≥ 95 % confirmed, latency table recorded | ☐ |
| T3.4-04 | Lights off | lights_off clips | Evaluate | 0 confirmations | ☐ |
| T3.4-05 | 30 min normal use | normal clip(s) | Evaluate | 0 confirmations (false-positive rate recorded) | ☐ |
| T3.4-06 | Translucent / partial (edge) | clips | Evaluate | Result recorded; limitation documented | ☐ |
| T3.4-07 | Screen brightness swing | clip | Evaluate | No confirmation | ☐ |
| T3.4-08 | Privacy guard | `git status` | Check | `data/` not tracked | ☐ |
| T3.4-09 | Regression after tuning | Unit tests | `pytest -q` | Still green with new thresholds | ☐ |

**7. Verification Checklist**
- [ ] `docs/obstruction-results.md` shows latency, FP and FN per scenario.
- [ ] Live check in a *different* lighting condition than calibration; note behaviour and recalibration advice.

**8. Completion Criteria:** Targets above are met (or the shortfall is documented with a plan); thresholds committed.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(obstruction): recorder, replay harness, tuned thresholds (M3.4)"
git push origin phase-3-obstruction
git tag -a m3.4 -m "M3.4 tuned"; git push origin m3.4
```
*Do not commit:* `data/clips/*`, any `.npz`/`.mp4` of you or your room.

**10. Rollback / Recovery:** `git revert <hash>` to restore previous thresholds; keep old values in `docs/obstruction-results.md` history.

---

## Phase 3 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 3.1, 3.2, 3.3, 3.4 ☐ |
| Tests passed | T3.1-01..10, T3.2-01..09, T3.3-01..11, T3.4-01..09 ☐ |
| Known issues | (translucent covers, shutter behaviour, exposure lag…) |
| Git commit / hash | `________` tag `phase-3-complete` |
| Overall verification | Results table meets targets; detector explainable; no frames in repo |
| **Go / No-Go for Phase 4** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-3-obstruction -m "merge: phase 3 complete"
git push origin main
git tag -a phase-3-complete -m "Phase 3 done"; git push origin phase-3-complete
```

---

# PHASE 4 — Policy Engine, Presence, Headless End-to-End

**Branch:** `phase-4-policy-presence`. Milestone 4.1 only needs Phase 1, but is placed here so it can consume real signals. This phase ends with the **first demoable build**.

## Milestone 4.1 — Policy engine core and state machine

**Requires:** Phase 1 complete (can be written before Phase 3, merged after).

**1. Milestone Name:** Pure, testable decision engine (Book §10).

**2. Objective:** One place decides actions from signals: states, rules, modes, cooldowns.

**3. Tasks to Complete**
- [ ] `states.py`: `INITIALIZING, CALIBRATING, MONITORING, OWNER_PRESENT, OWNER_ABSENT_PENDING, OWNER_ABSENT, SUSPICIOUS, TAMPERING_CONFIRMED, LOCK_REQUESTED, LOCKED, CAMERA_ERROR, RECOVERY`.
- [ ] `engine.py`: `handle(signal) -> list[Action]` with `Action ∈ {LOG, NOTIFY, LOCK}`; injected clock; no I/O.
- [ ] `rules.py`: rule table from Book §10.4 (obstruction confirmed → lock; partial + absent → lock; camera unavailable + absent (+phone, later) → lock; low brightness alone → never; frozen alone → retry/log).
- [ ] Modes: `strict`, `balanced` (default). Adaptive scoring deferred.
- [ ] Signals expire; deduplicated; lock cooldown (reuses M1.3) and "post-unlock grace" (default 10 s) so unlocking does not instantly relock.
- [ ] Every transition logged with reason.

**4. Files / Modules Affected:** `src/silentwatch/policy/{states,rules,engine}.py`, `tests/unit/test_policy.py`.

**5. Implementation Guidance**
- Explicit rules before weights (Book §21 "explainable rules before complex AI"). The Book's weight table is illustrative; adopt it only in a later "adaptive" milestone if time allows.
- Table-driven tests: each row = (initial state, signal sequence, expected actions).

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T4.1-01 | Obstruction confirmed | Balanced | Send signal | `LOCK` action once | ☐ |
| T4.1-02 | Low brightness only | Balanced | Send `LOW_BRIGHTNESS` | No lock | ☐ |
| T4.1-03 | Camera frozen alone | Balanced | Send | Retry/log, no lock | ☐ |
| T4.1-04 | Partial + absent | Balanced | Send both | Lock | ☐ |
| T4.1-05 | Camera unavailable, owner present | Balanced | Send | Warn, no lock | ☐ |
| T4.1-06 | Cooldown | Lock then obstruction again within window | Send | No second lock | ☐ |
| T4.1-07 | Post-unlock grace | Session just unlocked, still absent signal | Send | Waits grace before relock | ☐ |
| T4.1-08 | Strict vs balanced | Same signal | Both modes | Strict reacts sooner | ☐ |
| T4.1-09 | Signal expiry | Old signal | Advance clock | Ignored after expiry | ☐ |
| T4.1-10 | Oscillation guard | Rapid alternating signals | Feed | State does not flap | ☐ |
| T4.1-11 | Transition logging | Any transition | Read store | Logged with reason | ☐ |

**7. Verification Checklist**
- [ ] A diagram of the state machine in `docs/architecture.md` matches the code.
- [ ] No I/O or camera import inside `policy/`.

**8. Completion Criteria:** All Book §10.4 rules exist as passing tests.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(policy): state machine, rules, modes, cooldowns (M4.1)"
git push origin phase-4-policy-presence
git tag -a m4.1 -m "M4.1 policy"; git push origin m4.1
```

**10. Rollback / Recovery:** `git revert <hash>` / reset to `phase-3-complete`.

---

## Milestone 4.2 — Presence estimator (face detection)

**Requires:** M2.1, M4.1.

**1. Milestone Name:** Decide "someone is in front of the laptop", without identity.

**2. Objective:** Presence only (Book §6.1): detect a face/person with MediaPipe Face Detector and smooth the result. No recognition, no embeddings.

**3. Tasks to Complete**
- [ ] Add `mediapipe` to `requirements.txt`.
- [ ] `models/README.md` + `scripts/download_models.ps1` that downloads the Face Detector `.task` file and verifies SHA-256 (hash filled in after the first verified download).
- [ ] `PresenceEstimator.update(frame) -> PresenceObservation(face_count, max_confidence)`.
- [ ] Run at 5 FPS or gated (Stage 2) if CPU is high; measure.
- [ ] Hysteresis: present after 3 consecutive detections; absent only after config seconds.

**4. Files / Modules Affected:** `src/silentwatch/presence/estimator.py`, `scripts/download_models.ps1`, `models/README.md`, `tests/unit/test_presence.py`, `requirements.txt`.

**5. Implementation Guidance**
- MediaPipe is in the Book's stack for on-device face/hand perception and needs no cloud. Pin the version in `requirements-lock.txt`; its Python API changes between versions.
- Alternative if MediaPipe misbehaves: OpenCV Zoo YuNet through `cv2.FaceDetectorYN` (already in the OpenCV package). Record the decision.
- The detector input is the same frame the obstruction analyser uses; do not open the camera twice.
- Model files are git-ignored; only the script and hash are committed.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T4.2-01 | Face present | Real camera, you in front | Run 10 s | `face_count ≥ 1` stable | ☐ |
| T4.2-02 | Empty chair | You out of view | Run 10 s | `face_count = 0` | ☐ |
| T4.2-03 | Head turn / look down (edge) | You seated | Turn 2 s | Smoothed state stays present | ☐ |
| T4.2-04 | Two people | Another person beside you | Run | `face_count = 2` | ☐ |
| T4.2-05 | Poster/photo (limit) | Photo in front | Run | Detected as face (documented limit; presence is not authentication) | ☐ |
| T4.2-06 | Low light | Dim room | Run | Result recorded, no crash | ☐ |
| T4.2-07 | Model missing (failure) | Model file absent | Start | Clear message "run download_models.ps1", app continues without presence | ☐ |
| T4.2-08 | Hash mismatch (security) | Tampered model | Download script | Aborts with error | ☐ |
| T4.2-09 | Performance | 5 FPS | Measure | CPU within budget recorded | ☐ |
| T4.2-10 | Hysteresis unit test | Scripted observations | Feed | Transitions only after thresholds | ☐ |

**7. Verification Checklist**
- [ ] No face crops or embeddings stored.
- [ ] `models/*.task` is untracked.
- [ ] M2/M3 regressions green.

**8. Completion Criteria:** Presence stable with hysteresis; model integrity checked; performance recorded.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(presence): face-detection presence estimator with hysteresis (M4.2)"
git push origin phase-4-policy-presence
git tag -a m4.2 -m "M4.2 presence"; git push origin m4.2
```
*Do not commit:* model weights, frames.

**10. Rollback / Recovery:** `git revert <hash>`; `pip uninstall mediapipe` if it broke the environment, then recreate the venv from `requirements-lock.txt`.

---

## Milestone 4.3 — Owner-absence timer wired into policy

**Requires:** M4.1, M4.2.

**1. Milestone Name:** Absence pending → confirmed → lock request.

**2. Objective:** Implement Scenario A with the Book's state names and configurable timers (defaults: pending after 3 s, lock after 10 s absence; user-configurable).

**3. Tasks to Complete**
- [ ] Map `PresenceObservation` to `OWNER_PRESENT / PRESENCE_UNCERTAIN / OWNER_ABSENT_PENDING / OWNER_ABSENT_CONFIRMED` signals.
- [ ] Engine rule: confirmed absence beyond timeout → `LOCK`.
- [ ] Return from pending to present cancels the timer.
- [ ] A visible countdown signal (used by the UI later).
- [ ] Unknown person while owner absent increases urgency (shortens timer in strict mode). No identity claims: label "unrecognised presence" only if recognition exists (later), otherwise "someone present".

**4. Files / Modules Affected:** `src/silentwatch/policy/{rules,engine}.py`, `src/silentwatch/presence/estimator.py`, `tests/unit/test_absence.py`.

**5. Implementation Guidance**
- Hysteresis asymmetry: fast to "present" (3 detections), slow to "absent" (seconds).
- Do not lock when the camera is `UNAVAILABLE` solely because "no face"; absence needs a *working* camera (otherwise it's the camera-error rule).
- Debounce for the real-life "I leaned back" case; document the tuning.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T4.3-01 | Walk away | Scripted: present → none | Advance clock 12 s | Pending at 3 s, lock at 10 s | ☐ |
| T4.3-02 | Quick return | Absent 5 s, face returns | Feed | Timer cancelled, no lock | ☐ |
| T4.3-03 | Looks down 4 s | Present with gaps | Feed | No lock | ☐ |
| T4.3-04 | Camera error while no face | Unavailable + no face | Feed | No "absence" lock; camera rule applies | ☐ |
| T4.3-05 | Configurable timers | Config 20 s | Feed | Lock at 20 s | ☐ |
| T4.3-06 | Strict mode | Strict | Feed | Earlier lock | ☐ |
| T4.3-07 | Another person sits (no owner template yet) | Face present | Feed | No lock in MVP (presence ≠ identity); documented | ☐ |
| T4.3-08 | Regression | Earlier suites | `pytest -q` | Green | ☐ |

**7. Verification Checklist**
- [ ] Live dry-run: stand up, walk out of frame; log shows pending then `LOCK (dry-run)` at the configured time.

**8. Completion Criteria:** Scripted and live dry-run scenarios behave per Book §6.3.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(policy): owner absence timer and lock rule (M4.3)"
git push origin phase-4-policy-presence
git tag -a m4.3 -m "M4.3 absence"; git push origin m4.3
```

**10. Rollback / Recovery:** `git revert <hash>` / reset to `m4.2`.

---

## Milestone 4.4 — Headless end-to-end service (first demoable build)

**Requires:** M3.4, M4.1, M4.2, M4.3.

**1. Milestone Name:** Camera → analysis → policy → real lock, running as one process.

**2. Objective:** Wire everything and prove Book scenarios A, C, D, E, F on your laptop. This is the first build safe to demo.

**3. Tasks to Complete**
- [ ] `lifecycle.py`: start camera, calibration check, analysis loop, policy, lock service, event store, clean shutdown (Ctrl+C).
- [ ] CLI: `python -m silentwatch --headless [--dry-run] [--mode balanced]`.
- [ ] Startup rule: if no calibration, run it first; if camera unavailable, enter `CAMERA_ERROR` with retries.
- [ ] Safety: `--dry-run` default for the first live runs; explicit `--live` required for real locking.
- [ ] Console status line: state, obstruction state, presence, FPS.
- [ ] Post-unlock handling: reset timers, grace period.

**4. Files / Modules Affected:** `src/silentwatch/app/lifecycle.py`, `src/silentwatch/main.py`, `tests/integration/test_pipeline_replay.py`.

**5. Implementation Guidance**
- Replay integration test uses recorded or synthetic `FrameSource` + fake lock service, asserting the exact event sequence.
- Threading model: capture thread → bounded queue → analysis thread → policy (single-threaded decisions).
- Keep shutdown deterministic; verify no camera handle remains.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T4.4-01 | Scenario A live | Live mode, work saved | Walk away | Real lock at configured absence time | ☐ |
| T4.4-02 | Scenario C live | Live mode | Cover lens with hand | Real lock within ~1.5 s | ☐ |
| T4.4-03 | Scenario D live | Live mode | Lights off | No lock; warning logged at most | ☐ |
| T4.4-04 | Scenario E live | Seated, someone else covers camera | Cover | Lock (balanced mode) | ☐ |
| T4.4-05 | Scenario F live | Disable camera in Device Manager | Wait | `CAMERA_ERROR`, retries, no false tamper lock when present | ☐ |
| T4.4-06 | Replay integration | Recorded clips + fake lock | Run | Expected event sequence per clip | ☐ |
| T4.4-07 | Post-unlock | After lock → unlock | Observe | No immediate relock; grace works | ☐ |
| T4.4-08 | Clean exit | Ctrl+C | Observe | Camera released, DB closed, exit 0 | ☐ |
| T4.4-09 | 30-minute soak | Live dry-run | Normal work | 0 false locks, stable memory | ☐ |
| T4.4-10 | Event audit | After tests | Read store | Every lock has reason and state trail | ☐ |

**7. Verification Checklist**
- [ ] Record a short screen capture of scenarios A, C, D (demo rehearsal asset, kept **outside** the repo).
- [ ] CPU, RAM measured and noted in `docs/testing.md`.

**8. Completion Criteria:** All live scenarios pass with real Windows locks; soak test clean.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(app): headless end-to-end pipeline with live lock (M4.4)"
git push origin phase-4-policy-presence
git tag -a m4.4 -m "M4.4 first demoable build"; git push origin m4.4
```

**10. Rollback / Recovery:** `git revert <hash>`. Keep `--dry-run` as the safe fallback while diagnosing.

---

## Phase 4 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 4.1, 4.2, 4.3, 4.4 ☐ |
| Tests passed | T4.1-01..11, T4.2-01..10, T4.3-01..08, T4.4-01..10 ☐ |
| Known issues | |
| Git commit / hash | `________` tag `phase-4-complete` |
| Overall verification | Scenarios A, C, D, E, F demonstrated live; soak clean |
| **Go / No-Go for Phase 5 (and demo-readiness)** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-4-policy-presence -m "merge: phase 4 complete"
git push origin main
git tag -a phase-4-complete -m "Phase 4 done"; git push origin phase-4-complete
```

---

# PHASE 5 — Tray UI, Privacy Controls, Session Awareness

**Branch:** `phase-5-ui-privacy`. Book reference: §14, §8.6, §4.1 items 12-13. Keep the engine independent of the UI (Book §11).

## Milestone 5.1 — Tray app and monitoring indicator

**Requires:** Phase 4 complete.

**1. Milestone Name:** A visible tray icon that shows state and offers pause/resume/exit.

**2. Objective:** Meet the Book's rule that monitoring must be observable (not a hidden process): clear indicator, tray controls, no admin rights.

**3. Tasks to Complete**
- [ ] Add `PySide6-Essentials` to `requirements.txt`.
- [ ] `QSystemTrayIcon` with icons for: monitoring, paused, warning, camera error, locked.
- [ ] Menu: Open dashboard, Pause/Resume, Mode (Strict/Balanced), Run calibration, Quit.
- [ ] Engine runs in a worker thread; UI communicates by Qt signals/queues only.
- [ ] Icons in `assets/icons/` (original or properly licensed; list in the licence inventory).
- [ ] Single-instance guard (named mutex) so two copies never fight over the camera.

**4. Files / Modules Affected:** `src/silentwatch/app/tray.py`, `src/silentwatch/app/lifecycle.py`, `assets/icons/*`, `tests/unit/test_tray_state_mapping.py`.

**5. Implementation Guidance**
- PySide6 (LGPL/GPL/commercial): the Book flags licensing; using it dynamically as a library with the unmodified wheel is the usual LGPL route. Record this in the licence inventory (M9.4). If you want to avoid any Qt question, `CustomTkinter` + `pystray` is the lighter alternative, but both are valid; do not mix.
- Map engine state → icon in a pure function so it can be unit-tested without a display.
- Pause must release the camera (not just ignore frames).

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T5.1-01 | Tray appears | App started | Look at tray | Icon visible with tooltip state | ☐ |
| T5.1-02 | Pause | Running | Menu → Pause | Camera released (LED off), icon changes, no locks fire | ☐ |
| T5.1-03 | Resume | Paused | Resume | Monitoring restarts, calibration still valid | ☐ |
| T5.1-04 | State icons | Simulate each state | Unit test mapping | Correct icon per state | ☐ |
| T5.1-05 | Quit | Running | Quit | Process exits, camera released | ☐ |
| T5.1-06 | Single instance (negative) | App running | Launch second copy | Second exits with message | ☐ |
| T5.1-07 | Worker crash (failure) | Raise in worker | Observe | Tray shows error, app does not silently die | ☐ |
| T5.1-08 | No admin | Normal user | Start | Works without elevation | ☐ |
| T5.1-09 | Regression | Headless mode | `python -m silentwatch --headless --dry-run` | Still works | ☐ |

**7. Verification Checklist**
- [ ] Process visible in Task Manager under a clear name.
- [ ] Camera indicator behaviour consistent with tray state.

**8. Completion Criteria:** Tray fully controls the engine; indicator always truthful.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(ui): tray app with monitoring indicator and controls (M5.1)"
git push origin phase-5-ui-privacy
git tag -a m5.1 -m "M5.1 tray"; git push origin m5.1
```
*Do not commit:* `.ui` temp files, compiled caches.

**10. Rollback / Recovery:** `git revert <hash>` / reset to `phase-4-complete`; headless mode remains functional as a fallback.

---

## Milestone 5.2 — Dashboard: live preview, scores, event history

**Requires:** M5.1.

**1. Milestone Name:** A window that explains what the system sees and why it acted.

**2. Objective:** The demo centrepiece: live camera preview with obstruction score and presence state, plus an event-history table with a "why did it lock" detail view.

**3. Tasks to Complete**
- [ ] Dashboard window with: state banner, live preview (toggle), obstruction score bar, presence/countdown display.
- [ ] Event history view reading from the event store (filter by type/date).
- [ ] "Why" panel showing the stored reasons and feature scores for a selected lock.
- [ ] Preview is **off by default** and off while the window is closed (saves CPU, protects privacy).
- [ ] Frame handed to UI as a copy; no frame saved.

**4. Files / Modules Affected:** `src/silentwatch/ui/{dashboard,history}.py`, `tests/unit/test_history_model.py`.

**5. Implementation Guidance**
- Update the UI at ≤ 10 Hz even if analysis runs faster.
- History model is a thin wrapper over `EventStore.query`; test the model without Qt widgets.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T5.2-01 | Live preview | Dashboard open, preview on | Wave hand | Smooth image, score reacts | ☐ |
| T5.2-02 | Preview default off | Fresh start | Open | No frames displayed until enabled | ☐ |
| T5.2-03 | Close dashboard | Preview on | Close | Preview processing stops | ☐ |
| T5.2-04 | History populated | Several events | Open History | Rows match store | ☐ |
| T5.2-05 | Why panel | Select a lock event | Click | Reasons/scores shown | ☐ |
| T5.2-06 | Empty history (edge) | No events | Open | Friendly empty state | ☐ |
| T5.2-07 | Large history | 50,000 events | Open | Opens < 2 s (paged) | ☐ |
| T5.2-08 | Privacy | Run, inspect disk | Check | No image files written | ☐ |
| T5.2-09 | Regression | Tray controls | Use pause/resume | Still works | ☐ |

**7. Verification Checklist**
- [ ] Screenshot for the demo (blur or avoid your private surroundings) kept outside the repo or only if non-sensitive.
- [ ] CPU with dashboard open vs closed recorded.

**8. Completion Criteria:** Dashboard accurately reflects engine state; history explains locks.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(ui): dashboard with live preview, history, lock reasons (M5.2)"
git push origin phase-5-ui-privacy
git tag -a m5.2 -m "M5.2 dashboard"; git push origin m5.2
```

**10. Rollback / Recovery:** `git revert <hash>` / reset to `m5.1`.

---

## Milestone 5.3 — Settings, first-run consent and privacy controls

**Requires:** M5.2, M1.1, M1.2.

**1. Milestone Name:** Consent screen, editable settings, and "delete all my data".

**2. Objective:** Implement Book §14: disclosed camera use, configurable timers/modes, delete-all, snapshots off by default.

**3. Tasks to Complete**
- [ ] First-run dialog explaining camera use, local-only processing, limits (copy from Book §2.3 and §14); must be accepted before monitoring starts.
- [ ] Settings page: mode, absence timer, obstruction debounce, dry-run toggle, retention days, snapshot toggle (default off).
- [ ] Validation reuses M1.1; invalid input shows an inline error.
- [ ] "Delete all local data": events, calibration, settings, enrolled devices, snapshots, with confirmation.
- [ ] "Test lock" button (confirmation first; it really locks).

**4. Files / Modules Affected:** `src/silentwatch/ui/settings.py`, `src/silentwatch/storage/retention.py`, `src/silentwatch/config/loader.py`, `tests/unit/test_settings_validation.py`.

**5. Implementation Guidance**
- Settings changes apply live where safe, otherwise after restart; say which.
- Consent record stored as a timestamp only, no personal data.
- No microphone access anywhere (Book §14).

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T5.3-01 | First run | No settings | Start | Consent dialog blocks monitoring | ☐ |
| T5.3-02 | Decline consent (negative) | First run | Decline | App exits or stays disabled, camera never opened | ☐ |
| T5.3-03 | Change timer | Settings | Set 20 s, save | Persists; used by policy | ☐ |
| T5.3-04 | Invalid value | Settings | Enter -3 | Rejected inline | ☐ |
| T5.3-05 | Delete all | Data exists | Delete + confirm | Files/rows gone; app returns to first-run state | ☐ |
| T5.3-06 | Cancel delete (edge) | Same | Cancel | Nothing removed | ☐ |
| T5.3-07 | Snapshot default | Fresh | Inspect | Off; no evidence directory created | ☐ |
| T5.3-08 | Test lock | Settings | Click + confirm | Real lock | ☐ |
| T5.3-09 | Microphone audit | Process list/permissions | Check | No microphone access requested | ☐ |

**7. Verification Checklist**
- [ ] Windows Settings → Privacy → Microphone shows the app never used the microphone.
- [ ] Settings file contains no sensitive data.

**8. Completion Criteria:** Privacy requirements §14 items 1-9 demonstrably met.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(privacy): consent, settings, delete-all-data (M5.3)"
git push origin phase-5-ui-privacy
git tag -a m5.3 -m "M5.3 privacy"; git push origin m5.3
```

**10. Rollback / Recovery:** `git revert <hash>`. Reset your local `%APPDATA%\SilentWatch` folder if a settings-format change breaks loading (config loader already falls back to defaults).

---

## Milestone 5.4 — Windows session awareness and startup

**Requires:** M5.1, M4.4.

**1. Milestone Name:** Pause when Windows locks, resume on unlock, start at logon.

**2. Objective:** Book §15/§8.6: do not keep the camera running while locked or asleep, and start in a visible, user-controlled way.

**3. Tasks to Complete**
- [ ] Add `pywin32` to `requirements.txt` (WTS session notifications).
- [ ] Register `WTSRegisterSessionNotification` through a hidden message window; handle lock, unlock, logon, logoff, remote connect/disconnect.
- [ ] On lock: release the camera and stop analysis; on unlock: restart with the post-unlock grace.
- [ ] Handle sleep/resume (`WM_POWERBROADCAST`).
- [ ] Optional "Start with Windows" toggle using the Startup folder shortcut or Task Scheduler at user logon (no admin).

**4. Files / Modules Affected:** `src/silentwatch/windows/session.py`, `src/silentwatch/app/lifecycle.py`, `src/silentwatch/app/startup.py`, `tests/unit/test_session_events.py`.

**5. Implementation Guidance**
- `pywin32` is used instead of raw `ctypes` here because the message-pump boilerplate is large and well-trodden.
- Keep session handling in an adapter that emits internal events, so the policy remains platform-free.
- Test the logic with a fake event source; verify the real behaviour manually.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T5.4-01 | Lock pauses camera | Running | Win+L | Camera released (LED off) | ☐ |
| T5.4-02 | Unlock resumes | Locked | Sign in | Monitoring resumes after grace | ☐ |
| T5.4-03 | Self-lock then unlock | App-triggered lock | Unlock | No immediate relock | ☐ |
| T5.4-04 | Sleep/resume | Running | Sleep, wake | Camera re-initialised, no crash | ☐ |
| T5.4-05 | Sign out / sign in | Startup enabled | Cycle | App starts at logon, shows tray | ☐ |
| T5.4-06 | Startup disabled (negative) | Toggle off | Restart | App does not start | ☐ |
| T5.4-07 | Remote Desktop disconnect (edge) | RDP if available | Disconnect | Handled, no crash (or documented N/A) | ☐ |
| T5.4-08 | Missing privileges | Normal user | Register | Works without admin | ☐ |
| T5.4-09 | Regression | Whole suite | `pytest -q` | Green | ☐ |

**7. Verification Checklist**
- [ ] Event log shows session transitions in order.
- [ ] Startup entry can be removed from the UI and from Windows Settings → Apps → Startup.

**8. Completion Criteria:** Lock/unlock/sleep cycles are clean for 20 consecutive repetitions.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(windows): session lock/unlock awareness and optional startup (M5.4)"
git push origin phase-5-ui-privacy
git tag -a m5.4 -m "M5.4 session"; git push origin m5.4
```

**10. Rollback / Recovery:** `git revert <hash>`; remove the startup shortcut manually if testing left one (`shell:startup`).

---

## Phase 5 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 5.1, 5.2, 5.3, 5.4 ☐ |
| Tests passed | T5.1-01..09, T5.2-01..09, T5.3-01..09, T5.4-01..09 ☐ |
| Known issues | |
| Git commit / hash | `________` tag `phase-5-complete` |
| Overall verification | Full demo flow (walk away, cover, lights off, history/why) runs from the tray app |
| **Go / No-Go for Phases 6-8 (polished-demo ready)** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-5-ui-privacy -m "merge: phase 5 complete"
git push origin main
git tag -a phase-5-complete -m "Phase 5 done"; git push origin phase-5-complete
```

---

# PHASE 6 — Hand-Approach Detection (optional early warning)

**Branch:** `phase-6-hand`. Book reference: §5.2-E, §7.2. Optional: skip if time is short; the product works without it.

## Milestone 6.1 — Hand detector and approach score

**Requires:** Phase 5 complete (or Phase 4 if skipping UI), M4.2 (MediaPipe already installed).

**1. Milestone Name:** Detect a hand entering the frame and growing toward the lens.

**2. Objective:** Produce `hand_near_lens_score` (Book §5.3) as optional evidence, never as the sole reason to lock.

**3. Tasks to Complete**
- [ ] Download the MediaPipe Hand Landmarker `.task` model via `download_models.ps1` (hash verified).
- [ ] `HandApproachDetector.update(frame)` → bounding-box area ratio, growth rate over 0.5 s, and score 0..1.
- [ ] Config: enable flag (default on), thresholds.
- [ ] Offline benchmark script on recorded clips.

**4. Files / Modules Affected:** `src/silentwatch/camera/hand_detector.py`, `scripts/download_models.ps1`, `tests/unit/test_hand_score.py`.

**5. Implementation Guidance**
- Hand landmarks cannot prove a hand is covering the lens (Book §7.2); the score is an early-warning input only.
- Score computation (area growth) is a pure function so it can be tested with scripted boxes.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T6.1-01 | Hand approaching | Live | Move hand toward lens | Score rises | ☐ |
| T6.1-02 | No hand | Live | Idle | Score ≈ 0 | ☐ |
| T6.1-03 | Hand moving away | After T6.1-01 | Retreat | Score falls | ☐ |
| T6.1-04 | Low light / blur (edge) | Dim | Wave hand | No crash; result recorded | ☐ |
| T6.1-05 | Model missing (failure) | Remove file | Start | Feature disabled gracefully | ☐ |
| T6.1-06 | Score unit test | Scripted boxes | Feed growth | Monotone score, clipped to 0..1 | ☐ |
| T6.1-07 | Performance | Running | Measure CPU delta | Within budget recorded | ☐ |

**7. Verification Checklist**
- [ ] No hand images saved.
- [ ] Phase 3/4 regression suites green.

**8. Completion Criteria:** Score behaves sensibly in live and recorded tests.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(camera): hand approach score via mediapipe (M6.1)"
git push origin phase-6-hand
git tag -a m6.1 -m "M6.1 hand"; git push origin m6.1
```
*Do not commit:* `models/*.task`.

**10. Rollback / Recovery:** `git revert <hash>` / reset to `phase-5-complete`.

---

## Milestone 6.2 — Two-stage pipeline integration

**Requires:** M6.1.

**1. Milestone Name:** Run cheap checks always; hand model only when Stage 1 flags change.

**2. Objective:** Implement Book §15's two-stage design and feed the hand score into policy as supporting evidence.

**3. Tasks to Complete**
- [ ] Stage 1 (always): features + classifier. Stage 2 (conditional): hand detector when `frame_diff` or `POSSIBLE` triggers.
- [ ] New signal `HAND_APPROACHING` (+ policy rule: hand approaching **and** `POSSIBLE_OBSTRUCTION` → lock sooner; hand alone → notify only).
- [ ] Dashboard shows hand score.
- [ ] Measure CPU with and without Stage 2.

**4. Files / Modules Affected:** `src/silentwatch/camera/integrity.py`, `src/silentwatch/policy/rules.py`, `src/silentwatch/ui/dashboard.py`, `tests/unit/test_policy_hand.py`.

**5. Implementation Guidance**
- Do not let hand evidence ever lock the machine alone (Book §16 failure table).
- This milestone modifies existing behaviour, so run all Phase 3 and 4 replays as regression.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T6.2-01 | Hand + possible obstruction | Scripted signals | Feed | Lock earlier than obstruction alone | ☐ |
| T6.2-02 | Hand alone | Scripted | Feed | Notify only, no lock | ☐ |
| T6.2-03 | Stage 2 gating | Idle scene | Measure | Hand model not invoked | ☐ |
| T6.2-04 | Obstruction replay regression | Phase 3 clips | `evaluate.py` | Metrics not worse than M3.4 | ☐ |
| T6.2-05 | End-to-end live | Live mode | Hand approach and cover | Lock; log shows both signals | ☐ |
| T6.2-06 | Hand model failure | Model missing | Run | Falls back to Stage 1 only | ☐ |
| T6.2-07 | Policy regression | Full suite | `pytest -q` | Green | ☐ |

**7. Verification Checklist**
- [ ] CPU numbers recorded.
- [ ] Latency of detection not degraded compared with M3.4.

**8. Completion Criteria:** Better or equal detection with no new false locks.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(pipeline): two-stage detection with hand evidence in policy (M6.2)"
git push origin phase-6-hand
git tag -a m6.2 -m "M6.2 two-stage"; git push origin m6.2
```

**10. Rollback / Recovery:** `git revert <hash>`; set `hand.enabled = false` in config as an immediate runtime mitigation.

---

## Phase 6 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 6.1, 6.2 ☐ |
| Tests passed | T6.1-01..07, T6.2-01..07 ☐ |
| Known issues | |
| Git commit / hash | `________` tag `phase-6-complete` |
| Overall verification | Obstruction metrics unchanged or better; hand never locks alone |
| **Go / No-Go for next phase** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-6-hand -m "merge: phase 6 complete"
git push origin main
git tag -a phase-6-complete -m "Phase 6 done"; git push origin phase-6-complete
```

---

# PHASE 7 — Android Phone Proximity (Bluetooth)

**Branch:** `phase-7-ble`. Book reference: §9. Phone proximity is a supporting signal only (Book §9.2). Outcome depends on missing-info item 5, so Milestone 7.1 is a feasibility spike.

## Milestone 7.1 — Feasibility spike: how can the S24 FE be detected?

**Requires:** Phase 4 complete (policy exists to consume it later).

**1. Milestone Name:** Find out which signal your phone really gives the laptop.

**2. Objective:** Choose a method based on evidence: (a) BLE advertisement scanning with Bleak, or (b) paired-device connection state via Windows Bluetooth APIs, or (c) a small phone-side BLE advertiser. Samsung phones randomise BLE addresses and the phone is currently paired as a classic Bluetooth device.

**3. Tasks to Complete**
- [ ] Add `bleak` to `requirements.txt`.
- [ ] `scripts/ble_scan.py`: scan 30 s, print name, address, RSSI, service UUIDs, manufacturer data.
- [ ] Test: does the phone appear with stable identity (screen on, screen off, in pocket, Battery Saver)?
- [ ] Test option (b): read the paired phone's connection status via the WinRT Bluetooth device API (installed with Bleak) and time how fast it changes when you walk away or switch Bluetooth off.
- [ ] Write the decision, measured latencies, and limitations in `docs/decisions.md`.

**4. Files / Modules Affected:** `scripts/ble_scan.py`, `scripts/bt_connection_probe.py`, `docs/decisions.md`, `requirements.txt`.

**5. Implementation Guidance**
- Do not write production code yet; the output is a documented decision.
- Do not store the phone's MAC in the repo or docs (redact).
- If neither works reliably, Phase 7 is reduced to "log only" or dropped; the core product does not depend on it.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T7.1-01 | Scan runs | Bluetooth on | Run scanner | Device list printed, no crash | ☐ |
| T7.1-02 | Phone seen with screen on | Phone beside laptop | Scan | Identifiable? (record yes/no) | ☐ |
| T7.1-03 | Screen off / pocket | Same | Scan | Visibility recorded | ☐ |
| T7.1-04 | Battery saver | Enabled | Scan | Visibility recorded | ☐ |
| T7.1-05 | Connection-state probe | Phone paired | Walk away / Bluetooth off | Time-to-detect recorded | ☐ |
| T7.1-06 | Bluetooth off on laptop (failure) | Toggle off | Run | Clear error, no hang | ☐ |
| T7.1-07 | Address randomisation (edge) | Wait 20+ min | Rescan | Identity stability recorded | ☐ |

**7. Verification Checklist**
- [ ] Decision paragraph written with evidence table.
- [ ] No MAC addresses committed.

**8. Completion Criteria:** A defensible method is chosen (or "not feasible" is documented).

**9. Git Checkpoint**
```powershell
git status
git add .
git commit -m "docs(ble): proximity feasibility spike and decision (M7.1)"
git push origin phase-7-ble
git tag -a m7.1 -m "M7.1 ble spike"; git push origin m7.1
```
*Do not commit:* raw scan dumps containing addresses.

**10. Rollback / Recovery:** `git revert <hash>`; documentation only.

---

## Milestone 7.2 — Proximity service with smoothing and enrollment

**Requires:** M7.1 (chosen method), M1.2.

**1. Milestone Name:** `BluetoothProximityService` emitting `PHONE_PRESENT` / `PHONE_MISSING`.

**2. Objective:** Smoothed, debounced presence of the enrolled phone (Book §9.2 recommended policy).

**3. Tasks to Complete**
- [ ] Enrollment flow storing a device identifier and friendly name in `device_enrollment` (no secrets).
- [ ] Rolling window over observations; `MISSING` only after N consecutive misses or sustained drop (default 60 s, configurable).
- [ ] Handles Bluetooth off, adapter absent, sleep/wake, and reconnect.
- [ ] Emits events; no lock decisions here.

**4. Files / Modules Affected:** `src/silentwatch/bluetooth/{scanner,enrollment}.py`, `src/silentwatch/storage/database.py` (use `device_enrollment`), `tests/unit/test_proximity_smoothing.py`.

**5. Implementation Guidance**
- Smoothing is a pure function of timestamped observations (inject the clock).
- Provide an "unenroll" path and include it in delete-all.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T7.2-01 | Enroll | Phone nearby | Enroll | Row stored, no secrets | ☐ |
| T7.2-02 | Present | Phone beside laptop | Run | `PHONE_PRESENT` | ☐ |
| T7.2-03 | Missing after window | Phone moved away 2 min | Observe | `PHONE_MISSING` only after window | ☐ |
| T7.2-04 | Brief dropout (edge) | Interference 10 s | Observe | No missing event | ☐ |
| T7.2-05 | Bluetooth off (failure) | Toggle | Observe | `BT_UNAVAILABLE`, not `PHONE_MISSING` theft signal | ☐ |
| T7.2-06 | Sleep/wake | Laptop sleeps | Wake | Service recovers | ☐ |
| T7.2-07 | Unenroll | Enrolled | Unenroll | Row removed | ☐ |
| T7.2-08 | Smoothing unit tests | Scripted data | Feed | Window logic exact | ☐ |

**7. Verification Checklist**
- [ ] Test matrix from Book §18.3 recorded in `docs/testing.md`.

**8. Completion Criteria:** Stable signal with documented limits.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(bluetooth): phone proximity service with smoothing and enrollment (M7.2)"
git push origin phase-7-ble
git tag -a m7.2 -m "M7.2 proximity"; git push origin m7.2
```

**10. Rollback / Recovery:** `git revert <hash>`; disable with `bluetooth.enabled=false`.

---

## Milestone 7.3 — Combine phone signal in policy

**Requires:** M7.2, M4.1.

**1. Milestone Name:** Phone absence as one correlated risk input.

**2. Objective:** Implement Book §10.4 rules involving the phone: `PHONE_MISSING` alone never locks; camera unavailable + owner absent + phone missing locks; absence timeout shortens when the phone is also missing.

**3. Tasks to Complete**
- [ ] Add signals and rules; mode-dependent.
- [ ] Dashboard shows phone state.
- [ ] Regression run of all policy tests.

**4. Files / Modules Affected:** `src/silentwatch/policy/rules.py`, `src/silentwatch/ui/dashboard.py`, `tests/unit/test_policy_phone.py`.

**5. Implementation Guidance**
- Treat the phone as a corroborating signal (Book §9.2). Keep the rule set small and documented in `docs/architecture.md`.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T7.3-01 | Phone missing alone | Owner present | Signal | No lock | ☐ |
| T7.3-02 | Absent + phone missing | Scripted | Signal | Earlier lock than absence alone | ☐ |
| T7.3-03 | Camera unavailable + absent + phone missing | Scripted | Signal | Lock | ☐ |
| T7.3-04 | BT unavailable | Scripted | Signal | Does not count as phone missing | ☐ |
| T7.3-05 | Phone returns | After pending | Signal | Pending lock cancelled if still within grace | ☐ |
| T7.3-06 | Live walk-away with phone | Live | Walk with phone | Lock sooner than without | ☐ |
| T7.3-07 | Regression | Policy + obstruction replays | Run | Unchanged | ☐ |

**7. Verification Checklist**
- [ ] No rule locks on the phone signal alone.

**8. Completion Criteria:** Rules match Book §10.4; regressions clean.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(policy): correlate phone proximity with absence and camera faults (M7.3)"
git push origin phase-7-ble
git tag -a m7.3 -m "M7.3 phone policy"; git push origin m7.3
```

**10. Rollback / Recovery:** `git revert <hash>`; runtime mitigation: disable Bluetooth in settings.

---

## Phase 7 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 7.1, 7.2, 7.3 ☐ |
| Tests passed | T7.1-01..07, T7.2-01..08, T7.3-01..07 ☐ |
| Known issues | (phone model/OS limits) |
| Git commit / hash | `________` tag `phase-7-complete` |
| Overall verification | Phone never locks alone; test matrix recorded |
| **Go / No-Go for next phase** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-7-ble -m "merge: phase 7 complete"
git push origin main
git tag -a phase-7-complete -m "Phase 7 done"; git push origin phase-7-complete
```

---

# PHASE 8 — USB Monitoring and Evidence Snapshots (optional)

**Branch:** `phase-8-extras`. Book reference: §8.5, §5.6.

## Milestone 8.1 — USB storage arrival monitor

**Requires:** Phase 5 complete (uses `pywin32` message window from M5.4).

**1. Milestone Name:** Log USB storage insertion and raise risk if the owner is absent.

**2. Objective:** Monitoring only (no blocking, per Book §8.5).

**3. Tasks to Complete**
- [ ] Listen for `WM_DEVICECHANGE` (device arrival/removal) via the existing hidden window.
- [ ] Classify volume/disk-class arrivals; ignore HID/other classes.
- [ ] Event `USB_STORAGE_ARRIVED` with class only (no file listings, no serial numbers).
- [ ] Rule: arrival while `OWNER_ABSENT*` → lock (balanced), else log.

**4. Files / Modules Affected:** `src/silentwatch/windows/usb_monitor.py`, `src/silentwatch/policy/rules.py`, `tests/unit/test_usb_events.py`.

**5. Implementation Guidance**
- Do not read the contents of the inserted device.
- Test with your own USB stick.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T8.1-01 | Insert while present | Seated | Plug USB drive | Event logged, no lock | ☐ |
| T8.1-02 | Insert while absent | Owner absent | Plug | Lock in balanced mode | ☐ |
| T8.1-03 | Mouse/keyboard (negative) | Any | Plug HID | Ignored | ☐ |
| T8.1-04 | Removal | Drive in | Remove | Removal logged | ☐ |
| T8.1-05 | Privacy | Inspect event | Read | No serial/volume contents | ☐ |
| T8.1-06 | Regression | Full suite | `pytest -q` | Green | ☐ |

**7. Verification Checklist**
- [ ] Works as a normal user.

**8. Completion Criteria:** Arrival events and rule verified live.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(windows): USB storage arrival monitoring (M8.1)"
git push origin phase-8-extras
git tag -a m8.1 -m "M8.1 usb"; git push origin m8.1
```

**10. Rollback / Recovery:** `git revert <hash>`; disable with `usb.enabled=false`.

---

## Milestone 8.2 — Optional evidence snapshots with retention

**Requires:** M5.3 (privacy settings), M3.3.

**1. Milestone Name:** Opt-in, protected, auto-expiring snapshots.

**2. Objective:** Book §5.6: save the last pre-obstruction frame (and optionally the first obstructed frame) only when enabled; never claim it shows the intruder.

**3. Tasks to Complete**
- [ ] In-memory ring buffer of the last ~5 frames, **only when snapshots are enabled**.
- [ ] On tamper: write frame(s) to `%APPDATA%\SilentWatch\evidence\`, encrypted with Windows DPAPI (`win32crypt` from pywin32).
- [ ] Retention (default 7 days) and a size cap; purge job at start.
- [ ] Viewer in History that decrypts on demand.
- [ ] Delete-all includes evidence.

**4. Files / Modules Affected:** `src/silentwatch/storage/evidence.py`, `src/silentwatch/storage/retention.py`, `src/silentwatch/ui/history.py`, `tests/unit/test_evidence.py`.

**5. Implementation Guidance**
- DPAPI ties data to your Windows account without handling keys; no extra crypto dependency is needed. Introduce the `cryptography` package only if a later milestone (remote lock) needs it.
- Label saved images "last frame before obstruction", never "intruder".

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T8.2-01 | Disabled by default | Fresh | Trigger obstruction | No file written, no ring buffer allocated | ☐ |
| T8.2-02 | Enabled capture | Enabled | Trigger | Encrypted file(s) created | ☐ |
| T8.2-03 | Encrypted at rest | After capture | Open file with an image viewer | Not viewable | ☐ |
| T8.2-04 | Decrypt in UI | Same | History → view | Image displayed | ☐ |
| T8.2-05 | Retention | Files > 7 days (edit timestamps) | Start | Purged | ☐ |
| T8.2-06 | Size cap | Many events | Trigger | Oldest removed at cap | ☐ |
| T8.2-07 | Other Windows user (security) | Second account | Try to read | Fails | ☐ |
| T8.2-08 | Delete-all | Evidence exists | Delete all | Directory empty | ☐ |

**7. Verification Checklist**
- [ ] `evidence/` not in the repo; `.gitignore` already covers `data/`; add the evidence path if you ever change it to a project-relative folder.

**8. Completion Criteria:** Opt-in, encrypted, expiring evidence proven.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "feat(evidence): opt-in dpapi-encrypted snapshots with retention (M8.2)"
git push origin phase-8-extras
git tag -a m8.2 -m "M8.2 evidence"; git push origin m8.2
```
*Do not commit:* any evidence file.

**10. Rollback / Recovery:** `git revert <hash>`; delete the evidence folder.

---

## Phase 8 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 8.1, 8.2 ☐ |
| Tests passed | T8.1-01..06, T8.2-01..08 ☐ |
| Known issues | |
| Git commit / hash | `________` tag `phase-8-complete` |
| Overall verification | Both features opt-in/off-by-default where required; no personal data in repo |
| **Go / No-Go for Phase 9** | ☐ GO ☐ NO-GO |

```powershell
git switch main
git merge --no-ff phase-8-extras -m "merge: phase 8 complete"
git push origin main
git tag -a phase-8-complete -m "Phase 8 done"; git push origin phase-8-complete
```

---

# PHASE 9 — Hardening, Packaging, Documentation, Release

**Branch:** `phase-9-release`. Skip the optional phases you did not build; their rows become N/A.

## Milestone 9.1 — Failure-mode and security test pass

**Requires:** Phase 5 complete (plus any optional phases built).

**1. Milestone Name:** Execute the Book §18.4 security tests and §16 failure table.

**2. Objective:** Show the app behaves safely under crashes, restarts, revoked permissions and bad data.

**3. Tasks to Complete**
- [ ] Crash recovery: kill the process; restart; no corrupt DB, calibration still valid.
- [ ] Windows restart/logoff cycle with startup enabled.
- [ ] Revoke camera permission mid-run; remove camera; fill disk (simulated); lock DB file.
- [ ] Network audit: confirm the process makes **no outbound connections** (`Get-NetTCPConnection -OwningProcess <pid>`; also check with `netstat -ano`).
- [ ] Confirm no admin rights needed; no credentials handled; no microphone.
- [ ] Review `docs/threat-model.md` against implementation, including limits from Book §2.3 (killable by attacker, photo spoofing, etc.).

**4. Files / Modules Affected:** `docs/threat-model.md`, `docs/testing.md`, fixes across modules.

**5. Implementation Guidance**
- Fix every defect found with a regression test first, then the fix (separate commits).
- Do not claim effectiveness from a single demo (Book §18.4).

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T9.1-01 | Kill process | Running | `Stop-Process` | Restart clean; DB intact | ☐ |
| T9.1-02 | Reboot | Startup on | Restart | App returns to monitoring, tray visible | ☐ |
| T9.1-03 | Permission revoked | Running | Disable camera access | `UNAVAILABLE`, no crash | ☐ |
| T9.1-04 | Camera removed | Running | Disable in Device Manager | Recovery after re-enable | ☐ |
| T9.1-05 | DB locked/corrupt | Running | Lock/corrupt file | App continues, error logged | ☐ |
| T9.1-06 | Storage full | Simulated | Write events | No crash | ☐ |
| T9.1-07 | Outbound network | Running 10 min | Inspect connections | None | ☐ |
| T9.1-08 | Tampered settings | Edit JSON maliciously | Start | Validation rejects, defaults | ☐ |
| T9.1-09 | Privilege | Normal user | Run | No elevation requested | ☐ |
| T9.1-10 | Threat-model gap check | Review | Compare doc/code | No undocumented limits | ☐ |

**7. Verification Checklist**
- [ ] All defects found are fixed or listed as known limits.

**8. Completion Criteria:** No crash/leak under the failure matrix; threat model honest and current.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "test(security): failure-mode pass, fixes, threat model update (M9.1)"
git push origin phase-9-release
git tag -a m9.1 -m "M9.1 hardening"; git push origin m9.1
```

**10. Rollback / Recovery:** per-fix `git revert`; tag `m9.1` is the known-hardened state.

---

## Milestone 9.2 — Performance and power profiling

**Requires:** M9.1.

**1. Milestone Name:** Measure CPU, memory, battery cost and tune.

**2. Objective:** Book §15: low steady-state cost on the actual laptop.

**3. Tasks to Complete**
- [ ] 30-minute run per configuration: idle monitoring, dashboard preview on, hand stage on.
- [ ] Record CPU %, RSS memory (Task Manager / `Get-Process`), battery drop over 30 min on battery.
- [ ] Tune FPS/resolution/stage gating to meet budget (suggested: < 5 % average CPU, < 300 MB RAM, no thermal ramp; adjust to evidence).
- [ ] Results table in `docs/performance.md`.

**4. Files / Modules Affected:** `docs/performance.md`, `config/default.toml`.

**5. Implementation Guidance**
- Use a repeatable script: `scripts/measure.ps1` sampling the process every 5 s into a CSV (CSV not committed; summary is).

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T9.2-01 | Idle CPU | 30 min | Measure | Within budget | ☐ |
| T9.2-02 | Memory growth | 30 min | Sample RSS | Flat (no leak) | ☐ |
| T9.2-03 | Battery | On battery 30 min | Compare to baseline | Impact recorded | ☐ |
| T9.2-04 | Latency preserved | After tuning | `evaluate.py` | Detection targets from M3.4 still met | ☐ |
| T9.2-05 | Video call coexist | Meet/Zoom open | Run | Behaviour per M2.3 matrix | ☐ |

**7. Verification Checklist**
- [ ] `docs/performance.md` committed with numbers and test conditions.

**8. Completion Criteria:** Budget met or justified; detection quality unchanged.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "perf: profile cpu/memory/battery and tune sampling (M9.2)"
git push origin phase-9-release
git tag -a m9.2 -m "M9.2 perf"; git push origin m9.2
```
*Do not commit:* raw CSV logs with process info.

**10. Rollback / Recovery:** `git revert <hash>` returns previous sampling settings.

---

## Milestone 9.3 — Packaging as a Windows application

**Requires:** M9.1, M9.2.

**1. Milestone Name:** Build a one-folder Windows distribution and test it on a clean account.

**2. Objective:** A runnable `SilentWatch.exe` that does not need Python installed (Book §11 packaging).

**3. Tasks to Complete**
- [ ] Add `pyinstaller` to `requirements-dev.txt` (dev-only; it bundles the interpreter and dependencies into an executable).
- [ ] `silentwatch.spec` one-folder build; include icons, config defaults, model download instructions (models fetched at first run or shipped after licence check).
- [ ] Windowed (no console) build with tray.
- [ ] Test on the **second laptop** (your old Windows 11 Home machine, no Python/Git/dev tools installed). Copy `dist\SilentWatch` by USB or private share; do not upload it publicly. Windows 11 Home has no Windows Sandbox, so this laptop is the clean-machine test. A second local user account on the main laptop is an optional extra check only.
- [ ] On the second laptop: recalibrate for its webcam, record its results separately in `docs/obstruction-results.md` (do not mix with the HP camera numbers), and note its Bluetooth adapter and camera model in `docs/hardware-baseline.md`.
- [ ] Note the SmartScreen "unrecognised app" prompt for the unsigned exe in `docs/release.md`.
- [ ] Check antivirus false positives; note them in docs.

**4. Files / Modules Affected:** `silentwatch.spec`, `scripts/build.ps1`, `requirements-dev.txt`, `docs/release.md`.

**5. Implementation Guidance**
- PyInstaller is chosen for familiarity; Nuitka is the Book's alternative, evaluate only if PyInstaller output is unreliable with MediaPipe/PySide6.
- Unsigned executables trigger SmartScreen; document this (code-signing is a Book §17 Phase 8 item, optional).
- `dist/` and `build/` are never committed; release zips are attached on GitHub Releases.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T9.3-01 | Build | Venv | `scripts/build.ps1` | `dist\SilentWatch\SilentWatch.exe` produced | ☐ |
| T9.3-02 | Runs without Python | Second laptop, nothing installed | Launch exe | Tray appears, consent shown | ☐ |
| T9.3-03 | Camera in packaged app | Same | Recalibrate on its webcam, then cover lens | Calibration succeeds; obstruction detected | ☐ |
| T9.3-04 | Real lock in packaged app | Same, you know its sign-in | Trigger walk-away and cover | Locks | ☐ |
| T9.3-04b | Different hardware portability | Second laptop | Run the lights-off and normal-use checks | No false lock; results recorded separately | ☐ |
| T9.3-05 | Missing model | Remove model | Start | Graceful message | ☐ |
| T9.3-06 | Startup entry | Enable | Relogin | Starts | ☐ |
| T9.3-07 | Uninstall/cleanup | Delete folder + startup | Check | No leftovers except user data (documented) | ☐ |
| T9.3-08 | Size sanity | `dist` size | Measure | Recorded | ☐ |
| T9.3-09 | Regression | Source tests | `pytest -q` | Green | ☐ |

**7. Verification Checklist**
- [ ] No secrets/data inside `dist`.
- [ ] Windows Defender scan clean (or false positive noted).

**8. Completion Criteria:** The second laptop runs the full demo from the exe after its own calibration.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "build: pyinstaller one-folder packaging and install test (M9.3)"
git push origin phase-9-release
git tag -a m9.3 -m "M9.3 packaging"; git push origin m9.3
```
*Do not commit:* `dist/`, `build/`, `*.exe`, `*.zip`.

**10. Rollback / Recovery:** `git revert <hash>`; the source install still works as fallback for the demo.

---

## Milestone 9.4 — Documentation and licence inventory

**Requires:** M9.3.

**1. Milestone Name:** README, architecture, privacy, threat model, testing, and third-party licences.

**2. Objective:** Meet Book §19/§22: keep a dependency, model and asset licence inventory, and document limitations honestly.

**3. Tasks to Complete**
- [ ] `README.md`: what it does, limits, install, usage, demo steps, screenshots (non-sensitive).
- [ ] `docs/architecture.md` (state machine, data flow), `docs/privacy.md`, `docs/threat-model.md`, `docs/testing.md` (final results).
- [ ] `THIRD_PARTY_LICENSES.md`: every Python package (use `pip-licenses`, dev-only tool), models (MediaPipe model terms), icons, fonts; include Qt/LGPL notes and the Ultralytics note (not used).
- [ ] State clearly: not guaranteed anti-theft; presence ≠ identity; can be stopped by an attacker with control of the machine.
- [ ] Accuracy review: every number in docs comes from your measurements.

**4. Files / Modules Affected:** `README.md`, `docs/*.md`, `THIRD_PARTY_LICENSES.md`, `requirements-dev.txt`.

**5. Implementation Guidance**
- `pip-licenses` is justified only to generate the inventory; remove it from runtime requirements.
- Link every claim to the test that supports it.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T9.4-01 | Quick start works | Clean clone | Follow README only | App runs | ☐ |
| T9.4-02 | Licence inventory complete | Pip list | Compare to file | Every package present | ☐ |
| T9.4-03 | Link check | Docs | Open each link | No dead links | ☐ |
| T9.4-04 | Claim audit | Docs | Cross-check numbers | Match `performance.md` / results | ☐ |
| T9.4-05 | Privacy statement | Read vs code | Compare | No contradictions (no upload, no audio) | ☐ |
| T9.4-06 | Sensitive content scan | Repo | Search for emails/MACs/paths | None unwanted | ☐ |

**7. Verification Checklist**
- [ ] A person who has not seen the project can install and run it from the README.

**8. Completion Criteria:** Documentation complete, accurate, licence inventory finished.

**9. Git Checkpoint**
```powershell
git status
git add .
git commit -m "docs: readme, architecture, privacy, threat model, licence inventory (M9.4)"
git push origin phase-9-release
git tag -a m9.4 -m "M9.4 docs"; git push origin m9.4
```

**10. Rollback / Recovery:** `git revert <hash>`; docs only.

---

## Milestone 9.5 — Demo rehearsal, final regression and release tag

**Requires:** M9.1-M9.4.

**1. Milestone Name:** Rehearse the scripted demo, run everything once more, tag `v0.1.0`.

**2. Objective:** A reliable demo flow plus a clean, tagged repository.

**3. Tasks to Complete**
- [ ] Demo script in `docs/demo.md`: (1) walk away → lock, (2) cover camera → lock, (3) lights off → no lock, (4) dashboard "why", (5) optional phone.
- [ ] Rehearse three times in the **actual demo room**; recalibrate there; note thresholds.
- [ ] Prepare a fallback: recorded screen capture (kept outside Git) and a dry-run mode that shows decisions without locking.
- [ ] Full `pytest` run, full manual regression of Phase 4.4 live scenarios.
- [ ] Merge to `main`, tag `v0.1.0`.

**4. Files / Modules Affected:** `docs/demo.md`, all tests.

**5. Implementation Guidance**
- Close other camera apps before the demo.
- Save work before each live lock.

**6. Test Cases**

| ID | Test Scenario | Preconditions | Steps | Expected Result | Status |
|---|---|---|---|---|---|
| T9.5-01 | Demo run ×3 | Demo room | Follow script | 3/3 successful | ☐ |
| T9.5-02 | Full automated suite | Clean venv | `pytest -q` | All green | ☐ |
| T9.5-03 | Phase 4.4 live regression | Live | A, C, D, E, F | All pass | ☐ |
| T9.5-04 | Fallback path | Camera blocked | Use dry-run/recording | Demo still tells the story | ☐ |
| T9.5-05 | Fresh clone from GitHub | Temp folder | Setup + run | Works | ☐ |

**7. Verification Checklist**
- [ ] Final Release Checklist (below) fully ticked.

**8. Completion Criteria:** `v0.1.0` tagged on `main`.

**9. Git Checkpoint**
```powershell
python -m pytest -q
git status
git add .
git commit -m "release: demo script and v0.1.0 readiness (M9.5)"
git push origin phase-9-release
git switch main
git merge --no-ff phase-9-release -m "merge: phase 9 complete, release v0.1.0"
git push origin main
git tag -a v0.1.0 -m "SILENTWATCH v0.1.0"
git push origin v0.1.0
```

**10. Rollback / Recovery:** If a release bug appears: `git revert <hash>` on `main`, then `git tag -a v0.1.1`. Never delete or move a published tag that others may have used.

---

## Phase 9 Completion Checkpoint

| Item | Record |
|---|---|
| Completed milestones | 9.1-9.5 ☐ |
| Tests passed | T9.1-01..10, T9.2-01..05, T9.3-01..09, T9.4-01..06, T9.5-01..05 ☐ |
| Known issues | (final list, mirrored in README "Limitations") |
| Git commit / hash | `________` tag `v0.1.0` |
| Overall verification | Final Release Checklist complete |
| **Go / No-Go for release** | ☐ GO ☐ NO-GO |

---

# FINAL RELEASE CHECKLIST

**Functionality**
- [ ] Real Windows lock via `LockWorkStation` on obstruction, confirmed absence and (if built) USB-while-absent.
- [ ] Obstruction detected without any face; lights-off does not lock.
- [ ] Camera loss/freeze handled as faults, not automatic tampering.
- [ ] Strict and Balanced modes behave as documented; lock cooldown and post-unlock grace work.
- [ ] Optional features (hand, phone, USB, snapshots) each off-switchable.

**Testing**
- [ ] All unit and integration tests pass on a fresh clone.
- [ ] Obstruction results table meets targets or documents shortfalls.
- [ ] Live scenarios A, C, D, E, F pass; contention matrix complete.
- [ ] 30-minute soak and failure-mode pass done.

**Security & Privacy**
- [ ] No outbound network connections observed.
- [ ] No frames, face data or snapshots stored unless the user opted in; opt-in data encrypted (DPAPI) and expiring.
- [ ] Consent shown; delete-all works; no microphone; no admin required; no credentials handled.
- [ ] Threat model and limitations published honestly.

**Performance**
- [ ] CPU, memory and battery numbers recorded in `docs/performance.md`; no memory growth.

**Deployment**
- [ ] One-folder PyInstaller build verified on the second (old) laptop.
- [ ] Startup entry optional and removable.
- [ ] Models obtained via hash-verified script or licence-checked and listed.

**Documentation**
- [ ] README, architecture, privacy, threat model, testing, performance, demo, release notes.
- [ ] `THIRD_PARTY_LICENSES.md` complete (Python packages, models, icons, Qt/LGPL note).

**Git Repository Cleanliness**
- [ ] `git status` clean; every milestone has a tag; `main` only contains merged, green phases.
- [ ] No `.env`, `*.db`, `data/`, clips, models, `dist/`, `build/`, `.venv*` tracked (`git ls-files` audit).
- [ ] `git log --format=%B | Select-String "co-authored-by"` prints nothing; `git shortlog -sne --all` lists only you.
- [ ] No secrets, MAC addresses, serial numbers or personal photos anywhere in history (`git log -p` spot checks).
- [ ] `v0.1.0` annotated tag pushed.

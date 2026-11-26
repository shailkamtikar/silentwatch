# Threat model

SILENTWATCH is a defensive convenience layer on top of Windows sign-in. It reduces the window in which an unattended, unlocked laptop can be used. It is **not** a guaranteed anti-theft system.

## What it defends against (and how)

| Threat | Detection | Response | Tested by |
|---|---|---|---|
| Owner walks away, laptop stays unlocked | No face for `pending_s`, then `lock_after_s` | Real `LockWorkStation` | scenario A (automated + live dry-run) |
| Someone covers the camera (hand, finger, cloth, paper, shutter) | Collapse of scene structure vs calibrated baseline, sustained for the debounce | Lock | scenarios C, E, replay harness |
| Camera disabled/unplugged while owner away | Camera unavailable + owner absent | Lock (phone-missing required if a phone is in use) | policy tests, scenario F |
| USB storage plugged in while owner away | Volume arrival with USB bus type | Lock | M8.1 tests |
| Owner away with phone also gone | Phone missing + absence pending | Lock sooner | M7.3 tests |

## Deliberate non-actions (to avoid false locks and false claims)

Low brightness, a frozen feed, a camera outage while the owner is present, a missing phone and a hand near the lens **never lock on their own**. They are logged, warned about, or combined with other evidence.

## What it cannot defend against

1. **An attacker who can stop the app.** It runs as a normal user process. Anyone with the logged-in session (or an administrator) can close, pause or uninstall it. No self-protection is attempted (and hiding from Task Manager is a non-goal, see privacy rules).
2. **Total darkness with no screen light.** A fully black image cannot be told apart from a black cover; a dark room with screen glow (structure remains) is not treated as a cover.
3. **A photograph or screen held in front of the camera.** Presence detection is not identity verification and can be fooled.
4. **Translucent covers and partial covers** that leave scene structure; documented known limits of the classifier (see `docs/obstruction-results.md`).
5. **Someone outside the camera's view who simply starts using the keyboard** right after the owner leaves, before the absence timer expires. The timers are a trade-off between false locks and exposure time.
6. **Disk theft or booting another OS** (use BitLocker / device encryption), **malware**, and **coercion**.
7. **Hardware without the required sensors:** this laptop has no accelerometer, so no movement/snatch detection exists.

## Hardening measures implemented (M9.1)

- The real lock is requested **before** any database write, and events are written by a background thread, so a locked/full/slow database can never delay a lock (tested with a database held locked by another connection).
- A corrupted calibration row, a transient processing error, a failed hand model or a crashed event write never stop monitoring; 20 consecutive iteration failures surface as an error state in the tray instead of silent death.
- A rejected calibration is retried automatically; without a baseline the detector would be silently off.
- Settings are validated field by field; malformed, oversized or hostile settings files fall back to defaults and a safety floor on obstruction debounce can't be lowered below 0.2 s.
- Hard-killed processes leave a valid SQLite database (WAL, tested by killing a writer).
- No network code exists in the product (static test) and a live run showed 0 TCP connections and 0 UDP endpoints.
- It runs without elevation; no credentials, PINs or Windows passwords are read or stored.

## Residual risks to state in any demo or release

The camera indicator light is on whenever monitoring is on. Snapshots (off by default) are encrypted with Windows DPAPI, so only the same Windows user on the same machine can open them.

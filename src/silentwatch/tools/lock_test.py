"""Manual test: lock the real Windows session after a delay.

    python -m silentwatch.tools.lock_test --delay 5          # REALLY locks Windows
    python -m silentwatch.tools.lock_test --dry-run          # logs only

Save your work first. Unlock with your normal Windows sign-in.
"""

from __future__ import annotations

import argparse
import time

from silentwatch.config import app_data_dir
from silentwatch.storage import Database, EventStore
from silentwatch.windows.lock import WindowsLockService


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    db = Database(app_data_dir() / "silentwatch.db")
    store = EventStore(db)
    svc = WindowsLockService(store, dry_run=args.dry_run)
    for s in range(int(args.delay), 0, -1):
        print(f"Locking in {s}...", flush=True)
        time.sleep(1)
    res = svc.lock("manual lock_test")
    print(res)
    for e in store.recent(3):
        print(e.timestamp_utc, e.event_type.value, e.action_taken, e.details)
    db.close()
    return 0 if res.requested else 1


if __name__ == "__main__":
    raise SystemExit(main())

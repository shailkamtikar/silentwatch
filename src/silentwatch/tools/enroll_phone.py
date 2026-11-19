"""Enroll (or remove) the phone used as a proximity signal.

    python -m silentwatch.tools.enroll_phone --paired S24          # paired device whose name contains S24
    python -m silentwatch.tools.enroll_phone --ble-uuid <UUID>     # phone advertises this service UUID
    python -m silentwatch.tools.enroll_phone --remove

Stores an identifier and a friendly name locally. No secret or key is stored.
"""

from __future__ import annotations

import argparse
import asyncio

from silentwatch.bluetooth.enrollment import TYPE_BLE_UUID, EnrolledDevice, EnrollmentStore, find_paired
from silentwatch.config import app_data_dir
from silentwatch.storage import Database


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--paired", metavar="NAME")
    g.add_argument("--ble-uuid", metavar="UUID")
    g.add_argument("--remove", action="store_true")
    ap.add_argument("--friendly-name", default="My phone")
    a = ap.parse_args(argv)
    db = Database(app_data_dir() / "silentwatch.db")
    store = EnrollmentStore(db)
    try:
        if a.remove:
            print(f"removed {store.delete()} enrolled device(s)")
            return 0
        if a.paired:
            found = asyncio.run(find_paired(a.paired))
            if not found:
                print("No paired Bluetooth device matches that name.")
                return 1
            store.save(found[0])
            print(f"Enrolled paired device ({found[0].friendly_name}).")
        else:
            store.save(EnrolledDevice(a.ble_uuid.lower(), TYPE_BLE_UUID, a.friendly_name))
            print("Enrolled BLE service UUID.")
        print("Enable it with settings: bluetooth.enabled = true")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

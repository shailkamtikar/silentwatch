"""BLE feasibility scan: which devices advertise, how stable is their identity, how strong is the signal.

Addresses are NOT printed in full (they identify devices): only a short hash is shown.

    python scripts/ble_scan.py --seconds 20 [--name-contains S24]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import statistics

from bleak import BleakScanner


def short(addr: str) -> str:
    return "dev-" + hashlib.sha256(addr.encode()).hexdigest()[:6]


async def main(seconds: float, name_contains: str | None) -> None:
    seen: dict[str, dict] = {}

    def cb(device, adv):
        d = seen.setdefault(device.address, {"name": adv.local_name or device.name, "rssi": [], "uuids": set(), "mfr": set()})
        d["rssi"].append(adv.rssi)
        d["uuids"].update(adv.service_uuids)
        d["mfr"].update(adv.manufacturer_data.keys())
        if adv.local_name:
            d["name"] = adv.local_name

    async with BleakScanner(cb):
        await asyncio.sleep(seconds)

    print(f"{len(seen)} distinct BLE addresses in {seconds:.0f}s")
    named = 0
    for addr, d in sorted(seen.items(), key=lambda kv: -len(kv[1]["rssi"])):
        name = d["name"] or "(no name)"
        if d["name"]:
            named += 1
        if name_contains and name_contains.lower() not in name.lower():
            continue
        r = d["rssi"]
        print(f"{short(addr)}  name={name!r:28} adverts={len(r):3d} rssi mean={statistics.mean(r):.0f} "
              f"min={min(r)} max={max(r)}  service-uuids={len(d['uuids'])} mfr-ids={sorted(d['mfr'])}")
    print(f"named devices: {named}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--name-contains")
    a = ap.parse_args()
    asyncio.run(main(a.seconds, a.name_contains))

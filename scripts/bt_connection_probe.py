"""Probe option (b): connection state of a PAIRED Bluetooth device via the Windows Bluetooth API.

    python scripts/bt_connection_probe.py --name-contains S24 --seconds 30

Prints status changes with timestamps. Addresses/ids are never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from winrt.windows.devices.bluetooth import BluetoothConnectionStatus, BluetoothDevice
from winrt.windows.devices.enumeration import DeviceInformation


async def main(name_contains: str, seconds: float) -> int:
    selector = BluetoothDevice.get_device_selector_from_pairing_state(True)
    infos = await DeviceInformation.find_all_async_aqs_filter(selector)
    matches = [i for i in infos if name_contains.lower() in (i.name or "").lower()]
    print(f"paired Bluetooth devices: {len(infos)}; matching {name_contains!r}: {len(matches)}")
    if not matches:
        return 1
    dev = await BluetoothDevice.from_id_async(matches[0].id)
    t0 = time.monotonic()
    last = None
    while time.monotonic() - t0 < seconds:
        status = dev.connection_status
        if status != last:
            label = "CONNECTED" if status == BluetoothConnectionStatus.CONNECTED else "DISCONNECTED"
            print(f"[{time.monotonic() - t0:5.1f}s] {label}")
            last = status
        await asyncio.sleep(0.5)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name-contains", required=True)
    ap.add_argument("--seconds", type=float, default=20)
    a = ap.parse_args()
    raise SystemExit(asyncio.run(main(a.name_contains, a.seconds)))

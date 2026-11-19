"""Phone enrollment: stores an identifier and friendly name locally. No secrets, no remote-control keys."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from silentwatch.bluetooth.proximity import BleAdvertSource, PairedConnectionSource, ProximitySource
from silentwatch.storage import Database

TYPE_PAIRED = "paired_connection"
TYPE_BLE_UUID = "ble_service_uuid"


@dataclass(frozen=True)
class EnrolledDevice:
    device_id: str          # WinRT device id (paired) or the service UUID (BLE advert)
    device_type: str
    friendly_name: str


class EnrollmentStore:
    def __init__(self, db: Database):
        self.db = db

    def save(self, d: EnrolledDevice) -> None:
        if d.device_type not in (TYPE_PAIRED, TYPE_BLE_UUID):
            raise ValueError(f"unknown device type {d.device_type!r}")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.db.execute(
            "INSERT OR REPLACE INTO device_enrollment (device_id, device_type, friendly_name, created_at) VALUES (?, ?, ?, ?)",
            (d.device_id, d.device_type, d.friendly_name, now),
        )

    def load(self) -> EnrolledDevice | None:
        rows = self.db.query("SELECT device_id, device_type, friendly_name FROM device_enrollment ORDER BY created_at DESC LIMIT 1")
        return EnrolledDevice(*rows[0]) if rows else None

    def delete(self, device_id: str | None = None) -> int:
        if device_id is None:
            return self.db.execute("DELETE FROM device_enrollment").rowcount
        return self.db.execute("DELETE FROM device_enrollment WHERE device_id = ?", (device_id,)).rowcount

    def touch(self, device_id: str) -> None:
        self.db.execute("UPDATE device_enrollment SET last_seen_at = ? WHERE device_id = ?",
                        (datetime.now(timezone.utc).isoformat(timespec="seconds"), device_id))


def make_source(d: EnrolledDevice) -> ProximitySource:
    if d.device_type == TYPE_PAIRED:
        return PairedConnectionSource(d.device_id)
    return BleAdvertSource(d.device_id)


async def find_paired(name_contains: str) -> list[EnrolledDevice]:
    """List paired Bluetooth devices whose name matches (used by the enrollment tool)."""
    from winrt.windows.devices.bluetooth import BluetoothDevice
    from winrt.windows.devices.enumeration import DeviceInformation

    infos = await DeviceInformation.find_all_async_aqs_filter(BluetoothDevice.get_device_selector_from_pairing_state(True))
    return [EnrolledDevice(i.id, TYPE_PAIRED, i.name) for i in infos if name_contains.lower() in (i.name or "").lower()]

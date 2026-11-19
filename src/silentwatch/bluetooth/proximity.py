"""Phone proximity as a *supporting* signal (Book section 9). Never proof of theft, never a lock on its own.

Sources (see decision D16): the phone's live paired connection, or a BLE advertisement with a known service UUID.
Smoothing turns noisy readings into PRESENT / MISSING / UNAVAILABLE.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from silentwatch.storage import EventStore, EventType, Severity

log = logging.getLogger(__name__)


class ProximityState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"      # Bluetooth off / adapter missing / no usable source


@dataclass(frozen=True)
class Reading:
    available: bool                  # the radio/source could be used at all
    present: bool = False
    rssi: int | None = None


class ProximitySource(Protocol):
    async def poll(self) -> Reading: ...


class ProximitySmoother:
    """Pure, clock-free: feed (reading, ts). MISSING only after `missing_after_s` without a positive reading."""

    def __init__(self, missing_after_s: float = 60.0, present_after: int = 2):
        self.missing_after_s = missing_after_s
        self.present_after = present_after
        self.state = ProximityState.UNKNOWN
        self._ref: float | None = None     # last time the phone was seen (or the start of observation)
        self._consec = 0

    def update(self, r: Reading, ts: float) -> ProximityState:
        if not r.available:
            self.state = ProximityState.UNAVAILABLE
            self._consec = 0
            self._ref = None               # an outage must not count towards 'missing'
            return self.state
        if self._ref is None:
            self._ref = ts
        if r.present:
            self._ref = ts
            self._consec += 1
            if self._consec >= self.present_after:
                self.state = ProximityState.PRESENT
        else:
            self._consec = 0
            if ts - self._ref >= self.missing_after_s:
                self.state = ProximityState.MISSING
        return self.state


# --- sources --------------------------------------------------------------------------------
class PairedConnectionSource:
    """Connection state of a paired device through the Windows Bluetooth API (needs a live link)."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self._dev = None

    async def poll(self) -> Reading:
        try:
            from winrt.windows.devices.bluetooth import BluetoothConnectionStatus, BluetoothDevice

            if self._dev is None:
                self._dev = await BluetoothDevice.from_id_async(self.device_id)
            if self._dev is None:
                return Reading(False)
            return Reading(True, self._dev.connection_status == BluetoothConnectionStatus.CONNECTED)
        except Exception as exc:  # noqa: BLE001 - Bluetooth off, adapter missing, device removed ...
            log.debug("paired-connection poll failed: %r", exc)
            self._dev = None
            return Reading(False)


class BleAdvertSource:
    """Looks for advertisements carrying a given service UUID (phone-side advertiser app required)."""

    def __init__(self, service_uuid: str, scan_s: float = 2.0):
        self.uuid = service_uuid.lower()
        self.scan_s = scan_s

    async def poll(self) -> Reading:
        try:
            from bleak import BleakScanner

            found = await BleakScanner.discover(timeout=self.scan_s, return_adv=True)
            best = None
            for _addr, (_dev, adv) in found.items():
                if self.uuid in [u.lower() for u in adv.service_uuids]:
                    best = adv.rssi if best is None else max(best, adv.rssi)
            return Reading(True, best is not None, best)
        except Exception as exc:  # noqa: BLE001
            log.debug("BLE scan failed: %r", exc)
            return Reading(False)


# --- service ----------------------------------------------------------------------------------
_EVENT = {
    ProximityState.PRESENT: (EventType.PHONE_PRESENT, Severity.INFO),
    ProximityState.MISSING: (EventType.PHONE_MISSING, Severity.WARNING),
    ProximityState.UNAVAILABLE: (EventType.BT_UNAVAILABLE, Severity.WARNING),
}


class BluetoothProximityService:
    def __init__(
        self,
        source: ProximitySource,
        smoother: ProximitySmoother,
        on_state: Callable[[ProximityState], None],
        store: EventStore | None = None,
        poll_interval_s: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.source, self.smoother, self.on_state, self.store = source, smoother, on_state, store
        self.poll_interval_s = poll_interval_s
        self._clock = clock
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.state = ProximityState.UNKNOWN

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=lambda: asyncio.run(self._loop()), name="bt-proximity", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(10)
        self._thread = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                reading = await self.source.poll()
            except Exception:  # noqa: BLE001
                log.exception("proximity source crashed")
                reading = Reading(False)
            new = self.smoother.update(reading, self._clock())
            if new != self.state:
                self.state = new
                mapped = _EVENT.get(new)
                if mapped and self.store is not None:
                    self.store.append(mapped[0], mapped[1], "bluetooth", details={"rssi": reading.rssi})
                try:
                    self.on_state(new)
                except Exception:  # noqa: BLE001
                    log.exception("proximity callback failed")
            for _ in range(int(self.poll_interval_s / 0.05) or 1):
                if self._stop.is_set():
                    break
                await asyncio.sleep(0.05)

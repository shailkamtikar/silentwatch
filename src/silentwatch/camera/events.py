"""Map camera status notifications to stored events."""

from __future__ import annotations

from silentwatch.storage import EventStore, EventType, Severity

_MAP = {
    "UNAVAILABLE": (EventType.CAMERA_UNAVAILABLE, Severity.WARNING),
    "FROZEN": (EventType.CAMERA_FROZEN, Severity.WARNING),
    "RECOVERED": (EventType.CAMERA_RECOVERED, Severity.INFO),
    "RETRY": (EventType.CAMERA_RETRY, Severity.INFO),
    "FORMAT_CHANGED": (EventType.CAMERA_FORMAT_CHANGED, Severity.WARNING),
}


def log_camera_status(store: EventStore, kind: str, detail: str) -> None:
    mapped = _MAP.get(kind)
    if mapped is None:
        return  # GAP etc. are not worth storing
    etype, sev = mapped
    store.append(etype, sev, "camera", details={"detail": detail})

"""Event history: a Qt-free model (testable) and a thin Qt table adapter."""

from __future__ import annotations

from datetime import datetime

from silentwatch.storage import Event, EventStore, EventType

COLUMNS = ("Time", "Event", "Severity", "Source", "Action", "Summary")


def local_time(iso_utc: str | None) -> str:
    if not iso_utc:
        return ""
    try:
        return datetime.fromisoformat(iso_utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso_utc


def summary(ev: Event) -> str:
    d = ev.details or {}
    if "reason" in d:
        return str(d["reason"])
    if "reasons" in d and d["reasons"]:
        return "; ".join(str(r) for r in d["reasons"][:2])
    for k in ("detail", "notify", "mode", "paused"):
        if k in d:
            return f"{k}: {d[k]}"
    return ""


def why_text(ev: Event) -> str:
    """Human-readable explanation of why something happened (the 'why did it lock' panel)."""
    lines = [f"{ev.event_type.value} at {local_time(ev.timestamp_utc)}", f"Severity: {ev.severity.value}   Source: {ev.source}"]
    if ev.action_taken:
        lines.append(f"Action taken: {ev.action_taken}")
    d = ev.details or {}
    if d.get("reason"):
        lines += ["", f"Reason: {d['reason']}"]
    if d.get("reasons"):
        lines += ["", "Evidence:"] + [f"  - {r}" for r in d["reasons"]]
    if d.get("scores"):
        lines += ["", "Scores (relative to your calibrated baseline):"] + [f"  {k}: {v}" for k, v in d["scores"].items()]
    other = {k: v for k, v in d.items() if k not in ("reason", "reasons", "scores")}
    if other:
        lines += ["", "Details:"] + [f"  {k}: {v}" for k, v in other.items()]
    return "\n".join(lines)


class HistoryModel:
    def __init__(self, store: EventStore, page_size: int = 100):
        self.store = store
        self.page_size = page_size
        self.event_type: EventType | None = None
        self.page = 0
        self.rows: list[Event] = []

    def refresh(self) -> list[Event]:
        self.rows = self.store.query(event_type=self.event_type, limit=self.page_size, offset=self.page * self.page_size)
        return self.rows

    def set_filter(self, event_type: EventType | None) -> None:
        self.event_type = event_type
        self.page = 0
        self.refresh()

    def next_page(self) -> None:
        if len(self.rows) == self.page_size:
            self.page += 1
            self.refresh()

    def prev_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            self.refresh()

    def row_values(self, ev: Event) -> tuple[str, ...]:
        return (local_time(ev.timestamp_utc), ev.event_type.value, ev.severity.value, ev.source, ev.action_taken or "", summary(ev))

    @property
    def is_empty(self) -> bool:
        return not self.rows and self.page == 0


def make_table_model(model: HistoryModel):
    from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

    class EventTableModel(QAbstractTableModel):
        def rowCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(model.rows)

        def columnCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(COLUMNS)

        def data(self, index, role=Qt.ItemDataRole.DisplayRole):
            if role == Qt.ItemDataRole.DisplayRole and index.isValid():
                return model.row_values(model.rows[index.row()])[index.column()]
            return None

        def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
            if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
                return COLUMNS[section]
            return None

        def reload(self):
            self.beginResetModel()
            model.refresh()
            self.endResetModel()

    return EventTableModel()

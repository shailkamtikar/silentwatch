import os
import time

import numpy as np
import pytest

from silentwatch.storage import Database, EventStore, EventType, Severity
from silentwatch.ui.dashboard import numpy_to_qimage, structure_loss_percent
from silentwatch.ui.history import HistoryModel, summary, why_text


@pytest.fixture
def store(tmp_path):
    db = Database(tmp_path / "h.db")
    yield EventStore(db)
    db.close()


def test_empty_history_is_flagged(store):
    m = HistoryModel(store)
    m.refresh()
    assert m.is_empty


def test_rows_match_store(store):
    for i in range(5):
        store.append(EventType.STATE_CHANGED, details={"detail": f"s{i}"})
    m = HistoryModel(store)
    m.refresh()
    assert len(m.rows) == 5 and m.rows[0].details["detail"] == "s4"
    values = m.row_values(m.rows[0])
    assert values[1] == "STATE_CHANGED" and values[5] == "detail: s4"


def test_filter_and_paging(store):
    for i in range(25):
        store.append(EventType.STATE_CHANGED)
    store.append(EventType.LOCK_REQUESTED, Severity.CRITICAL, details={"reason": "r"})
    m = HistoryModel(store, page_size=10)
    m.refresh()
    m.next_page()
    assert m.page == 1 and len(m.rows) == 10
    m.set_filter(EventType.LOCK_REQUESTED)
    assert m.page == 0 and len(m.rows) == 1


def test_why_text_contains_reasons_and_scores(store):
    store.append(
        EventType.OBSTRUCTION_CONFIRMED, Severity.CRITICAL, "obstruction",
        details={"reasons": ["contrast 0.04x baseline", "edges 0.00x baseline"], "scores": {"contrast_ratio": 0.04}},
    )
    ev = store.recent(1)[0]
    txt = why_text(ev)
    assert "contrast 0.04x baseline" in txt and "contrast_ratio: 0.04" in txt and "CRITICAL" in txt
    assert "contrast" in summary(ev)


def test_lock_reason_shown(store):
    store.append(EventType.LOCK_REQUESTED, Severity.CRITICAL, "lock_service", details={"reason": "owner absent beyond configured timeout"})
    assert "owner absent beyond configured timeout" in why_text(store.recent(1)[0])


def test_large_history_opens_fast(store):
    db = store.db
    db.transaction(
        lambda c: c.executemany(
            "INSERT INTO events (timestamp_utc, event_type, severity, source) VALUES (?, 'STATE_CHANGED', 'INFO', 't')",
            [("2026-01-01T00:00:%02d+00:00" % (i % 60),) for i in range(50_000)],
        )
    )
    m = HistoryModel(store)
    t = time.perf_counter()
    m.refresh()
    assert time.perf_counter() - t < 2.0 and len(m.rows) == 100


def test_structure_loss_percent():
    assert structure_loss_percent(None) == 0
    assert structure_loss_percent({"contrast_ratio": 1.0, "edge_ratio": 1.2}) == 0
    assert structure_loss_percent({"contrast_ratio": 0.02, "edge_ratio": 0.0}) == 100
    assert structure_loss_percent({"contrast_ratio": 0.5, "edge_ratio": 0.6}) == 50


def test_dashboard_widget_behaviour(tmp_path):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from silentwatch.ui.dashboard import make_dashboard
    from tests.unit.test_service_controls import build_service

    app = QApplication.instance() or QApplication([])
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(1.0)
    dash = make_dashboard(svc)
    dash.show()
    app.processEvents()
    # preview default off: nothing shown, service keeps no frame
    assert svc.latest_preview() is None and not dash.chk_preview.isChecked()
    assert dash.preview.pixmap().isNull()
    # enabling shows frames
    dash.chk_preview.setChecked(True)
    time.sleep(0.6)
    dash._draw_preview()
    assert not dash.preview.pixmap().isNull()
    # banner reflects status, history table populated from the store
    dash.refresh_status()
    assert dash.banner.text()
    dash.reload_history()
    assert dash.table_model.rowCount() == len(dash.history.rows) > 0
    dash._show_why(dash.table_model.index(0, 0))
    assert dash.why.toPlainText()
    # closing the dashboard stops preview processing
    dash.hide()
    app.processEvents()
    assert svc.latest_preview() is None and not dash.preview_timer.isActive()
    svc.stop()
    db.close()


def test_no_image_files_written_during_preview(tmp_path):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from silentwatch.ui.dashboard import make_dashboard
    from tests.unit.test_service_controls import build_service

    app = QApplication.instance() or QApplication([])
    svc, db, world = build_service(tmp_path)
    svc.start()
    dash = make_dashboard(svc)
    dash.show()
    dash.chk_preview.setChecked(True)
    time.sleep(0.8)
    dash._draw_preview()
    svc.stop()
    db.close()
    bad = [p for p in tmp_path.rglob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".mp4", ".npz")]
    assert bad == []


def test_numpy_to_qimage_roundtrip():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    img = np.zeros((10, 20, 3), np.uint8)
    img[:, :, 2] = 255  # red in BGR
    q = numpy_to_qimage(img)
    assert (q.width(), q.height()) == (20, 10) and q.pixelColor(0, 0).red() == 255

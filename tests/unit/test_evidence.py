import os
import time

import cv2
import numpy as np
import pytest

from silentwatch.storage import EventType
from silentwatch.storage.evidence import EvidenceError, EvidenceStore
from silentwatch.storage.retention import delete_all_local_data
from tests.fixtures import synthetic as syn
from tests.unit.test_service_controls import build_service, wait_for


def img(seed=1):
    return syn.scene(seed, 96, 128)


def test_roundtrip_is_lossless_and_encrypted_at_rest(tmp_path):
    st = EvidenceStore(tmp_path / "evidence")
    p = st.save(img(), "last_frame_before_obstruction")
    raw = p.read_bytes()
    assert not raw.startswith(b"\x89PNG")                                   # not a viewable image on disk
    assert cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) is None
    assert b"PNG" not in raw[:64]
    assert (st.load(p) == img()).all()


def test_nothing_exists_until_first_save(tmp_path):
    st = EvidenceStore(tmp_path / "evidence")
    assert not (tmp_path / "evidence").exists() and st.files() == [] and st.purge() == 0


def test_label_is_sanitised_and_never_claims_an_intruder(tmp_path):
    st = EvidenceStore(tmp_path / "e")
    p = st.save(img(), "../../Evil Name!")
    assert p.parent == tmp_path / "e" and ".." not in p.name and "intruder" not in p.name


def test_retention_purges_old_snapshots(tmp_path):
    st = EvidenceStore(tmp_path / "e", retention_days=7)
    old = st.save(img(1), "a")
    new = st.save(img(2), "b")
    t = time.time() - 8 * 86400
    os.utime(old, (t, t))
    assert st.purge() == 1 and not old.exists() and new.exists()


def test_size_cap_removes_oldest_first_but_keeps_the_newest(tmp_path):
    st = EvidenceStore(tmp_path / "e", max_bytes=1)       # absurdly small cap
    last = None
    for i in range(4):
        last = st.save(img(i), f"s{i}")
        time.sleep(0.01)
    files = st.files()
    assert files == [last]


def test_corrupted_or_foreign_file_fails_cleanly(tmp_path):
    st = EvidenceStore(tmp_path / "e")
    p = st.save(img(), "x")
    data = bytearray(p.read_bytes())
    data[len(data) // 2] ^= 0xFF
    p.write_bytes(bytes(data))
    with pytest.raises(EvidenceError):
        st.load(p)
    with pytest.raises(EvidenceError):
        st.load(tmp_path / "missing.swe")


def test_delete_all_removes_evidence(tmp_path):
    st = EvidenceStore(tmp_path / "evidence")
    st.save(img(), "x")
    delete_all_local_data(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_disabled_by_default_service_writes_nothing(tmp_path):
    svc, db, world = build_service(tmp_path)
    assert svc.evidence is None
    svc.start()
    time.sleep(0.8)
    world.scene = "finger"
    assert wait_for(lambda: svc.lock_actions, 5)
    svc.stop()
    assert not (tmp_path / "evidence").exists()
    assert svc.store.query(event_type=EventType.SNAPSHOT_SAVED) == []
    db.close()


def test_enabled_service_saves_pre_and_first_obstruction_frames(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.evidence = EvidenceStore(tmp_path / "evidence")
    svc.start()
    time.sleep(1.0)
    world.scene = "finger"
    assert wait_for(lambda: len(svc.evidence.files()) >= 2, 6)
    svc.stop()
    names = [f.name for f in svc.evidence.files()]
    assert any("last_frame_before_obstruction" in n for n in names) and any("first_obstructed_frame" in n for n in names)
    events = svc.store.query(event_type=EventType.SNAPSHOT_SAVED)
    assert len(events) == 2 and all(e.details["file"] in names for e in events)
    # the pre-obstruction snapshot shows the normal scene (bright, textured), the other one the covered lens
    pre = [f for f in svc.evidence.files() if "before" in f.name][0]
    assert svc.evidence.load(pre).std() > 20
    db.close()


def test_dashboard_snapshot_viewer(tmp_path, monkeypatch):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog

    from silentwatch.ui.dashboard import make_dashboard

    app = QApplication.instance() or QApplication([])
    svc, db, world = build_service(tmp_path)
    svc.evidence = EvidenceStore(tmp_path / "evidence")
    p = svc.evidence.save(img(), "last_frame_before_obstruction")
    svc.store.append(EventType.SNAPSHOT_SAVED, source="evidence", details={"file": p.name, "label": "last frame before obstruction"})
    dash = make_dashboard(svc)
    dash.reload_history()
    dash._show_why(dash.table_model.index(0, 0))
    assert dash.btn_snapshot.isEnabled()
    shown = []
    monkeypatch.setattr(QDialog, "exec", lambda self: shown.append(self.windowTitle()) or 0)
    dash._view_snapshot()
    assert shown and "not necessarily" in shown[0]
    db.close()
    app.processEvents()

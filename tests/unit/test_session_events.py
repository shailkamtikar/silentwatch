import time

from silentwatch.app import startup
from silentwatch.windows.session import is_workstation_locked
from silentwatch.windows.session_watcher import WM_POWERBROADCAST, WM_WTSSESSION_CHANGE, SessionWatcher
from tests.unit.test_service_controls import build_service, wait_for


def test_watcher_receives_synthetic_session_and_power_messages():
    import win32gui

    got = []
    w = SessionWatcher(got.append)
    assert w.start(), w.error
    for wparam in (7, 8, 6, 5):
        win32gui.SendMessage(w.hwnd, WM_WTSSESSION_CHANGE, wparam, 1)
    for wparam in (4, 18):
        win32gui.SendMessage(w.hwnd, WM_POWERBROADCAST, wparam, 0)
    win32gui.SendMessage(w.hwnd, WM_WTSSESSION_CHANGE, 99, 1)   # unknown code ignored
    w.stop()
    assert got == ["LOCK", "UNLOCK", "LOGOFF", "LOGON", "SUSPEND", "RESUME"]


def test_watcher_survives_callback_exception():
    import win32gui

    got = []

    def cb(kind):
        got.append(kind)
        raise RuntimeError("boom")

    w = SessionWatcher(cb)
    assert w.start()
    win32gui.SendMessage(w.hwnd, WM_WTSSESSION_CHANGE, 7, 1)
    win32gui.SendMessage(w.hwnd, WM_WTSSESSION_CHANGE, 8, 1)
    w.stop()
    assert got == ["LOCK", "UNLOCK"]


def test_real_session_is_not_locked_now():
    assert is_workstation_locked() is False     # we are running interactively


def test_lock_event_releases_camera_then_self_heals_if_unlock_missed(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(1.0)
    svc.on_session_event("LOCK")
    assert wait_for(lambda: svc.status().camera == "STOPPED", 3)
    # the UNLOCK notification never arrives: polling (not locked) must restore monitoring, not leave us blind
    assert wait_for(lambda: svc.status().camera == "RUNNING", 8)
    svc.stop()
    db.close()


def test_suspend_releases_camera_and_resume_restores(tmp_path):
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(1.0)
    svc.on_session_event("SUSPEND")
    assert wait_for(lambda: svc.status().camera == "STOPPED", 3)
    svc.on_session_event("RESUME")
    assert wait_for(lambda: svc.status().camera == "RUNNING", 5)
    svc.stop()
    db.close()


def test_twenty_lock_unlock_cycles_are_clean(tmp_path):
    svc, db, world = build_service(tmp_path)
    flag = {"locked": False}
    svc._session_locked = lambda: flag["locked"]
    svc.start()
    time.sleep(1.0)
    for _ in range(20):
        flag["locked"] = True
        assert wait_for(lambda: svc.status().camera == "STOPPED", 3)
        flag["locked"] = False
        assert wait_for(lambda: svc.status().camera == "RUNNING", 3)
    assert not svc.crashed and svc.src.released >= 20
    svc.stop()
    db.close()


def test_startup_toggle_roundtrip_and_removal(tmp_path):
    assert not startup.is_enabled(tmp_path)
    p = startup.enable(tmp_path)
    assert startup.is_enabled(tmp_path) and p.read_text().startswith("@echo off")
    assert startup.disable(tmp_path) is True
    assert not startup.is_enabled(tmp_path)
    assert startup.disable(tmp_path) is False

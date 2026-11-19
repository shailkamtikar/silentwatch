import os
import time

import pytest

from silentwatch.app.lifecycle import ServiceStatus
from silentwatch.app.tray import IconKind, icon_kind, tooltip
from silentwatch.camera.obstruction import ObstructionState
from silentwatch.policy import State
from silentwatch.windows import single_instance


def status(state, **kw):
    return ServiceStatus(state, ObstructionState.NORMAL, "OWNER_PRESENT", "RUNNING", 0, 0.0, **kw)


@pytest.mark.parametrize(
    "state,kind",
    [
        (State.MONITORING, IconKind.MONITORING),
        (State.OWNER_PRESENT, IconKind.MONITORING),
        (State.OWNER_ABSENT_PENDING, IconKind.WARNING),
        (State.SUSPICIOUS, IconKind.WARNING),
        (State.TAMPERING_CONFIRMED, IconKind.ALERT),
        (State.LOCK_REQUESTED, IconKind.ALERT),
        (State.CAMERA_ERROR, IconKind.CAMERA_ERROR),
        (State.LOCKED, IconKind.LOCKED),
        (State.DISABLED, IconKind.PAUSED),
    ],
)
def test_state_icons(state, kind):
    assert icon_kind(status(state)) == kind


def test_paused_and_crashed_override():
    assert icon_kind(status(State.OWNER_PRESENT, paused=True)) == IconKind.PAUSED
    assert icon_kind(status(State.OWNER_PRESENT, crashed=True, paused=True)) == IconKind.ERROR


def test_tooltip_is_truthful():
    assert "paused" in tooltip(status(State.DISABLED, paused=True)).lower()
    assert "camera on" in tooltip(status(State.OWNER_PRESENT)).lower()
    assert "stopped unexpectedly" in tooltip(status(State.MONITORING, crashed=True))
    assert "locking in 4s" in tooltip(status(State.OWNER_ABSENT_PENDING, lock_in_s=4.2))


def test_single_instance_blocks_second_copy():
    name = f"Local\\SilentWatchTest.{os.getpid()}.{time.time_ns()}"
    first = single_instance.acquire(name)
    assert first is not None
    assert single_instance.acquire(name) is None
    first.release()
    again = single_instance.acquire(name)
    assert again is not None
    again.release()


def test_qt_tray_builds_and_pause_toggles(tmp_path):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from silentwatch.app.tray import TrayApp
    from tests.unit.test_service_controls import build_service

    app = QApplication.instance() or QApplication([])
    svc, db, world = build_service(tmp_path)
    svc.start()
    time.sleep(1.0)
    tray = TrayApp(svc)
    assert tray.refresh() in (IconKind.MONITORING, IconKind.WARNING, IconKind.CAMERA_ERROR)
    tray.toggle_pause()
    assert svc.status().paused and tray.act_pause.text().startswith("Resume")
    tray.toggle_pause()
    assert not svc.status().paused
    tray.mode_actions["strict"].trigger()
    assert svc.core.mode == "strict"
    svc.stop()
    db.close()
    app.processEvents()

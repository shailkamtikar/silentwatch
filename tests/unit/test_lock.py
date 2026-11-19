import pathlib
import re

from silentwatch.storage import Database, EventStore, EventType
from silentwatch.windows.lock import WindowsLockService


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def make(tmp_path, fn, dry=False, cooldown=5.0, clock=None):
    db = Database(tmp_path / "l.db")
    store = EventStore(db)
    return WindowsLockService(store, dry_run=dry, cooldown_s=cooldown, lock_fn=fn, clock=clock or Clock()), store


def test_api_called(tmp_path):
    calls = []
    svc, store = make(tmp_path, lambda: (calls.append(1) or True, None))
    res = svc.lock("test")
    assert calls == [1] and res.requested and not res.dry_run
    types = [e.event_type for e in store.recent(5)]
    assert EventType.LOCK_REQUESTED in types and EventType.LOCK_RESULT in types


def test_api_failure(tmp_path):
    svc, store = make(tmp_path, lambda: (False, 5))
    res = svc.lock("test")
    assert not res.requested and res.win32_error == 5
    assert store.recent(1)[0].action_taken == "failed"


def test_exception_does_not_escape(tmp_path):
    def boom():
        raise OSError("nope")

    svc, _ = make(tmp_path, boom)
    assert svc.lock("x").requested is False


def test_dry_run_never_calls_api(tmp_path):
    def boom():
        raise AssertionError("must not be called")

    svc, store = make(tmp_path, boom, dry=True)
    res = svc.lock("test")
    assert res.dry_run and res.requested
    assert store.recent(1)[0].action_taken == "dry_run"


def test_cooldown(tmp_path):
    clock = Clock()
    calls = []
    svc, store = make(tmp_path, lambda: (calls.append(1) or True, None), clock=clock)
    svc.lock("a")
    clock.t += 1
    second = svc.lock("b")
    assert second.suppressed and len(calls) == 1
    assert store.recent(1)[0].event_type == EventType.LOCK_SUPPRESSED
    clock.t += 10
    assert svc.lock("c").requested and len(calls) == 2


def test_reason_logged(tmp_path):
    svc, store = make(tmp_path, lambda: (True, None))
    svc.lock("camera obstruction")
    reqs = store.query(event_type=EventType.LOCK_REQUESTED)
    assert reqs[0].details["reason"] == "camera obstruction"


def test_no_credential_handling():
    root = pathlib.Path(__file__).parents[2] / "src" / "silentwatch"
    bad = re.compile(r"\b(password|passwd|pin_code|credential)\b", re.I)
    for f in root.rglob("*.py"):
        assert not bad.search(f.read_text(encoding="utf-8")), f

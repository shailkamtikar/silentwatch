import time

from silentwatch.camera.capture import Backoff, CameraCaptureService, CaptureState
from silentwatch.camera.sources import FakeFrameSource
from tests.fixtures import synthetic as syn


def varied(n=100000):
    for i in range(n):
        yield syn.noise(seed=i, h=48, w=64)


def fast_backoff():
    return Backoff(base=0.02, cap=0.08)


def test_backoff_schedule():
    b = Backoff(1, 30)
    assert [b.next() for _ in range(7)] == [1, 2, 4, 8, 16, 30, 30]


def test_backoff_reset():
    b = Backoff(1, 30)
    b.next(), b.next(), b.next()
    b.reset()
    assert b.next() == 1


class FlakyFactory:
    """First N opens fail, then a working source is returned."""

    def __init__(self, fail_opens):
        self.fail_opens, self.opens, self.sources = fail_opens, 0, []

    def __call__(self):
        self.opens += 1
        ok = self.opens > self.fail_opens
        src = FakeFrameSource(varied, fps=200, open_ok=ok)
        self.sources.append(src)
        return src


def test_recovers_after_open_failures():
    events = []
    fac = FlakyFactory(3)
    svc = CameraCaptureService(
        fac, 50, 0, 8, backoff_factory=fast_backoff, on_status=lambda k, d: events.append(k)
    )
    with svc:
        f = svc.get(timeout=3)
    assert f is not None
    assert events[0] == "UNAVAILABLE" and "RECOVERED" in events
    assert events.count("UNAVAILABLE") == 1  # not spammed while retrying
    assert svc.reconnects >= 3


def test_midstream_loss_reconnects():
    state = {"n": 0}

    def factory():
        state["n"] += 1
        if state["n"] == 1:
            # works for 10 frames, then every read fails
            def gen():
                for i in range(10):
                    yield syn.noise(seed=i, h=48, w=64)
                while True:
                    yield None

            return FakeFrameSource(gen, fps=200)
        return FakeFrameSource(varied, fps=200)

    events = []
    svc = CameraCaptureService(
        factory, 50, 0, 8, read_fail_limit=3, backoff_factory=fast_backoff, on_status=lambda k, d: events.append(k)
    )
    with svc:
        got = 0
        deadline = time.time() + 5
        while got < 15 and time.time() < deadline:
            if svc.get(timeout=0.5):
                got += 1
    assert got >= 15 and "UNAVAILABLE" in events and "RECOVERED" in events


def test_frozen_triggers_reopen():
    state = {"n": 0}

    def factory():
        state["n"] += 1
        if state["n"] == 1:
            still = syn.scene(1, 96, 128)

            def gen():
                while True:
                    yield still

            return FakeFrameSource(gen, fps=300)
        return FakeFrameSource(varied, fps=200)

    events = []
    svc = CameraCaptureService(
        factory, 100, 0, 8, frozen_frames=5, frozen_seconds=0, frozen_reopen_interval_s=0, backoff_factory=fast_backoff, on_status=lambda k, d: events.append(k)
    )
    with svc:
        deadline = time.time() + 5
        while "RECOVERED" not in events and time.time() < deadline:
            svc.get(timeout=0.2)
    assert "FROZEN" in events and "RECOVERED" in events


def test_stop_during_retry_is_prompt():
    svc = CameraCaptureService(
        lambda: FakeFrameSource(varied, open_ok=False), 5, 0, 8, backoff_factory=lambda: Backoff(5, 30)
    )
    svc.start()
    time.sleep(0.3)
    t0 = time.monotonic()
    svc.stop()
    assert time.monotonic() - t0 < 1.0
    assert svc.state == CaptureState.STOPPED


def test_no_retry_mode_reports_error():
    svc = CameraCaptureService(
        lambda: FakeFrameSource(varied, open_ok=False), 5, 0, 8, retry_on_open_failure=False
    )
    svc.start()
    time.sleep(0.3)
    assert svc.state == CaptureState.ERROR and "cannot open" in svc.error
    svc.stop()


def test_every_attempt_releases_source():
    fac = FlakyFactory(3)
    svc = CameraCaptureService(fac, 50, 0, 8, backoff_factory=fast_backoff)
    with svc:
        svc.get(timeout=3)
    assert all(s.released >= 1 for s in fac.sources)


def test_frozen_reopen_is_rate_limited():
    opens = {"n": 0}

    def factory():
        opens["n"] += 1
        still = syn.scene(1, 96, 128)

        def gen():
            while True:
                yield still

        return FakeFrameSource(gen, fps=300)

    svc = CameraCaptureService(
        factory, 100, 0, 8, frozen_frames=5, frozen_seconds=0, frozen_reopen_interval_s=3600, backoff_factory=fast_backoff
    )
    with svc:
        time.sleep(1.5)
    assert opens["n"] <= 2  # one reopen at most per interval

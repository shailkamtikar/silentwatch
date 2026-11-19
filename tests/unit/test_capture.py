import time

import pytest

from silentwatch.camera.capture import CameraCaptureService, CaptureState
from silentwatch.camera.sources import FakeFrameSource
from tests.fixtures import synthetic as syn


def frames(n=10_000):
    for i in range(n):
        yield syn.noise(seed=i % 5, h=48, w=64)


def make(fps=30.0, analysis=5.0, warmup=2, qsize=8, **kw):
    src = FakeFrameSource(frames, fps=fps, **kw)
    return CameraCaptureService(lambda: src, analysis, warmup, qsize), src


def test_start_stop_releases():
    svc, src = make()
    svc.start()
    assert svc.get(timeout=3) is not None
    svc.stop()
    assert svc.state == CaptureState.STOPPED
    assert src.released == 1 and not src.opened


def test_frame_metadata_monotonic():
    svc, _ = make(analysis=20.0)
    with svc:
        got = [svc.get(timeout=3) for _ in range(5)]
    assert all(f is not None for f in got)
    assert [f.index for f in got] == list(range(5))
    assert all(b.monotonic_ts > a.monotonic_ts for a, b in zip(got, got[1:]))
    assert (got[0].width, got[0].height) == (64, 48)


def test_rate_limiting():
    svc, _ = make(fps=60.0, analysis=5.0)
    with svc:
        time.sleep(3.0)
    emitted = svc.frames_emitted
    assert 9 <= emitted <= 18  # ~15 expected over 3 s at 5 fps (minus warm-up)


def test_open_failure_is_reported_not_raised():
    svc, _ = make(open_ok=False)
    svc.start()
    time.sleep(0.3)
    assert svc.state == CaptureState.RETRYING  # retries forever with backoff, never raises
    svc.stop()


def test_queue_overflow_drops_oldest():
    svc, _ = make(fps=100.0, analysis=30.0, warmup=0, qsize=2)
    svc.start()
    time.sleep(0.6)  # consumer does nothing
    svc.stop()
    assert svc._q.qsize() <= 2
    assert svc.frames_dropped > 0


def test_double_start_is_idempotent():
    svc, src = make()
    svc.start()
    svc.start()
    time.sleep(0.2)
    svc.stop()
    assert src.released == 1


def test_warmup_frames_discarded():
    # first 3 frames are black (auto-exposure warm-up), then real ones
    def gen():
        for _ in range(3):
            yield syn.black(48, 64)
        for i in range(1000):
            yield syn.noise(seed=i, h=48, w=64)

    src = FakeFrameSource(gen, fps=100)
    svc = CameraCaptureService(lambda: src, analysis_fps=50, warmup_frames=3)
    with svc:
        f = svc.get(timeout=2)
    assert f is not None and f.image.mean() > 50


def test_start_stop_cycles_release_each_time():
    for _ in range(10):
        svc, src = make(fps=0)
        svc.start()
        svc.get(timeout=2)
        svc.stop()
        assert src.released == 1

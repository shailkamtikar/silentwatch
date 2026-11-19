from silentwatch.camera.health import CameraHealthMonitor, HealthEventKind, HealthState
from tests.fixtures import synthetic as syn


def kinds(events):
    return [e.kind for e in events]


def feed(mon, frames, dt=0.2, t0=0.0):
    out = []
    for i, f in enumerate(frames):
        out += mon.observe(f is not None, f, t0 + i * dt)
    return out


def test_healthy_stream():
    m = CameraHealthMonitor()
    ev = feed(m, [syn.noise(seed=i, h=96, w=128) for i in range(100)])
    assert m.state == HealthState.OK and ev == []


def test_frozen_after_threshold_not_before():
    m = CameraHealthMonitor(frozen_frames=10)
    f = syn.scene(1, 96, 128)
    ev = feed(m, [f] * 9)
    assert m.state == HealthState.OK and ev == []
    ev = feed(m, [f], t0=9 * 0.2)
    assert m.state == HealthState.FROZEN and kinds(ev) == [HealthEventKind.FROZEN]


def test_unavailable_after_failures():
    m = CameraHealthMonitor(read_fail_limit=5)
    ev = feed(m, [None] * 4)
    assert m.state == HealthState.OK and ev == []
    ev = feed(m, [None], t0=5)
    assert m.state == HealthState.UNAVAILABLE and kinds(ev) == [HealthEventKind.UNAVAILABLE]


def test_recovery_after_unavailable():
    m = CameraHealthMonitor(read_fail_limit=3)
    feed(m, [None] * 3)
    ev = feed(m, [syn.noise(1, h=96, w=128)], t0=10)
    assert m.state == HealthState.OK and HealthEventKind.RECOVERED in kinds(ev)


def test_recovery_after_frozen():
    m = CameraHealthMonitor(frozen_frames=3)
    f = syn.scene(2, 96, 128)
    feed(m, [f] * 3)
    assert m.state == HealthState.FROZEN
    ev = feed(m, [syn.scene(3, 96, 128)], t0=10)
    assert m.state == HealthState.OK and HealthEventKind.RECOVERED in kinds(ev)


def test_format_change():
    m = CameraHealthMonitor()
    feed(m, [syn.noise(1, h=96, w=128)])
    ev = feed(m, [syn.noise(2, h=48, w=64)], t0=1)
    assert HealthEventKind.FORMAT_CHANGED in kinds(ev)


def test_timestamp_gap_not_freeze():
    m = CameraHealthMonitor(expected_interval_s=0.2)
    feed(m, [syn.noise(1, h=96, w=128)], t0=0)
    ev = m.observe(True, syn.noise(2, h=96, w=128), 3.0)
    assert kinds(ev) == [HealthEventKind.GAP] and m.state == HealthState.OK


def test_shutter_black_frames_are_not_frozen():
    m = CameraHealthMonitor(frozen_frames=5)
    ev = feed(m, [syn.black(96, 128)] * 50)
    assert m.state == HealthState.OK and ev == []


def test_no_event_spam():
    m = CameraHealthMonitor(frozen_frames=3)
    f = syn.scene(4, 96, 128)
    ev = feed(m, [f] * 40)
    assert kinds(ev).count(HealthEventKind.FROZEN) == 1


def test_isolated_failure_does_not_trip():
    m = CameraHealthMonitor(read_fail_limit=5)
    frames = [syn.noise(i, h=96, w=128) for i in range(20)]
    frames[5] = None
    assert feed(m, frames) == [] and m.state == HealthState.OK

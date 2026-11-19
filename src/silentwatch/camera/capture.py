"""Camera capture service: own thread, bounded queue, health monitoring, reconnect with backoff."""

from __future__ import annotations

import enum
import logging
import queue
import threading
import time
from typing import Callable

from silentwatch.camera.frame import Frame, FrameSource
from silentwatch.camera.health import CameraHealthMonitor, HealthEventKind, HealthState

log = logging.getLogger(__name__)

StatusCallback = Callable[[str, str], None]  # (kind, detail)


class CaptureState(str, enum.Enum):
    STOPPED = "STOPPED"
    OPENING = "OPENING"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"   # camera lost; waiting to reconnect
    ERROR = "ERROR"         # unrecoverable (only if retries are disabled)


class Backoff:
    """1, 2, 4, 8 ... capped. reset() after a success."""

    def __init__(self, base: float = 1.0, cap: float = 30.0):
        self.base, self.cap = base, cap
        self._n = 0

    def next(self) -> float:
        delay = min(self.cap, self.base * (2 ** self._n))
        self._n += 1
        return delay

    def reset(self) -> None:
        self._n = 0


class CameraCaptureService:
    """Reads frames on a worker thread; consumers call get().

    Failures never end the thread: the camera is released and re-opened with backoff until stop().
    """

    def __init__(
        self,
        source_factory: Callable[[], FrameSource],
        analysis_fps: float = 5.0,
        warmup_frames: int = 15,
        queue_size: int = 8,
        frozen_frames: int = 10,
        read_fail_limit: int = 5,
        backoff_factory: Callable[[], Backoff] = Backoff,
        on_status: StatusCallback | None = None,
        retry_on_open_failure: bool = True,
    ):
        self._factory = source_factory
        self._interval = 1.0 / analysis_fps
        self._warmup = warmup_frames
        self._q: queue.Queue[Frame] = queue.Queue(maxsize=queue_size)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._frozen_frames = frozen_frames
        self._fail_limit = read_fail_limit
        self._backoff = backoff_factory()
        self._on_status = on_status
        self._retry = retry_on_open_failure
        self.state = CaptureState.STOPPED
        self.error: str | None = None
        self.health_state = HealthState.OK
        self.frames_emitted = 0
        self.frames_dropped = 0
        self.reconnects = 0

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return  # idempotent
        self._stop.clear()
        self.state = CaptureState.OPENING
        self.error = None
        self._thread = threading.Thread(target=self._run, name="camera-capture", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout)
        self._thread = None
        self.state = CaptureState.STOPPED

    def __enter__(self) -> "CameraCaptureService":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def get(self, timeout: float = 1.0) -> Frame | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    # -- worker ----------------------------------------------------------------
    def _notify(self, kind: str, detail: str = "") -> None:
        log.info("camera status: %s %s", kind, detail)
        if self._on_status is not None:
            try:
                self._on_status(kind, detail)
            except Exception:  # noqa: BLE001 - a bad callback must not kill capture
                log.exception("status callback failed")

    def _publish(self, frame: Frame) -> None:
        while True:
            try:
                self._q.put_nowait(frame)
                self.frames_emitted += 1
                return
            except queue.Full:
                try:
                    self._q.get_nowait()  # drop oldest
                    self.frames_dropped += 1
                except queue.Empty:
                    pass

    def _run(self) -> None:
        lost = False
        while not self._stop.is_set():
            source = self._factory()
            try:
                if not source.open():
                    if not self._retry:
                        self.state, self.error = CaptureState.ERROR, f"cannot open {source.name}"
                        self._notify("UNAVAILABLE", "open failed (device missing, busy, disabled or privacy-blocked)")
                        return
                    if not lost:
                        self._notify("UNAVAILABLE", "open failed (device missing, busy, disabled or privacy-blocked)")
                    lost = True
                    self.state = CaptureState.RETRYING
                else:
                    if self._read_loop(source, was_lost=lost):
                        return  # stopped cleanly
                    lost = True
                    self.state = CaptureState.RETRYING
            except Exception as exc:  # noqa: BLE001
                log.exception("capture loop crashed")
                lost = True
                self.error = repr(exc)
                self.state = CaptureState.RETRYING
            finally:
                try:
                    source.release()
                except Exception:  # noqa: BLE001
                    log.exception("release failed")
            if self._stop.is_set():
                return
            delay = self._backoff.next()
            self._notify("RETRY", f"reconnecting in {delay:.1f}s")
            self.reconnects += 1
            if self._stop.wait(delay):
                return

    def _read_loop(self, source: FrameSource, was_lost: bool) -> bool:
        """Returns True if stopped by request, False if the camera needs reconnecting."""
        monitor = CameraHealthMonitor(self._frozen_frames, self._fail_limit, self._interval)
        self.state = CaptureState.RUNNING
        index = read_count = 0
        next_emit = 0.0
        announced_recovery = not was_lost
        while not self._stop.is_set():
            ok, img = source.read()
            now = time.monotonic()
            if not ok:
                events = monitor.observe(False, None, now)
                self.health_state = monitor.state
                if any(e.kind == HealthEventKind.UNAVAILABLE for e in events):
                    for e in events:
                        self._notify(e.kind.value, e.detail)
                    return False
                time.sleep(0.02)
                continue
            read_count += 1
            if read_count <= self._warmup:
                continue  # auto-exposure warm-up frames are discarded (D4)
            if now < next_emit:
                continue
            next_emit = now + self._interval
            if not announced_recovery:
                self._backoff.reset()
                self._notify("RECOVERED", "camera reconnected")
                announced_recovery = True
            events = monitor.observe(True, img, now)
            self.health_state = monitor.state
            for e in events:
                self._notify(e.kind.value, e.detail)
            if monitor.state == HealthState.FROZEN:
                return False  # re-open the device; a frozen driver often needs it
            self._publish(Frame(img, now, index))
            index += 1
        return True

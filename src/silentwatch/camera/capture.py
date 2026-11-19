"""Camera capture service: own thread, bounded queue, clean release."""

from __future__ import annotations

import enum
import logging
import queue
import threading
import time
from typing import Callable

from silentwatch.camera.frame import Frame, FrameSource

log = logging.getLogger(__name__)


class CaptureState(str, enum.Enum):
    STOPPED = "STOPPED"
    OPENING = "OPENING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"


class CameraCaptureService:
    """Reads frames from a FrameSource on a worker thread; consumers call get()."""

    def __init__(
        self,
        source_factory: Callable[[], FrameSource],
        analysis_fps: float = 5.0,
        warmup_frames: int = 15,
        queue_size: int = 8,
    ):
        self._factory = source_factory
        self._interval = 1.0 / analysis_fps
        self._warmup = warmup_frames
        self._q: queue.Queue[Frame] = queue.Queue(maxsize=queue_size)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._source: FrameSource | None = None
        self.state = CaptureState.STOPPED
        self.error: str | None = None
        self.frames_emitted = 0
        self.frames_dropped = 0

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
        source = self._factory()
        self._source = source
        try:
            if not source.open():
                self.state, self.error = CaptureState.ERROR, f"cannot open {source.name}"
                log.error(self.error)
                return
            self.state = CaptureState.RUNNING
            index = 0
            read_count = 0
            next_emit = 0.0
            fails = 0
            while not self._stop.is_set():
                ok, img = source.read()
                if not ok:
                    fails += 1
                    if fails >= 50:
                        self.state, self.error = CaptureState.ERROR, "camera stopped delivering frames"
                        return
                    time.sleep(0.02)
                    continue
                fails = 0
                read_count += 1
                if read_count <= self._warmup:
                    continue  # auto-exposure warm-up frames are discarded (D4)
                now = time.monotonic()
                if now < next_emit:
                    continue
                next_emit = now + self._interval
                self._publish(Frame(img, now, index))
                index += 1
        except Exception as exc:  # noqa: BLE001
            self.state, self.error = CaptureState.ERROR, repr(exc)
            log.exception("capture thread crashed")
        finally:
            try:
                source.release()
            finally:
                self._source = None

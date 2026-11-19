"""Concrete frame sources."""

from __future__ import annotations

import logging
import time
from typing import Callable, Iterable, Iterator

import numpy as np

log = logging.getLogger(__name__)


class CvFrameSource:
    """OpenCV VideoCapture (DirectShow by default; MSMF was far slower on the HP camera, see D4)."""

    def __init__(self, index: int = 0, width: int = 640, height: int = 480, backend: str = "dshow"):
        self.name = f"camera{index}"
        self._index, self._w, self._h, self._backend = index, width, height, backend
        self._cap = None

    def open(self) -> bool:
        import cv2

        be = cv2.CAP_DSHOW if self._backend == "dshow" else cv2.CAP_MSMF
        cap = cv2.VideoCapture(self._index, be)
        if not cap.isOpened():
            cap.release()
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._h)
        self._cap = cap
        return True

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._cap is None:
            return False, None
        try:
            ok, img = self._cap.read()
        except Exception as exc:  # cv2.error on some driver faults
            log.warning("camera read raised %r", exc)
            return False, None
        return (True, img) if ok and img is not None else (False, None)

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None


class FakeFrameSource:
    """Deterministic source for tests and replay.

    `frames` is an iterable of ndarray (or None to simulate a failed read). `fps` paces reads
    (0 = as fast as possible). `open_ok` simulates a camera that cannot be opened.
    """

    def __init__(
        self,
        frames: Iterable[np.ndarray | None] | Callable[[], Iterator[np.ndarray | None]],
        fps: float = 0.0,
        open_ok: bool = True,
        name: str = "fake",
        loop: bool = False,
    ):
        self.name = name
        self._factory = frames if callable(frames) else None
        self._frames = None if callable(frames) else list(frames)
        self._fps = fps
        self._open_ok = open_ok
        self._loop = loop
        self._it: Iterator[np.ndarray | None] | None = None
        self.opened = False
        self.released = 0

    def open(self) -> bool:
        if not self._open_ok:
            return False
        self._it = self._factory() if self._factory else iter(self._frames)
        self.opened = True
        return True

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._fps > 0:
            time.sleep(1.0 / self._fps)
        if self._it is None:
            return False, None
        try:
            img = next(self._it)
        except StopIteration:
            if self._loop and self._frames:
                self._it = iter(self._frames)
                return self.read()
            return False, None
        return (img is not None), img

    def release(self) -> None:
        self.released += 1
        self.opened = False
        self._it = None


class CallableFrameSource:
    """Pulls each frame from `fn()` (None = failed read). Lets tests change the 'scene' while running."""

    def __init__(self, fn: Callable[[], np.ndarray | None], fps: float = 30.0, name: str = "callable"):
        self.name = name
        self._fn = fn
        self._fps = fps
        self.opened = False
        self.released = 0

    def open(self) -> bool:
        self.opened = True
        return True

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._fps > 0:
            time.sleep(1.0 / self._fps)
        img = self._fn()
        return (img is not None), img

    def release(self) -> None:
        self.released += 1
        self.opened = False

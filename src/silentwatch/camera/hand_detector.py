"""Hand-approach early warning (Book section 5.2-E). Evidence only: a hand never locks the laptop by itself.

A landmark model cannot prove a hand covers the lens, so this module only reports how large the hand is in
the frame and how fast it is growing toward the camera.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

DEFAULT_HAND_MODEL = Path(__file__).parents[3] / "models" / "hand_landmarker.task"
WINDOW_S = 0.5            # growth is measured over this window
MIN_AREA_FOR_GROWTH = 0.05  # hands smaller than 5 % of the frame do not count as 'approaching'


class HandModelMissingError(RuntimeError):
    pass


@dataclass(frozen=True)
class HandBox:
    """Normalised (0..1) bounding box of one detected hand."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)


class HandBackend(Protocol):
    def detect(self, bgr: np.ndarray) -> list[HandBox]: ...


class MediaPipeHandBackend:
    def __init__(self, model_path: Path | str = DEFAULT_HAND_MODEL, max_hands: int = 2):
        path = Path(model_path)
        if not path.exists():
            raise HandModelMissingError(f"Hand model not found at {path}. Run scripts/download_models.ps1")
        import mediapipe as mp
        from mediapipe.tasks import python as mpp
        from mediapipe.tasks.python import vision

        self._mp = mp
        opts = vision.HandLandmarkerOptions(base_options=mpp.BaseOptions(model_asset_path=str(path)), num_hands=max_hands)
        self._det = vision.HandLandmarker.create_from_options(opts)

    def detect(self, bgr: np.ndarray) -> list[HandBox]:
        import cv2

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        res = self._det.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb))
        boxes = []
        for lm in res.hand_landmarks:
            xs = [p.x for p in lm]
            ys = [p.y for p in lm]
            boxes.append(HandBox(max(0.0, min(xs)), max(0.0, min(ys)), min(1.0, max(xs)), min(1.0, max(ys))))
        return boxes

    def close(self) -> None:
        self._det.close()


@dataclass(frozen=True)
class HandScore:
    score: float          # 0..1
    area: float           # largest hand's share of the frame
    growth: float         # relative area growth over the last WINDOW_S


def score_from(area_now: float, area_then: float | None, approach_growth: float) -> HandScore:
    """Pure scoring function (monotone in growth for a given size, and in size)."""
    if area_now <= 0:
        return HandScore(0.0, 0.0, 0.0)
    growth = 0.0 if area_then is None else (area_now - area_then) / max(area_then, 0.01)
    growth_term = min(1.0, max(0.0, growth) / (2.0 * approach_growth)) * min(1.0, area_now / MIN_AREA_FOR_GROWTH)
    size_term = min(1.0, max(0.0, (area_now - 0.10) / 0.30))     # a hand filling the frame is itself a warning
    return HandScore(max(growth_term, size_term), area_now, growth)


class HandApproachTracker:
    def __init__(self, approach_growth: float = 0.35, threshold: float = 0.5):
        self.approach_growth = approach_growth
        self.threshold = threshold
        self._hist: deque[tuple[float, float]] = deque()   # (ts, largest area)

    def update(self, boxes: list[HandBox], ts: float) -> HandScore:
        area = max((b.area for b in boxes), default=0.0)
        self._hist.append((ts, area))
        while self._hist and ts - self._hist[0][0] > 2.0:
            self._hist.popleft()
        if area <= 0:
            return HandScore(0.0, 0.0, 0.0)
        then = None
        for t, a in self._hist:
            if ts - t >= WINDOW_S - 1e-9 and a > 0:
                then = a            # most recent sample at least WINDOW_S old
        return score_from(area, then, self.approach_growth)

    def approaching(self, s: HandScore) -> bool:
        return s.score >= self.threshold

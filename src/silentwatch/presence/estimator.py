"""Presence (is someone in front of the laptop?) - deliberately NOT identity (Book section 6.1).

Pipeline: FaceBackend (per-frame detections) -> PresenceTracker (hysteresis + absence timers).
No face crops, embeddings or images are kept.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)

DEFAULT_FACE_MODEL = Path(__file__).parents[3] / "models" / "blaze_face_short_range.tflite"


class ModelMissingError(RuntimeError):
    """Raised with an actionable message when the face model file is not present."""


class FaceBackend(Protocol):
    def detect(self, bgr: np.ndarray) -> list[float]:
        """Return a confidence (0..1) for each face found."""


class MediaPipeFaceBackend:
    def __init__(self, model_path: Path | str = DEFAULT_FACE_MODEL, min_confidence: float = 0.5):
        path = Path(model_path)
        if not path.exists():
            raise ModelMissingError(f"Face model not found at {path}. Run scripts/download_models.ps1")
        import mediapipe as mp  # imported lazily: heavy, and optional for headless unit tests
        from mediapipe.tasks import python as mpp
        from mediapipe.tasks.python import vision

        self._mp = mp
        opts = vision.FaceDetectorOptions(
            base_options=mpp.BaseOptions(model_asset_path=str(path)), min_detection_confidence=min_confidence
        )
        self._det = vision.FaceDetector.create_from_options(opts)

    def detect(self, bgr: np.ndarray) -> list[float]:
        import cv2

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        res = self._det.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb))
        return [float(d.categories[0].score) for d in res.detections]

    def close(self) -> None:
        self._det.close()


@dataclass(frozen=True)
class PresenceObservation:
    face_count: int
    max_confidence: float


class PresenceState(str, enum.Enum):
    UNCERTAIN = "PRESENCE_UNCERTAIN"
    PRESENT = "OWNER_PRESENT"
    ABSENT_PENDING = "OWNER_ABSENT_PENDING"
    ABSENT_CONFIRMED = "OWNER_ABSENT_CONFIRMED"


class PresenceEstimator:
    """Runs the backend on a frame and applies the confidence threshold."""

    def __init__(self, backend: FaceBackend, min_confidence: float = 0.5):
        self.backend = backend
        self.min_confidence = min_confidence

    def observe(self, bgr: np.ndarray) -> PresenceObservation:
        scores = [s for s in self.backend.detect(bgr) if s >= self.min_confidence]
        return PresenceObservation(len(scores), max(scores, default=0.0))


class PresenceTracker:
    """Hysteresis: quick to become present, slow to become absent.

    - PRESENT after `present_detections` consecutive detections.
    - UNCERTAIN when no face for a short gap (head turn, looking down).
    - ABSENT_PENDING after `pending_s` without a face; ABSENT_CONFIRMED after `lock_after_s`.
    - While the camera is unusable (`pause()`), timers do not advance: no camera is not the same as no owner.
    """

    UNCERTAIN_GAP_S = 1.0

    def __init__(self, present_detections: int = 3, pending_s: float = 3.0, lock_after_s: float = 10.0):
        if lock_after_s < pending_s:
            raise ValueError("lock_after_s must be >= pending_s")
        self.present_detections = present_detections
        self.pending_s = pending_s
        self.lock_after_s = lock_after_s
        self.state = PresenceState.UNCERTAIN
        self._consec = 0
        self._last_seen: float | None = None
        self._start: float | None = None
        self._paused_at: float | None = None

    def pause(self, ts: float) -> None:
        if self._paused_at is None:
            self._paused_at = ts

    def seconds_since_seen(self, ts: float) -> float:
        ref = self._last_seen if self._last_seen is not None else (self._start if self._start is not None else ts)
        return max(0.0, ts - ref)

    def update(self, obs: PresenceObservation, ts: float) -> PresenceState:
        if self._start is None:
            self._start = ts
        if self._paused_at is not None:
            # shift reference times forward by the paused duration so a camera outage never counts as absence
            lost = ts - self._paused_at
            if self._last_seen is not None:
                self._last_seen += lost
            self._start += lost
            self._paused_at = None

        if obs.face_count > 0:
            self._last_seen = ts
            self._consec += 1
            if self._consec >= self.present_detections:
                self.state = PresenceState.PRESENT
            elif self.state in (PresenceState.UNCERTAIN, PresenceState.PRESENT):
                pass  # not enough detections yet to leave an absent state; keep current
            return self.state

        self._consec = 0
        gap = self.seconds_since_seen(ts)
        if gap >= self.lock_after_s:
            self.state = PresenceState.ABSENT_CONFIRMED
        elif gap >= self.pending_s:
            if self.state != PresenceState.ABSENT_CONFIRMED:
                self.state = PresenceState.ABSENT_PENDING
        elif gap >= self.UNCERTAIN_GAP_S and self.state == PresenceState.PRESENT:
            self.state = PresenceState.UNCERTAIN
        return self.state

"""Calibration: learn what 'normal' looks like for this camera in this room (numbers only, no images)."""

from __future__ import annotations

import enum
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Sequence

import numpy as np

from silentwatch.camera.integrity import FeatureExtractor, FrameFeatures
from silentwatch.storage import Database, EventStore, EventType, Severity

MIN_FRAMES = 15

# Floors keep z-scores finite when the baseline barely varies (quiet static scene).
STD_FLOORS = {
    "mean_luma": 2.0,
    "median_luma": 2.0,
    "dark_ratio": 0.02,
    "std_luma": 1.5,
    "tile_flat_ratio": 0.06,
    "edge_density": 0.004,
    "laplacian_var": 15.0,
    "entropy": 0.1,
    "structure_ratio": 0.05,
    "frame_diff": 0.3,
}


class CalibrationError(Exception):
    """Calibration rejected; the message is shown to the user."""


@dataclass(frozen=True)
class FeatureStat:
    mean: float
    std: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class Baseline:
    camera_id: str
    resolution: str
    stats: dict[str, FeatureStat]
    n_frames: int
    calibrated_at: str

    def z(self, name: str, value: float) -> float:
        """Signed deviation from baseline in (floored) standard deviations."""
        s = self.stats[name]
        return (value - s.mean) / max(s.std, STD_FLOORS.get(name, 1e-3), 1e-9)

    def to_json(self) -> str:
        return json.dumps(
            {
                "n_frames": self.n_frames,
                "stats": {k: [v.mean, v.std, v.minimum, v.maximum] for k, v in self.stats.items()},
            }
        )

    @classmethod
    def from_json(cls, camera_id: str, resolution: str, calibrated_at: str, text: str) -> "Baseline":
        d = json.loads(text)
        return cls(
            camera_id,
            resolution,
            {k: FeatureStat(*v) for k, v in d["stats"].items()},
            int(d["n_frames"]),
            calibrated_at,
        )


class CalibrationStatus(str, enum.Enum):
    OK = "OK"
    MISSING = "MISSING"
    RESOLUTION_CHANGED = "RESOLUTION_CHANGED"
    STALE = "STALE"


def compute_baseline(
    features: Sequence[FrameFeatures], camera_id: str, resolution: str, now: datetime | None = None
) -> Baseline:
    """Validate and summarise features. Raises CalibrationError with a human-readable reason."""
    if len(features) < MIN_FRAMES:
        raise CalibrationError(f"Only {len(features)} usable frames captured; need at least {MIN_FRAMES}.")
    cols = {n: [getattr(f, n) for f in features] for n in FrameFeatures.names()}

    # Covered / featureless: no usable scene structure. A dark but structured room is accepted.
    if statistics.median(cols["std_luma"]) < 4.0 and statistics.mean(cols["tile_flat_ratio"]) > 0.9:
        raise CalibrationError("The camera appears covered or sees nothing (no scene structure). Uncover it and retry.")

    # Note: a perfectly static stream is NOT rejected. A dim, still room can legitimately deliver bit-identical
    # frames for many seconds (decision D9), so it cannot be told apart from a frozen driver here.
    stats = {
        n: FeatureStat(float(np.mean(v)), float(np.std(v)), float(np.min(v)), float(np.max(v))) for n, v in cols.items()
    }
    ts = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    return Baseline(camera_id, resolution, stats, len(features), ts)


def baseline_from_images(
    images: Sequence[np.ndarray], camera_id: str, resolution: str, now: datetime | None = None
) -> Baseline:
    ex = FeatureExtractor()
    return compute_baseline([ex.update(im) for im in images], camera_id, resolution, now)


class CalibrationStore:
    def __init__(self, db: Database):
        self.db = db

    def save(self, b: Baseline) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO camera_calibration (camera_id, resolution, baseline_features_json, calibrated_at)"
            " VALUES (?, ?, ?, ?)",
            (b.camera_id, b.resolution, b.to_json(), b.calibrated_at),
        )

    def load(self, camera_id: str, resolution: str) -> Baseline | None:
        rows = self.db.query(
            "SELECT baseline_features_json, calibrated_at FROM camera_calibration WHERE camera_id=? AND resolution=?",
            (camera_id, resolution),
        )
        return Baseline.from_json(camera_id, resolution, rows[0][1], rows[0][0]) if rows else None

    def status(
        self, camera_id: str, resolution: str, stale_days: int = 30, now: datetime | None = None
    ) -> CalibrationStatus:
        b = self.load(camera_id, resolution)
        if b is None:
            other = self.db.query("SELECT 1 FROM camera_calibration WHERE camera_id=?", (camera_id,))
            return CalibrationStatus.RESOLUTION_CHANGED if other else CalibrationStatus.MISSING
        age = (now or datetime.now(timezone.utc)) - datetime.fromisoformat(b.calibrated_at)
        return CalibrationStatus.STALE if age > timedelta(days=stale_days) else CalibrationStatus.OK

    def clear(self) -> None:
        self.db.execute("DELETE FROM camera_calibration")


def collect_features(
    get_image: Callable[[], np.ndarray | None],
    seconds: float,
    clock: Callable[[], float],
    settle_timeout_s: float = 5.0,
) -> list[FrameFeatures]:
    """Gather features for `seconds`, first skipping frames while brightness is still settling.

    Auto-exposure can take several seconds on some webcams (see D4/D7), so a fixed frame count is not enough.
    """
    ex = FeatureExtractor()
    feats: list[FrameFeatures] = []
    start = clock()
    settled = False
    recent: list[float] = []
    collect_from = None
    while True:
        now = clock()
        if collect_from is not None and now - collect_from >= seconds:
            break
        if collect_from is None and now - start > settle_timeout_s:
            settled = True  # give up waiting; use whatever is there
            collect_from = now
        img = get_image()
        if img is None:
            if now - start > settle_timeout_s + seconds + 5:
                break
            continue
        f = ex.update(img)
        if not settled:
            recent = (recent + [f.mean_luma])[-5:]
            if len(recent) == 5 and (max(recent) - min(recent)) <= max(1.5, 0.1 * np.mean(recent)):
                settled = True
                collect_from = now
            continue
        feats.append(f)
    return feats


def log_result(store: EventStore | None, ok: bool, detail: str) -> None:
    if store is None:
        return
    store.append(
        EventType.CALIBRATION_DONE if ok else EventType.CALIBRATION_REJECTED,
        Severity.INFO if ok else Severity.WARNING,
        "calibration",
        details={"detail": detail},
    )

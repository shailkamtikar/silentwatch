"""Frame feature extraction for camera-integrity analysis (Book section 5.2 A-D).

All functions are pure and deterministic. No single absolute threshold is used downstream:
the classifier compares these numbers with a per-camera calibration baseline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

import cv2
import numpy as np

ANALYSIS_SIZE = (160, 120)  # (w, h) every frame is reduced to this before measuring
DARK_LEVEL = 20            # gray level below which a pixel counts as "dark"
FLAT_TILE_STD = 3.0        # a tile with gray std below this has "lost structure"


@dataclass(frozen=True)
class FrameFeatures:
    mean_luma: float          # 0..255
    median_luma: float        # 0..255
    dark_ratio: float         # fraction of pixels below DARK_LEVEL
    std_luma: float           # global contrast
    tile_flat_ratio: float    # fraction of 4x4 tiles with almost no variation
    edge_density: float       # fraction of Canny edge pixels
    laplacian_var: float      # sharpness / detail
    entropy: float            # bits (0..5) over a 32-bin histogram
    structure_ratio: float    # low-frequency std / full std: ~0 for pure noise or uniform, high for real scenes
    frame_diff: float         # mean absolute difference to the previous analysed frame

    def as_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def names(cls) -> list[str]:
        return [f.name for f in fields(cls)]


def to_gray_small(img: np.ndarray) -> np.ndarray:
    """Validate and reduce a frame to a small uint8 grayscale image."""
    if img is None or not isinstance(img, np.ndarray) or img.size == 0:
        raise ValueError("frame must be a non-empty numpy array")
    if img.ndim == 3 and img.shape[2] == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif img.ndim == 2:
        gray = img
    else:
        raise ValueError(f"unsupported frame shape {img.shape}")
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    return cv2.resize(gray, ANALYSIS_SIZE, interpolation=cv2.INTER_AREA)


def _entropy(gray: np.ndarray) -> float:
    hist = np.bincount((gray >> 3).ravel(), minlength=32).astype(np.float64)
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def _tile_flat_ratio(gray: np.ndarray, grid: int = 4) -> float:
    h, w = gray.shape
    th, tw = h // grid, w // grid
    flat = 0
    g = gray.astype(np.float32)
    for r in range(grid):
        for c in range(grid):
            if g[r * th : (r + 1) * th, c * tw : (c + 1) * tw].std() < FLAT_TILE_STD:
                flat += 1
    return flat / (grid * grid)


def _structure_ratio(gray: np.ndarray, std: float) -> float:
    if std < 1e-6:
        return 0.0
    low = cv2.resize(gray, (8, 6), interpolation=cv2.INTER_AREA).astype(np.float32)
    return float(min(1.0, low.std() / std))


def extract_features(img: np.ndarray, prev_gray: np.ndarray | None = None) -> tuple[FrameFeatures, np.ndarray]:
    """Return (features, small_gray). Pass small_gray back in as prev_gray for frame_diff."""
    gray = to_gray_small(img)
    g32 = gray.astype(np.float32)
    mean = float(g32.mean())
    std = float(g32.std())
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 40, 120)
    diff = 0.0
    if prev_gray is not None and prev_gray.shape == gray.shape:
        diff = float(np.abs(g32 - prev_gray.astype(np.float32)).mean())
    feats = FrameFeatures(
        mean_luma=mean,
        median_luma=float(np.median(gray)),
        dark_ratio=float((gray < DARK_LEVEL).mean()),
        std_luma=std,
        tile_flat_ratio=_tile_flat_ratio(gray),
        edge_density=float((edges > 0).mean()),
        laplacian_var=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        entropy=_entropy(gray),
        structure_ratio=_structure_ratio(gray, std),
        frame_diff=diff,
    )
    return feats, gray


class FeatureExtractor:
    """Stateful wrapper that remembers the previous frame for frame_diff."""

    def __init__(self) -> None:
        self._prev: np.ndarray | None = None

    def update(self, img: np.ndarray) -> FrameFeatures:
        feats, gray = extract_features(img, self._prev)
        self._prev = gray
        return feats

    def reset(self) -> None:
        self._prev = None

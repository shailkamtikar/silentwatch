"""Synthetic frames for tests (BGR uint8, 480x640 unless stated)."""

from __future__ import annotations

import cv2
import numpy as np

H, W = 480, 640


def black(h=H, w=W):
    return np.zeros((h, w, 3), np.uint8)


def uniform(v=128, h=H, w=W):
    return np.full((h, w, 3), v, np.uint8)


def noise(seed=0, mean=100, sigma=25, h=H, w=W):
    rng = np.random.default_rng(seed)
    g = np.clip(rng.normal(mean, sigma, (h, w)), 0, 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def checkerboard(cell=40, h=H, w=W):
    y, x = np.indices((h, w))
    g = (((x // cell) + (y // cell)) % 2 * 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def scene(seed=0, h=H, w=W):
    """A textured, 'room-like' frame: gradient + shapes + mild noise. Different per seed."""
    rng = np.random.default_rng(seed)
    base = np.tile(np.linspace(60, 180, w, dtype=np.float32), (h, 1))
    img = np.dstack([base, base * 0.9, base * 0.8]).astype(np.uint8)
    for _ in range(25):
        x0, y0 = int(rng.integers(0, w - 60)), int(rng.integers(0, h - 60))
        c = tuple(int(v) for v in rng.integers(20, 240, 3))
        cv2.rectangle(img, (x0, y0), (x0 + int(rng.integers(20, 120)), y0 + int(rng.integers(20, 120))), c, -1)
    n = rng.normal(0, 3, img.shape)
    return np.clip(img.astype(np.float32) + n, 0, 255).astype(np.uint8)


def dim(img, factor=0.1):
    return (img.astype(np.float32) * factor).astype(np.uint8)


def blurred(img, k=51):
    return cv2.GaussianBlur(img, (k, k), 0)

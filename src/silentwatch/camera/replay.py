"""Replay clips through the obstruction pipeline and score the outcome (Book section 18.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

from silentwatch.camera.calibration import Baseline, baseline_from_images
from silentwatch.camera.integrity import FeatureExtractor
from silentwatch.camera.obstruction import ObstructionClassifier, ObstructionState, Thresholds
from silentwatch.config.models import ObstructionConfig
from silentwatch.testing import synthetic as syn

H, W = 96, 128
DT = 0.2  # 5 fps analysis rate


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    expect_confirm: bool            # should this scenario end in CONFIRMED_OBSTRUCTION?
    cover_start_s: float | None     # when the obstruction begins (None = no obstruction)
    known_limit: bool = False       # documented limitation rather than a defect


@dataclass(frozen=True)
class ClipResult:
    scenario: str
    expect_confirm: bool
    confirmed: bool
    latency_s: float | None
    passed: bool
    known_limit: bool
    note: str = ""


# --- synthetic timeline builders -------------------------------------------------------------
def _normal(i: int) -> np.ndarray:
    return syn.scene(seed=i % 3, h=H, w=W)


def _finger(i: int) -> np.ndarray:
    rng = np.random.default_rng(i)
    img = np.full((H, W, 3), (45, 90, 190), np.float32) + rng.normal(0, 1.0, (H, W, 3))
    return np.clip(img, 0, 255).astype(np.uint8)


def _black(i: int) -> np.ndarray:
    rng = np.random.default_rng(i)
    return np.clip(rng.normal(0.4, 0.6, (H, W, 3)), 0, 255).astype(np.uint8)


def _paper(i: int) -> np.ndarray:
    rng = np.random.default_rng(i)
    return np.clip(np.full((H, W, 3), 200, np.float32) + rng.normal(0, 1.5, (H, W, 3)), 0, 255).astype(np.uint8)


def _half(i: int) -> np.ndarray:
    img = _normal(i).copy()
    img[:, : W // 2] = _finger(i)[:, : W // 2]
    return img


def _lights_off(i: int) -> np.ndarray:
    return syn.dim(_normal(i), 0.12)


def _shutter(i: int) -> np.ndarray:
    return np.zeros((H, W, 3), np.uint8)


def _translucent(i: int) -> np.ndarray:
    return (0.55 * _normal(i).astype(np.float32) + 0.45 * _finger(i).astype(np.float32)).astype(np.uint8)


def _brightness_swing(i: int) -> np.ndarray:
    k = 1.0 + 0.5 * np.sin(i / 8.0)
    return np.clip(_normal(i).astype(np.float32) * k, 0, 255).astype(np.uint8)


def _timeline(parts: Sequence[tuple[Callable[[int], np.ndarray], float]]) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    for fn, secs in parts:
        for _ in range(int(round(secs / DT))):
            frames.append(fn(len(frames)))
    return frames


def _slow_cover() -> list[np.ndarray]:
    frames = _timeline([(_normal, 4)])
    n = int(1.5 / DT)
    for k in range(n):
        a = (k + 1) / n
        i = len(frames)
        frames.append((_normal(i).astype(np.float32) * (1 - a) + _finger(i).astype(np.float32) * a).astype(np.uint8))
    return frames + _timeline([(_finger, 3)])


SYNTHETIC: dict[str, tuple[Scenario, Callable[[], list[np.ndarray]]]] = {}


def _reg(name, desc, expect, cover, build, limit=False):
    SYNTHETIC[name] = (Scenario(name, desc, expect, cover, limit), build)


_reg("normal_use", "Normal scene for 60 s", False, None, lambda: _timeline([(_normal, 60)]))
_reg("dim_room", "Dim room with screen glow", False, None, lambda: _timeline([(lambda i: syn.dim(_normal(i), 0.3), 30)]))
_reg("lights_off", "Lights switched off, screen glow remains", False, None, lambda: _timeline([(_normal, 4), (_lights_off, 20)]))
_reg("brightness_swing", "Screen/sun brightness oscillating", False, None, lambda: _timeline([(_brightness_swing, 60)]))
_reg("hand_fast", "Hand covers lens quickly", True, 4.0, lambda: _timeline([(_normal, 4), (_finger, 4)]))
_reg("hand_slow", "Hand approaches slowly over 1.5 s", True, 5.5, _slow_cover)
_reg("finger", "Finger over lens", True, 4.0, lambda: _timeline([(_normal, 4), (_finger, 4)]))
_reg("cloth", "Dark cloth over lens", True, 4.0, lambda: _timeline([(_normal, 4), (_black, 4)]))
_reg("paper", "Sheet of paper over lens", True, 4.0, lambda: _timeline([(_normal, 4), (_paper, 4)]))
_reg("shutter", "Privacy shutter closed (constant black)", True, 4.0, lambda: _timeline([(_normal, 4), (_shutter, 4)]))
_reg("partial", "Half the lens covered", False, 4.0, lambda: _timeline([(_normal, 4), (_half, 5)]))
_reg("translucent", "Translucent material (blend)", False, 4.0, lambda: _timeline([(_normal, 4), (_translucent, 5)]), True)


def evaluate_frames(
    frames: Iterable[np.ndarray],
    baseline: Baseline,
    cfg: ObstructionConfig,
    scenario: Scenario,
    mode: str = "balanced",
    thresholds: Thresholds | None = None,
) -> ClipResult:
    clf = ObstructionClassifier(baseline, cfg, mode, thresholds)
    ex = FeatureExtractor()
    first_confirm: float | None = None
    for k, img in enumerate(frames):
        r = clf.update(ex.update(img), k * DT)
        if r.state == ObstructionState.CONFIRMED_OBSTRUCTION and first_confirm is None:
            first_confirm = k * DT
    confirmed = first_confirm is not None
    latency = None
    if confirmed and scenario.cover_start_s is not None:
        latency = max(0.0, first_confirm - scenario.cover_start_s)
    passed = confirmed == scenario.expect_confirm
    if passed and scenario.expect_confirm and latency is not None and latency > 1.5 + 2 * DT:
        passed = False
    note = ""
    if confirmed and not scenario.expect_confirm:
        note = "FALSE POSITIVE"
    elif not confirmed and scenario.expect_confirm:
        note = "MISSED"
    return ClipResult(scenario.name, scenario.expect_confirm, confirmed, latency, passed, scenario.known_limit, note)


def synthetic_baseline() -> Baseline:
    return baseline_from_images([_normal(i) for i in range(30)], "synthetic", f"{W}x{H}")


def run_synthetic(cfg: ObstructionConfig, mode: str = "balanced") -> list[ClipResult]:
    base = synthetic_baseline()
    return [evaluate_frames(build(), base, cfg, sc, mode) for sc, build in SYNTHETIC.values()]


# --- recorded clips (git-ignored, contain the user's room) ---------------------------------------
def save_clip(path: Path, frames: np.ndarray, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, frames=frames, meta=json.dumps(meta))


def load_clip(path: Path) -> tuple[np.ndarray, dict]:
    with np.load(path, allow_pickle=False) as z:
        return z["frames"], json.loads(str(z["meta"]))


def to_markdown(results: Sequence[ClipResult], title: str) -> str:
    lines = [f"### {title}", "", "| Scenario | Expected | Confirmed | Latency (s) | Result | Note |", "|---|---|---|---|---|---|"]
    for r in results:
        res = "PASS" if r.passed else ("KNOWN LIMIT" if r.known_limit else "FAIL")
        lat = f"{r.latency_s:.1f}" if r.latency_s is not None else "-"
        lines.append(
            f"| {r.scenario} | {'confirm' if r.expect_confirm else 'no confirm'} | {'yes' if r.confirmed else 'no'} | {lat} | {res} | {r.note} |"
        )
    return "\n".join(lines) + "\n"

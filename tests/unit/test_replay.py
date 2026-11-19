import json
import subprocess
from pathlib import Path

import numpy as np

from silentwatch.camera.replay import SYNTHETIC, load_clip, run_synthetic, save_clip
from silentwatch.config import default_config

ROOT = Path(__file__).parents[2]
CFG = default_config().obstruction


def test_replay_is_deterministic():
    a = [(r.scenario, r.confirmed, r.latency_s) for r in run_synthetic(CFG)]
    b = [(r.scenario, r.confirmed, r.latency_s) for r in run_synthetic(CFG)]
    assert a == b


def test_all_synthetic_scenarios_pass_or_are_known_limits():
    for r in run_synthetic(CFG):
        assert r.passed or r.known_limit, f"{r.scenario}: {r.note}"


def test_opaque_covers_confirm_within_1_5_s():
    res = {r.scenario: r for r in run_synthetic(CFG)}
    for name in ("hand_fast", "hand_slow", "finger", "cloth", "paper", "shutter"):
        assert res[name].confirmed and res[name].latency_s <= 1.5, name


def test_lights_off_and_normal_use_never_confirm():
    res = {r.scenario: r for r in run_synthetic(CFG)}
    for name in ("normal_use", "dim_room", "lights_off", "brightness_swing"):
        assert not res[name].confirmed, name


def test_strict_mode_not_slower_than_balanced():
    bal = {r.scenario: r for r in run_synthetic(CFG, "balanced")}
    strict = {r.scenario: r for r in run_synthetic(CFG, "strict")}
    assert strict["finger"].latency_s <= bal["finger"].latency_s


def test_manifest_matches_registry():
    m = json.loads((ROOT / "tests/fixtures/clips_manifest.json").read_text())
    assert set(m) == set(SYNTHETIC)
    assert all(m[n]["expect_confirm"] == SYNTHETIC[n][0].expect_confirm for n in m)


def test_clip_roundtrip(tmp_path):
    frames = np.random.default_rng(0).integers(0, 255, (5, 96, 128, 3), dtype=np.uint8)
    p = tmp_path / "x" / "take1.npz"
    save_clip(p, frames, {"scenario": "x", "expect_confirm": False})
    f2, meta = load_clip(p)
    assert (f2 == frames).all() and meta["scenario"] == "x"


def test_recorded_data_is_git_ignored():
    out = subprocess.run(["git", "check-ignore", "-q", "data/clips/normal/take1.npz"], cwd=ROOT)
    assert out.returncode == 0

import time

import numpy as np
import pytest

from silentwatch.camera.integrity import FeatureExtractor, FrameFeatures, extract_features
from tests.fixtures import synthetic as syn


def feats(img, prev=None):
    return extract_features(img, prev)[0]


def test_black_frame():
    f = feats(syn.black())
    assert f.mean_luma == 0 and f.dark_ratio == 1.0
    assert f.edge_density == 0 and f.std_luma == 0 and f.structure_ratio == 0
    assert f.tile_flat_ratio == 1.0


def test_checkerboard_has_high_edges_and_contrast():
    f = feats(syn.checkerboard())
    assert f.edge_density > 0.05 and f.std_luma > 100 and f.tile_flat_ratio == 0.0


def test_uniform_gray_is_featureless_but_not_dark():
    f = feats(syn.uniform(128))
    assert f.dark_ratio == 0 and f.edge_density == 0 and f.std_luma == 0
    assert f.tile_flat_ratio == 1.0


def test_blur_reduces_sharpness():
    base = syn.checkerboard(cell=8)
    assert feats(syn.blurred(base, 31)).laplacian_var < feats(base).laplacian_var


def test_frame_diff():
    a = syn.scene(1)
    _, ga = extract_features(a)
    same = feats(a, ga)
    other = feats(syn.scene(2), ga)
    assert same.frame_diff == 0 and other.frame_diff > 5


def test_dim_textured_scene_beats_black():
    dim = feats(syn.dim(syn.checkerboard(cell=80), 0.2))
    black = feats(syn.black())
    assert dim.mean_luma < 60 and dim.edge_density > black.edge_density
    assert dim.structure_ratio > 0.1


def test_pure_noise_has_no_structure():
    f = feats(syn.noise(1, mean=60, sigma=20))
    assert f.structure_ratio < 0.15 and f.edge_density >= 0
    real = feats(syn.scene(1))
    assert real.structure_ratio > f.structure_ratio + 0.2


@pytest.mark.parametrize("bad", [None, np.zeros((0, 0, 3), np.uint8), np.zeros((4, 4, 3, 1), np.uint8), "x"])
def test_invalid_input(bad):
    with pytest.raises(ValueError):
        extract_features(bad)


def test_grayscale_input_accepted():
    f = feats(np.full((120, 160), 90, np.uint8))
    assert f.mean_luma == pytest.approx(90, abs=1)


def test_determinism():
    img = syn.scene(3)
    assert feats(img) == feats(img.copy())


def test_extractor_tracks_previous_frame():
    ex = FeatureExtractor()
    ex.update(syn.scene(1))
    assert ex.update(syn.scene(1)).frame_diff == 0
    assert ex.update(syn.scene(9)).frame_diff > 5


def test_performance_under_5ms():
    img = syn.scene(4)
    extract_features(img)  # warm up
    n = 200
    t = time.perf_counter()
    for _ in range(n):
        extract_features(img)
    per = (time.perf_counter() - t) / n * 1000
    assert per < 5.0, f"{per:.2f} ms/frame"


def test_feature_names_complete():
    assert set(FrameFeatures.names()) == set(feats(syn.scene(1)).as_dict())

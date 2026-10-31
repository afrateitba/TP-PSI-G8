import numpy as np
import pytest
from skimage.transform import resize

from src.config import RAW_DIR, SPLIT_CSV
from src.evaluation import (build_sample, load_sample, map_images, sample_auc, sample_values)
from src.metrics import auc_by_subset

HAS_DATA = (RAW_DIR / "images").exists() and SPLIT_CSV.exists()


def _scene(h=200, w=260, seed=0):
    rng = np.random.default_rng(seed)
    vessels = np.zeros((h, w), bool)
    vessels[40:41, 10:250] = True        # fino
    vessels[100:105, 10:250] = True      # mediano
    vessels[150:161, 10:250] = True      # grueso
    fov = np.ones((h, w), bool)
    fov[:5] = fov[-5:] = False
    score = vessels * 1.0 + rng.normal(0, 0.8, (h, w))
    return vessels, fov, score


def test_build_sample_takes_all_vessels_and_a_fraction_of_background():
    vessels, fov, _ = _scene()
    s = build_sample(vessels, fov, np.random.default_rng(1), bg_fraction=0.2)
    assert s.truth.sum() == (vessels & fov).sum()
    n_bg = (fov & ~vessels).sum()
    assert (~s.truth).sum() == round(0.2 * n_bg)
    assert set(np.unique(s.cls[s.truth])) == {1, 2, 3}
    assert (s.cls[~s.truth] == 0).all()


def test_sample_values_match_resize():
    rng = np.random.default_rng(2)
    small = rng.normal(size=(50, 65))
    full = resize(small, (100, 130), order=1, preserve_range=True, anti_aliasing=False)
    vessels = np.zeros((100, 130), bool)
    vessels[40:60, 40:90] = True
    s = build_sample(vessels, np.ones((100, 130), bool), np.random.default_rng(0), bg_fraction=1.0)
    inner = (s.rows > 2) & (s.rows < 97) & (s.cols > 2) & (s.cols < 127)
    assert np.allclose(sample_values(small, s)[inner], full[s.rows, s.cols][inner], atol=1e-6)


def test_sample_auc_close_to_full_auc():
    vessels, fov, score = _scene()
    s = build_sample(vessels, fov, np.random.default_rng(3), bg_fraction=0.2)
    fast = sample_auc(score, s)
    thin = np.zeros_like(vessels)
    thin[40:41] = True
    full = auc_by_subset(score, vessels, {"finos": thin}, fov)
    assert fast["todos"] == pytest.approx(full["todos"], abs=0.01)
    assert fast["finos"] == pytest.approx(full["finos"], abs=0.02)


def _square(x):
    return x * x


def test_map_images_keeps_order():
    assert map_images(_square, [3, 1, 2], workers=1) == [9, 1, 4]
    assert map_images(_square, [3, 1, 2], workers=2) == [9, 1, 4]


@pytest.mark.skipif(not HAS_DATA, reason="faltan las imágenes en data/raw")
def test_load_sample_is_cached_and_fixed(tmp_path):
    a = load_sample("01_h", cache_dir=tmp_path)
    assert (tmp_path / "muestra_01_h.npz").exists()
    b = load_sample("01_h", cache_dir=tmp_path)
    assert np.array_equal(a.rows, b.rows) and np.array_equal(a.cls, b.cls)
    assert 0.05 < a.truth.mean() < 0.6


def test_weighted_matthews_matches_full_count():
    from src.evaluation import weighted_matthews
    from src.metrics import matthews
    rng = np.random.default_rng(4)
    truth = rng.random(200000) < 0.1
    pred = np.where(truth, rng.random(truth.size) < 0.8, rng.random(truth.size) < 0.05)
    keep = truth | (rng.random(truth.size) < 0.2)           # todos los vasos y 20 % del fondo
    w = np.where(truth[keep], 1.0, 5.0)
    assert weighted_matthews(pred[keep], truth[keep], w) == pytest.approx(matthews(pred, truth), abs=0.01)

import numpy as np
import pytest
from skimage.color import rgb2gray

from src.color import (MAP_NAMES, basic_maps, color_maps, color_maps_at_scale, pca_directions, pca_maps,
                       sign_by_max_coef, sign_by_vessels, standardize)
from src.metrics import auc


def _fake_fundus(h=240, w=320, seed=2026):
    """Retina rojiza con manchas de color suaves y vasos finos oscuros en el verde."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:h, :w]
    region = (yy - h / 2) ** 2 + (xx - w / 2) ** 2 <= (0.45 * w) ** 2
    rgb = np.zeros((h, w, 3))
    rgb[..., 0] = 170 + 25 * np.sin(xx / 40)          # el rojo varía en el fondo
    rgb[..., 1] = 70 + 10 * np.cos(yy / 30)
    rgb[..., 2] = 30 + 5 * np.sin((xx + yy) / 50)
    vessels = np.zeros((h, w), bool)
    for r in (60, 120, 180):
        vessels[r - 1:r + 2, 30:290] = True             # vasos de 3 píxeles
    rgb[vessels] -= [25, 35, 8]                         # más oscuros, sobre todo en verde
    rgb += rng.normal(0, 2, rgb.shape)
    rgb[~region] = 0
    return rgb.clip(0, 255).astype(np.uint8), region, vessels & region


def test_basic_maps_match_definitions():
    rgb, _, _ = _fake_fundus()
    m = basic_maps(rgb)
    assert list(m) == MAP_NAMES[:7]
    assert np.allclose(m["Verde"], rgb[..., 1] / 255.0)
    assert np.allclose(m["Escala de grises"], rgb2gray(rgb.astype(np.float32) / 255.0))


def test_pca_directions_are_orthonormal_and_sorted():
    rgb, region, _ = _fake_fundus()
    mean, vec, frac = pca_directions(rgb, region)
    assert np.allclose(vec.T @ vec, np.eye(3), atol=1e-6)
    assert frac.sum() == pytest.approx(1) and (np.diff(frac) <= 0).all()
    assert np.allclose(mean, rgb[region].mean(axis=0) / 255.0, atol=1e-6)


def test_sign_by_max_coef():
    v = sign_by_max_coef(np.array([[0.1, -0.9, 0.0], [-0.8, 0.2, 1.0], [0.6, 0.4, 0.0]]))
    assert (v[np.argmax(np.abs(v), axis=0), range(3)] > 0).all()


def test_sign_by_vessels_ignores_input_sign_and_makes_vessels_bright():
    rgb, region, vessels = _fake_fundus()
    mean, vec, _ = pca_directions(rgb, region)
    a = sign_by_vessels(rgb, region, mean, vec, step=1, size=11)
    b = sign_by_vessels(rgb, region, mean, -vec, step=1, size=11)
    assert np.allclose(a, b)
    maps = pca_maps(rgb, mean, a)
    best = max(maps.values(), key=lambda m: auc(m, vessels, region))
    assert auc(best, vessels, region) > 0.9            # vasos como valores altos


def test_color_maps_has_the_ten_maps():
    rgb, region, _ = _fake_fundus()
    for rule in ("max_coef", "vessels"):
        m = color_maps(rgb, region, pca_sign=rule)
        assert list(m) == MAP_NAMES
        assert all(x.shape == rgb.shape[:2] for x in m.values())
    with pytest.raises(ValueError):
        color_maps(rgb, region, pca_sign="otra")


def test_standardize_uses_region_only():
    m = np.arange(16, dtype=float).reshape(4, 4)
    region = np.zeros((4, 4), bool)
    region[1:3, 1:3] = True
    z = standardize(m, region)
    assert z[region].mean() == pytest.approx(0, abs=1e-6)
    assert z[region].std() == pytest.approx(1, abs=1e-6)


def test_color_maps_at_scale_returns_original_size():
    rgb, region, vessels = _fake_fundus(h=240, w=320)
    for f in (1, 2, 4):
        m = color_maps_at_scale(rgb, f, names=["Verde", "PC3"])
        assert list(m) == ["Verde", "PC3"]
        assert all(v.shape == rgb.shape[:2] for v in m.values())
    # a la mitad, el verde sigue separando los vasos de 3 píxeles
    half = color_maps_at_scale(rgb, 2, names=["Verde"])["Verde"]
    assert auc(-half, vessels, region) > 0.8

import numpy as np
import pytest

from src.config import ENHANCE_FILTERS
from src.enhance import (apply_filter, fill_outside, frangi_filter, gabor_filter,
                         glcm_texture, line_detector, matched_filter, orient,
                         prepare_maps, quantize, scale_px, sigma_for_width, tophat,
                         upscale)


def synthetic_line(width=5, dark=True, n=101):
    """Imagen plana con una línea vertical de ancho conocido en el centro."""
    background, vessel = (100.0, 50.0) if dark else (50.0, 100.0)
    img = np.full((n, n), background, dtype=np.float32)
    c = n // 2
    img[:, c - width // 2: c + width // 2 + 1] = vessel
    line = np.zeros((n, n), bool)
    line[:, c - width // 2: c + width // 2 + 1] = True
    return img, line


def diagonal_line(width=5, n=101):
    """Línea clara a 45°, de ancho aproximado `width`, sobre fondo plano."""
    y, x = np.mgrid[:n, :n]
    line = np.abs(x - y) / np.sqrt(2) <= width / 2
    return np.where(line, 100.0, 50.0).astype(np.float32), line


# --- Preparación ---------------------------------------------------------------

def test_scale_px():
    assert scale_px(0.001, 3262) == pytest.approx(3.262)


def test_orient_flips_green():
    m = np.array([[0.2, 0.8]], dtype=np.float32)
    assert np.array_equal(orient(m, "Verde"), -m)
    assert np.array_equal(orient(m, "PC3"), m)


def test_fill_outside_removes_step():
    img = np.zeros((50, 50), np.float32)
    region = np.zeros((50, 50), bool)
    region[10:40, 10:40] = True
    img[region] = 7.0
    assert np.all(fill_outside(img, region) == 7.0)   # afuera copia el valor del borde de adentro


# --- Sombrero de copa y Frangi -------------------------------------------------

def test_tophat_highlights_line():
    img, line = synthetic_line(width=5, dark=False)
    out = tophat(img, radius_px=6)
    assert out[line].mean() == pytest.approx(50.0)          # todo el contraste en la línea
    assert np.abs(out[~line]).max() == pytest.approx(0.0)   # fondo plano → cero


def test_tophat_ignores_wide_structures():
    # una banda de 31 píxeles no entra en un disco de radio 6: no se resalta entera
    img, line = synthetic_line(width=31, dark=False)
    assert tophat(img, radius_px=6)[line].mean() < 5


def test_frangi_highlights_line():
    img, line = synthetic_line(width=5, dark=False)
    out = frangi_filter(img, [sigma_for_width(5)])
    c = img.shape[0] // 2
    assert out[10:-10, c].min() > 10 * out[10:-10, :c - 10].max()


def test_frangi_ignores_fov_edge_after_filling():
    # un disco claro (la retina) sobre negro: sin rellenar, el borde parece un vaso
    n = 201
    yy, xx = np.mgrid[:n, :n]
    region = np.hypot(yy - n // 2, xx - n // 2) < 80
    img = np.where(region, 1.0, 0.0).astype(np.float32)
    edge = region & ~np.pad(region[2:-2, 2:-2] & region[:-4, 2:-2] & region[4:, 2:-2]
                            & region[2:-2, :-4] & region[2:-2, 4:], 2)
    raw = frangi_filter(img, [2.0])
    filled = frangi_filter(fill_outside(img, region), [2.0])
    assert filled[edge].max() < 0.1 * raw[edge].max()


# --- Filtros orientados ----------------------------------------------------------

ORIENTED = [
    lambda m: matched_filter(m, sigma_px=2.5, length_px=9),
    lambda m: line_detector(m, length_px=15),
    lambda m: gabor_filter(m, sigma_px=2.5),
]


@pytest.mark.parametrize("f", ORIENTED)
def test_oriented_highlights_line_not_background(f):
    img, line = synthetic_line(width=5, dark=False)
    out = f(img)
    c = img.shape[0] // 2
    assert out[20:-20, c].min() > 1                      # centro de la línea: positivo
    assert np.abs(out[20:-20, 5:c - 20]).max() < 1e-3    # fondo plano, también junto al borde: cero


@pytest.mark.parametrize("f", ORIENTED)
def test_oriented_works_on_diagonal(f):
    vertical, _ = synthetic_line(width=5, dark=False)
    diagonal, _ = diagonal_line(width=5)
    c = vertical.shape[0] // 2
    assert f(diagonal)[c, c] == pytest.approx(f(vertical)[c, c], rel=0.25)   # no depende de la orientación


@pytest.mark.parametrize("f", [ORIENTED[0], ORIENTED[2]])
def test_matched_and_gabor_ignore_wide_structures(f):
    narrow, _ = synthetic_line(width=5, dark=False)
    wide, _ = synthetic_line(width=31, dark=False)
    c = narrow.shape[0] // 2
    assert f(wide)[c, c] < 0.1 * f(narrow)[c, c]         # el centro de una meseta da casi 0


# --- Textura -----------------------------------------------------------------------

def test_quantize_splits_evenly():
    m = np.random.default_rng(2026).random((100, 100)).astype(np.float32)
    q = quantize(m, 8)
    assert q.min() == 0 and q.max() == 7
    counts = np.bincount(q.ravel(), minlength=8)
    assert counts.min() > 0.9 * counts.max()       # cada nivel con ~1/8 de los píxeles


def test_glcm_constant_image():
    t = glcm_texture(np.full((40, 40), 3, np.uint8), levels=8, window_px=7)
    assert np.allclose(t["contraste"], 0)
    assert np.allclose(t["homogeneidad"], 1)
    assert np.allclose(t["energía"], 1)


def test_glcm_vertical_stripes():
    # columnas 0, 1, 0, 1…: el vecino horizontal y los diagonales siempre difieren en 1;
    # el vertical, nunca. Promedio de las 4 direcciones: contraste 3/4, homogeneidad
    # (3 · 1/2 + 1) / 4 = 0,625; energía 1/2 en cada dirección.
    # ventana de lado par: cubre tantas columnas 0 como 1
    q = np.tile(np.array([0, 1], np.uint8), (40, 20))
    t = glcm_texture(q, levels=2, window_px=8)
    center = (slice(10, 30), slice(10, 30))
    assert np.allclose(t["contraste"][center], 0.75)
    assert np.allclose(t["homogeneidad"][center], 0.625)
    assert np.allclose(t["energía"][center], 0.5)


def test_glcm_matches_skimage():
    # con una ventana que cubre casi toda la imagen, el contraste y la energía
    # (promediados en las 4 direcciones) coinciden con graycomatrix
    from skimage.feature import graycomatrix, graycoprops
    rng = np.random.default_rng(2026)
    q = rng.integers(0, 4, (60, 60)).astype(np.uint8)
    t = glcm_texture(q, levels=4, window_px=61)
    g = graycomatrix(q, [1], [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4], levels=4,
                     symmetric=True, normed=True)
    assert t["contraste"][30, 30] == pytest.approx(graycoprops(g, "contrast").mean(), rel=0.05)
    assert t["energía"][30, 30] == pytest.approx((graycoprops(g, "energy") ** 2).mean(), rel=0.05)


# --- Preparación de los mapas y resolución -------------------------------------------

def synthetic_photo():
    """Retina rojiza recortada arriba y abajo (como en la base), con un vaso vertical oscuro."""
    rng = np.random.default_rng(2026)
    h, w = 400, 600
    yy, xx = np.mgrid[:h, :w]
    fov = np.hypot(yy - h / 2, xx - w / 2) < 250
    vessel = fov & (np.abs(xx - 330) <= 3)
    rgb = np.zeros((h, w, 3), np.float32)
    rgb[fov] = (180, 90, 40)
    rgb[vessel] = (150, 50, 30)
    rgb[fov] += rng.normal(0, 3, (fov.sum(), 3))
    return rgb.clip(0, 255).astype(np.uint8), fov, vessel


@pytest.mark.parametrize("factor", [1, 2, 4])
def test_prepare_maps_reduces_and_measures_diameter(factor):
    rgb, fov, vessel = synthetic_photo()
    maps, region, diameter = prepare_maps(rgb, ["Verde", "PC3"], factor)
    assert maps["Verde"].shape == (400 // factor, 600 // factor)
    assert diameter == pytest.approx(500 / factor, abs=3)


def test_prepare_maps_orients_and_fills():
    rgb, fov, vessel = synthetic_photo()
    maps, region, _ = prepare_maps(rgb, ["Verde"])
    green = maps["Verde"]
    assert green[vessel].mean() > green[fov & ~vessel].mean()     # vaso claro tras invertir
    inside = green[region]
    assert inside.min() - 1e-6 <= green[0, 0] <= inside.max() + 1e-6   # sin escalón afuera


def test_upscale_returns_original_shape():
    assert upscale(np.ones((100, 150), np.float32), (400, 600)).shape == (400, 600)


@pytest.mark.parametrize("factor", [1, 2])
def test_frangi_at_reduced_resolution_finds_vessel(factor):
    from src.metrics import auc
    rgb, fov, vessel = synthetic_photo()
    maps, _, diameter = prepare_maps(rgb, ["Verde"], factor)
    sigma = scale_px(sigma_for_width(7) / 500, diameter)     # vaso de 7 px en la original
    out = upscale(frangi_filter(maps["Verde"], [sigma]), rgb.shape[:2])
    assert auc(out, vessel, fov) > 0.95


# --- Filtros con los parámetros de la etapa 4 ------------------------------------------

def line_for_filters(width=5, n=121):
    img = np.full((n, n), 50.0, np.float32)
    c = n // 2
    img[:, c - width // 2: c + width // 2 + 1] = 100.0
    return img, c


@pytest.mark.parametrize("name", ENHANCE_FILTERS[1:])
def test_each_filter_highlights_line(name):
    img, c = line_for_filters()
    out = apply_filter(name, img, diameter=3262)
    assert out.shape == img.shape
    assert out[30:-30, c].mean() > out[30:-30, 5:c - 25].mean()


def test_no_filter_returns_map():
    img, _ = line_for_filters()
    assert np.array_equal(apply_filter("sin filtro", img, 3262), img)


def test_unknown_filter():
    img, _ = line_for_filters()
    with pytest.raises(ValueError):
        apply_filter("Sobel", img, 3262)


@pytest.mark.parametrize("name", ENHANCE_FILTERS[1:])
def test_works_with_small_diameter(name):
    # a la cuarta parte de la resolución las σ más chicas quedan en el piso de 0,5
    img, c = line_for_filters(width=3)
    assert np.isfinite(apply_filter(name, img, diameter=3262 / 4)).all()
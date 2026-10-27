import numpy as np
import pytest

from src.vessels import (MEDIUM, THICK, THIN, profile_width, skeleton_widths, visible_widths,
                         width_classes, width_map)


def _bars(widths, length=120, gap=20):
    """Barras horizontales de los anchos pedidos, una debajo de la otra."""
    h = sum(widths) + gap * (len(widths) + 1)
    img = np.zeros((h, length + 2 * gap), bool)
    rows, y = [], gap
    for w in widths:
        img[y:y + w, gap:gap + length] = True
        rows.append((y, y + w))
        y += w + gap
    return img, rows


@pytest.mark.parametrize("w", [1, 3, 5, 7, 9])
def test_odd_widths_are_exact(w):
    img, _ = _bars([w])
    skel, widths = skeleton_widths(img)
    # Lejos de las puntas, el ancho medido es el real.
    middle = widths[:, 40:-40][skel[:, 40:-40]]
    assert np.median(middle) == pytest.approx(w)


@pytest.mark.parametrize("w", [2, 4, 6])
def test_even_widths_are_one_less(w):
    img, _ = _bars([w])
    skel, widths = skeleton_widths(img)
    middle = widths[:, 40:-40][skel[:, 40:-40]]
    assert np.median(middle) == pytest.approx(w - 1)


def test_diagonal_vessel_within_one_pixel():
    # Vaso a 45°: píxeles a distancia perpendicular ≤ 2,5 de la recta y = x,
    # o sea 5 píxeles de ancho medidos en perpendicular.
    yy, xx = np.mgrid[:200, :200]
    img = (np.abs(yy - xx) / np.sqrt(2) <= 2.5) & (xx > 20) & (xx < 180)
    skel, widths = skeleton_widths(img)
    middle = widths[60:140, 60:140][skel[60:140, 60:140]]
    assert abs(np.median(middle) - 5) <= 1


def test_width_map_and_classes():
    img, rows = _bars([1, 5, 9])
    wmap = width_map(img)
    assert (wmap[~img] == 0).all()
    for (y0, y1), w in zip(rows, [1, 5, 9]):
        assert np.median(wmap[y0:y1, 40:-40]) == pytest.approx(w)
    classes = width_classes(wmap, (2, 6))
    assert (classes[~img] == 0).all()
    for (y0, y1), c in zip(rows, [THIN, MEDIUM, THICK]):
        assert np.median(classes[y0:y1, 40:-40]) == c


def test_empty_mask():
    empty = np.zeros((20, 20), bool)
    assert (width_map(empty) == 0).all()


# --- Ancho visible ---------------------------------------------------------

def _gaussian_vessels(fwhms_and_offsets, angle_deg, size=201, depth=80.0, noise=3.0, seed=2026):
    """Vasos oscuros de perfil de campana, paralelos, a `angle_deg` grados.

    Cada vaso es (ancho a mitad de profundidad, distancia perpendicular al centro).
    """
    rng = np.random.default_rng(seed)
    a = np.deg2rad(angle_deg)
    ty, tx = np.sin(a), np.cos(a)
    yy, xx = np.mgrid[:size, :size] - size // 2
    d = yy * tx - xx * ty                      # distancia con signo a la recta central
    img = np.full((size, size), 200.0)
    for fwhm, off in fwhms_and_offsets:
        sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
        img -= depth * np.exp(-((d - off) ** 2) / (2 * sigma ** 2))
    return img + rng.normal(0, noise, img.shape), (ty, tx)


@pytest.mark.parametrize("angle", [0, 30, 45])
@pytest.mark.parametrize("fwhm", [6, 10])
def test_profile_width_recovers_known_width(fwhm, angle):
    img, direction = _gaussian_vessels([(fwhm, 0)], angle)
    c = img.shape[0] // 2
    w = profile_width(img, (c, c), direction, half_length=max(12, 3 * fwhm))
    assert abs(w - fwhm) / fwhm < 0.10


def test_profile_width_flat_region_is_not_measurable():
    img = 200 + np.random.default_rng(1).normal(0, 3, (101, 101))
    assert np.isnan(profile_width(img, (50, 50), (0, 1), half_length=15))


def test_profile_width_wider_than_window_is_not_measurable():
    # Un vaso de 30 píxeles visto con una ventana de ±12: el perfil no vuelve al fondo.
    img, direction = _gaussian_vessels([(30, 0)], 0)
    c = img.shape[0] // 2
    assert np.isnan(profile_width(img, (c, c), direction, half_length=12))


def test_profile_width_next_to_dark_patch_is_not_measurable():
    # Vaso de 6 píxeles al lado de una mancha oscura ancha (como una hemorragia):
    # de ese lado el perfil no vuelve al fondo.
    img, direction = _gaussian_vessels([(6, 0), (40, 16)], 0)
    c = img.shape[0] // 2
    assert np.isnan(profile_width(img, (c, c), direction, half_length=15))


def test_profile_width_next_to_dark_edge_is_not_measurable():
    # Vaso de 6 píxeles a 4 píxeles de un borde oscuro (como el del campo de visión).
    img, direction = _gaussian_vessels([(6, 0)], 0)
    c = img.shape[0] // 2
    img[c + 4:, :] -= 100
    assert np.isnan(profile_width(img, (c, c), direction, half_length=15))


@pytest.mark.parametrize("offset, measurable", [(12, False), (25, True)])
def test_profile_width_with_neighbor_vessel(offset, measurable):
    # Otro vaso dentro de la ventana contamina el fondo: no medible.
    # Fuera de la ventana no molesta y el ancho sale bien.
    img, direction = _gaussian_vessels([(6, 0), (6, offset)], 0)
    c = img.shape[0] // 2
    w = profile_width(img, (c, c), direction, half_length=18)
    if measurable:
        assert w == pytest.approx(6, rel=0.1)
    else:
        assert np.isnan(w)



def test_visible_widths_on_synthetic_vessel():
    # Vaso horizontal de 7 píxeles marcado y con perfil visible de 7 píxeles.
    img, _ = _gaussian_vessels([(7, 0)], 0, size=301)
    vessels = np.zeros(img.shape, bool)
    vessels[147:154, 20:281] = True
    fov = np.ones(img.shape, bool)
    t = visible_widths(img, vessels, fov, n_points=20, rng=np.random.default_rng(0), border=10)
    assert len(t) == 20
    assert (t["marked_width"] == 7).all()
    assert t["visible_width"].median() == pytest.approx(7, rel=0.1)

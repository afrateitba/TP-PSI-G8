import numpy as np
import pytest

from src.vessels import MEDIUM, THICK, THIN, skeleton_widths, width_classes, width_map


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

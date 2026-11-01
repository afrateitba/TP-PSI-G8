import numpy as np
import pytest

from src.clinical import (clean_skeleton, clinical_measures, path_length, prune_spurs, segment_tortuosity,
                          segments, skeleton_length)


def _band(shape, dist_fn, half_width):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    return dist_fn(yy, xx) <= half_width


def test_skeleton_length_counts_straight_and_diagonal_steps():
    s = np.zeros((20, 20), bool)
    s[5, 2:12] = True                              # 10 píxeles en fila: 9 pasos
    assert skeleton_length(s) == pytest.approx(9)
    d = np.zeros((20, 20), bool)
    d[np.arange(10), np.arange(10)] = True         # diagonal: 9 pasos de √2
    assert skeleton_length(d) == pytest.approx(9 * np.sqrt(2))
    c = np.zeros((5, 5), bool)
    c[1, 1:3] = c[2, 2] = True                     # esquina: dos pasos rectos, la diagonal no se suma
    assert skeleton_length(c) == pytest.approx(2)


def test_segments_split_at_bifurcations():
    s = np.zeros((30, 30), bool)
    s[15, 2:28] = True
    s[2:15, 15] = True                             # una T: tres tramos
    _, n = segments(s)
    assert n == 3


def test_path_length_of_a_tilted_line_is_close_to_euclidean():
    xs = np.arange(0, 200)
    path = np.c_[np.round(xs / 2), xs]             # pendiente 1/2, en escalones de píxel
    exact = np.hypot(*(path[-1] - path[0]))
    assert path_length(path, 1) > 1.05 * exact     # con pasos de píxel sobra
    assert path_length(path, 6) == pytest.approx(exact, rel=0.01)


def test_tortuosity_of_straight_and_semicircular_vessels():
    shape = (300, 400)
    straight = _band(shape, lambda y, x: np.abs((y - 50) - 0.5 * (x - 50)) / np.hypot(1, 0.5)
                     * ((x > 30) & (x < 370)) + 1e3 * ~((x > 30) & (x < 370)), 2.5)
    fov = np.ones(shape, bool)
    t = segment_tortuosity(clean_skeleton(straight, fov, 3262), 3262)
    assert len(t) == 1 and t[0] == pytest.approx(1.0, abs=0.015)
    cy, cx, r = 250, 200, 120
    arc = _band(shape, lambda y, x: np.abs(np.hypot(y - cy, x - cx) - r) + 1e3 * (y > cy), 2.5)
    t = segment_tortuosity(clean_skeleton(arc, fov, 3262), 3262)
    assert len(t) == 1 and t[0] == pytest.approx(np.pi / 2, rel=0.03)


def test_prune_spurs_removes_short_side_branches_only():
    s = np.zeros((60, 120), bool)
    s[30, 5:115] = True
    s[25:30, 40] = True                            # ramita de 5 píxeles
    s[5:30, 80] = True                             # rama de 25 píxeles
    p = prune_spurs(s, max_len=10)
    assert not p[25:29, 40].any()
    assert p[5:29, 80].all()
    assert p[30, 10:110].all()


def test_clean_skeleton_fills_small_holes():
    m = np.zeros((60, 200), bool)
    m[22:39, 10:190] = True                        # vaso grueso de 17 píxeles
    m[29:32, 50:150] = False                       # reflejo central: agujero de 3 × 100
    skel = clean_skeleton(m, np.ones_like(m), diameter=3262)
    _, n = segments(skel)
    assert n == 1                                  # un solo tramo, sin el lazo del agujero


def test_clinical_measures_on_a_simple_mask():
    shape = (300, 400)
    fov = np.ones(shape, bool)
    m = np.zeros(shape, bool)
    m[148:153, 20:380] = True
    out = clinical_measures(m, fov)
    assert out["proporción"] == pytest.approx(m.sum() / fov.sum())
    assert out["tortuosidad"] == pytest.approx(1.0, abs=0.01)
    assert out["longitud"] > 0

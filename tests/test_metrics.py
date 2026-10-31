import numpy as np
import pytest

from src.metrics import (accuracy, auc, auc_by_subset, centerline_dice, centerline_precision, centerline_sensitivity,
                         centerline_sensitivity_by_class, confusion, dice, matthews, sensitivity,
                         specificity)


def _example(tp, fn, fp, tn):
    """Máscaras planas con las cantidades pedidas de cada caso."""
    truth = np.r_[np.ones(tp + fn, bool), np.zeros(fp + tn, bool)]
    pred = np.r_[np.ones(tp, bool), np.zeros(fn, bool), np.ones(fp, bool), np.zeros(tn, bool)]
    return pred, truth


def test_example_from_the_discussion():
    # 1.000.000 de píxeles, 100.000 de vaso: umbrales A y B de la charla sobre Youden.
    a = _example(tp=80_000, fn=20_000, fp=18_000, tn=882_000)
    b = _example(tp=90_000, fn=10_000, fp=90_000, tn=810_000)
    assert confusion(*a) == {"tp": 80_000, "fp": 18_000, "fn": 20_000, "tn": 882_000}
    assert matthews(*a) == pytest.approx(0.787, abs=1e-3)
    assert matthews(*b) == pytest.approx(0.625, abs=1e-3)
    assert dice(*a) == pytest.approx(160 / 198)
    assert dice(*b) == pytest.approx(180 / 280)
    assert sensitivity(*a) == pytest.approx(0.80)
    assert specificity(*b) == pytest.approx(0.90)
    assert accuracy(*a) == pytest.approx(0.962)


def test_perfect_and_inverted():
    truth = np.zeros((10, 10), bool)
    truth[3:6] = True
    assert matthews(truth, truth) == pytest.approx(1)
    assert matthews(~truth, truth) == pytest.approx(-1)
    assert dice(truth, truth) == pytest.approx(1)


def test_region_excludes_outside_pixels():
    truth = np.zeros((10, 10), bool)
    truth[:, 4] = True
    pred = truth.copy()
    pred[:, 0] = True                       # falsos positivos fuera de la región
    region = np.zeros((10, 10), bool)
    region[:, 2:] = True
    assert confusion(pred, truth, region)["fp"] == 0
    assert dice(pred, truth, region) == pytest.approx(1)


def test_empty_cases_give_nan_and_bad_shape_fails():
    empty = np.zeros((4, 4), bool)
    assert np.isnan(sensitivity(empty, empty))
    assert np.isnan(matthews(empty, empty))
    with pytest.raises(ValueError):
        confusion(empty, np.zeros((4, 5), bool))


def test_auc_known_values():
    truth = np.array([1, 1, 0, 0, 0], bool)
    assert auc(np.array([5, 4, 3, 2, 1.0]), truth) == pytest.approx(1)
    assert auc(np.array([1, 2, 3, 4, 5.0]), truth) == pytest.approx(0)
    assert auc(np.ones(5), truth) == pytest.approx(0.5)            # todo empatado
    # vasos 3 y 1, fondo 2, 0, 0: 3 le gana a los tres; 1 le gana a dos y pierde con uno
    assert auc(np.array([3, 1, 2, 0, 0.0]), truth) == pytest.approx(5 / 6)


def test_auc_region_and_errors():
    truth = np.array([1, 0, 0, 1], bool)
    score = np.array([0.9, 0.1, 0.95, 0.8])
    region = np.array([True, True, False, True])
    assert auc(score, truth, region) == pytest.approx(1)
    with pytest.raises(ValueError):
        auc(score, np.zeros(4, bool))


# --- Línea central -----------------------------------------------------------

def _bar(width, rows=(30, 70), length=100, size=(100, 120), center=None):
    img = np.zeros(size, bool)
    for r in rows:
        img[r - width // 2: r - width // 2 + width, 10:10 + length] = True
    return img


def test_centerline_ignores_drawn_width():
    # El experto marca 9 píxeles y el algoritmo 7, sobre los mismos vasos.
    expert, algo = _bar(9), _bar(7)
    assert sensitivity(algo, expert) == pytest.approx(7 / 9)
    assert centerline_sensitivity(algo, expert) == pytest.approx(1)
    assert centerline_precision(algo, expert) == pytest.approx(1)
    assert centerline_dice(algo, expert) == pytest.approx(1)


def test_centerline_missing_and_spurious_vessels():
    expert = _bar(5, rows=(30, 70))
    only_one = _bar(5, rows=(30,))
    assert centerline_sensitivity(only_one, expert) == pytest.approx(0.5, abs=0.02)
    assert centerline_precision(only_one, expert) == pytest.approx(1)
    extra = _bar(5, rows=(30, 70, 90))
    assert centerline_precision(extra, expert) == pytest.approx(2 / 3, abs=0.02)
    assert centerline_sensitivity(extra, expert) == pytest.approx(1)


def test_centerline_by_class():
    expert = np.zeros((120, 140), bool)
    expert[20:21, 10:130] = True      # fino (1 píxel)
    expert[50:55, 10:130] = True      # mediano (5)
    expert[80:91, 10:130] = True      # grueso (11)
    algo = expert.copy()
    algo[20:21] = False               # se pierde el fino
    by = centerline_sensitivity_by_class(algo, expert, (3.47, 9.0))
    assert by["fino"] < 0.05          # solo las puntas de la barra mediana miden menos de 3,47
    assert by["mediano"] == pytest.approx(1)
    assert by["grueso"] == pytest.approx(1)


def test_auc_by_subset_matches_auc_and_subsets():
    rng = np.random.default_rng(5)
    truth = rng.random(2000) < 0.2
    thin = truth & (rng.random(2000) < 0.5)
    score = rng.normal(size=2000) + 1.5 * truth - 1.0 * thin   # los finos se separan peor
    out = auc_by_subset(score, truth, {"finos": thin})
    assert out["todos"] == pytest.approx(auc(score, truth))
    assert out["finos"] == pytest.approx(auc(score[~truth | thin], thin[~truth | thin]))
    assert out["finos"] < out["todos"]

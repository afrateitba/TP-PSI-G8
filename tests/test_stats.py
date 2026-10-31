import numpy as np
import pandas as pd
import pytest

from src.split import person_folds
from src.stats import fisher_direction, percentile_interval, person_bootstrap_means


def _table():
    rows = [("a1", "h", "P1"), ("a2", "h", "P1"), ("b", "h", "P2"), ("c", "h", "P3"),
            ("d1", "dr", "P4"), ("d2", "dr", "P4"), ("e", "dr", "P5"), ("f", "dr", "P6"),
            ("g", "dr", "P7"), ("h1", "g", "P8"), ("h2", "g", "P8"), ("i", "g", "P9")]
    return pd.DataFrame(rows, columns=["image", "group", "person"])


def test_person_folds_keeps_persons_and_balances():
    t = _table()
    folds = person_folds(t, k=3, seed=1)
    assert set(folds.index) == set(t.person)
    assert sorted(folds.value_counts()) == [3, 3, 3]          # 9 personas en 3 grupos
    for g, d in t.drop_duplicates("person").groupby("group"):  # cada grupo clínico repartido
        assert folds[d.person].nunique() == min(3, len(d))
    assert folds.equals(person_folds(t, k=3, seed=1))


def test_person_bootstrap_resamples_whole_persons():
    t = _table().set_index("image")
    # Las dos imágenes de P1 valen 10; el resto 0. Si se sortea P1, entran las dos.
    vals = pd.Series(0.0, index=t.index)
    vals[["a1", "a2"]] = 10.0
    means = person_bootstrap_means(vals, t.person, reps=4000, seed=0)[:, 0]
    assert means.mean() == pytest.approx(vals.mean(), abs=0.15)
    lo, hi = percentile_interval(means)
    assert lo < vals.mean() < hi


def test_person_bootstrap_columns_share_draws():
    t = _table().set_index("image")
    rng = np.random.default_rng(3)
    a = pd.Series(rng.normal(size=len(t)), index=t.index)
    frame = pd.DataFrame({"a": a, "b": a + 0.5})
    m = person_bootstrap_means(frame, t.person, reps=500)
    assert np.allclose(m[:, 1] - m[:, 0], 0.5)                # diferencia apareada exacta


def test_fisher_direction_points_to_vessels():
    rng = np.random.default_rng(0)
    bg = rng.normal([0, 0], [1, 1], (5000, 2))
    ves = rng.normal([2, 0], [1, 1], (500, 2))               # solo el primer mapa separa
    x = np.r_[bg, ves]
    y = np.r_[np.zeros(5000, bool), np.ones(500, bool)]
    w = fisher_direction(x, y)
    assert w[0] > 0.95 and abs(w[1]) < 0.15


def test_fit_logistic_recovers_coefficients():
    from src.stats import fit_logistic, predict_logistic
    rng = np.random.default_rng(1)
    x = rng.normal(size=(20000, 2))
    true = np.array([-1.0, 2.0, 0.0])          # solo la primera columna importa
    p = 1 / (1 + np.exp(-(true[0] + x @ true[1:])))
    y = rng.random(len(p)) < p
    w = fit_logistic(x, y, ridge=1e-6)
    assert np.allclose(w, true, atol=0.1)
    assert np.all((predict_logistic(x, w) >= 0) & (predict_logistic(x, w) <= 1))


def test_fit_logistic_separable_does_not_explode():
    from src.stats import fit_logistic
    x = np.r_[np.linspace(-3, -1, 50), np.linspace(1, 3, 50)][:, None]
    y = np.r_[np.zeros(50, bool), np.ones(50, bool)]
    w = fit_logistic(x, y, ridge=1e-2)
    assert np.all(np.isfinite(w)) and w[1] > 0

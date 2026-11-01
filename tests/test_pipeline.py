import numpy as np
import pytest

from src.config import RAW_DIR, SEGMENT_FEATURES, SPLIT_CSV
from src.pipeline import (compute_features, load_weights, save_weights, segment_image,
                          segment_reference)

HAS_DATA = (RAW_DIR / "images").exists() and SPLIT_CSV.exists()


def _fake_fundus(h=360, w=480, seed=3):
    """Fondo de ojo sintético: círculo rojizo con iluminación despareja y vasos oscuros en el verde."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:h, :w]
    inside = (yy - h / 2) ** 2 + (xx - w / 2) ** 2 <= (0.46 * w) ** 2
    rgb = np.zeros((h, w, 3))
    rgb[..., 0] = 180
    rgb[..., 1] = 80 + 25 * xx / w                     # iluminación que crece a la derecha
    rgb[..., 2] = 35
    vessels = np.zeros((h, w), bool)
    for r in (110, 180, 250):
        vessels[r - 2:r + 3, 60:420] = True             # vasos de 5 píxeles
    rgb[vessels, 1] -= 35
    rgb += rng.normal(0, 2, rgb.shape)
    rgb[~inside] = 0
    return rgb.clip(0, 255).astype(np.uint8), vessels & inside, inside


def test_compute_features_shape_and_standardized():
    rgb, _, _ = _fake_fundus()
    f, region = compute_features(rgb, factor=1)
    assert f.shape == (len(SEGMENT_FEATURES),) + rgb.shape[:2]
    assert np.allclose(f[:, region].mean(axis=1), 0, atol=1e-3)


def test_segment_image_marks_the_fraction_and_finds_vessels():
    rgb, vessels, inside = _fake_fundus()
    w = np.zeros(len(SEGMENT_FEATURES) + 1)
    w[1 + SEGMENT_FEATURES.index("detector de líneas")] = 1.0   # solo el detector
    mask = segment_image(rgb, w, fraction=0.05)
    assert mask.shape == rgb.shape[:2] and mask.dtype == bool
    assert mask[inside].mean() == pytest.approx(0.05, abs=0.01)
    assert mask[vessels].mean() > 0.5                            # encuentra los vasos
    ref = segment_reference(rgb, fraction=0.05)
    assert (ref == mask).mean() > 0.99                           # con esos pesos es la referencia


def test_weights_round_trip(tmp_path):
    w = np.arange(len(SEGMENT_FEATURES) + 1, dtype=float)
    save_weights(w, tmp_path / "pesos.json", note="prueba")
    assert np.allclose(load_weights(tmp_path / "pesos.json"), w)


def test_dev_mask_cache_round_trip(tmp_path):
    from src.pipeline import load_dev_mask, save_dev_masks
    rng = np.random.default_rng(0)
    a, b = rng.random((37, 53)) > 0.5, rng.random((37, 53)) > 0.9
    save_dev_masks("01_h", {"combinación": a, "referencia": b}, cache=tmp_path)
    assert (load_dev_mask("01_h", "combinación", cache=tmp_path) == a).all()
    assert (load_dev_mask("01_h", "referencia", cache=tmp_path) == b).all()


def test_feature_bank_contains_base_maps_and_scales():
    from src.pipeline import compute_feature_bank
    rgb, _, _ = _fake_fundus()
    bank, names = compute_feature_bank(rgb, factor=2)
    base, _ = compute_features(rgb, factor=2)
    assert names[:len(SEGMENT_FEATURES)] == SEGMENT_FEATURES
    assert np.allclose(bank[:len(SEGMENT_FEATURES)], base, atol=1e-5)    # los mismos mapas de siempre
    assert sum(n.startswith("Gabor ") for n in names) == 5
    assert {"textura contraste", "textura homogeneidad", "textura energía"} <= set(names)
    assert np.isfinite(bank).all()


def _threshold_samples(share, bg_weight):
    """Muestras para el umbral donde solo el detector separa los vasos (una `share` de la muestra)."""
    rng = np.random.default_rng(1)
    ref = SEGMENT_FEATURES.index("detector de líneas")
    samples = {}
    for i in ("a", "b"):
        y = rng.random(4000) < share
        x = rng.normal(0, 1, (y.size, len(SEGMENT_FEATURES)))
        x[:, ref] = np.where(y, 3.0, -3.0) + rng.normal(0, 0.3, y.size)
        samples[i] = {"x_thr": x, "y_thr": y, "w_thr": np.where(y, 1.0, bg_weight)}
    return samples, ref


def test_choose_fraction_finds_the_weighted_vessel_share():
    from src.pipeline import choose_fraction
    samples, ref = _threshold_samples(0.6 / 1.48, 5.0)     # con el fondo pesando 5, los vasos son el 12 %
    w = np.zeros(len(SEGMENT_FEATURES) + 1)
    w[1 + ref] = 1.0
    assert choose_fraction(samples, w, ["a", "b"]) == pytest.approx(0.12)
    assert choose_fraction(samples, None, ["a", "b"]) == pytest.approx(0.12)   # la referencia


def test_choose_value_separates_the_vessels():
    from src.pipeline import choose_value
    samples, ref = _threshold_samples(0.12, 1.0)
    for weights in (None, np.r_[0.0, np.eye(len(SEGMENT_FEATURES))[ref]]):
        t = choose_value(samples, weights, ["a", "b"])
        x = samples["a"]["x_thr"][:, ref]
        score = x if weights is None else 1 / (1 + np.exp(-x))
        assert (score > t).mean() == pytest.approx(samples["a"]["y_thr"].mean(), abs=0.01)


def test_feature_scores_match_the_stacked_maps():
    from src.pipeline import feature_scores
    from src.stats import predict_logistic
    rgb, _, _ = _fake_fundus()
    f, region = compute_features(rgb, factor=2)
    w = np.random.default_rng(4).normal(0, 0.5, len(SEGMENT_FEATURES) + 1)
    (prob,), kept, region2 = feature_scores(rgb, [w], factor=2, keep=("detector de líneas",))
    expected = predict_logistic(f.reshape(len(f), -1).T, w).reshape(f.shape[1:])
    assert (region == region2).all()
    assert np.allclose(prob, expected, atol=1e-6)
    assert np.allclose(kept["detector de líneas"], f[SEGMENT_FEATURES.index("detector de líneas")])


def test_segment_image_at_full_resolution():
    rgb, vessels, inside = _fake_fundus()
    w = np.zeros(len(SEGMENT_FEATURES) + 1)
    w[1 + SEGMENT_FEATURES.index("detector de líneas")] = 1.0
    mask = segment_image(rgb, w, fraction=0.05, factor=1)
    assert mask.shape == rgb.shape[:2]
    assert mask[vessels].mean() > 0.5

import numpy as np
import pytest

from src.degrade import gaussian_blur, gaussian_noise, jpeg_recompress, restore_photo


def photo(n=128, seed=2026):
    """Foto sintética: retina rojiza en un círculo, fondo negro y un vaso oscuro con bordes netos."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:n, :n]
    region = np.hypot(yy - n / 2, xx - n / 2) < n * 0.45
    rgb = np.zeros((n, n, 3), np.float32)
    rgb[region] = (180, 90, 40)
    vessel = region & (np.abs(xx - n // 2) <= 2)
    rgb[vessel] = (140, 50, 30)
    rgb[region] += rng.normal(0, 1, (region.sum(), 3))
    return np.clip(rgb, 0, 255).astype(np.uint8), region


def mse(a, b, region):
    return float(((a.astype(float) - b.astype(float))[region] ** 2).mean())


def test_degradations_keep_shape_and_type():
    rgb, _ = photo()
    for out in (jpeg_recompress(rgb, 30), gaussian_blur(rgb, 2), gaussian_noise(rgb, 10, 1)):
        assert out.shape == rgb.shape and out.dtype == np.uint8


def test_lower_jpeg_quality_degrades_more():
    rgb, region = photo()
    assert mse(jpeg_recompress(rgb, 30), rgb, region) > mse(jpeg_recompress(rgb, 90), rgb, region)


def test_blur_zero_is_identity_and_blur_degrades():
    rgb, region = photo()
    assert np.array_equal(gaussian_blur(rgb, 0), rgb)
    assert mse(gaussian_blur(rgb, 4), rgb, region) > mse(gaussian_blur(rgb, 1), rgb, region) > 0


def test_noise_has_requested_sigma_and_is_reproducible():
    gray = np.full((200, 200, 3), 128, np.uint8)
    noisy = gaussian_noise(gray, 10, seed=7)
    assert (noisy.astype(float) - 128).std() == pytest.approx(10, rel=0.05)
    assert np.array_equal(noisy, gaussian_noise(gray, 10, seed=7))


@pytest.mark.parametrize("kind,degrade,kw", [
    ("wiener_ruido", lambda p: gaussian_noise(p, 20, seed=1), {}),
    ("wiener_desenfoque", lambda p: gaussian_blur(p, 2), {"blur_sigma_px": 2}),
])
def test_wiener_restores_and_keeps_outside(kind, degrade, kw):
    from scipy import ndimage as ndi
    rgb, region = photo(256)
    bad = degrade(rgb)
    fixed = restore_photo(bad, kind, region, **kw)
    # adentro, lejos del borde del campo (ahí la deconvolución oscila: ver restore_photo)
    inner = ndi.binary_erosion(region, iterations=15)
    assert mse(fixed, rgb, inner) < mse(bad, rgb, inner)            # mejora adentro
    assert np.array_equal(fixed[~region], bad[~region])            # afuera queda igual


def test_deblock_keeps_type():
    rgb, _ = photo()
    out = restore_photo(jpeg_recompress(rgb, 30), "bloques")
    assert out.shape == rgb.shape and out.dtype == np.uint8


def test_unknown_or_incomplete_restoration():
    rgb, region = photo()
    with pytest.raises(ValueError):
        restore_photo(rgb, "mediana", region)
    with pytest.raises(ValueError):
        restore_photo(rgb, "wiener_desenfoque", region)
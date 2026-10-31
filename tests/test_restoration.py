import numpy as np
import pytest

from src.restoration import (background_correct, clahe, deblock, fill_outside, gaussian_psf,
                         homomorphic, wiener_deblur, wiener_denoise)
from src.metrics import auc


def _scene(h=200, w=260, seed=0):
    """Fondo con iluminación inclinada, un vaso fino oscuro y ruido; región circular."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:h, :w]
    region = (yy - h / 2) ** 2 + (xx - w / 2) ** 2 <= (0.45 * w) ** 2
    m = 0.3 + 0.5 * xx / w                                  # iluminación que crece a la derecha
    vessel = np.zeros((h, w), bool)
    vessel[98:101, 20:240] = True                           # vaso de 3 píxeles
    m = m - 0.08 * vessel + rng.normal(0, 0.01, (h, w))
    m[~region] = 0
    return m.astype(np.float32), region, vessel & region


def test_fill_outside_copies_border():
    m = np.arange(25, dtype=float).reshape(5, 5)
    region = np.zeros((5, 5), bool)
    region[1:4, 1:4] = True
    f = fill_outside(m, region)
    assert np.allclose(f[region], m[region])
    assert f[0, 0] == m[1, 1] and f[4, 4] == m[3, 3]


def test_background_correct_flattens_and_keeps_vessel():
    m, region, vessel = _scene()
    out = background_correct(m, region, size=31)
    bg = region & ~vessel
    # el fondo queda plano: la diferencia izquierda-derecha casi desaparece
    left, right = out[bg & (np.arange(m.shape[1]) < 80)], out[bg & (np.arange(m.shape[1]) > 180)]
    assert abs(left.mean() - right.mean()) < 0.02
    assert auc(-out, vessel, region) > auc(-m, vessel, region)
    assert auc(-out, vessel, region) > 0.95


def test_clahe_in_unit_range_and_keeps_vessel():
    m, region, vessel = _scene()
    out = clahe(m, region)
    assert out.min() >= 0 and out.max() <= 1
    assert auc(-out, vessel, region) > auc(-m, vessel, region) + 0.05


def test_homomorphic_attenuates_illumination():
    # En el logaritmo, la diferencia lenta entre derecha e izquierda se reduce a la mitad.
    from src.restoration import _rescale
    m, region, vessel = _scene()
    out = homomorphic(m, region, sigma=20, low_gain=0.5)
    bg = region & ~vessel
    cols = np.arange(m.shape[1])
    before = np.log(_rescale(m, region) + 0.01)
    after = np.log(out)
    spread = lambda a: a[bg & (cols > 160) & (cols < 200)].mean() - a[bg & (cols > 60) & (cols < 100)].mean()
    assert spread(after) < 0.7 * spread(before)


def test_wiener_denoise_reduces_noise_keeps_edge():
    rng = np.random.default_rng(1)
    clean = np.zeros((120, 120), np.float32)
    clean[:, 60:] = 1.0
    noisy = clean + rng.normal(0, 0.1, clean.shape).astype(np.float32)
    region = np.ones(clean.shape, bool)
    out = wiener_denoise(noisy, region, size=5)
    assert out[:, 10:50].std() < 0.6 * noisy[:, 10:50].std()
    assert out[:, 62:110].mean() - out[:, 10:58].mean() > 0.9   # el borde sigue


def test_wiener_deblur_recovers_contrast():
    from scipy.signal import fftconvolve
    line = np.zeros((128, 128))
    line[62:65, :] = 1.0
    blurred = fftconvolve(line, gaussian_psf(2.0), mode="same")
    region = np.ones(line.shape, bool)
    out = wiener_deblur(blurred, region, sigma=2.0, balance=0.01)
    contrast = lambda a: a[60:67, 20:108].max() - np.median(a[20:40, 20:108])
    rescaled = (blurred - blurred.min()) / (blurred.max() - blurred.min())
    assert contrast(out) / out[20:108, 20:108].std() > contrast(rescaled) / rescaled[20:108, 20:108].std()


def test_deblock_reduces_block_jumps():
    rng = np.random.default_rng(2)
    blocks = np.kron(rng.integers(80, 160, (8, 8)), np.ones((8, 8))).astype(np.uint8)
    out = deblock(blocks)
    jump = lambda a: np.abs(np.diff(a.astype(float), axis=1))[:, 7::8].mean()
    assert jump(out) < 0.6 * jump(blocks)
    assert out.dtype == blocks.dtype
    # dentro de un bloque, lejos de los bordes, no cambia
    assert (out[3:5, 3:5] == blocks[3:5, 3:5]).all()
    rgb = np.stack([blocks] * 3, axis=2)
    assert deblock(rgb).shape == rgb.shape


def test_wiener_denoise_no_nan_in_flat_regions():
    m = np.zeros((60, 60), np.float32)
    m[20:40, 20:40] = np.random.default_rng(3).normal(0.5, 0.1, (20, 20))
    region = np.zeros((60, 60), bool)
    region[20:40, 20:40] = True
    out = wiener_denoise(m, region, size=5)
    assert np.isfinite(out).all()

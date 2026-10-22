import numpy as np
import pytest

from src.fov import detect_fov, detect_fov_robust, fov_diameter
from src.metrics import dice


def _fake_fundus(h=300, w=420, radius=190, seed=2026):
    """Círculo rojizo recortado arriba y abajo, con un 'vaso' oscuro y ruido afuera."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:h, :w]
    inside = (yy - h / 2) ** 2 + (xx - w / 2) ** 2 <= radius ** 2
    rgb = rng.normal(3, 2, (h, w, 3)).clip(0, 255)
    rgb[inside] = rng.normal([180, 70, 30], 15, (inside.sum(), 3)).clip(0, 255)
    rgb[140:150, 100:300, 0] = 40              # vaso grueso oscuro adentro
    rgb[5, 5, 0] = 200                         # punto brillante suelto afuera
    return rgb.astype(np.uint8), inside


def test_fov_diameter_of_cut_circle():
    _, inside = _fake_fundus()
    assert fov_diameter(inside) == 381       # 2·190 + 1
    with pytest.raises(ValueError):
        fov_diameter(np.zeros((5, 5), bool))


def test_detect_fov_recovers_circle():
    rgb, inside = _fake_fundus()
    found = detect_fov(rgb)
    assert dice(found, inside) > 0.999
    assert found[145, 200]                   # el vaso oscuro queda adentro
    assert not found[5, 5]                   # el punto suelto queda afuera


def _vignetted(h=400, w=560, radius=250, edge=0.35, background=3.0, seed=7):
    """Fondo de ojo con la periferia oscura: el brillo cae a `edge` en el borde."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:h, :w]
    r = np.hypot(yy - h / 2, xx - w / 2) / radius
    inside = r <= 1
    gain = 1 - (1 - edge) * r ** 2
    rgb = rng.normal(background, 2, (h, w, 3))
    rgb[inside] = (np.array([190, 75, 35]) * gain[inside, None]
                   + rng.normal(0, 8, (inside.sum(), 3)))
    return rgb.clip(0, 255).astype(np.uint8), inside


def test_robust_handles_dark_periphery():
    rgb, inside = _vignetted(edge=0.3)
    assert dice(detect_fov_robust(rgb), inside) > 0.99


@pytest.mark.parametrize("variant", ["gris", "oscura", "fondo_gris", "texto", "16_bits"])
def test_robust_other_configurations(variant):
    rgb, inside = _vignetted()
    if variant == "gris":                      # foto en escala de grises
        img = rgb[..., 1]
    elif variant == "oscura":                  # poca exposición
        img = (rgb * 0.4).astype(np.uint8)
    elif variant == "fondo_gris":              # afuera gris con ruido en vez de negro
        img = rgb.copy()
        img[~inside] = np.random.default_rng(1).normal(25, 5, ((~inside).sum(), 3)).clip(0, 255)
    elif variant == "texto":                   # etiqueta blanca en una esquina
        img = rgb.copy()
        img[5:25, 5:90] = 255
    else:                                      # imagen de 16 bits
        img = rgb.astype(np.uint16) * 257
    assert dice(detect_fov_robust(img), inside) > 0.99


def test_robust_full_frame_returns_everything():
    rgb, _ = _vignetted()
    crop = rgb[120:280, 200:360]               # recorte totalmente dentro de la retina
    assert detect_fov_robust(crop).all()


def test_detect_fov_margin():
    rgb, inside = _fake_fundus()
    smaller, larger = detect_fov(rgb, margin=3), detect_fov(rgb, margin=-3)
    assert smaller.sum() < inside.sum() < larger.sum()
    assert fov_diameter(inside) - fov_diameter(smaller) == pytest.approx(6, abs=1)

"""Degradaciones y restauración de la foto.  Esquema v1, etapa 8 (notebooks/08_robustez.ipynb).

Las degradaciones simulan una foto peor (más comprimida, desenfocada o con
ruido) y la restauración se aplica a la foto degradada antes del algoritmo.
Todas reciben y devuelven la foto a color en uint8, del mismo tamaño.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

RESTORATIONS = ("bloques", "wiener_ruido", "wiener_desenfoque")


def jpeg_recompress(rgb: np.ndarray, quality: int) -> np.ndarray:
    """Recomprime la foto en .jpg con calidad `quality` (en memoria) y la vuelve a leer."""
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality, subsampling=2)
    buf.seek(0)
    with Image.open(buf) as im:
        return np.asarray(im.convert("RGB")).copy()


def gaussian_blur(rgb: np.ndarray, sigma_px: float) -> np.ndarray:
    """Desenfoque gaussiano de desvío `sigma_px` píxeles en cada canal (bordes por reflexión)."""
    if sigma_px <= 0:
        return rgb.copy()
    out = ndi.gaussian_filter(rgb.astype(np.float32), sigma=(sigma_px, sigma_px, 0), mode="reflect")
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def gaussian_noise(rgb: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    """Ruido gaussiano de desvío `sigma` niveles de gris, independiente en cada píxel y canal.

    `seed` fija el ruido, para que cada imagen reciba siempre el mismo.
    """
    rng = np.random.default_rng(seed)
    noisy = rgb.astype(np.float32) + rng.normal(0, sigma, rgb.shape).astype(np.float32)
    return np.clip(np.round(noisy), 0, 255).astype(np.uint8)


def restore_photo(rgb: np.ndarray, kind: str, region: np.ndarray | None = None,
                  blur_sigma_px: float | None = None) -> np.ndarray:
    """Restaura la foto degradada con las funciones de la etapa 3 (src/restoration.py).

    `kind`:
    - "bloques": suavizado de los bordes de los bloques .jpg (deblock), a toda la foto;
    - "wiener_ruido": Wiener local (wiener_denoise) en cada canal;
    - "wiener_desenfoque": deconvolución de Wiener en cada canal, con un
      desenfoque gaussiano de desvío `blur_sigma_px` (el que se agregó).

    Los dos Wiener trabajan dentro del campo de visión `region` (si no se da,
    se detecta) y dejan el exterior como estaba: si el exterior quedara
    rellenado, la detección del campo de visión del algoritmo no encontraría
    el borde negro.

    Limitación: con desenfoque, la deconvolución oscila en una franja junto al
    borde del campo de visión (el desenfoque mezcló el negro de afuera con la
    retina). Lejos del borde reduce el error (en una foto sintética, de 7,6 a
    4,9 de error cuadrático medio; junto al vaso, de 82 a 45).
    """
    from skimage import restoration as skr

    from . import config as c
    from .restoration import deblock, fill_outside, gaussian_psf, wiener_denoise

    if kind == "bloques":
        return deblock(rgb)
    if kind not in RESTORATIONS:
        raise ValueError(f"Restauración desconocida: {kind!r}")
    if region is None:
        from .fov import detect_fov_robust
        region = detect_fov_robust(rgb)
    if kind == "wiener_desenfoque" and not blur_sigma_px:
        raise ValueError("Falta blur_sigma_px para la deconvolución de Wiener")
    out = rgb.copy()
    for ch in range(rgb.shape[2]):
        x = rgb[..., ch].astype(np.float32)
        if kind == "wiener_ruido":
            y = wiener_denoise(x, region, c.ROBUST_WIENER_SIZE)
        else:
            f = fill_outside(x / 255.0, region).astype(np.float64)
            y = 255.0 * skr.wiener(f, gaussian_psf(blur_sigma_px), c.ROBUST_DEBLUR_BALANCE, clip=False)
        out[..., ch] = np.where(region, np.clip(np.round(y), 0, 255), rgb[..., ch]).astype(np.uint8)
    return out
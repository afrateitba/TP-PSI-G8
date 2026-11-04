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

# --- Calidad de la foto y restauración clásica (temas obligatorios) -------------

def jpeg_size(rgb: np.ndarray, quality: int) -> int:
    """Tamaño en bytes de la foto guardada en .jpg con calidad `quality`."""
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality, subsampling=2)
    return buf.getbuffer().nbytes


def image_quality(img: np.ndarray, ref: np.ndarray, region: np.ndarray,
                  inner: np.ndarray | None = None) -> dict[str, float]:
    """PSNR y SSIM de `img` contra `ref` (una banda, 0–255), dentro de `region`.

    El PSNR usa el error cuadrático medio de los píxeles de la región; el SSIM
    es el promedio, en la región, del mapa de similitud estructural (skimage,
    ventana de 7 × 7). Si se da `inner` (por ejemplo, el campo de visión sin
    una franja junto al borde, donde la deconvolución oscila), agrega
    "PSNR interior" y "SSIM interior" con el mismo mapa.
    """
    from skimage.metrics import structural_similarity

    a = np.asarray(img, dtype=np.float64)
    b = np.asarray(ref, dtype=np.float64)
    _, ssim_map = structural_similarity(a, b, data_range=255.0, full=True)

    def psnr(r):
        mse = np.mean((a[r] - b[r]) ** 2)
        return float("inf") if mse == 0 else float(10 * np.log10(255.0 ** 2 / mse))

    out = {"PSNR": psnr(region), "SSIM": float(ssim_map[region].mean())}
    if inner is not None:
        out.update({"PSNR interior": psnr(inner), "SSIM interior": float(ssim_map[inner].mean())})
    return out


def inner_region(region: np.ndarray, margin_rel: float = 0.02) -> np.ndarray:
    """`region` sin una franja de `margin_rel` × su ancho junto al borde."""
    width = int(region.any(axis=0).sum())
    return ndi.distance_transform_edt(region) > margin_rel * width


def degrade_band(band: np.ndarray, blur_px: float, noise_sigma: float, seed: int) -> np.ndarray:
    """Una banda (0–255) con desenfoque gaussiano de `blur_px` y ruido gaussiano de `noise_sigma`."""
    out = np.asarray(band, dtype=np.float64)
    if blur_px > 0:
        out = ndi.gaussian_filter(out, blur_px, mode="reflect")
    if noise_sigma > 0:
        out = out + np.random.default_rng(seed).normal(0, noise_sigma, out.shape)
    return np.clip(out, 0, 255)


def _otf(kernel: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Transformada de un núcleo centrado, del tamaño `shape` (para rfft2)."""
    padded = np.zeros(shape)
    kh, kw = kernel.shape
    padded[:kh, :kw] = kernel
    padded = np.roll(padded, (-(kh // 2), -(kw // 2)), axis=(0, 1))
    return np.fft.rfft2(padded)


LAPLACIAN = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
CLASSIC_RESTORATIONS = ("filtro inverso", "Wiener", "mínimos cuadrados restringidos")


def restore_band(band: np.ndarray, region: np.ndarray, blur_px: float, method: str,
                 param: float) -> np.ndarray:
    """Restaura una banda desenfocada con un desenfoque gaussiano conocido de `blur_px`.

    En frecuencia, con G la transformada de la imagen y H la del desenfoque:
    - "filtro inverso": F = G / H donde |H| > `param`, y 0 donde no (inverso truncado);
    - "Wiener": F = H* G / (|H|² + K), con K = `param` (cociente ruido / señal constante);
    - "mínimos cuadrados restringidos": F = H* G / (|H|² + γ |P|²), con P el
      laplaciano y γ = `param`.
    Antes se rellena el exterior de `region` y se extiende la imagen por
    reflexión (la transformada supone que la imagen se repite). Devuelve 0–255.
    """
    from .restoration import fill_outside, gaussian_psf

    if method not in CLASSIC_RESTORATIONS:
        raise ValueError(f"Método desconocido: {method!r}")
    psf = gaussian_psf(blur_px)
    pad = 2 * psf.shape[0]
    g = np.pad(fill_outside(np.asarray(band, dtype=np.float64) / 255.0, region).astype(np.float64),
               pad, mode="reflect")
    G = np.fft.rfft2(g)
    H = _otf(psf, g.shape)
    if method == "filtro inverso":
        keep = np.abs(H) > param
        F = np.where(keep, G / np.where(keep, H, 1), 0)
    elif method == "Wiener":
        F = np.conj(H) * G / (np.abs(H) ** 2 + param)
    else:
        P = _otf(LAPLACIAN, g.shape)
        F = np.conj(H) * G / (np.abs(H) ** 2 + param * np.abs(P) ** 2)
    f = np.fft.irfft2(F, s=g.shape)[pad:-pad, pad:-pad]
    return np.clip(255.0 * f, 0, 255)
"""Mejoramiento y restauración de mapas (etapa 3b; los filtros de realce de la etapa 4 están en src/enhance.py).  Esquema v1, etapa 3 (notebooks/03b_restauracion.ipynb).

Todas las funciones reciben un mapa (dos dimensiones) y, si hace falta, la
región del campo de visión detectado. Afuera del campo de visión el mapa se
rellena con los valores del borde de adentro antes de filtrar, para que el
salto contra el negro no parezca un vaso. El resultado conserva el tamaño.
Las escalas se expresan en proporción al diámetro del campo de visión.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from scipy.signal import wiener as _wiener_local
from skimage import exposure, restoration
from skimage.transform import resize


def fill_outside(m: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Copia de `m` donde cada píxel de afuera de `region` toma el valor del píxel de adentro más cercano."""
    _, (rows, cols) = ndi.distance_transform_edt(~region, return_indices=True)
    return m[rows, cols].astype(np.float32)


def _rescale(m: np.ndarray, region: np.ndarray, lo: float = 0.5, hi: float = 99.5) -> np.ndarray:
    """Lleva el mapa a 0–1 con los percentiles de `region`, recortando los extremos."""
    a, b = np.percentile(m[region], [lo, hi])
    return np.clip((m - a) / (b - a), 0, 1).astype(np.float32)


def background_correct(m: np.ndarray, region: np.ndarray, size: int) -> np.ndarray:
    """Resta el fondo: una mediana de `size` píxeles de lado, más grande que los vasos más gruesos.

    Para que sea rápido, la mediana se calcula en una versión reducida unas
    size / 8 veces y se agranda con interpolación lineal (el fondo varía lento).
    """
    f = fill_outside(m, region)
    step = max(1, size // 8)
    small = f[::step, ::step]
    bg = ndi.median_filter(small, size=max(3, (size // step) | 1))
    bg = resize(bg, m.shape, order=1, preserve_range=True, anti_aliasing=False)
    return (f - bg).astype(np.float32)


def clahe(m: np.ndarray, region: np.ndarray, clip: float = 0.01,
          kernel_frac: float = 0.125) -> np.ndarray:
    """Ecualización adaptativa del histograma con límite de contraste, entre 0 y 1.

    La ventana es `kernel_frac` del lado menor de la imagen.
    """
    x = fill_outside(_rescale(m, region), region)
    kernel = max(8, int(kernel_frac * min(m.shape)))
    return exposure.equalize_adapthist(x, kernel_size=kernel, clip_limit=clip).astype(np.float32)


def homomorphic(m: np.ndarray, region: np.ndarray, sigma: float,
                low_gain: float = 0.5, high_gain: float = 1.0) -> np.ndarray:
    """Filtro homomórfico: en el logaritmo, atenúa lo lento (iluminación) y conserva lo rápido.

    La parte lenta es un suavizado gaussiano de desvío `sigma` píxeles.
    """
    x = np.log(fill_outside(_rescale(m, region), region) + 0.01)
    low = ndi.gaussian_filter(x, sigma)
    return np.exp(low_gain * low + high_gain * (x - low)).astype(np.float32)


def wiener_denoise(m: np.ndarray, region: np.ndarray, size: int = 5) -> np.ndarray:
    """Filtro de Wiener adaptativo local: suaviza según la varianza de cada ventana de `size` × `size`.

    Donde la ventana es constante (varianza 0, por ejemplo afuera del campo de
    visión ya rellenado) scipy divide por cero; ahí se deja el valor original.
    """
    f = fill_outside(m, region).astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = _wiener_local(f, mysize=size)
    return np.where(np.isfinite(out), out, f).astype(np.float32)


def gaussian_psf(sigma: float) -> np.ndarray:
    """Desenfoque gaussiano supuesto de la cámara, normalizado a suma 1."""
    r = max(1, int(np.ceil(3 * sigma)))
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    k = np.exp(-(x ** 2 + y ** 2) / (2 * sigma ** 2))
    return k / k.sum()


def wiener_deblur(m: np.ndarray, region: np.ndarray, sigma: float, balance: float) -> np.ndarray:
    """Deconvolución de Wiener con un desenfoque gaussiano de desvío `sigma`.

    `balance` regula cuánto se confía en la imagen frente al ruido: más chico
    devuelve más nitidez y más ruido. Trabaja con el mapa llevado a 0–1.
    """
    x = fill_outside(_rescale(m, region), region).astype(np.float64)
    return restoration.wiener(x, gaussian_psf(sigma), balance, clip=False).astype(np.float32)


def deblock(img: np.ndarray, block: int = 8) -> np.ndarray:
    """Suaviza los bordes de los bloques de compresión .jpg (filas y columnas múltiplos de `block`).

    En las dos filas y columnas a cada lado de cada borde de bloque se aplica
    un promedio [1, 2, 1] / 4 a través del borde. El resto queda igual. Sirve
    para imágenes en escala de grises o a color, en su resolución original.
    """
    out = img.astype(np.float32)
    for axis in (0, 1):
        n = out.shape[axis]
        edges = np.arange(block, n, block)
        idx = np.unique(np.concatenate([edges - 2, edges - 1, edges, edges + 1]))
        idx = idx[(idx > 0) & (idx < n - 1)]
        smooth = ndi.correlate1d(out, np.array([1, 2, 1], np.float32) / 4, axis=axis, mode="nearest")
        take = [slice(None)] * out.ndim
        take[axis] = idx
        out[tuple(take)] = smooth[tuple(take)]
    if np.issubdtype(img.dtype, np.integer):
        return np.clip(np.round(out), 0, np.iinfo(img.dtype).max).astype(img.dtype)
    return out

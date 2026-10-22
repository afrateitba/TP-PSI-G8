"""Campo de visión: tamaño y detección automática.  Esquema v1, etapa 1."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import threshold_otsu


def fov_diameter(fov: np.ndarray) -> int:
    """Ancho horizontal del campo de visión, en píxeles.

    El campo de visión es un círculo que puede estar recortado arriba y abajo
    por el borde de la imagen; por eso se usa el ancho y no el alto.
    """
    cols = np.flatnonzero(fov.any(axis=0))
    if cols.size == 0:
        raise ValueError("El campo de visión está vacío")
    return int(cols[-1] - cols[0] + 1)


def detect_fov(rgb: np.ndarray, margin: float = 0.0, step: int = 4) -> np.ndarray:
    """Campo de visión a partir de la imagen a color.

    1. Umbral de Otsu sobre el canal rojo: la retina es rojiza y afuera la
       foto es casi negra. El umbral se calcula con uno de cada `step`
       píxeles por fila y por columna, para que sea rápido.
    2. Se queda con la región conectada más grande y le rellena los huecos
       (vasos gruesos o mácula que hayan quedado debajo del umbral).
    3. `margin` > 0 achica el borde esos píxeles; < 0 lo agranda.

    Es la candidata original de la etapa 1. Falla con periferias oscuras
    (14_h): usar detect_fov_robust.
    """
    red = rgb[..., 0]
    mask = red > threshold_otsu(red[::step, ::step])
    labels, n = ndi.label(mask)
    if n == 0:
        raise ValueError("No se encontró ninguna región iluminada")
    largest = np.argmax(np.bincount(labels.ravel())[1:]) + 1
    mask = ndi.binary_fill_holes(labels == largest)
    return _apply_margin(mask, margin)


def _apply_margin(mask: np.ndarray, margin: float) -> np.ndarray:
    """Achica (margin > 0) o agranda (margin < 0) el borde de la máscara."""
    if margin > 0:
        return ndi.distance_transform_edt(mask) > margin
    if margin < 0:
        return ndi.distance_transform_edt(~mask) <= -margin
    return mask


def _largest_component(mask: np.ndarray) -> np.ndarray:
    labels, n = ndi.label(mask)
    if n == 0:
        return mask
    return labels == np.argmax(np.bincount(labels.ravel())[1:]) + 1


def brightness(img: np.ndarray) -> np.ndarray:
    """Brillo entre 0 y 1: el máximo de los canales (o la imagen, si es gris).

    Con el máximo, la retina se ve iluminada aunque la foto sea rojiza, verde
    (fotos sin rojo) o en escala de grises.
    """
    a = np.asarray(img)
    scale = float(np.iinfo(a.dtype).max) if np.issubdtype(a.dtype, np.integer) else 1.0
    a = a.astype(np.float32) / scale
    return a.max(axis=2) if a.ndim == 3 else a


def detect_fov_robust(img: np.ndarray, margin: float = 0.0,
                      max_dark_ratio: float = 0.25, min_dark_fraction: float = 0.01,
                      open_frac: float = 0.005) -> np.ndarray:
    """Campo de visión para imágenes de cualquier cámara, tamaño y exposición.

    1. Brillo (`brightness`) suavizado con una mediana de 3 x 3.
    2. Umbral de Otsu sobre el **logaritmo** del brillo, calculado en una
       versión reducida a unos 1.000 píxeles de ancho. El logaritmo achica la
       diferencia entre el centro y una periferia oscura (un factor 2) frente
       a la diferencia con el negro de afuera (un factor de 20 o más), así que
       el umbral cae entre la retina y el fondo, no dentro de la retina.
    3. Si no hay un fondo oscuro de verdad (la parte oscura es menos de
       `min_dark_fraction` de la imagen, o su brillo típico supera
       `max_dark_ratio` del de la parte clara), la retina ocupa toda la
       imagen y se devuelve todo True.
    4. Región conectada más grande (descarta textos o reflejos de afuera),
       relleno de huecos y apertura con un disco de radio `open_frac` x el
       lado menor, para quitar salientes finas del borde.
    5. `margin` achica (> 0) o agranda (< 0) el borde en píxeles.
    """
    b = ndi.median_filter(brightness(img), size=3)
    step = max(1, round(max(b.shape) / 1000))
    logb = np.log1p(255 * b[::step, ::step])
    t = threshold_otsu(logb)
    dark = logb <= t
    dark_level = np.median(b[::step, ::step][dark]) if dark.any() else 0.0
    light_level = np.median(b[::step, ::step][~dark])
    if dark.mean() < min_dark_fraction or dark_level > max_dark_ratio * light_level:
        return np.ones(b.shape, bool)

    mask = b > np.expm1(t) / 255
    mask = ndi.binary_fill_holes(_largest_component(mask))
    r = open_frac * min(b.shape)
    if r >= 1:   # apertura: erosión y dilatación con un disco de radio r
        eroded = ndi.distance_transform_edt(mask) > r
        mask = _largest_component((ndi.distance_transform_edt(~eroded) <= r) & mask)
    return _apply_margin(mask, margin)

"""Grosor de los vasos en una máscara.  Esquema v1, etapa 1; plan, sección 5."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

THIN, MEDIUM, THICK = 1, 2, 3   # clases de width_classes; 0 es fondo


def skeleton_widths(vessels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Línea central de los vasos y su ancho en cada punto.

    El ancho es 2·d − 1, con d la distancia del punto al fondo más cercano:
    un vaso de 1 píxel da 1 y uno de 5 píxeles da 5. Con anchos pares da uno
    menos (la línea central cae sobre una de las dos filas del medio); como
    todas las imágenes se miden igual, el sesgo no cambia el orden.
    Devuelve (esqueleto booleano, anchos con 0 fuera del esqueleto).
    """
    vessels = vessels.astype(bool)
    skel = skeletonize(vessels)
    dist = ndi.distance_transform_edt(vessels)
    widths = np.zeros(vessels.shape)
    widths[skel] = 2 * dist[skel] - 1
    return skel, widths


def width_map(vessels: np.ndarray, skel: np.ndarray | None = None,
              widths: np.ndarray | None = None) -> np.ndarray:
    """Ancho de cada píxel de vaso: el del punto de la línea central más cercano.

    Fuera de los vasos vale 0. Si ya se calcularon `skel` y `widths` con
    skeleton_widths, se pueden pasar para no repetir la cuenta.
    """
    vessels = vessels.astype(bool)
    if skel is None or widths is None:
        skel, widths = skeleton_widths(vessels)
    if not skel.any():
        return np.zeros(vessels.shape)
    _, (rows, cols) = ndi.distance_transform_edt(~skel, return_indices=True)
    out = widths[rows, cols]
    out[~vessels] = 0
    return out


def width_classes(wmap: np.ndarray, limits: tuple[float, float]) -> np.ndarray:
    """Clase de cada píxel de vaso según su ancho.

    THIN si ancho ≤ limits[0], THICK si ancho > limits[1], MEDIUM en el medio.
    El fondo (ancho 0) queda en 0.
    """
    lo, hi = limits
    out = np.where(wmap <= lo, THIN, np.where(wmap > hi, THICK, MEDIUM)).astype(np.uint8)
    out[wmap <= 0] = 0
    return out

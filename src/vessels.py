"""Grosor de los vasos: en la máscara (etapa 1; plan, sección 5) y visible en la foto (etapa 1c)."""
from __future__ import annotations

import numpy as np
import pandas as pd
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


# --- Ancho visible en la foto (etapa 1c) ----------------------------------

def profile_width(channel: np.ndarray, point: tuple[float, float],
                  direction: tuple[float, float], half_length: float,
                  step: float = 0.25, n_parallel: int = 5,
                  min_snr: float = 3.0) -> float:
    """Ancho visible de un vaso oscuro a mitad de su profundidad, en píxeles.

    Se lee el brillo de `channel` sobre la perpendicular al vaso que pasa por
    `point` (fila, columna), de −half_length a +half_length, cada `step`
    píxeles; se promedian `n_parallel` perfiles paralelos separados 1 píxel a
    lo largo del vaso. `direction` es la dirección del vaso (fila, columna).

    - Fondo de cada lado: mediana del 20 % exterior del perfil de ese lado.
    - Mínimo: buscado a no más de half_length / 4 del punto (el vaso tiene
      que estar donde dice la línea central).
    - Ancho: distancia entre los puntos donde el perfil cruza, a cada lado del
      mínimo, la mitad entre el fondo de ese lado y el mínimo.

    Devuelve NaN ("no medible") si:
    - la profundidad de algún lado es menor que `min_snr` veces el ruido de
      los extremos, o menor que la mitad de la del otro lado (un lado no
      vuelve al fondo: borde oscuro, mancha o vaso pegado);
    - algún extremo todavía sube hacia afuera (el vaso es más ancho que la
      ventana y el "fondo" está sobre su ladera);
    - algún lado no cruza la mitad antes del extremo, o el mínimo queda
      corrido del centro del ancho medido.
    """
    ty, tx = np.asarray(direction, float) / np.hypot(*direction)
    ny, nx = -tx, ty
    s = np.arange(-half_length, half_length + step / 2, step)
    o = np.arange(n_parallel) - (n_parallel - 1) / 2
    yy = point[0] + s[None, :] * ny + o[:, None] * ty
    xx = point[1] + s[None, :] * nx + o[:, None] * tx
    prof = ndi.map_coordinates(channel.astype(float), [yy, xx], order=1, mode="nearest").mean(axis=0)

    k = max(4, int(0.2 * len(s)))
    left, right = prof[:k], prof[-k:]
    bg_l, bg_r = np.median(left), np.median(right)
    noise = max(np.std(np.diff(np.r_[left[::4], right[::4]])) / np.sqrt(2), 1e-6)
    center = np.abs(s) <= half_length / 4
    i_min = np.flatnonzero(center)[np.argmin(prof[center])]
    d_l, d_r = bg_l - prof[i_min], bg_r - prof[i_min]
    if min(d_l, d_r) < min_snr * noise or min(d_l, d_r) < 0.5 * max(d_l, d_r):
        return float("nan")
    h = k // 2   # extremos: la mitad exterior no puede estar bastante más clara que la interior
    rise_tol = max(2 * noise, 0.15 * (d_l + d_r) / 2)
    if (np.median(left[:h]) - np.median(left[h:]) > rise_tol
            or np.median(right[-h:]) - np.median(right[:-h]) > rise_tol):
        return float("nan")

    def crossing(level: float, idx: range) -> float | None:
        prev = i_min
        for i in idx:
            if prof[i] >= level:
                f = (level - prof[prev]) / (prof[i] - prof[prev])
                return s[prev] + f * (s[i] - s[prev])
            prev = i
        return None

    s_l = crossing((bg_l + prof[i_min]) / 2, range(i_min - 1, k - 1, -1))
    s_r = crossing((bg_r + prof[i_min]) / 2, range(i_min + 1, len(s) - k + 1))
    if s_l is None or s_r is None:
        return float("nan")
    width = s_r - s_l
    if abs(s[i_min] - (s_l + s_r) / 2) > 0.25 * width:
        return float("nan")
    return float(width)


def _local_direction(skel: np.ndarray, y: int, x: int, radius: int = 5) -> tuple[float, float]:
    """Dirección de la línea central alrededor de (y, x): eje principal de sus puntos vecinos."""
    win = skel[max(0, y - radius): y + radius + 1, max(0, x - radius): x + radius + 1]
    ys, xs = np.nonzero(win)
    pts = np.c_[ys, xs].astype(float)
    pts -= pts.mean(axis=0)
    _, vecs = np.linalg.eigh(pts.T @ pts)
    return float(vecs[0, 1]), float(vecs[1, 1])


def visible_widths(channel: np.ndarray, vessels: np.ndarray, fov: np.ndarray,
                   n_points: int, rng: np.random.Generator,
                   border: int = 50, junction_gap: int = 15) -> pd.DataFrame:
    """Ancho marcado y ancho visible en puntos al azar de la línea central.

    Se eligen `n_points` puntos de la línea central de `vessels` (dentro de
    `fov`) que estén a más de `border` píxeles del borde del campo de visión
    y a más de `junction_gap` píxeles de bifurcaciones, cruces y puntas.
    En cada uno se mide el ancho visible con profile_width, con una
    perpendicular de largo max(12, 3 × ancho marcado) a cada lado: así se
    puede medir un vaso visible hasta unas 2,4 veces más ancho que lo marcado
    antes de que el extremo caiga sobre su ladera.
    Devuelve una fila por punto: y, x, marked_width, visible_width (NaN si no
    se pudo medir).
    """
    skel, widths = skeleton_widths(vessels & fov)
    neighbors = ndi.convolve(skel.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - 1
    irregular = skel & (neighbors != 2)
    far_from_irregular = ndi.distance_transform_edt(~irregular) > junction_gap
    inside = ndi.distance_transform_edt(fov) > border
    ys, xs = np.nonzero(skel & (neighbors == 2) & far_from_irregular & inside)
    pick = rng.choice(len(ys), size=min(n_points, len(ys)), replace=False)
    rows = []
    for y, x in zip(ys[pick], xs[pick]):
        w = widths[y, x]
        rows.append({"y": int(y), "x": int(x), "marked_width": float(w),
                     "visible_width": profile_width(channel, (y, x), _local_direction(skel, y, x),
                                                    max(12.0, 3.0 * w))})
    return pd.DataFrame(rows)

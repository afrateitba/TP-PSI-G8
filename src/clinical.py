"""Medidas clínicas sobre una máscara de vasos (etapa 7; esquema, etapa 7; plan, desvío 14.7).

Las tres se calculan igual sobre la máscara de los expertos y sobre la del
algoritmo, dentro del mismo campo de visión (el de la base):
- proporción de vasos en el campo;
- longitud del esqueleto dividida por el diámetro del campo;
- tortuosidad: en cada tramo del esqueleto entre bifurcaciones, la longitud
  del camino dividida por la distancia en línea recta entre sus extremos; el
  resumen por imagen es la mediana de los tramos que no son cortos.

Antes del esqueleto se rellenan los agujeros chicos de la máscara (por
ejemplo, el reflejo del centro de los vasos gruesos), y después se podan las
ramitas cortas que salen de una bifurcación. Todos los largos están en
proporción al diámetro del campo (config.CLINICAL_*), así que sirven a
cualquier resolución.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import remove_small_holes, skeletonize

from .config import (CLINICAL_HOLE_REL, CLINICAL_MIN_SEGMENT_REL, CLINICAL_SPUR_REL,
                     CLINICAL_STEP_REL)

EIGHT = np.ones((3, 3), bool)
OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """a desplazado: el valor en (y, x) es el de a en (y + dy, x + dx); afuera, 0."""
    out = np.zeros_like(a)
    h, w = a.shape
    out[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)] = \
        a[max(0, dy):h - max(0, -dy), max(0, dx):w - max(0, -dx)]
    return out


def neighbor_count(skel: np.ndarray) -> np.ndarray:
    """Cantidad de vecinos (de los 8) que están en el esqueleto, para cada píxel del esqueleto."""
    skel = skel.astype(bool)
    n = ndi.convolve(skel.astype(np.int16), EIGHT.astype(np.int16), mode="constant") - 1
    return np.where(skel, n, 0)


def skeleton_length(skel: np.ndarray) -> float:
    """Largo total del esqueleto en píxeles: pasos rectos 1 y diagonales √2.

    Una diagonal no se cuenta cuando el camino ya pasa por el píxel recto de
    la esquina (si no, ese escalón se contaría dos veces).
    """
    s = skel.astype(bool)
    straight = (s[:, :-1] & s[:, 1:]).sum() + (s[:-1, :] & s[1:, :]).sum()
    down_right = s[:-1, :-1] & s[1:, 1:] & ~s[:-1, 1:] & ~s[1:, :-1]
    down_left = s[:-1, 1:] & s[1:, :-1] & ~s[:-1, :-1] & ~s[1:, 1:]
    return float(straight + np.sqrt(2) * (down_right.sum() + down_left.sum()))


def segments(skel: np.ndarray) -> tuple[np.ndarray, int]:
    """Tramos del esqueleto entre bifurcaciones: se sacan los píxeles con 3 vecinos o más.

    Devuelve (etiquetas con 0 afuera, cantidad de tramos).
    """
    skel = skel.astype(bool)
    return ndi.label(skel & ~(neighbor_count(skel) >= 3), structure=EIGHT)


def ordered_paths(labels: np.ndarray, n: int) -> dict[int, np.ndarray]:
    """Píxeles de cada tramo en orden, de una punta a la otra.

    Solo los tramos con exactamente dos puntas (los cerrados se dejan afuera).
    Las puntas son los píxeles con un solo vecino del mismo tramo.
    """
    same = np.zeros(labels.shape, np.uint8)
    for dy, dx in OFFSETS:
        same += (_shift(labels, dy, dx) == labels) & (labels > 0)
    ys, xs = np.nonzero(labels)
    lab = labels[ys, xs]
    order = np.argsort(lab, kind="stable")
    ys, xs, lab = ys[order], xs[order], lab[order]
    bounds = np.searchsorted(lab, np.arange(1, n + 2))
    paths = {}
    for k in range(1, n + 1):
        py, px = ys[bounds[k - 1]:bounds[k]], xs[bounds[k - 1]:bounds[k]]
        if len(py) == 1:
            paths[k] = np.array([[py[0], px[0]]])
            continue
        ends = np.flatnonzero(same[py, px] == 1)
        if len(ends) != 2:
            continue
        left = set(zip(py.tolist(), px.tolist()))
        cur = (int(py[ends[0]]), int(px[ends[0]]))
        goal = (int(py[ends[1]]), int(px[ends[1]]))
        path = [cur]
        left.discard(cur)
        while cur != goal:
            nxt = [(cur[0] + dy, cur[1] + dx) for dy, dx in OFFSETS if (cur[0] + dy, cur[1] + dx) in left]
            if not nxt:
                break
            # primero los vecinos rectos: así una esquina no se saltea con la diagonal
            cur = min(nxt, key=lambda p: abs(p[0] - cur[0]) + abs(p[1] - cur[1]))
            path.append(cur)
            left.discard(cur)
        if cur == goal:
            paths[k] = np.array(path)
    return paths


def path_length(path: np.ndarray, step: int) -> float:
    """Largo de un camino ordenado, como poligonal que toma un punto cada `step` píxeles.

    Con los pasos de píxel (1 y √2) un vaso recto en diagonal mediría hasta un
    8 % más que la distancia en línea recta; tomar puntos espaciados lo evita.
    """
    if len(path) < 2:
        return 0.0
    idx = np.unique(np.r_[np.arange(0, len(path), max(int(step), 1)), len(path) - 1])
    return float(np.sqrt((np.diff(path[idx], axis=0) ** 2).sum(axis=1)).sum())


def prune_spurs(skel: np.ndarray, max_len: float, rounds: int = 2) -> np.ndarray:
    """Saca las ramitas: tramos con una punta libre, pegados a una bifurcación y más cortos que `max_len`.

    Son las que deja el esqueleto en el borde de los vasos gruesos. Se hace
    `rounds` veces, porque al sacar una ramita puede aparecer otra. Los tramos
    sueltos (sin bifurcación) se dejan.
    """
    skel = skel.astype(bool)
    for _ in range(rounds):
        nb = neighbor_count(skel)
        junction = skel & (nb >= 3)
        labels, n = ndi.label(skel & ~junction, structure=EIGHT)
        if n == 0:
            break
        length = np.full(n + 1, np.inf)      # los tramos cerrados no se podan
        for k, path in ordered_paths(labels, n).items():
            length[k] = path_length(path, 1)
        touches = np.zeros(n + 1, bool)
        touches[np.unique(labels[ndi.binary_dilation(junction, EIGHT)])] = True
        free = np.zeros(n + 1, bool)
        free[np.unique(labels[skel & (nb == 1)])] = True
        spur = touches & free & (length < max_len)
        spur[0] = False
        if not spur.any():
            break
        skel = skeletonize(skel & ~spur[labels])
    return skel


def clean_skeleton(mask: np.ndarray, fov: np.ndarray, diameter: float,
                   spur_rel: float = CLINICAL_SPUR_REL) -> np.ndarray:
    """Esqueleto de la máscara dentro del campo: rellena los agujeros chicos, esqueletiza y poda las ramitas."""
    hole = (CLINICAL_HOLE_REL * diameter) ** 2
    filled = remove_small_holes(mask.astype(bool) & fov, max_size=max(int(hole) - 1, 0)) & fov
    return prune_spurs(skeletonize(filled), spur_rel * diameter)


def segment_lengths(skel: np.ndarray, diameter: float) -> tuple[np.ndarray, np.ndarray]:
    """Largo del camino y distancia en línea recta (en píxeles) de cada tramo con dos puntas."""
    labels, n = segments(skel)
    step = CLINICAL_STEP_REL * diameter
    paths = list(ordered_paths(labels, n).values())
    arc = np.array([path_length(p, step) for p in paths])
    chord = np.array([float(np.hypot(*(p[-1] - p[0]))) for p in paths])
    return arc, chord


def segment_tortuosity(skel: np.ndarray, diameter: float,
                       min_rel: float = CLINICAL_MIN_SEGMENT_REL) -> np.ndarray:
    """Tortuosidad (largo del camino / distancia en línea recta) de cada tramo no corto.

    Los tramos más cortos que `min_rel` × diámetro se descartan, y también los
    cerrados (sin dos puntas).
    """
    arc, chord = segment_lengths(skel, diameter)
    keep = (arc >= min_rel * diameter) & (chord > 0)
    return arc[keep] / chord[keep]


def clinical_measures(mask: np.ndarray, fov: np.ndarray, spur_rel: float = CLINICAL_SPUR_REL,
                      min_rel: float = CLINICAL_MIN_SEGMENT_REL) -> dict[str, float]:
    """Las tres medidas de una imagen, dentro del campo de visión `fov`."""
    from .fov import fov_diameter

    fov = fov.astype(bool)
    d = fov_diameter(fov)
    skel = clean_skeleton(mask, fov, d, spur_rel)
    tort = segment_tortuosity(skel, d, min_rel)
    return {"proporción": float((mask.astype(bool) & fov).sum() / fov.sum()),
            "longitud": skeleton_length(skel) / d,
            "tortuosidad": float(np.median(tort)) if len(tort) else float("nan"),
            "tramos": len(tort)}

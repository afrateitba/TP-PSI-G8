"""Evaluación rápida de mapas en desarrollo: muestra fija de píxeles y trabajo en paralelo.

Para elegir entre candidatas (etapas 4 y siguientes) no hace falta ordenar
los 7 millones de píxeles de cada imagen: se usan **todos** los píxeles de
vaso del campo de visión de la base y una muestra al azar fija de una
fracción del fondo (`EVAL_BG_FRACTION`), siempre la misma para cada imagen.
La evaluación sigue siendo a resolución original: el mapa calculado a menor
resolución se interpola en esos píxeles, igual que si se lo agrandara.
La evaluación final en prueba usa todos los píxeles (plan, sección 3).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

from .config import EVAL_BG_FRACTION, RESULTS_DIR, SEED, WIDTH_LIMITS_PX
from .metrics import auc_by_subset

CACHE_DIR = RESULTS_DIR / "cache"
CLASS_NAMES = {1: "finos", 2: "medianos", 3: "gruesos"}


@dataclass
class EvalSample:
    """Píxeles de evaluación de una imagen (coordenadas a resolución original)."""
    rows: np.ndarray       # int32
    cols: np.ndarray       # int32
    truth: np.ndarray      # bool: vaso según los expertos
    cls: np.ndarray        # uint8: 0 fondo, 1 fino, 2 mediano, 3 grueso (ancho marcado)
    shape: tuple

    def subsets(self) -> dict[str, np.ndarray]:
        return {name: self.cls == c for c, name in CLASS_NAMES.items()}


def build_sample(vessels: np.ndarray, fov: np.ndarray, rng: np.random.Generator,
                 bg_fraction: float = EVAL_BG_FRACTION,
                 limits: tuple[float, float] = WIDTH_LIMITS_PX) -> EvalSample:
    """Todos los vasos dentro de `fov` y una fracción al azar del fondo, con la clase de grosor."""
    from .vessels import width_classes, width_map

    v = vessels.astype(bool) & fov
    classes = width_classes(width_map(v), limits)
    ves_idx = np.flatnonzero(v)
    bg_idx = np.flatnonzero(fov & ~v)
    keep = rng.choice(bg_idx, size=int(round(bg_fraction * bg_idx.size)), replace=False)
    idx = np.sort(np.concatenate([ves_idx, keep]))
    rows, cols = np.unravel_index(idx, v.shape)
    return EvalSample(rows.astype(np.int32), cols.astype(np.int32), v.ravel()[idx],
                      classes.ravel()[idx].astype(np.uint8), v.shape)


def load_sample(image_id: str, cache_dir: Path = CACHE_DIR) -> EvalSample:
    """Muestra de evaluación de una imagen de desarrollo, guardada en `cache_dir` la primera vez.

    La semilla depende de SEED y del nombre de la imagen, así que la muestra
    es siempre la misma. Usa load_vessels y load_fov: con una imagen de prueba
    da LockedImageError.
    """
    from .data import load_fov, load_vessels

    path = cache_dir / f"muestra_{image_id}.npz"
    if path.exists():
        z = np.load(path)
        return EvalSample(z["rows"], z["cols"], z["truth"], z["cls"], tuple(z["shape"]))
    seed = SEED + sum(ord(ch) for ch in image_id)
    s = build_sample(load_vessels(image_id), load_fov(image_id), np.random.default_rng(seed))
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, rows=s.rows, cols=s.cols, truth=s.truth, cls=s.cls, shape=np.array(s.shape))
    return s


def sample_values(m: np.ndarray, sample: EvalSample) -> np.ndarray:
    """Valores de un mapa en los píxeles de la muestra.

    Si el mapa está a menor resolución que la imagen original, se interpola
    linealmente en la posición de cada píxel original (los centros de píxel se
    alinean igual que al agrandar con skimage.transform.resize).
    """
    if m.shape == tuple(sample.shape):
        return m[sample.rows, sample.cols].astype(np.float64)
    fy, fx = m.shape[0] / sample.shape[0], m.shape[1] / sample.shape[1]
    y = (sample.rows + 0.5) * fy - 0.5
    x = (sample.cols + 0.5) * fx - 0.5
    return ndi.map_coordinates(m.astype(np.float64), [y, x], order=1, mode="nearest")


def sample_auc(m: np.ndarray, sample: EvalSample) -> dict[str, float]:
    """Área bajo la curva (vasos como valores altos) de todos los vasos y por grosor, en la muestra."""
    return auc_by_subset(sample_values(m, sample), sample.truth, sample.subsets())


def map_images(func, image_ids, workers: int = 4) -> list:
    """Aplica `func(image_id)` a cada imagen en paralelo, en procesos separados.

    Devuelve los resultados en el orden de `image_ids`. Funciona desde un
    cuaderno (joblib serializa funciones definidas en el cuaderno). Con
    `workers=1` corre en el proceso actual, útil para depurar.
    """
    if workers == 1:
        return [func(i) for i in image_ids]
    from joblib import Parallel, delayed

    return Parallel(n_jobs=workers)(delayed(func)(i) for i in image_ids)


def weighted_matthews(pred: np.ndarray, truth: np.ndarray, weights: np.ndarray) -> float:
    """Matthews con pesos por píxel: para estimarlo en una muestra que no tiene las proporciones reales.

    En la muestra de evaluación el fondo está submuestreado; con peso
    1 / EVAL_BG_FRACTION en el fondo y 1 en los vasos se recuperan las
    cantidades reales.
    """
    pred, truth = np.asarray(pred, bool), np.asarray(truth, bool)
    tp = weights[pred & truth].sum()
    fp = weights[pred & ~truth].sum()
    fn = weights[~pred & truth].sum()
    tn = weights[~pred & ~truth].sum()
    den = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return float((tp * tn - fp * fn) / den) if den else float("nan")

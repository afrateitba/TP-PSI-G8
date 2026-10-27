"""Remuestreo por persona y combinación lineal de mapas.  Esquema v1, sección 5.2."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SEED


def person_bootstrap_means(values: pd.DataFrame | pd.Series, persons: pd.Series,
                           reps: int = 2000, seed: int = SEED) -> np.ndarray:
    """Medias remuestreando personas enteras con reposición.

    `values` tiene una fila por imagen (una o varias columnas) y `persons` la
    persona de cada imagen, con el mismo índice. En cada remuestreo se sortean
    tantas personas como hay, con reposición, y se promedian todas las
    imágenes de las elegidas (cada imagen pesa lo mismo). Devuelve un arreglo
    (reps, columnas). Con la misma `seed`, los sorteos son los mismos para
    todas las columnas: las diferencias entre columnas quedan apareadas.
    """
    frame = values.to_frame() if isinstance(values, pd.Series) else values
    codes, uniq = pd.factorize(persons.loc[frame.index])
    sums = np.zeros((len(uniq), frame.shape[1]))
    np.add.at(sums, codes, frame.to_numpy(dtype=float))
    counts = np.bincount(codes, minlength=len(uniq)).astype(float)
    draws = np.random.default_rng(seed).integers(0, len(uniq), size=(reps, len(uniq)))
    return sums[draws].sum(axis=1) / counts[draws].sum(axis=1)[:, None]


def percentile_interval(samples: np.ndarray, level: float = 0.95) -> tuple:
    """Intervalo por percentiles de los remuestreos (por columna)."""
    tail = 100 * (1 - level) / 2
    lo, hi = np.percentile(samples, [tail, 100 - tail], axis=0)
    return lo, hi


def fisher_direction(x: np.ndarray, y: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    """Dirección del discriminante lineal de Fisher: Σ⁻¹ (μ₁ − μ₀).

    `x` tiene una fila por píxel y una columna por mapa; `y` es True en los
    vasos. Σ es la covarianza promedio de las dos clases. El puntaje x @ w es
    más alto en los vasos. Se normaliza a largo 1.
    """
    y = np.asarray(y, bool)
    a, b = x[y], x[~y]
    cov = (np.cov(a, rowvar=False) + np.cov(b, rowvar=False)) / 2
    cov = np.atleast_2d(cov) + ridge * np.eye(x.shape[1])
    w = np.linalg.solve(cov, a.mean(axis=0) - b.mean(axis=0))
    return w / np.linalg.norm(w)

"""Medidas de una máscara contra la referencia.  Plan de evaluación, sección 4.

Todas reciben máscaras booleanas del mismo tamaño y, opcionalmente, una
región (el campo de visión de la base): lo que queda afuera no cuenta.
"""
from __future__ import annotations

import numpy as np


def confusion(pred: np.ndarray, truth: np.ndarray,
              region: np.ndarray | None = None) -> dict[str, int]:
    """Cuenta de píxeles: tp (vaso marcado), fp (fondo marcado),
    fn (vaso no marcado) y tn (fondo no marcado)."""
    if pred.shape != truth.shape:
        raise ValueError(f"Tamaños distintos: {pred.shape} y {truth.shape}")
    if region is not None:
        pred, truth = pred[region], truth[region]
    pred, truth = pred.astype(bool), truth.astype(bool)
    tp = int(np.count_nonzero(pred & truth))
    fp = int(np.count_nonzero(pred & ~truth))
    fn = int(np.count_nonzero(~pred & truth))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": int(pred.size) - tp - fp - fn}


def _ratio(num: float, den: float) -> float:
    return num / den if den else float("nan")


def dice(pred, truth, region=None) -> float:
    """Superposición: 2·tp / (2·tp + fp + fn)."""
    c = confusion(pred, truth, region)
    return _ratio(2 * c["tp"], 2 * c["tp"] + c["fp"] + c["fn"])


def matthews(pred, truth, region=None) -> float:
    """Coeficiente de correlación de Matthews, de −1 a 1."""
    c = confusion(pred, truth, region)
    tp, fp, fn, tn = (float(c[k]) for k in ("tp", "fp", "fn", "tn"))
    den = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return _ratio(tp * tn - fp * fn, den)


def sensitivity(pred, truth, region=None) -> float:
    """Fracción de los vasos que se marcan: tp / (tp + fn)."""
    c = confusion(pred, truth, region)
    return _ratio(c["tp"], c["tp"] + c["fn"])


def specificity(pred, truth, region=None) -> float:
    """Fracción del fondo que no se marca: tn / (tn + fp)."""
    c = confusion(pred, truth, region)
    return _ratio(c["tn"], c["tn"] + c["fp"])


def accuracy(pred, truth, region=None) -> float:
    """Fracción de píxeles bien clasificados. Solo para comparar con la literatura."""
    c = confusion(pred, truth, region)
    return _ratio(c["tp"] + c["tn"], sum(c.values()))


def auc(score: np.ndarray, truth: np.ndarray, region: np.ndarray | None = None) -> float:
    """Área bajo la curva de sensibilidad contra falsos positivos de un mapa continuo.

    Es la probabilidad de que un píxel de vaso al azar tenga un `score` más
    alto que un píxel de fondo al azar; los empates cuentan la mitad. Más alto
    tiene que querer decir "más vaso": para un mapa donde los vasos son
    oscuros, pasar -mapa. Se calcula con rangos (prueba de Mann–Whitney).
    """
    from scipy.stats import rankdata

    if score.shape != truth.shape:
        raise ValueError(f"Tamaños distintos: {score.shape} y {truth.shape}")
    if region is not None:
        score, truth = score[region], truth[region]
    s = np.asarray(score, dtype=np.float64).ravel()
    t = np.asarray(truth, dtype=bool).ravel()
    n_pos = int(t.sum())
    n_neg = t.size - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("La región tiene que tener vasos y fondo")
    ranks = rankdata(s, method="average")
    return float((ranks[t].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))

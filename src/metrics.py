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


# --- Línea central (desvío 14.3 del plan) ----------------------------------
# Comparan los esqueletos y no los píxeles: no dependen de cuán ancho se
# dibujó cada vaso (etapa 1c: las máscaras de sanos están marcadas más anchas).

def _skeleton(mask: np.ndarray, region: np.ndarray | None) -> np.ndarray:
    from skimage.morphology import skeletonize

    m = mask.astype(bool)
    if region is not None:
        m = m & region
    return skeletonize(m)


def centerline_sensitivity(pred, truth, region=None) -> float:
    """¿Encontró los vasos? Fracción de la línea central de `truth` que cae dentro de `pred`."""
    skel = _skeleton(truth, region)
    return _ratio(np.count_nonzero(skel & pred.astype(bool)), np.count_nonzero(skel))


def centerline_precision(pred, truth, region=None) -> float:
    """¿Lo marcado son vasos? Fracción de la línea central de `pred` que cae dentro de `truth`."""
    skel = _skeleton(pred, region)
    return _ratio(np.count_nonzero(skel & truth.astype(bool)), np.count_nonzero(skel))


def centerline_dice(pred, truth, region=None) -> float:
    """Combinación de las dos anteriores: 2·P·S / (P + S) (Shit et al., 2021)."""
    s = centerline_sensitivity(pred, truth, region)
    p = centerline_precision(pred, truth, region)
    return _ratio(2 * p * s, p + s)


def centerline_sensitivity_by_class(pred, truth, limits, region=None) -> dict[str, float]:
    """Sensibilidad de línea central de los vasos finos, medianos y gruesos.

    La clase de cada punto de la línea central de `truth` sale de su ancho
    marcado (vessels.skeleton_widths) y de `limits` (config.WIDTH_LIMITS_PX).
    """
    from .vessels import skeleton_widths

    t = truth.astype(bool) if region is None else truth.astype(bool) & region
    skel, widths = skeleton_widths(t)
    w = widths[skel]
    hit = pred.astype(bool)[skel]
    lo, hi = limits
    classes = {"fino": w <= lo, "mediano": (w > lo) & (w <= hi), "grueso": w > hi}
    return {k: _ratio(np.count_nonzero(hit & c), np.count_nonzero(c)) for k, c in classes.items()}


# --- Área bajo la curva por grosor (plan, secciones 4 y 5) ---------------------
# La misma área de `auc`, pero solo con los vasos finos: los medianos y gruesos
# no cuentan ni como vaso ni como fondo (etapas 3 y 4).

def auc_thin(score: np.ndarray, truth: np.ndarray, region: np.ndarray | None = None,
             limits: tuple[float, float] | None = None) -> float:
    """Área bajo la curva solo con los vasos finos (plan, sección 4).

    Los vasos son los píxeles de `truth` con ancho <= limits[0] (cada píxel
    toma el ancho del punto más cercano de la línea central,
    vessels.width_map). Los vasos medianos y gruesos se sacan de la región:
    no cuentan ni como vaso ni como fondo. Así se comparan los finos contra
    todo el fondo. `limits` por defecto: config.WIDTH_LIMITS_PX.
    """
    from .vessels import width_map

    if limits is None:
        from .config import WIDTH_LIMITS_PX as limits
    t = truth.astype(bool)
    if region is not None:
        t = t & region
    thin = t & (width_map(t) <= limits[0])
    zone = ~(t & ~thin)                       # todo menos los vasos no finos
    if region is not None:
        zone &= region
    return auc(score, thin, zone)
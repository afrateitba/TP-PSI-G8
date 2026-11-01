"""Algoritmo final de segmentación, en una sola función (etapas 5b y 5e; plan, desvíos 14.5 y 14.6).

Recibe solo la foto a color, como lo hará con las imágenes de la cátedra:
1. reduce la foto a 1/SEGMENT_FACTOR y detecta el campo de visión;
2. toma el verde, con los vasos como valores altos, y le corrige el fondo
   (gaussiana de σ = SEGMENT_BACKGROUND_SIGMA_REL × diámetro);
3. calcula los filtros de la etapa 4 sobre ese verde, con la mayor respuesta
   entre escalas y además en cada escala por separado, y estandariza los
   mapas (SEGMENT_FEATURES) dentro del campo detectado;
4. los combina con una regresión logística (pesos ajustados con desarrollo);
5. agranda la probabilidad al tamaño original y marca como vaso la fracción
   SEGMENT_FRACTION más alta del campo de visión detectado a resolución original.

La referencia clásica (plan, sección 10) es el mismo camino con un solo mapa,
el detector de líneas, y la misma regla de umbral.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import (EVAL_BG_FRACTION, ROOT, SEGMENT_BACKGROUND_SIGMA_REL, SEGMENT_BASE_FEATURES,
                     SEGMENT_FACTOR, SEGMENT_FEATURES, SEGMENT_FRACTION, SEGMENT_REFERENCE_FILTER,
                     SEED)

WEIGHTS_PATH = ROOT / "models" / "pesos_combinacion.json"
N_TRAIN = 20_000    # píxeles de vaso y de fondo por imagen para ajustar los pesos
N_THR = 30_000      # píxeles de la muestra fija por imagen para elegir la fracción
FRACTIONS = np.round(np.arange(0.05, 0.20, 0.01), 2)   # fracciones candidatas


def _maps(rgb: np.ndarray, factor: int, texture: bool) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Todos los mapas sin estandarizar, a 1/`factor`: (nombre → mapa, campo detectado).

    Los de SEGMENT_BASE_FEATURES (los orientados como la mayor respuesta entre
    escalas, igual que apply_filter, sin volver a calcularlos); cada filtro
    orientado y Frangi en cada escala de la etapa 4 por separado; y, si
    `texture`, la textura de la matriz de coocurrencia del verde corregido.
    """
    from . import config as c
    from .enhance import (apply_filter, frangi_filter, gabor_filter, glcm_texture, line_detector,
                          matched_filter, prepare_maps, quantize, scale_px, sigma_for_width)
    from .preprocess import corregir_fondo

    maps, region, d = prepare_maps(rgb, ["Verde"], factor)
    green = corregir_fondo(maps["Verde"], region, SEGMENT_BACKGROUND_SIGMA_REL * d)
    widths = [scale_px(r, d) for r in c.ENHANCE_WIDTHS_REL]
    scales = {}
    for w, px in zip(c.ENHANCE_WIDTHS_PX, widths):
        s = max(sigma_for_width(px), c.ENHANCE_SIGMA_MIN_PX)
        scales[f"detector de líneas {w}"] = line_detector(green, max(c.ENHANCE_LINE_LENGTH * px, 3))
        scales[f"filtro adaptado {w}"] = matched_filter(green, s, c.ENHANCE_MATCHED_LENGTH * s)
        scales[f"Gabor {w}"] = gabor_filter(green, s, c.ENHANCE_GABOR_ELONGATION)
        scales[f"Frangi {w}"] = frangi_filter(green, [s])
    out = {}
    for name in SEGMENT_BASE_FEATURES:
        if name == "verde corregido":
            out[name] = green
        elif name in ("detector de líneas", "filtro adaptado", "Gabor"):
            out[name] = np.max([scales[f"{name} {w}"] for w in c.ENHANCE_WIDTHS_PX], axis=0)
        else:
            out[name] = apply_filter(name, green, d)
    out.update(scales)
    if texture:
        window = max(3, int(round(scale_px(c.GLCM_WINDOW_REL, d))) | 1)
        for name, m in glcm_texture(quantize(green, c.GLCM_LEVELS, region), c.GLCM_LEVELS, window).items():
            out[f"textura {name}"] = m
    return out, region


def _stack(maps: dict[str, np.ndarray], names: list[str], region: np.ndarray) -> np.ndarray:
    from .color import standardize

    return np.stack([standardize(np.asarray(maps[n], dtype=np.float32), region) for n in names])


def compute_features(rgb: np.ndarray, factor: int = SEGMENT_FACTOR) -> tuple[np.ndarray, np.ndarray]:
    """Los mapas de SEGMENT_FEATURES estandarizados, a 1/`factor` de la resolución.

    Devuelve (mapas con forma (n_mapas, alto, ancho), campo detectado a esa
    resolución). Usa solo la foto.
    """
    maps, region = _maps(rgb, factor, texture=any(n.startswith("textura") for n in SEGMENT_FEATURES))
    return _stack(maps, SEGMENT_FEATURES, region), region


def compute_feature_bank(rgb: np.ndarray, factor: int = SEGMENT_FACTOR) -> tuple[np.ndarray, list[str]]:
    """Banco completo de mapas de la ronda de mejoras (etapa 5e): todos los de _maps, con textura.

    Devuelve (mapas estandarizados, nombres).
    """
    maps, region = _maps(rgb, factor, texture=True)
    names = list(maps)
    return _stack(maps, names, region), names


def _threshold(score_full: np.ndarray, fov_full: np.ndarray, fraction: float | None,
               value: float | None) -> np.ndarray:
    from .segment import segmentar_fraccion

    if value is not None:
        return (score_full > value) & fov_full
    return segmentar_fraccion(score_full, fov_full, fraction)[0]


def segment_image(rgb: np.ndarray, weights: np.ndarray, fraction: float | None = SEGMENT_FRACTION,
                  value: float | None = None, features: np.ndarray | None = None,
                  return_score: bool = False):
    """Máscara de vasos (booleana, del tamaño de la foto) con la combinación de filtros.

    `weights` son los de fit_weights / load_weights (ordenada al origen primero).
    El umbral marca la `fraction` más alta del campo detectado; si se da
    `value`, en cambio, marca la probabilidad mayor que `value`. `features`
    permite pasar los mapas ya calculados (compute_features) para no repetirlos.
    """
    from .enhance import upscale
    from .fov import detect_fov_robust
    from .stats import predict_logistic

    if features is None:
        features, _ = compute_features(rgb)
    prob = predict_logistic(features.reshape(len(features), -1).T, weights)
    prob = upscale(prob.reshape(features.shape[1:]).astype(np.float32), rgb.shape[:2])
    mask = _threshold(prob, detect_fov_robust(rgb), fraction, value)
    return (mask, prob) if return_score else mask


def segment_reference(rgb: np.ndarray, fraction: float | None = SEGMENT_FRACTION,
                      value: float | None = None, features: np.ndarray | None = None) -> np.ndarray:
    """Referencia clásica: solo el detector de líneas sobre el verde, con la misma regla de umbral."""
    from .enhance import upscale
    from .fov import detect_fov_robust

    if features is None:
        features, _ = compute_features(rgb)
    score = upscale(features[SEGMENT_FEATURES.index(SEGMENT_REFERENCE_FILTER)], rgb.shape[:2])
    return _threshold(score, detect_fov_robust(rgb), fraction, value)


def training_pixels(image_id: str, features: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Píxeles de una imagen de desarrollo para ajustar los pesos y elegir la fracción.

    Salen de la muestra fija de evaluación (src/evaluation.py), con la semilla
    que depende de la imagen, como en notebooks/05b y 05e: "x" e "y" son
    N_TRAIN píxeles de vaso y N_TRAIN de fondo (para los pesos); "x_thr",
    "y_thr" y "w_thr" son N_THR píxeles de la muestra con su peso (el fondo
    pesa 1 / EVAL_BG_FRACTION), para elegir la fracción.
    """
    from .data import load_image
    from .evaluation import load_sample, sample_values

    s = load_sample(image_id)
    if features is None:
        features, _ = compute_features(load_image(image_id))
    v = np.stack([sample_values(f, s) for f in features], axis=1).astype(np.float32)
    rng = np.random.default_rng(SEED + sum(map(ord, image_id)))
    pos, neg = np.flatnonzero(s.truth), np.flatnonzero(~s.truth)
    pick = np.r_[rng.choice(pos, N_TRAIN, replace=False), rng.choice(neg, N_TRAIN, replace=False)]
    thr = rng.choice(len(s.truth), N_THR, replace=False)
    return {"x": v[pick], "y": s.truth[pick], "x_thr": v[thr], "y_thr": s.truth[thr],
            "w_thr": np.where(s.truth[thr], 1.0, 1 / EVAL_BG_FRACTION)}


def fit_weights(samples: dict[str, dict], image_ids) -> np.ndarray:
    """Pesos de la regresión logística con los píxeles de entrenamiento de `image_ids`."""
    from .stats import fit_logistic

    x = np.concatenate([samples[i]["x"] for i in image_ids])
    y = np.concatenate([samples[i]["y"] for i in image_ids])
    return fit_logistic(x, y, ridge=1e-3)


def _weighted_quantile(v: np.ndarray, w: np.ndarray, q: float) -> float:
    o = np.argsort(v)
    return v[o][np.searchsorted(np.cumsum(w[o]) / w.sum(), q)]


def _threshold_scores(samples: dict[str, dict], weights: np.ndarray | None, image_ids) -> dict:
    """Puntaje de la muestra para el umbral: la probabilidad con `weights`, o el
    detector de líneas solo (la referencia) si `weights` es None."""
    from .stats import predict_logistic

    ref = SEGMENT_FEATURES.index(SEGMENT_REFERENCE_FILTER)
    return {i: predict_logistic(samples[i]["x_thr"], weights) if weights is not None
            else samples[i]["x_thr"][:, ref].astype(np.float64) for i in image_ids}


def choose_fraction(samples: dict[str, dict], weights: np.ndarray | None, image_ids,
                    fractions=FRACTIONS) -> float:
    """La fracción de `fractions` con el mejor Matthews medio en `image_ids`.

    En cada imagen se marca la fracción más alta del puntaje (cuantil con los
    pesos de la muestra) y Matthews se estima con weighted_matthews. Con
    `weights` None el puntaje es el de la referencia.
    """
    from .evaluation import weighted_matthews

    image_ids = list(image_ids)
    scores = _threshold_scores(samples, weights, image_ids)

    def mean_matthews(f):
        return np.mean([weighted_matthews(scores[i] > _weighted_quantile(scores[i], samples[i]["w_thr"], 1 - f),
                                          samples[i]["y_thr"], samples[i]["w_thr"]) for i in image_ids])
    return float(max(fractions, key=mean_matthews))


def choose_value(samples: dict[str, dict], weights: np.ndarray | None, image_ids) -> float:
    """El valor fijo del puntaje con el mejor Matthews medio en `image_ids` (como en 05b).

    Las candidatas son 60 cuantiles, de 0,70 a 0,995, de los puntajes de todas
    las imágenes de `image_ids` juntas. Con `weights` None el puntaje es el de
    la referencia.
    """
    from .evaluation import weighted_matthews

    image_ids = list(image_ids)
    scores = _threshold_scores(samples, weights, image_ids)
    grid = np.quantile(np.concatenate([scores[i] for i in image_ids]), np.linspace(0.70, 0.995, 60))

    def mean_matthews(t):
        return np.mean([weighted_matthews(scores[i] > t, samples[i]["y_thr"], samples[i]["w_thr"])
                        for i in image_ids])
    return float(max(grid, key=mean_matthews))


def save_weights(weights: np.ndarray, path: Path = WEIGHTS_PATH, note: str = "",
                 fraction: float = SEGMENT_FRACTION, value: float | None = None) -> None:
    """Guarda los pesos con los nombres de los mapas, para que el script los pueda usar.

    También guarda la fracción y el valor fijo elegidos con las mismas imágenes
    (la regla se cierra en la etapa 8; plan, desvíos 14.5 y 14.7).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"features": SEGMENT_FEATURES, "intercept": float(weights[0]),
            "coefficients": [float(w) for w in weights[1:]], "fraction": fraction, "value": value,
            "note": note}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_weights(path: Path = WEIGHTS_PATH) -> np.ndarray:
    """Pesos guardados con save_weights. Falla si los mapas no coinciden con SEGMENT_FEATURES."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data["features"] != SEGMENT_FEATURES:
        raise ValueError("Los pesos guardados son de otros mapas que los de config.SEGMENT_FEATURES")
    return np.array([data["intercept"], *data["coefficients"]])


MASK_CACHE = ROOT / "results" / "cache" / "mascaras_cv"


def save_dev_masks(image_id: str, masks: dict[str, np.ndarray], cache: Path = MASK_CACHE) -> None:
    """Guarda las máscaras de desarrollo de una imagen (comprimidas bit a bit)."""
    cache.mkdir(parents=True, exist_ok=True)
    shape = next(iter(masks.values())).shape
    np.savez_compressed(cache / f"{image_id}.npz", shape=np.array(shape),
                        **{k: np.packbits(v.ravel()) for k, v in masks.items()})


def load_dev_mask(image_id: str, kind: str = "combinación", cache: Path = MASK_CACHE) -> np.ndarray:
    """Máscara de desarrollo guardada por save_dev_masks.

    `kind` es "combinación" (algoritmo final) o "referencia" (detector de
    líneas solo), con la fracción fija; con " valor fijo" al final ("combinación
    valor fijo", "referencia valor fijo"), con el valor fijo. Cada imagen se
    segmentó con los pesos y el umbral de la vuelta de validación cruzada en la
    que quedó afuera (notebooks/05d).
    """
    z = np.load(cache / f"{image_id}.npz")
    shape = tuple(z["shape"])
    return np.unpackbits(z[kind])[: shape[0] * shape[1]].reshape(shape).astype(bool)

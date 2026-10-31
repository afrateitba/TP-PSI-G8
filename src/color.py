"""Mapas de color.  Esquema v1, etapa 2 (notebooks/02_mapas_color.ipynb).

Cada mapa da un valor continuo por píxel a partir de la foto sola: los tres
canales, la escala de grises, los tres canales del espacio Lab y las tres
componentes principales del color, calculadas en cada imagen dentro del
campo de visión detectado. Todavía no son máscaras de vasos.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.color import rgb2gray, rgb2lab

from .config import PCA_SIGN_RULE
from .fov import detect_fov_robust

MAP_NAMES = ["Rojo", "Verde", "Azul", "Escala de grises", "Lab L*", "Lab a*", "Lab b*",
             "PC1", "PC2", "PC3"]
PCA_SIGN_RULES = ("max_coef", "vessels")


def basic_maps(rgb: np.ndarray) -> dict[str, np.ndarray]:
    """Rojo, verde, azul, escala de grises y Lab, con la foto llevada a 0–1."""
    img = rgb.astype(np.float32) / 255.0
    lab = rgb2lab(img)
    return {
        "Rojo": img[..., 0], "Verde": img[..., 1], "Azul": img[..., 2],
        "Escala de grises": rgb2gray(img),
        "Lab L*": lab[..., 0], "Lab a*": lab[..., 1], "Lab b*": lab[..., 2],
    }


def pca_directions(rgb: np.ndarray, region: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Componentes principales del color dentro de `region`.

    Se calculan sobre rojo, verde y azul llevados a 0–1, centrados y sin
    estandarizar cada canal. Devuelve (media de los tres canales, direcciones
    en columnas ordenadas de mayor a menor variación, fracción de variación
    de cada una). El signo de cada dirección queda sin fijar.
    """
    pixels = rgb[region].astype(np.float32) / 255.0
    mean = pixels.mean(axis=0, dtype=np.float64)
    values, vectors = np.linalg.eigh(np.cov(pixels, rowvar=False))
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]
    return mean, vectors, values / values.sum()


def sign_by_max_coef(vectors: np.ndarray) -> np.ndarray:
    """Regla de signo de la etapa 2: el coeficiente de mayor valor absoluto, positivo.

    No tiene relación con los vasos, así que el sentido "vasos claros u
    oscuros" de una componente puede cambiar de una imagen a otra.
    """
    v = vectors.copy()
    for j in range(v.shape[1]):
        if v[np.argmax(np.abs(v[:, j])), j] < 0:
            v[:, j] *= -1
    return v


def sign_by_vessels(rgb: np.ndarray, region: np.ndarray, mean: np.ndarray,
                    vectors: np.ndarray, step: int = 4, size: int = 25) -> np.ndarray:
    """Regla de signo ligada a los vasos, sin usar ninguna máscara de expertos.

    Los vasos son estructuras finas más oscuras que su entorno en el canal
    verde. Se calcula, a 1/`step` de la resolución, "oscuridad local" =
    mediana del verde en una ventana de `size` píxeles − verde. Cada
    componente se orienta para que su correlación con esa oscuridad, dentro de
    `region`, sea positiva: así los vasos quedan siempre como valores altos.
    """
    img = rgb[::step, ::step].astype(np.float32) / 255.0
    reg = region[::step, ::step]
    green = np.where(reg, img[..., 1], img[..., 1][reg].mean())
    darkness = (ndi.median_filter(green, size=size) - green)[reg]
    darkness -= darkness.mean()
    v = vectors.copy()
    for j in range(v.shape[1]):
        comp = (img[reg] @ v[:, j].astype(np.float32)) - float(mean @ v[:, j])
        if np.dot(comp - comp.mean(), darkness) < 0:
            v[:, j] *= -1
    return v


def pca_maps(rgb: np.ndarray, mean: np.ndarray, vectors: np.ndarray) -> dict[str, np.ndarray]:
    """Proyección de la foto sobre cada dirección: PC1, PC2 y PC3."""
    img = rgb.astype(np.float32) / 255.0
    return {f"PC{j + 1}": img @ vectors[:, j].astype(np.float32) - float(mean @ vectors[:, j])
            for j in range(vectors.shape[1])}


def color_maps(rgb: np.ndarray, region: np.ndarray | None = None,
               pca_sign: str = PCA_SIGN_RULE) -> dict[str, np.ndarray]:
    """Los diez mapas de la etapa 2, usando solo la foto.

    `region` es donde se calculan las componentes principales; si no se da,
    se usa el campo de visión detectado (detect_fov_robust), como en la
    etapa 2. `pca_sign` elige la regla de signo de las componentes:
    "vessels" (sign_by_vessels, la adoptada en la etapa 2b) o "max_coef" (la
    original de la etapa 2, que sigue usando su cuaderno).
    """
    if pca_sign not in PCA_SIGN_RULES:
        raise ValueError(f"Regla de signo desconocida: {pca_sign}")
    if region is None:
        region = detect_fov_robust(rgb)
    maps = basic_maps(rgb)
    mean, vectors, _ = pca_directions(rgb, region)
    vectors = (sign_by_max_coef(vectors) if pca_sign == "max_coef"
               else sign_by_vessels(rgb, region, mean, vectors))
    maps.update(pca_maps(rgb, mean, vectors))
    return maps


def standardize(m: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Mapa centrado y escalado con la media y el desvío de `region` (sin máscaras de expertos)."""
    v = m[region]
    return ((m - v.mean()) / v.std()).astype(np.float32)


def color_maps_at_scale(rgb: np.ndarray, factor: int, names: list[str] | None = None,
                        pca_sign: str = PCA_SIGN_RULE) -> dict[str, np.ndarray]:
    """Mapas calculados con la foto reducida `factor` veces y llevados al tamaño original.

    La reducción promedia bloques de factor × factor píxeles; el campo de
    visión para las componentes se detecta en la foto reducida; cada mapa se
    agranda con interpolación lineal. Sirve para evaluar a resolución
    original lo que se calcula a resolución reducida (plan, sección 3).
    """
    from PIL import Image
    from skimage.transform import resize

    if factor == 1:
        maps = color_maps(rgb, pca_sign=pca_sign)
    else:
        small = np.asarray(Image.fromarray(rgb).reduce(factor))
        maps = {k: resize(v, rgb.shape[:2], order=1, preserve_range=True, anti_aliasing=False)
                .astype(np.float32)
                for k, v in color_maps(small, pca_sign=pca_sign).items()}
    return maps if names is None else {k: maps[k] for k in names}


NONLINEAR_NAMES = ["Verde / rojo", "Verde / azul", "Cromaticidad verde", "Cromaticidad roja", "Saturación"]


def nonlinear_maps(rgb: np.ndarray, eps: float = 1.0 / 255) -> dict[str, np.ndarray]:
    """Mapas de color no lineales (etapa 2e).

    - Cocientes verde / rojo y verde / azul: el rojo y el azul llevan sobre todo
      la iluminación y el pigmento del fondo; dividir los cancela sin estimarlos.
    - Cromaticidades: cada canal dividido por la suma de los tres; separan el
      color del brillo.
    - Saturación del espacio matiz–saturación–brillo: (máximo − mínimo) / máximo.
    `eps` evita dividir por cero afuera del campo de visión.
    """
    img = rgb.astype(np.float32) / 255.0
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    total = r + g + b + eps
    mx, mn = img.max(axis=2), img.min(axis=2)
    return {
        "Verde / rojo": g / (r + eps),
        "Verde / azul": g / (b + eps),
        "Cromaticidad verde": g / total,
        "Cromaticidad roja": r / total,
        "Saturación": (mx - mn) / (mx + eps),
    }

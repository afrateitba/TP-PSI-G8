"""Lectura de la base: imágenes, máscaras y datos de cada archivo.

Candado del conjunto de prueba (plan de evaluación, sección 1):
- load_image, load_vessels y load_fov no abren imágenes de prueba.
- La única entrada a prueba es load_test_case, que solo se usa en
  notebooks/99_prueba.ipynb sobre la versión `congelado-test`.
- image_table lee las 45 imágenes sin pasar por el candado porque arma la
  partición; scripts/make_split.py no la vuelve a correr si split.csv existe.
tests/test_lock.py controla que ninguna de esas entradas se use en otro lado.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi

from .config import (GROUPS, IMAGE_IDS, MASK_THRESHOLD, QUANT_SPLIT, RAW_DIR,
                     SAME_PERSON_MAX_GAP_MIN, SPLIT_CSV)

EXIF_DATETIME = 306   # etiqueta del archivo con la fecha y hora de la toma


class LockedImageError(PermissionError):
    """Se intentó abrir una imagen de prueba antes de la evaluación final."""


@lru_cache(maxsize=1)
def load_split() -> pd.DataFrame:
    """Partición guardada (data/split.csv). Sin el archivo no se abre nada."""
    if not SPLIT_CSV.exists():
        raise FileNotFoundError(f"Falta {SPLIT_CSV}: sin partición no se sabe qué es prueba")
    return pd.read_csv(SPLIT_CSV)


def dev_ids(group: str | None = None) -> list[str]:
    """Imágenes de desarrollo, de todos los grupos o de uno, en el orden de IMAGE_IDS."""
    s = load_split()
    keep = s["set"] == "dev"
    if group is not None:
        keep &= s["group"] == group
    chosen = set(s.loc[keep, "image"])
    return [i for i in IMAGE_IDS if i in chosen]


def heldout_ids() -> list[str]:
    """Imágenes de prueba. Solo para notebooks/99_prueba.ipynb."""
    chosen = set(load_split().query("set == 'test'")["image"])
    return [i for i in IMAGE_IDS if i in chosen]


def _check_unlocked(image_id: str) -> None:
    if image_id in heldout_ids():
        raise LockedImageError(
            f"{image_id} es una imagen de prueba y está bloqueada hasta la evaluación "
            "final (docs/plan_evaluacion.md, sección 1).")


def image_path(image_id: str, raw_dir: Path = RAW_DIR) -> Path:
    """Ruta de la imagen a color. La extensión varía (.jpg en h y g, .JPG en dr)."""
    found = sorted((raw_dir / "images").glob(f"{image_id}.*"))
    if not found:
        raise FileNotFoundError(f"No está la imagen {image_id} en {raw_dir / 'images'}")
    return found[0]


def group_of(image_id: str) -> str:
    """Grupo a partir del nombre: '03_dr' -> 'dr'."""
    group = image_id.split("_", 1)[1]
    if group not in GROUPS:
        raise ValueError(f"Grupo desconocido en {image_id}")
    return group


def _read_rgb(path: Path) -> np.ndarray:
    """Imagen a color de un archivo, sin candado. Solo para uso interno."""
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def _binary(path: Path) -> np.ndarray:
    """Máscara de un archivo .tif como booleano (> MASK_THRESHOLD), sin candado."""
    with Image.open(path) as im:
        a = np.asarray(im)
    if a.ndim == 3:
        a = a[..., 0]
    return a > MASK_THRESHOLD


def _vessels_path(image_id: str, raw_dir: Path) -> Path:
    return raw_dir / "manual1" / f"{image_id}.tif"


def _fov_path(image_id: str, raw_dir: Path) -> Path:
    return raw_dir / "mask" / f"{image_id}_mask.tif"


def load_image(image_id: str, raw_dir: Path = RAW_DIR) -> np.ndarray:
    """Imagen a color (alto, ancho, 3) en uint8, canales rojo, verde y azul.

    Solo imágenes de desarrollo: con una de prueba da LockedImageError.
    """
    _check_unlocked(image_id)
    return _read_rgb(image_path(image_id, raw_dir))


def load_vessels(image_id: str, raw_dir: Path = RAW_DIR) -> np.ndarray:
    """Máscara de vasos de los expertos (manual1/), True = vaso. Solo desarrollo."""
    _check_unlocked(image_id)
    return _binary(_vessels_path(image_id, raw_dir))


def load_fov(image_id: str, raw_dir: Path = RAW_DIR) -> np.ndarray:
    """Máscara del campo de visión de la base (mask/), True = adentro. Solo desarrollo."""
    _check_unlocked(image_id)
    return _binary(_fov_path(image_id, raw_dir))


def load_test_case(image_id: str, raw_dir: Path = RAW_DIR) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Imagen, máscara de vasos y campo de visión de una imagen de PRUEBA.

    Es la única entrada al conjunto de prueba y solo se usa en
    notebooks/99_prueba.ipynb, sobre la versión `congelado-test`
    (tests/test_lock.py lo controla). Con una imagen de desarrollo da error,
    para que no se use como cargador general.
    """
    if image_id not in heldout_ids():
        raise ValueError(f"{image_id} no es una imagen de prueba; usar load_image")
    return (_read_rgb(image_path(image_id, raw_dir)),
            _binary(_vessels_path(image_id, raw_dir)),
            _binary(_fov_path(image_id, raw_dir)))


def capture_time(path: Path) -> datetime:
    """Fecha y hora de la toma, guardadas por la cámara en el archivo."""
    with Image.open(path) as im:
        return datetime.strptime(im.getexif()[EXIF_DATETIME], "%Y:%m:%d %H:%M:%S")


def quant_mean(path: Path) -> float:
    """Media de la tabla de cuantización del brillo del .jpg.

    Cuanto más alta, más comprimida está la imagen (pierde más detalle).
    """
    with Image.open(path) as im:
        return float(np.mean(im.quantization[0]))


def disc_side(rgb: np.ndarray, fov: np.ndarray, factor: int = 8) -> str:
    """Lado del disco óptico: 'izquierda' o 'derecha'.

    El disco es la zona más brillante del campo de visión. Se busca el máximo
    del brillo suavizado en la imagen reducida `factor` veces. Sirve para
    distinguir ojo derecho de ojo izquierdo; no es un detector del disco.
    """
    small = rgb[::factor, ::factor].astype(float).mean(axis=2)
    inside = fov[::factor, ::factor]
    smooth = ndi.gaussian_filter(small, 8) * inside
    _, x = np.unravel_index(np.argmax(smooth), smooth.shape)
    return "izquierda" if x < smooth.shape[1] / 2 else "derecha"


def assign_persons(times: pd.Series,
                   max_gap_min: float = SAME_PERSON_MAX_GAP_MIN) -> pd.Series:
    """Persona de cada imagen ('P01', 'P02', ...), indexada como `times`.

    Dos imágenes son de la misma persona si se sacaron con a lo sumo
    `max_gap_min` minutos de diferencia, y la unión es transitiva. Ante la
    duda conviene agrupar: juntar de más solo cuesta balance en la partición;
    separar a una misma persona pone su otro ojo en prueba.
    Las personas se numeran por orden de su primera imagen en `times`.
    """
    order = times.sort_values()
    gap_min = order.diff().dt.total_seconds() / 60
    session = (~(gap_min <= max_gap_min)).cumsum()   # nueva persona si el salto es grande
    first = {}
    for image_id in times.index:
        first.setdefault(session[image_id], len(first) + 1)
    return session.map(lambda s: f"P{first[s]:02d}").reindex(times.index).rename("person")


def image_table(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Una fila por imagen con grupo, persona, compresión y lado del disco.

    Solo sirve para armar la partición (scripts/make_split.py): lee las 45
    imágenes sin pasar por el candado. Lo que calcula ya está en split.csv.
    """
    rows = []
    for image_id in IMAGE_IDS:
        path = image_path(image_id, raw_dir)
        q = quant_mean(path)
        rows.append({
            "image": image_id,
            "group": group_of(image_id),
            "capture_time": capture_time(path),
            "quant_mean": round(q, 2),
            "more_compressed": q > QUANT_SPLIT,
            "disc_side": disc_side(_read_rgb(path), _binary(_fov_path(image_id, raw_dir))),
        })
    table = pd.DataFrame(rows).set_index("image")
    table.insert(1, "person", assign_persons(table["capture_time"]))
    return table.reset_index()

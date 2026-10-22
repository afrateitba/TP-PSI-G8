"""Lectura de la base: imágenes, máscaras y datos de cada archivo."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi

from .config import (GROUPS, IMAGE_IDS, MASK_THRESHOLD, QUANT_SPLIT, RAW_DIR,
                     SAME_PERSON_MAX_GAP_MIN)

EXIF_DATETIME = 306   # etiqueta del archivo con la fecha y hora de la toma


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


def load_image(image_id: str, raw_dir: Path = RAW_DIR) -> np.ndarray:
    """Imagen a color (alto, ancho, 3) en uint8, canales rojo, verde y azul."""
    with Image.open(image_path(image_id, raw_dir)) as im:
        return np.asarray(im.convert("RGB"))


def _binary(path: Path) -> np.ndarray:
    """Máscara de un archivo .tif como booleano (> MASK_THRESHOLD)."""
    with Image.open(path) as im:
        a = np.asarray(im)
    if a.ndim == 3:
        a = a[..., 0]
    return a > MASK_THRESHOLD


def load_vessels(image_id: str, raw_dir: Path = RAW_DIR) -> np.ndarray:
    """Máscara de vasos de los expertos (manual1/), True = vaso."""
    return _binary(raw_dir / "manual1" / f"{image_id}.tif")


def load_fov(image_id: str, raw_dir: Path = RAW_DIR) -> np.ndarray:
    """Máscara del campo de visión de la base (mask/), True = adentro."""
    return _binary(raw_dir / "mask" / f"{image_id}_mask.tif")


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
    """Una fila por imagen con grupo, persona, compresión y lado del disco."""
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
            "disc_side": disc_side(load_image(image_id, raw_dir), load_fov(image_id, raw_dir)),
        })
    table = pd.DataFrame(rows).set_index("image")
    table.insert(1, "person", assign_persons(table["capture_time"]))
    return table.reset_index()

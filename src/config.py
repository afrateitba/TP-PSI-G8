"""Constantes del proyecto: rutas, base de datos y partición."""
from pathlib import Path

# --- Rutas ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # no se versiona (ver .gitignore)
SPLIT_CSV = DATA_DIR / "split.csv"  # se versiona una sola vez
RESULTS_DIR = ROOT / "results"

# --- Base de datos -------------------------------------------------------
# High-Resolution Fundus Image Database (Budai et al., 2013), licencia
# Creative Commons 4.0 con atribución. all.zip trae imágenes, máscaras de
# vasos de los expertos y máscaras del campo de visión de las 45 imágenes.
HRF_URL = "https://www5.cs.fau.de/fileadmin/research/datasets/fundus-images/all.zip"
HRF_ZIP_BYTES = 76_317_613

# Sufijo del nombre de archivo -> grupo. 15 imágenes por grupo: 01_h ... 15_g.
GROUPS = {"h": "sano", "dr": "retinopatía diabética", "g": "glaucoma"}
N_PER_GROUP = 15
IMAGE_IDS = [f"{i:02d}_{g}" for g in GROUPS for i in range(1, N_PER_GROUP + 1)]

# Las máscaras de vasos son 0/255, salvo 11_h, 12_h y 13_h, que tienen entre
# 600 y 1.600 píxeles grises en los bordes. Es vaso lo que supera este valor.
MASK_THRESHOLD = 127

# Las imágenes ya vienen en .jpg con dos niveles de compresión. La media de la
# tabla de cuantización del brillo vale 2,94 en unas y 11,06 en otras; este
# valor las separa.
QUANT_SPLIT = 6.0

# La base no dice qué imágenes son de la misma persona. Dos fotos sacadas con
# a lo sumo estos minutos de diferencia se toman como de la misma persona
# (en la base son los dos ojos, sacados con 1 a 5 minutos de diferencia).
SAME_PERSON_MAX_GAP_MIN = 10

# --- Partición -----------------------------------------------------------
SEED = 2026
TEST_PER_GROUP = 5   # 15 imágenes de prueba, 30 de desarrollo

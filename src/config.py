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

# --- Elección entre candidatas (esquema 5.3; plan, desvío 14.4) -----------
# Una candidata es no inferior si el límite inferior del intervalo al 95 %
# de (candidata − mejor) es >= −margen.
NONINF_MARGIN_AUC = 0.02
NONINF_MARGIN_MATTHEWS = 0.03   # también para el Dice de línea central
TEST_PER_GROUP = 5   # 15 imágenes de prueba, 30 de desarrollo

# --- Calibración (etapa 1, notebooks/01_contexto.ipynb) -------------------
# Diámetro del campo de visión: 3.261 a 3.263 píxeles en desarrollo.
FOV_DIAMETER_REF = 3262
# Límites entre vasos finos, medianos y gruesos: terciles del ancho sobre la
# línea central de las 30 máscaras de desarrollo. Fino <= 3,47; grueso > 9.
# Fijos para todas las imágenes; no se cambian más (plan, sección 5).
WIDTH_LIMITS_PX = (3.4721359549995796, 9.0)
WIDTH_LIMITS_REL = (WIDTH_LIMITS_PX[0] / FOV_DIAMETER_REF, WIDTH_LIMITS_PX[1] / FOV_DIAMETER_REF)
# Campo de visión: el algoritmo lo detecta solo con fov.detect_fov_robust.
# La candidata original (Otsu sobre el rojo) falló en 14_h (0,954); la robusta
# da Dice >= 0,9993 en las 30 de desarrollo y >= 0,996 en 9 variantes que
# simulan otras cámaras (notebooks/01b_campo_de_vision.ipynb; desvío 14.2).
USE_AUTO_FOV = True

# --- Mapas de color (etapa 2) ----------------------------------------------
# Mapa principal provisional: tercera componente principal del color por
# imagen, con vasos claros (notebooks/02_mapas_color.ipynb). Signo de las
# componentes: "vessels" (orientadas por la oscuridad local del verde), que
# no invierte ninguna imagen de desarrollo ni con la foto sobreexpuesta
# (notebooks/02b_signo_componentes.ipynb).
PCA_SIGN_RULE = "vessels"
# Elección del mapa (etapa 2d, notebooks/02d_mapas_corregidos.ipynb, después
# de la etapa 3): con el fondo corregido el verde es el mejor mapa (0,942) en
# las 5 vueltas, y ningún otro le suma 0,01 al combinarlo. Reemplaza la
# elección de la etapa 2c (tercera componente), que comparaba mapas crudos.
COLOR_MAIN_MAP = "Verde"
COLOR_REFERENCE_MAP = "Verde"
COLOR_EXTRA_MAPS: list[str] = []

# --- Mejoramiento y restauración (etapa 3) --------------------------------
# Se calcula a 1/STAGE3_FACTOR de la resolución y se evalúa a la original.
STAGE3_FACTOR = 2
# Ventana de la corrección del fondo: unas 3 veces el vaso más grueso (99 %
# de los anchos: 26 píxeles), en proporción al diámetro del campo de visión.
BACKGROUND_WINDOW_REL = 0.024
HOMOMORPHIC_SIGMA_REL = 0.01
CLAHE_CLIP = 0.01
CLAHE_KERNEL_FRAC = 0.125
WIENER_SIZE = 5
WIENER_DEBLUR_SIGMAS = (1.0, 2.0)       # píxeles de la resolución de trabajo
WIENER_DEBLUR_BALANCES = (0.01, 0.1)
# Cadena adoptada para el verde (notebooks/03_mejoramiento.ipynb): suavizado
# de bloques (foto original) → Wiener contra el ruido → corrección del fondo.
# Wiener contra el desenfoque se probó y no se adopta (empeora 0,035).
PREPROCESS_CHAIN = ("bloques", "wiener_ruido", "fondo")

# --- Evaluación rápida en desarrollo (src/evaluation.py) ------------------
# Fracción del fondo que entra en la muestra fija de evaluación (todos los
# vasos entran siempre). La evaluación final en prueba usa todos los píxeles.
EVAL_BG_FRACTION = 0.2

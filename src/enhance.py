"""Etapa 4: filtros de realce de vasos.

Convención: todas las funciones reciben un mapa de una sola banda con los
vasos CLAROS (valores altos) y devuelven un mapa del mismo tamaño en el que
un valor alto indica vaso. Los mapas con vasos oscuros se invierten antes
con `orientar`.
"""
import numpy as np
from skimage.morphology import white_tophat, disk

# Sentido de cada mapa de la etapa 2: True si los vasos son claros.
# Las componentes principales quedan con vasos claros por la regla de signo
# "vessels" (color.sign_by_vessels). Falta confirmar Azul con la etapa 2c.
VASOS_CLAROS = {"PC1": True, "PC2": True, "PC3": True,
                "Verde": False, "Escala de grises": False}


def orientar(mapa, nombre):
    """Devuelve el mapa con los vasos claros, invirtiéndolo si hace falta."""
    if nombre not in VASOS_CLAROS:
        raise KeyError(f"Sentido no definido para el mapa {nombre!r}")
    mapa = np.asarray(mapa, dtype=np.float32)
    return mapa if VASOS_CLAROS[nombre] else -mapa


def escala_px(escala_rel, diametro_fov):
    """Pasa una escala expresada en proporción al diámetro del campo de visión a píxeles."""
    return escala_rel * diametro_fov


def sombrero_de_copa(mapa, radio_px):
    """Sombrero de copa blanco: resalta estructuras claras más angostas que el disco."""
    radio = max(1, int(round(radio_px)))
    return white_tophat(np.asarray(mapa, dtype=np.float32), disk(radio))
"""Etapa 4: filtros de realce de vasos.

Convención: todas las funciones reciben un mapa de una sola banda con los
vasos CLAROS (valores altos) y devuelven un mapa del mismo tamaño en el que
un valor alto indica vaso. Los mapas con vasos oscuros se invierten antes
con `orientar`.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage.filters import frangi
from skimage.morphology import white_tophat, disk

# Sentido de cada mapa de la etapa 2: True si los vasos son claros.
# Las componentes principales quedan con vasos claros por la regla de signo
# "vessels" (color.sign_by_vessels).
VASOS_CLAROS = {"PC1": True, "PC2": True, "PC3": True,
                "Verde": False, "Escala de grises": False,
                "Azul": True}   # área media 0,508 (etapa 2c): sentido casi indiferente


def orientar(mapa, nombre):
    """Devuelve el mapa con los vasos claros, invirtiéndolo si hace falta."""
    if nombre not in VASOS_CLAROS:
        raise KeyError(f"Sentido no definido para el mapa {nombre!r}")
    mapa = np.asarray(mapa, dtype=np.float32)
    return mapa if VASOS_CLAROS[nombre] else -mapa


def escala_px(escala_rel, diametro_fov):
    """Pasa una escala expresada en proporción al diámetro del campo de visión a píxeles."""
    return escala_rel * diametro_fov


def rellenar_fuera(mapa, region):
    """Copia a cada píxel de afuera de `region` el valor del píxel de adentro más cercano.

    Evita el escalón entre la retina y el fondo negro, que los filtros
    confunden con un vaso en el borde del campo de visión.
    """
    _, (iy, ix) = ndi.distance_transform_edt(~region, return_indices=True)
    return np.asarray(mapa, dtype=np.float32)[iy, ix]


def sombrero_de_copa(mapa, radio_px):
    """Sombrero de copa blanco: resalta estructuras claras más angostas que el disco."""
    radio = max(1, int(round(radio_px)))
    return white_tophat(np.asarray(mapa, dtype=np.float32), disk(radio))


def sigma_para_ancho(ancho_px):
    """Escala de la gaussiana que mejor responde a un vaso de ese ancho: σ = ancho / 2.

    Con las derivadas normalizadas por σ² (como en Frangi), la respuesta en
    el centro de una franja de ancho w es máxima en σ = w/2.
    """
    return ancho_px / 2


def frangi_realce(mapa, sigmas_px):
    """Filtro de Frangi para estructuras claras, en las escalas `sigmas_px` (píxeles).

    Para cada píxel toma la mayor respuesta entre las escalas.
    """
    return frangi(np.asarray(mapa, dtype=np.float32), sigmas=list(sigmas_px),
                  black_ridges=False).astype(np.float32)
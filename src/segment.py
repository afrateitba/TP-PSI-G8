"""Funciones para obtener máscaras de vasos."""

import numpy as np
from skimage.filters import threshold_otsu


def segmentar_otsu(mapa, campo):
    """Segmenta un mapa con vasos claros dentro del campo de visión."""
    mapa = np.asarray(mapa)
    campo = np.asarray(campo, dtype=bool)

    valores = mapa[campo]

    if valores.size == 0:
        raise ValueError("El campo de visión está vacío.")

    umbral = threshold_otsu(valores)
    mascara = (mapa > umbral) & campo

    return mascara, float(umbral)

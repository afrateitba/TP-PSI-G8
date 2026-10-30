"""Preprocesamiento de los mapas de características."""

import numpy as np
from scipy.ndimage import gaussian_filter


def corregir_fondo(mapa, campo, sigma):
    """Resta un fondo suave estimado dentro del campo de visión."""
    mapa = np.asarray(mapa, dtype=np.float32)
    campo = np.asarray(campo, dtype=bool)

    numerador = gaussian_filter(
        np.where(campo, mapa, 0.0), sigma=sigma
    )
    denominador = gaussian_filter(
        campo.astype(np.float32), sigma=sigma
    )

    fondo = numerador / np.maximum(denominador, 1e-8)
    return mapa - fondo

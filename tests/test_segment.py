"""Pruebas de la segmentación por Otsu."""

import numpy as np
from src.segment import segmentar_otsu


def test_otsu_separa_vasos_y_excluye_exterior():
    """Detecta una línea clara sin incluir píxeles fuera del campo."""
    mapa = np.zeros((10, 10))
    mapa[:, 5] = 1
    mapa[:, 0] = 100  # Exterior brillante: no debe afectar el umbral.

    campo = np.ones((10, 10), dtype=bool)
    campo[:, 0] = False

    esperado = np.zeros((10, 10), dtype=bool)
    esperado[:, 5] = True

    mascara, _ = segmentar_otsu(mapa, campo)

    np.testing.assert_array_equal(mascara, esperado)

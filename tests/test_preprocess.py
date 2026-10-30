"""Pruebas de la corrección del fondo."""

import numpy as np
from src.preprocess import corregir_fondo


def test_fondo_constante_y_exterior_excluido():
    """Un campo uniforme queda en cero, aunque el exterior sea brillante."""
    campo = np.zeros((20, 20), dtype=bool)
    campo[4:16, 4:16] = True

    mapa = np.full((20, 20), 100.0)
    mapa[campo] = 3.0

    resultado = corregir_fondo(mapa, campo, sigma=2)

    np.testing.assert_allclose(
        resultado[campo], 0, atol=1e-5
    )

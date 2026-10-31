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


def test_fraccion_marca_la_proporcion_pedida():
    from src.segment import segmentar_fraccion
    mapa = np.arange(100, dtype=float).reshape(10, 10)
    campo = np.ones((10, 10), dtype=bool)
    mascara, _ = segmentar_fraccion(mapa, campo, 0.1)
    assert mascara.sum() == 10 and mascara[9].all()


def test_histeresis_recupera_lo_debil_conectado():
    from src.segment import segmentar_histeresis
    rng = np.random.default_rng(0)
    mapa = rng.normal(0, 0.01, (40, 60))    # fondo con un poco de ruido
    mapa[10, 5:30] += 1.0         # vaso fuerte
    mapa[10, 30:55] += 0.5        # continuación débil, conectada
    mapa[30, 5:55] += 0.5         # vaso débil suelto
    campo = np.ones((40, 60), dtype=bool)
    # alto: parte del vaso fuerte (12 de 2400 píxeles); bajo: todo lo marcado (144)
    mascara, _ = segmentar_histeresis(mapa, campo, frac_alto=0.005, frac_bajo=0.06)
    assert mascara[10, 5:55].all()            # fuerte y su continuación
    assert not mascara[30].any()              # el débil suelto no


def test_limpiar_por_forma_quita_manchas_redondas():
    from src.segment import limpiar_por_forma
    m = np.zeros((80, 120), dtype=bool)
    m[10:12, 5:100] = True                    # vaso fino y largo
    yy, xx = np.mgrid[:80, :120]
    m |= (yy - 50) ** 2 + (xx - 30) ** 2 <= 36   # mancha redonda chica
    m |= (yy - 50) ** 2 + (xx - 90) ** 2 <= 225  # mancha redonda grande
    limpia = limpiar_por_forma(m, alargamiento_min=4, area_max=300)
    assert limpia[10:12, 5:100].all()         # el vaso queda
    assert not limpia[50, 30]                 # la mancha chica se va
    assert limpia[50, 90]                     # la grande supera area_max y queda

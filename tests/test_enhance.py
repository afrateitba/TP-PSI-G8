import numpy as np
import pytest

from src.enhance import escala_px, orientar, sombrero_de_copa


def linea_sintetica(ancho=5, oscura=True, n=101):
    """Imagen plana con una línea vertical de ancho conocido en el centro."""
    fondo, vaso = (100.0, 50.0) if oscura else (50.0, 100.0)
    img = np.full((n, n), fondo, dtype=np.float32)
    c = n // 2
    img[:, c - ancho // 2: c + ancho // 2 + 1] = vaso
    linea = np.zeros((n, n), bool)
    linea[:, c - ancho // 2: c + ancho // 2 + 1] = True
    return img, linea


def test_escala_px():
    assert escala_px(0.001, 3262) == pytest.approx(3.262)


def test_orientar_invierte_el_verde():
    m = np.array([[0.2, 0.8]], dtype=np.float32)
    assert np.array_equal(orientar(m, "Verde"), -m)
    assert np.array_equal(orientar(m, "PC3"), m)


def test_sombrero_resalta_la_linea():
    img, linea = linea_sintetica(ancho=5, oscura=False)
    salida = sombrero_de_copa(img, radio_px=6)
    assert salida[linea].mean() == pytest.approx(50.0)          # todo el contraste en la línea
    assert np.abs(salida[~linea]).max() == pytest.approx(0.0)   # fondo plano → cero


def test_sombrero_ignora_estructuras_anchas():
    # una banda de 31 píxeles no entra en un disco de radio 6: no se resalta entera
    img, linea = linea_sintetica(ancho=31, oscura=False)
    salida = sombrero_de_copa(img, radio_px=6)
    assert salida[linea].mean() < 5
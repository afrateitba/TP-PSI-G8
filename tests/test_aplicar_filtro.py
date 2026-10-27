import numpy as np
import pytest

from src.config import REALCE_FILTROS
from src.enhance import aplicar_filtro


def linea(ancho=5, n=121):
    img = np.full((n, n), 50.0, np.float32)
    c = n // 2
    img[:, c - ancho // 2: c + ancho // 2 + 1] = 100.0
    return img, c


@pytest.mark.parametrize("nombre", REALCE_FILTROS[1:])
def test_cada_filtro_resalta_la_linea(nombre):
    img, c = linea()
    salida = aplicar_filtro(nombre, img, diametro_fov=3262)
    assert salida.shape == img.shape
    assert salida[30:-30, c].mean() > salida[30:-30, 5:c - 25].mean()


def test_sin_filtro_devuelve_el_mapa():
    img, _ = linea()
    assert np.array_equal(aplicar_filtro("sin filtro", img, 3262), img)


def test_filtro_desconocido():
    img, _ = linea()
    with pytest.raises(ValueError):
        aplicar_filtro("Sobel", img, 3262)


@pytest.mark.parametrize("nombre", REALCE_FILTROS[1:])
def test_funciona_con_un_diametro_chico(nombre):
    # a la cuarta parte de la resolución las σ más chicas quedan en el piso de 0,5
    img, c = linea(ancho=3)
    salida = aplicar_filtro(nombre, img, diametro_fov=3262 / 4)
    assert np.isfinite(salida).all()
import numpy as np
import pytest

from src.enhance import (cuantizar, detector_lineas, escala_px, filtro_adaptado,
                         frangi_realce, gabor_realce, orientar, rellenar_fuera,
                         sigma_para_ancho, sombrero_de_copa, textura_glcm)


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


def test_rellenar_fuera_quita_el_escalon():
    img = np.zeros((50, 50), np.float32)
    region = np.zeros((50, 50), bool)
    region[10:40, 10:40] = True
    img[region] = 7.0
    out = rellenar_fuera(img, region)
    assert np.all(out == 7.0)            # afuera copia el valor del borde de adentro


def test_frangi_resalta_la_linea():
    img, linea = linea_sintetica(ancho=5, oscura=False)
    salida = frangi_realce(img, [sigma_para_ancho(5)])
    c = img.shape[0] // 2
    centro = salida[10:-10, c]                       # lejos de los bordes de la imagen
    fondo = salida[10:-10, :c - 10]
    assert centro.min() > 10 * fondo.max()


def test_frangi_no_marca_el_borde_si_se_rellena():
    # un disco claro (la retina) sobre negro: sin rellenar, el borde parece un vaso
    n = 201
    yy, xx = np.mgrid[:n, :n]
    region = np.hypot(yy - n // 2, xx - n // 2) < 80
    img = np.where(region, 1.0, 0.0).astype(np.float32)
    borde = region & ~np.pad(region[2:-2, 2:-2] & region[:-4, 2:-2] & region[4:, 2:-2]
                             & region[2:-2, :-4] & region[2:-2, 4:], 2)
    crudo = frangi_realce(img, [2.0])
    relleno = frangi_realce(rellenar_fuera(img, region), [2.0])
    assert relleno[borde].max() < 0.1 * crudo[borde].max()


   # --- Detector de líneas y filtro adaptado -----------------------------------

def linea_diagonal(ancho=5, n=101):
    """Línea clara a 45°, de ancho aproximado `ancho`, sobre fondo plano."""
    y, x = np.mgrid[:n, :n]
    linea = np.abs(x - y) / np.sqrt(2) <= ancho / 2
    return np.where(linea, 100.0, 50.0).astype(np.float32), linea


@pytest.mark.parametrize("filtro", [
    lambda m: filtro_adaptado(m, sigma_px=2.5, largo_px=9),
    lambda m: detector_lineas(m, largo_px=15),
    lambda m: gabor_realce(m, sigma_px=2.5),
])
def test_orientado_resalta_la_linea_y_no_el_fondo(filtro):
    img, linea = linea_sintetica(ancho=5, oscura=False)
    salida = filtro(img)
    c = img.shape[0] // 2
    assert salida[20:-20, c].min() > 1                      # centro de la línea: positivo
    assert np.abs(salida[20:-20, 5:c - 20]).max() < 1e-3    # fondo plano, también junto al borde: cero


@pytest.mark.parametrize("filtro", [
    lambda m: filtro_adaptado(m, sigma_px=2.5, largo_px=9),
    lambda m: detector_lineas(m, largo_px=15),
    lambda m: gabor_realce(m, sigma_px=2.5),
])
def test_orientado_funciona_en_diagonal(filtro):
    vertical, _ = linea_sintetica(ancho=5, oscura=False)
    diagonal, _ = linea_diagonal(ancho=5)
    c = vertical.shape[0] // 2
    rv = filtro(vertical)[c, c]
    rd = filtro(diagonal)[c, c]
    assert rd == pytest.approx(rv, rel=0.25)                # no depende de la orientación


def test_adaptado_ignora_estructuras_anchas():
    angosta, _ = linea_sintetica(ancho=5, oscura=False)
    ancha, _ = linea_sintetica(ancho=31, oscura=False)
    c = angosta.shape[0] // 2
    r_angosta = filtro_adaptado(angosta, 2.5, 9)[c, c]
    r_ancha = filtro_adaptado(ancha, 2.5, 9)[c, c]
    assert r_ancha < 0.1 * r_angosta                        # el centro de una meseta da casi 0 


def test_gabor_ignora_estructuras_anchas():
    angosta, _ = linea_sintetica(ancho=5, oscura=False)
    ancha, _ = linea_sintetica(ancho=31, oscura=False)
    c = angosta.shape[0] // 2
    assert gabor_realce(ancha, 2.5)[c, c] < 0.1 * gabor_realce(angosta, 2.5)[c, c]


   # --- Textura -----------------------------------------------------------------

def test_cuantizar_reparte_por_igual():
    m = np.random.default_rng(2026).random((100, 100)).astype(np.float32)
    q = cuantizar(m, 8)
    assert q.min() == 0 and q.max() == 7
    conteos = np.bincount(q.ravel(), minlength=8)
    assert conteos.min() > 0.9 * conteos.max()       # cada nivel con ~1/8 de los píxeles


def test_glcm_imagen_constante():
    t = textura_glcm(np.full((40, 40), 3, np.uint8), niveles=8, ventana_px=7)
    assert np.allclose(t["contraste"], 0)
    assert np.allclose(t["homogeneidad"], 1)
    assert np.allclose(t["energia"], 1)


def test_glcm_rayas_verticales():
    # columnas 0, 1, 0, 1…: el vecino horizontal y los diagonales siempre difieren en 1;
    # el vertical, nunca. Promedio de las 4 direcciones: contraste 3/4, homogeneidad
    # (3 · 1/2 + 1) / 4 = 0,625; energía 1/2 en cada dirección.
    # ventana de lado par: cubre tantas columnas 0 como 1
    q = np.tile(np.array([0, 1], np.uint8), (40, 20))
    t = textura_glcm(q, niveles=2, ventana_px=8)
    centro = (slice(10, 30), slice(10, 30))
    assert np.allclose(t["contraste"][centro], 0.75)
    assert np.allclose(t["homogeneidad"][centro], 0.625)
    assert np.allclose(t["energia"][centro], 0.5)


def test_glcm_coincide_con_skimage():
    # con una ventana que cubre casi toda la imagen, el contraste y la energía
    # (promediados en las 4 direcciones) coinciden con graycomatrix
    from skimage.feature import graycomatrix, graycoprops
    rng = np.random.default_rng(2026)
    q = rng.integers(0, 4, (60, 60)).astype(np.uint8)
    t = textura_glcm(q, niveles=4, ventana_px=61)
    g = graycomatrix(q, [1], [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4], levels=4,
                     symmetric=True, normed=True)
    assert t["contraste"][30, 30] == pytest.approx(graycoprops(g, "contrast").mean(), rel=0.05)
    assert t["energia"][30, 30] == pytest.approx((graycoprops(g, "energy") ** 2).mean(), rel=0.05) 
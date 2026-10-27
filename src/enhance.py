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
from scipy.signal import oaconvolve

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


# --- Filtros orientados: detector de líneas y filtro adaptado ----------------
N_ORIENTACIONES = 12   # cada 15°


def _ejes(radio, theta):
    """Coordenadas de un núcleo de (2·radio+1)² píxeles rotadas un ángulo `theta`.

    `u` es la distancia a través del vaso; `v`, a lo largo del vaso.
    """
    y, x = np.mgrid[-radio:radio + 1, -radio:radio + 1].astype(np.float32)
    u = x * np.cos(theta) + y * np.sin(theta)
    v = -x * np.sin(theta) + y * np.cos(theta)
    return u, v


def _maximo_orientado(mapa, nucleos):
    """Mayor respuesta, píxel a píxel, entre los núcleos (uno por orientación).

    Antes de convolucionar se extiende la imagen por reflexión: con el relleno
    con ceros por defecto, los bordes de la imagen (donde el campo de visión
    toca el borde de la foto, arriba y abajo) darían respuestas falsas.
    """
    mapa = np.asarray(mapa, dtype=np.float32)
    radio = max(k.shape[0] for k in nucleos) // 2
    extendido = np.pad(mapa, radio, mode="reflect")
    salida = None
    for k in nucleos:
        r = oaconvolve(extendido, k, mode="same")[radio:-radio, radio:-radio].astype(np.float32)
        salida = r if salida is None else np.maximum(salida, r)
    return salida


def nucleo_adaptado(sigma_px, largo_px, theta):
    """Núcleo del filtro adaptado (Chaudhuri et al., 1989) para vasos claros.

    Perfil gaussiano de desvío `sigma_px` a través del vaso, constante a lo
    largo de `largo_px`, recortado en ±3σ y con media cero (un fondo plano da 0).
    """
    radio = int(np.ceil(max(3 * sigma_px, largo_px / 2))) + 1
    u, v = _ejes(radio, theta)
    soporte = (np.abs(u) <= 3 * sigma_px) & (np.abs(v) <= largo_px / 2)
    k = np.exp(-u ** 2 / (2 * sigma_px ** 2))
    k[soporte] -= k[soporte].mean()
    k[~soporte] = 0
    return (k / np.abs(k).sum()).astype(np.float32)


def filtro_adaptado(mapa, sigma_px, largo_px, n_orientaciones=N_ORIENTACIONES):
    """Filtro adaptado en `n_orientaciones` ángulos; para cada píxel, la mayor respuesta."""
    angulos = np.arange(n_orientaciones) * np.pi / n_orientaciones
    return _maximo_orientado(mapa, [nucleo_adaptado(sigma_px, largo_px, t) for t in angulos])


def nucleo_linea(largo_px, theta):
    """Segmento de largo `largo_px` y un píxel de ancho, normalizado a suma 1."""
    radio = int(np.ceil(largo_px / 2))
    u, v = _ejes(radio, theta)
    k = ((np.abs(u) <= 0.5) & (np.abs(v) <= largo_px / 2)).astype(np.float32)
    return k / k.sum()


def detector_lineas(mapa, largo_px, n_orientaciones=N_ORIENTACIONES):
    """Detector de líneas (Ricci y Perfetti, 2007) para vasos claros.

    Promedio sobre el mejor segmento de largo `largo_px` menos el promedio de
    la ventana cuadrada del mismo lado. Un fondo plano da 0.
    """
    mapa = np.asarray(mapa, dtype=np.float32)
    angulos = np.arange(n_orientaciones) * np.pi / n_orientaciones
    lineas = _maximo_orientado(mapa, [nucleo_linea(largo_px, t) for t in angulos])
    lado = 2 * int(np.ceil(largo_px / 2)) + 1
    return lineas - ndi.uniform_filter(mapa, size=lado)


    # --- Gabor -------------------------------------------------------------------

def nucleo_gabor(sigma_px, theta, elongacion=2.0):
    """Parte real (par) de un núcleo de Gabor orientado, para vasos claros.

    A través del vaso: coseno de longitud de onda 4·σ bajo una gaussiana de
    desvío `sigma_px`, de modo que el lóbulo positivo central tiene un ancho
    de unos 2·σ, como el vaso (sigma_para_ancho). A lo largo del vaso: una
    gaussiana `elongacion` veces más larga. Media cero (un fondo plano da 0).
    """
    sigma_v = elongacion * sigma_px
    radio = int(np.ceil(3 * max(sigma_px, sigma_v)))
    u, v = _ejes(radio, theta)
    k = (np.exp(-u ** 2 / (2 * sigma_px ** 2) - v ** 2 / (2 * sigma_v ** 2))
         * np.cos(2 * np.pi * u / (4 * sigma_px)))
    k -= k.mean()
    return (k / np.abs(k).sum()).astype(np.float32)


def gabor_realce(mapa, sigma_px, elongacion=2.0, n_orientaciones=N_ORIENTACIONES):
    """Filtro de Gabor en `n_orientaciones` ángulos; para cada píxel, la mayor respuesta."""
    angulos = np.arange(n_orientaciones) * np.pi / n_orientaciones
    return _maximo_orientado(mapa, [nucleo_gabor(sigma_px, t, elongacion) for t in angulos])


# --- Textura: matriz de coocurrencia en una ventana -------------------------
# Cuatro direcciones (0°, 45°, 90° y 135°); cada medida se promedia entre ellas.
DESPLAZAMIENTOS = ((0, 1), (-1, 1), (-1, 0), (-1, -1))   # (fila, columna) para distancia 1


def cuantizar(mapa, niveles, region=None):
    """Lleva el mapa a `niveles` niveles de gris (0 … niveles − 1) con igual cantidad de píxeles.

    Los cortes son los cuantiles del mapa dentro de `region` (por ejemplo, el
    campo de visión detectado); sin `region`, de toda la imagen.
    """
    mapa = np.asarray(mapa, dtype=np.float32)
    valores = mapa[region] if region is not None else mapa.ravel()
    cortes = np.quantile(valores, np.arange(1, niveles) / niveles)
    return np.searchsorted(cortes, mapa, side="right").astype(np.uint8)


def textura_glcm(q, niveles, ventana_px, distancia=1):
    """Contraste, homogeneidad y energía de la matriz de coocurrencia alrededor de cada píxel.

    `q` es un mapa cuantizado (cuantizar). Para cada píxel se cuentan los
    pares (píxel, vecino a `distancia` en cada dirección) dentro de una
    ventana de `ventana_px` de lado, con la matriz simétrica y normalizada,
    como graycomatrix(symmetric=True, normed=True). Se calcula con filtros de
    promedio sobre los pares, sin recorrer las ventanas una por una.

    "Energía" es la suma de los cuadrados de la matriz (segundo momento
    angular); graycoprops(..., "energy") da su raíz cuadrada.

    Devuelve un diccionario con los tres mapas. No siguen la convención
    "alto = vaso": su sentido lo decide la combinación de la etapa 5.
    """
    q = np.asarray(q, dtype=np.int16)
    alto, ancho = q.shape
    d = distancia
    extendida = np.pad(q, d, mode="reflect")
    media = lambda a: ndi.uniform_filter(a.astype(np.float32), size=ventana_px, mode="reflect")
    contraste = np.zeros(q.shape, np.float32)
    homogeneidad = np.zeros(q.shape, np.float32)
    energia = np.zeros(q.shape, np.float32)
    for dy, dx in DESPLAZAMIENTOS:
        vecino = extendida[d + dy * d: d + dy * d + alto, d + dx * d: d + dx * d + ancho]
        dif2 = (q - vecino).astype(np.float32) ** 2
        contraste += media(dif2)
        homogeneidad += media(1.0 / (1.0 + dif2))
        a, b = np.minimum(q, vecino), np.maximum(q, vecino)   # par sin orden
        for i in range(niveles):
            for j in range(i, niveles):
                p = media((a == i) & (b == j))
                # matriz simétrica: un par i ≠ j se reparte en (i, j) y (j, i)
                energia += p ** 2 if i == j else p ** 2 / 2
    n = len(DESPLAZAMIENTOS)
    return {"contraste": contraste / n, "homogeneidad": homogeneidad / n, "energia": energia / n}
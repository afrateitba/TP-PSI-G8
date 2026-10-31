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


def segmentar_fraccion(mapa, campo, fraccion):
    """Marca como vaso la `fraccion` de píxeles del campo con valores más altos.

    Es un umbral distinto en cada imagen, pero con la misma proporción de
    vasos: se adapta al brillo de cada foto como Otsu, sin suponer que el
    histograma tenga dos grupos.
    """
    mapa = np.asarray(mapa)
    campo = np.asarray(campo, dtype=bool)
    valores = mapa[campo]
    if valores.size == 0:
        raise ValueError("El campo de visión está vacío.")
    umbral = np.quantile(valores, 1 - fraccion)
    return (mapa > umbral) & campo, float(umbral)


def segmentar_histeresis(mapa, campo, frac_alto, frac_bajo):
    """Umbral con histéresis, con los dos umbrales como fracciones de píxeles del campo.

    El umbral alto deja como vaso la `frac_alto` de píxeles más altos (vasos
    seguros); el bajo, la `frac_bajo` más alta (con frac_bajo > frac_alto),
    pero esos píxeles solo quedan si están conectados (ocho vecinos) a un
    vaso seguro. Así se recuperan vasos finos débiles que continúan a uno
    grueso, sin aceptar manchas sueltas del fondo.
    """
    from skimage.filters import apply_hysteresis_threshold

    if not 0 < frac_alto < frac_bajo < 1:
        raise ValueError("Se necesita 0 < frac_alto < frac_bajo < 1.")
    mapa = np.asarray(mapa, dtype=np.float32)
    campo = np.asarray(campo, dtype=bool)
    valores = mapa[campo]
    if valores.size == 0:
        raise ValueError("El campo de visión está vacío.")
    alto, bajo = np.quantile(valores, [1 - frac_alto, 1 - frac_bajo])
    dentro = np.where(campo, mapa, valores.min())
    return apply_hysteresis_threshold(dentro, bajo, alto) & campo, (float(bajo), float(alto))


def limpiar_por_forma(mascara, alargamiento_min, area_max):
    """Quita las componentes chicas que no son alargadas.

    Para cada componente (ocho vecinos): área A y largo L de su línea
    central. El alargamiento L² / A vale alrededor de largo / ancho: es
    grande en un vaso y chico en una mancha redonda. Se quitan las
    componentes con A <= `area_max` y alargamiento < `alargamiento_min`; las
    grandes (el árbol de vasos principal) se conservan siempre.
    """
    from scipy import ndimage as ndi
    from skimage.morphology import skeletonize

    mascara = np.asarray(mascara, dtype=bool)
    etiquetas, n = ndi.label(mascara, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return mascara.copy()
    area = np.bincount(etiquetas.ravel(), minlength=n + 1)
    largo = np.bincount(etiquetas.ravel(), weights=skeletonize(mascara).ravel(), minlength=n + 1)
    alargamiento = largo ** 2 / np.maximum(area, 1)
    quitar = (area <= area_max) & (alargamiento < alargamiento_min)
    quitar[0] = False
    return mascara & ~quitar[etiquetas]

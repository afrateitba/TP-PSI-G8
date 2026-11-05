# PSIB2026Q2-TPI-Grupo08-Frate_Tenca_Weizman

Trabajo práctico de procesamiento de imágenes biomédicas (ITBA, 16.63, 2026 segundo cuatrimestre).
Segmentación de vasos en imágenes de fondo de ojo de la High-Resolution Fundus Image Database, combinando mapas de características de color.

Integrantes: Augusto Frate, Karolina Tenca, Leah Weizman.

## Instalación

Con Python 3.12:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # en Linux o macOS: .venv/bin/python
```

## Datos

```bash
.venv/Scripts/python scripts/download_data.py
```

Descarga la base (unos 76 megabytes) a `data/raw/`, que no se versiona. Base de Budai et al. (2013), licencia Creative Commons 4.0 con atribución.

## Segmentar una foto nueva

El algoritmo final (congelado en la etiqueta `congelado-test`) recibe solo la foto a color; detecta solo el campo de visión.

```bash
.venv/Scripts/python scripts/segmentar.py foto.jpg mascara.png
.venv/Scripts/python scripts/segmentar.py foto.jpg mascara.png --superpuesta vista.png   # también la foto con los vasos en verde
.venv/Scripts/python scripts/segmentar.py foto.jpg mascara.png --referencia             # método clásico: solo el detector de líneas
```

La máscara se guarda en blanco (vaso) y negro (fondo), del tamaño de la foto. Tarda unos 30 segundos por foto. Desde Python: `src.pipeline.segment_final(rgb)`.

**Qué hace:** reduce la foto a la mitad, toma el canal verde y le corrige el fondo; calcula 26 mapas de realce (verde corregido, sombrero de copa, y detector de líneas, filtro adaptado, Gabor y Frangi con la mayor respuesta entre 5 escalas y en cada escala por separado); los combina con una regresión logística por píxel y marca como vaso la probabilidad mayor que el valor fijo. Los pesos y los umbrales están en `models/pesos_combinacion.json`, ajustados con las 30 imágenes de desarrollo.

**Resultado en el conjunto de prueba** (15 imágenes de 10 personas, corrido una sola vez): coeficiente de Matthews 0,729 contra 0,709 del método clásico, +0,020 (intervalo al 95 %: 0,012 a 0,028). Detalle en `notebooks/99_prueba.ipynb`.

## Ejecución

- `scripts/make_split.py`: genera `data/split.csv` (ya está generado y versionado; no se vuelve a correr).
- `notebooks/`: un cuaderno por etapa, numerado. Las máscaras de desarrollo con validación cruzada, que usan las etapas 6 a 8, las genera `05d_mascaras_desarrollo.ipynb` en `results/cache/` (no versionado); hay que correrlo antes de esas etapas.
- `notebooks/99_prueba.ipynb`: la evaluación en el conjunto de prueba. Se corrió una sola vez sobre `congelado-test` y no se vuelve a correr; es el único lugar donde se pueden abrir las imágenes de prueba.
- `notebooks/05_segmentacion.ipynb` es la primera versión de la etapa 5, hecha en Colab: queda como registro y no se corre localmente (sus celdas reescriben archivos de `src/` y `tests/`).
- Pruebas: `.venv/Scripts/python -m pytest`

## Documentos

- `docs/esquema_v1.md`: plan del trabajo, etapas y criterios.
- `docs/plan_evaluacion.md`: cómo se evalúa y qué se hace con el conjunto de prueba.

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/` | Funciones del algoritmo. `config.py` tiene todos los parámetros; `data.py` lee la base (con el candado que bloquea las imágenes de prueba); `split.py` arma la partición. |
| `scripts/` | Descarga de datos, partición y `segmentar.py` (el algoritmo final para fotos nuevas). |
| `notebooks/` | Un cuaderno por etapa. |
| `tests/` | Pruebas automáticas. |
| `docs/` | Esquema y plan de evaluación. |
| `data/` | `split.csv` (versionado) y `raw/` (no versionado). |
| `results/` | Mapas y salidas intermedias (no versionado). |
| `models/` | Pesos de la regresión y umbrales del algoritmo final. |

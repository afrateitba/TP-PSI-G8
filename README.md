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

## Ejecución

- `scripts/make_split.py`: genera `data/split.csv` (ya está generado y versionado; no se vuelve a correr).
- `notebooks/`: un cuaderno por etapa, numerado.
- Pruebas: `.venv/Scripts/python -m pytest`

## Documentos

- `docs/esquema_v1.md`: plan del trabajo, etapas y criterios.
- `docs/plan_evaluacion.md`: cómo se evalúa y qué se hace con el conjunto de prueba.

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/` | Funciones del algoritmo. `config.py` tiene todos los parámetros; `data.py` lee la base; `split.py` arma la partición. |
| `scripts/` | Descarga de datos y partición. |
| `notebooks/` | Un cuaderno por etapa. |
| `tests/` | Pruebas automáticas. |
| `docs/` | Esquema y plan de evaluación. |
| `data/` | `split.csv` (versionado) y `raw/` (no versionado). |
| `results/` | Mapas y salidas intermedias (no versionado). |

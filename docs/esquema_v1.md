# Esquema general v1 — Trabajo de imágenes PSIB 2026Q2, Grupo 08 (Frate, Tenca, Weizman)
## Segmentación de vasos en fondo de ojo combinando mapas de características de color

> **Estado al 05/11/2026** (prueba corrida una vez sobre `congelado-test`; ver la sección 6). Primera versión del 21/10, escrita después de la devolución del anteproyecto (mail de Tomás del 14/10) y de revisar la base. Lo que está medido dice con qué; lo que es una decisión de criterio, y no de datos, se marca como tal.

---

### 0. Cómo usar este documento

- La sección 6 es el checklist: qué está hecho y qué falta.
- Antes de cambiar cualquier cosa del algoritmo, leer la sección 5. Son los criterios que valen para todas las etapas.
- **Sobre el conjunto de prueba manda `docs/plan_evaluacion.md`.** Si este esquema y el plan dicen cosas distintas, vale el plan.
- Los números de desarrollo son **optimistas**, porque se usaron para elegir. La estimación honesta sale de la validación cruzada por personas y del conjunto de prueba.

---

### 1. Restricciones

| Origen | Restricción |
|---|---|
| Consigna | Temas obligatorios: contexto de las imágenes; mejoramiento; reconstrucción; compresión y descompresión; segmentación; análisis de texturas; visualización, estadística y comparaciones. La interfaz gráfica es opcional. |
| Consigna | La cátedra va a probar el algoritmo con imágenes que no vimos. |
| Consigna | Informe de 8 páginas como máximo (más 4 de anexo); repositorio con instrucciones; historial de aportes incremental y **repartido entre los tres**. Entrega 05/11, defensa 12 o 14/11. |
| Devolución del anteproyecto (14/10) | El centro es la segmentación con distintos mapas de características, aprovechando el color y mejorando los métodos clásicos. La compresión, como objetivo secundario. Hay que definir cómo se compara con las máscaras de los expertos. No clasificar la enfermedad por tortuosidad; a lo sumo, comparar la tortuosidad de la referencia con la del algoritmo. |
| Decisión del grupo (21/10) | **Nada queda como ensayo suelto.** Cada tema entra al algoritmo como candidato, como calibración, como análisis de errores que lleva a una corrección o como validación de sus máscaras. |
| Imágenes nuevas | El algoritmo recibe solo la imagen a color. **Nunca usa el grupo ni la máscara de los expertos**, porque las imágenes de la cátedra no los traen. El grupo y las máscaras sirven solo para evaluar y para elegir. |

---

### 2. Pregunta y objetivos

**Pregunta principal.** Combinar varios mapas de características, aprovechando el color, ¿segmenta los vasos mejor que el método clásico de un solo mapa del canal verde? Se mide contra las máscaras de los expertos.

**Objetivos específicos.**
1. Calibrar el algoritmo con las características de la base: grosor de los vasos, campo de visión, resolución y compresión.
2. Elegir con datos los mapas de color, el mejoramiento y la restauración, los filtros de realce y los mapas de textura.
3. Segmentar y evaluar contra los expertos, incluidos los vasos finos.
4. Ver si el algoritmo funciona igual de bien en ojos enfermos y si conserva las diferencias reales entre grupos.
5. Validar que las máscaras sirven para medir: proporción de vasos, longitud y tortuosidad.
6. Conocer hasta dónde funciona ante más compresión, desenfoque y ruido.

**Fuera del alcance:** diagnóstico, clasificación de gravedad y detección de lesiones.

---

### 3. Datos

High-Resolution Fundus Image Database (Budai et al., 2013), licencia Creative Commons 4.0 con atribución. Se descarga con `scripts/download_data.py`.

**Lo que se encontró al revisar la base (21/10, antes de la partición):**

- **45 imágenes**, 15 por grupo (sano, retinopatía diabética, glaucoma). Todas de 3504 × 2336 píxeles, a color con 8 bits por canal, de la misma cámara (Canon EOS 20D), sacadas entre 2006 y 2009.
- **Máscaras.** Cada imagen tiene la máscara de vasos de los expertos y la del campo de visión, del mismo tamaño que la imagen. El campo de visión ocupa el 84,5 % en todas. Tres máscaras de vasos (11, 12 y 13 de sanos) tienen entre 600 y 1.600 píxeles grises en los bordes: se cuenta como vaso lo que pasa de la mitad de la escala (`MASK_THRESHOLD`). Algunas marcan pocos píxeles de vaso fuera del campo de visión; no importa, porque se evalúa solo adentro.
- **Personas.** La base no dice qué imagen es de quién. Hay pares de fotos sacadas el mismo día con 1 a 5 minutos de diferencia; en cada par el disco óptico está de lados opuestos, o sea que son el ojo derecho y el izquierdo de una persona. Se agrupan las fotos sacadas con 10 minutos o menos de diferencia (`assign_persons`). **Resultado: 28 personas**, ninguna con imágenes de dos grupos. Es una inferencia y se declara como tal.

  | Grupo | Imágenes | Personas con dos ojos | Personas con un ojo | Personas |
  |---|---|---|---|---|
  | Sanos | 15 | 7 | 1 | 8 |
  | Retinopatía diabética | 15 | 3 | 9 | 12 |
  | Glaucoma | 15 | 7 | 1 | 8 |

- **Compresión.** Las originales ya son .jpg, con dos niveles: la media de la tabla de cuantización del brillo vale 2,94 en unas (unos 2 megabytes por imagen) y 11,06 en otras (unos 0,9 megabytes). El nivel está repartido de forma despareja entre grupos, así que **compresión y grupo están mezclados**:

  | Grupo | Menos comprimidas | Más comprimidas |
  |---|---|---|
  | Sanos | 5 | 10 |
  | Retinopatía diabética | 12 | 3 |
  | Glaucoma | 8 | 7 |

- **Proporción de vasos** en el campo de visión según las máscaras de los expertos: alrededor de 11 % en sanos y 8 % en los otros dos grupos.

> **Aviso.** Esta revisión se hizo sobre las 45 imágenes porque hacía falta para armar la partición (personas y compresión). De las máscaras se miró la proporción de vasos de cada imagen y su formato; de las imágenes, el color medio por canal. El detalle está en `docs/plan_evaluacion.md`, desvío 14.1. **Desde la partición, todo lo descriptivo se calcula solo con desarrollo.**

**Desvío respecto del anteproyecto.** El anteproyecto usaba 30 imágenes (sanos y retinopatía) y dejaba afuera el glaucoma. Se usan las 45 para desarrollar y evaluar la segmentación. Motivos: la devolución pone la segmentación en el centro, y con 30 imágenes el conjunto de prueba quedaría en unas 10. La comparación entre grupos sigue siendo sanos contra retinopatía, con el glaucoma como tercer grupo de control.

**Partición** (`data/split.csv`, `src/split.py`). Personas enteras; 5 imágenes de cada grupo en prueba; dentro de cada grupo, la cantidad de imágenes más comprimidas en prueba es el piso o el techo de lo proporcional; sorteo entre todas las particiones válidas con semilla 2026.

| | Desarrollo | Prueba |
|---|---|---|
| Imágenes (sanos / retinopatía / glaucoma) | 10 / 10 / 10 | 5 / 5 / 5 |
| Personas (sanos / retinopatía / glaucoma) | 5 / 8 / 5 | 3 / 4 / 3 |
| Más comprimidas (sanos / retinopatía / glaucoma) | 6 / 2 / 4 | 4 / 1 / 3 |

15_h y 15_g son las únicas imágenes sueltas de su grupo y, con un cupo impar, van a prueba en todas las particiones válidas (desvío 14.1 del plan). La revisión de la partición (21/10) no encontró personas ni ojos repetidos entre conjuntos.

---

### 4. Etapas

Cada etapa termina en una **decisión sobre el algoritmo** (se adopta, se descarta o se fija un parámetro) o en una **medida de su validez**. Las reglas exactas (candidatas, medida, regla de elección y desempate) se escriben al principio de cada cuaderno, antes de correr.

| Etapa | Qué se hace | Qué aporta al algoritmo | Cómo se decide |
|---|---|---|---|
| **0. Partición y plan** | Personas, partición, plan de evaluación | Que la estimación final sea honesta | Criterio |
| **1. Contexto y calibración** | Grosor de los vasos y diámetro del campo de visión, en desarrollo; detección automática del campo de visión | Escalas de los filtros; límites entre vasos finos, medianos y gruesos; funciona con imágenes sin máscara y de otra resolución | Medido en desarrollo |
| **2. Mapas de color** | Rojo, verde, azul, luminosidad y canales de color del espacio Lab, componentes principales de los tres canales | Con qué colores trabaja | Área bajo la curva por imagen |
| **3. Mejoramiento y restauración** | Sin mejora, corrección del fondo, ecualización adaptativa del histograma, filtro homomórfico, Wiener contra el ruido, Wiener contra el desenfoque, suavizado de los bloques de compresión | Qué preprocesamiento se aplica | Área bajo la curva, en todos los vasos y en los finos |
| **4. Realce de vasos y textura** | Frangi, filtro adaptado, Gabor, sombrero de copa, detector de líneas; contraste, homogeneidad y energía de la matriz de coocurrencia en una ventana | Qué mapas entran a la combinación | Área bajo la curva, en todos los vasos y en los finos |
| **5. Segmentación** | Combinación de mapas, regla del umbral, limpieza de manchas sueltas | La máscara final | Coeficiente de Matthews |
| **6. Análisis de errores** | Errores por grosor, por zona, por nivel de compresión y por grupo | Dónde falla y qué corregir | Una sola vuelta de corrección, declarada como desvío |
| **7. Medidas clínicas** | Proporción de vasos, longitud y tortuosidad con la máscara de los expertos y con la del algoritmo | Valida que la máscara sirve para medir; la tortuosidad desempata entre candidatas | Concordancia (Bland–Altman y correlación intraclase) |
| **8. Robustez** | Más compresión, desenfoque y ruido agregados | Hasta dónde funciona; confirma si sirven el Wiener y el suavizado de bloques | Curvas de desempeño contra degradación |
| **9. Congelar y prueba** | Todo, una sola vez, sobre las 15 imágenes de prueba | Estimación final | `docs/plan_evaluacion.md` |
| **10. Interfaz (opcional)** | Cargar una imagen y obtener su máscara y sus medidas | Lo mismo que hará la cátedra | — |

#### 4.1 Detalle de cada etapa

**Etapa 1 — Contexto y calibración.**
- **Grosor de los vasos:** se calcula en las máscaras de los expertos de desarrollo, como el doble de la distancia al borde medida sobre el esqueleto. Se expresa en píxeles y en proporción al diámetro del campo de visión. Los **terciles** fijan los límites entre vasos finos, medianos y gruesos, y no se cambian después.
- **Escalas:** las de los filtros salen de esa distribución y se expresan en proporción al diámetro del campo de visión, para que el algoritmo funcione con imágenes de otra resolución.
- **Campo de visión automático:** umbral sobre el canal rojo más limpieza morfológica, comparado con las máscaras de la base. **Criterio:** se usa en el algoritmo si su coeficiente de Dice con la máscara de la base es de al menos 0,99 en todas las imágenes de desarrollo. La evaluación siempre usa la máscara de la base. *(22/10: esa candidata falló en una imagen; se adoptó `detect_fov_robust`, que además pasa 9 variantes que simulan otras cámaras. Desvío 14.2 del plan.)*
- **Resolución de trabajo:** las candidatas son la original, la mitad y la cuarta parte. No se decide acá: entra como candidata en las etapas 2 a 4, siempre evaluando a la resolución original. Si una resolución reducida es no inferior, se elige la más reducida porque es más rápida.

**Etapa 2 — Mapas de color.** Para cada mapa e imagen, el área bajo la curva de sensibilidad contra falsos positivos dentro del campo de visión. El sentido (vaso más claro o más oscuro) se fija con los datos de desarrollo. Se elige el mejor con la regla de la sección 5.3. Orden de simplicidad: verde, luminosidad, otros canales, componentes principales. Además pasan a la etapa 4 los mapas que, sin ser los mejores solos, aportan información distinta (correlación baja con el elegido); la combinación se decide en la etapa 5.

**Etapa 3 — Mejoramiento y restauración.** Cada candidata se aplica sobre los mapas que vienen de la etapa 2 y se mide el área bajo la curva, en todos los vasos y solo en los finos. El filtro de Wiener (contra el ruido y contra el desenfoque) y el suavizado de bloques son temas obligatorios: se rigen por la sección 5.4.

**Etapa 4 — Realce de vasos y textura.** Los filtros usan las escalas de la etapa 1. Los mapas de textura se calculan con pocos niveles de gris y a la resolución que permita el tiempo de cálculo; esa elección se declara. La textura es un tema obligatorio (sección 5.4) y se juzga dentro de la combinación de la etapa 5.

**Etapa 5 — Segmentación.**
- **Combinación** (candidatas, de la más simple a la más compleja): el mejor mapa solo; promedio con pesos de los mapas normalizados; regresión logística por píxel con los mapas como entradas. Los pesos y la regresión se ajustan con validación cruzada por personas.
- **Umbral:** un valor único para todas las imágenes, o una regla por imagen (Otsu, o un porcentaje fijo de píxeles). El punto se elige con el índice de Youden o con el máximo de Matthews.
- **Limpieza:** se quitan las manchas de menos de cierto tamaño. El tamaño se elige en desarrollo y se acepta solo si la sensibilidad en vasos finos no cae más de 0,02. *(27/10, desvío 14.3 del plan: esa sensibilidad se mide sobre la línea central, `centerline_sensitivity_by_class`, para que no dependa del ancho marcado.)*
- **Medida principal:** Matthews por imagen. **Desempate:** la candidata con mejor concordancia de tortuosidad con los expertos.
- **Agregado el 31/10 (pruebas de mejora, después de ver que el algoritmo detecta el 11 % de los vasos finos):**
  - **Combinación de filtros sobre el verde** (`05b_combinacion_filtros.ipynb`): regresión logística con el verde corregido y las respuestas de los cinco filtros de la etapa 4, a la mitad de resolución, con tres reglas de umbral (Otsu, fracción fija de píxeles y valor fijo elegidos en entrenamiento). Es la candidata de combinación que el esquema preveía y no se había probado con filtros.
  - **Umbral con histéresis** (prueba 1): un umbral alto marca los vasos seguros y uno bajo acepta píxeles más débiles solo si están conectados a un vaso seguro. Los dos umbrales se eligen en entrenamiento, por ejemplo como múltiplos del de Otsu o como fracciones de píxeles. Apunta a los vasos finos.
  - **Limpieza por forma** (prueba 1): se quitan las componentes que no son alargadas (por ejemplo, poca longitud de línea central para su área), en vez de quitarlas por tamaño. Apunta a las lesiones redondas de la retinopatía sin borrar vasos finos. La regla de la limpieza sigue siendo la de arriba: no puede bajar más de 0,02 la sensibilidad de línea central en vasos finos.
  - **Textura sobre el verde en la combinación** (prueba 4, solo si la combinación de filtros mejora a la referencia): contraste, homogeneidad y energía de la matriz de coocurrencia, patrones binarios locales y energías de Laws, calculados sobre el verde corregido, como entradas adicionales de la regresión. Cubre el tema obligatorio de textura con el mapa que se usa de verdad (en la etapa 4 la textura se calculó sobre la tercera componente).
  - Todas se comparan contra la referencia (verde con detector de líneas y Otsu, a la mitad de resolución) con las reglas de la sección 5.3 y validación cruzada por personas.
  - **Ronda única de mejoras** (`05e_ronda_mejoras.ipynb`, después de adoptar la combinación): la combinación de `05b` contra la misma con cada filtro también en cada escala por separado, con la textura del verde, y con las dos cosas. Regla fijada antes de correr: se reemplaza solo si mejora Matthews con un intervalo que no incluye el cero y no empeora los vasos finos; después el algoritmo se cierra (desvío 14.6).

**Etapa 6 — Análisis de errores.** Errores por grosor del vaso; por zona (cerca del disco óptico, ubicado como la zona más brillante, contra el resto); por nivel de compresión; por grupo. La base no marca lesiones, así que los falsos positivos de la retinopatía se revisan a ojo. **Disparador fijado de antemano:** si un subgrupo queda peor que el resto en Matthews y el intervalo de confianza al 95 % de la diferencia no incluye el cero, se prueba **una** corrección dirigida, con las reglas de la etapa que corresponda. Se declara como desvío. *(27/10, desvío 14.3 del plan: la corrección se dispara solo si la diferencia aparece también en el Dice de línea central; si aparece solo en Matthews, se atribuye a la forma de marcar de los expertos y se informa, sin corregir.)*

**Etapa 7 — Medidas clínicas.**
- **Medidas:** proporción de vasos en el campo de visión; longitud total del esqueleto dividida por el diámetro del campo de visión; tortuosidad.
- **Tortuosidad:** se define con las máscaras de los expertos de desarrollo antes de mirar las del algoritmo. Por defecto: longitud del camino dividida por la distancia en línea recta, por tramo entre bifurcaciones, descartando los tramos cortos; el resumen por imagen es la mediana.
- **Validación:**
  1. Concordancia entre la medida de los expertos y la del algoritmo, con Bland–Altman y correlación intraclase.
  2. **Diferencias entre grupos:** la diferencia entre sanos y retinopatía calculada con las máscaras de los expertos se compara con la calculada con las del algoritmo. Si el algoritmo la borra o la agranda, se reporta como un sesgo suyo. Como compresión y grupo están mezclados, la comparación se repite dentro de cada nivel de compresión.
- **Agregado el 31/10 (desvío 14.7 del plan):** con la fracción fija, la proporción de vasos del algoritmo la fija el umbral (8,9 % a 10 % en todas las imágenes). Las medidas se calculan con las dos reglas de umbral (fracción fija y valor fijo), para la combinación y para la referencia, y la concordancia clínica entra en la elección de la regla de la etapa 8.

**Etapa 8 — Robustez.** Sobre las imágenes de desarrollo: compresión .jpg con calidades decrecientes, desenfoque gaussiano y ruido gaussiano en niveles crecientes. Para cada nivel, Matthews del algoritmo con y sin los pasos de restauración. Da el rango en el que el algoritmo funciona y si el Wiener y el suavizado de bloques ayudan cuando la imagen es peor.
- **Agregado el 31/10:**
  - **Curva de compresión** (prueba 2, tema obligatorio): las fotos de desarrollo se comprimen en .jpg con calidades de 90 a 10. Para cada calidad: tamaño del archivo (y cuánto se reduce), relación señal a ruido pico e índice de similitud estructural contra la original, y Matthews y sensibilidad de línea central en vasos finos del algoritmo final. La pregunta es la del anteproyecto: ¿hasta qué calidad se puede comprimir sin que la segmentación sea inferior a la de la foto original (margen −0,03)? Se informa por nivel de compresión de origen, porque las originales ya vienen en dos niveles.
  - **Restauración con degradación controlada** (prueba 3, tema obligatorio de reconstrucción): a las fotos de desarrollo se les agrega desenfoque gaussiano y ruido gaussiano conocidos, y se restauran con el filtro inverso, Wiener y mínimos cuadrados restringidos. Como se conoce la imagen verdadera, se mide la relación señal a ruido pico y la similitud estructural de cada restauración contra la original, y la segmentación de la imagen degradada y de la restaurada. Completa lo de la etapa 3, donde Wiener solo pudo evaluarse sobre las fotos reales, sin saber cuánto desenfoque tenían.
- **Agregado el 3/11** (`notebooks/08_robustez.ipynb`, `src/degrade.py`): la restauración se aplica a la foto antes del algoritmo, porque el algoritmo final no incluye los pasos de la etapa 3. Se hizo: Matthews y Dice del algoritmo con JPEG de calidad 90 a 30, desenfoque y ruido en tres niveles, con y sin restauración; y, sobre la foto, tamaño de archivo, PSNR y SSIM con calidades de 90 a 10 (también por nivel de origen), y filtro inverso, Wiener y mínimos cuadrados restringidos con desenfoque y ruido conocidos. **No se hizo:** Matthews con calidades por debajo de 30 ni la sensibilidad de línea central por nivel. Resultado en el checklist.

---

### 5. Criterios de trabajo (adaptados del trabajo de señales)

**5.1 Cómo se decide**
1. **Solo con desarrollo.** Prueba no se mira ni se describe.
2. **Reglas antes de correr.** Cada cuaderno empieza con la pregunta y las reglas: candidatas, medida, cómo se elige y qué pasa si hay empate.
3. **Si hay que cambiar una regla después de ver los datos,** se declara como desvío en el cuaderno, con su motivo. Si afecta a prueba, se agrega además en `plan_evaluacion.md`, con fecha. Nunca se reescribe lo anterior.
4. **Datos o criterio.** Si algo no se puede decidir con datos, se dice que es una decisión de criterio y por qué.
5. **Sin supuestos heredados.** Lo que viene de la literatura se verifica antes de usarlo; si no se puede, se marca como supuesto.

**5.2 Estadística**
- **La unidad es la persona.** Los dos ojos de una persona no son independientes. La incertidumbre sale de remuestrear personas enteras: 2.000 remuestreos en desarrollo y 10.000 en prueba.
- **Medidas por imagen,** resumidas con la media de las imágenes.
- **Comparar candidatas:** diferencia apareada imagen por imagen, con su intervalo de confianza al 95 % por remuestreo de personas.
- **Siempre el tamaño del efecto con su intervalo.** "Sin diferencia" no quiere decir "iguales".

**5.3 Elegir entre candidatas**
1. Grupo: las candidatas no inferiores a la mejor en la medida de la etapa (límite inferior del intervalo de confianza al 95 % de la diferencia ≥ −0,02 en el área bajo la curva y ≥ −0,03 en Matthews y en el Dice de línea central; desvío 14.4 del plan, `notebooks/05a_margen_matthews.ipynb`).
2. Dentro del grupo, la más simple según un orden fijado antes de correr.
3. Control: validación cruzada por personas (5 grupos de personas, repartiendo los tres grupos clínicos). Se reporta el optimismo (medida al elegir menos medida afuera) y si la elección es estable entre grupos.

**5.4 Temas obligatorios** (restauración, compresión y textura)
- Se compara el algoritmo con el paso nuevo contra el algoritmo sin él, **sobre las mismas imágenes** y con los mismos remuestreos.
- **Se adopta si es no inferior** en el área bajo la curva y, cuando ya hay máscara, también en Matthews.
- Si empeora, se reporta y no se adopta. Aun así figura en el informe como probado dentro del algoritmo.

**5.5 Código**
- Funciones en `src/` con docstring en castellano. Los parámetros van en `src/config.py`, no escritos en el código.
- Cada función nueva lleva su prueba en `tests/`: si se puede, con una imagen sintética de resultado conocido; con datos reales, con `skipif` si faltan los archivos. **`pytest` tiene que pasar antes de cada commit.**
- Semilla 2026 en todo lo aleatorio.
- **Candado de prueba.** Para recorrer imágenes se usa `dev_ids()`. `load_image`, `load_vessels` y `load_fov` dan error con una imagen de prueba. La única entrada a prueba es `load_test_case`, que solo puede aparecer en `notebooks/99_prueba.ipynb`; `tests/test_lock.py` falla si aparece en otro lado.
- Las imágenes son grandes (8 millones de píxeles). Los mapas intermedios se guardan en `results/`, que no se versiona.

**5.6 Cuadernos**
- Un cuaderno por etapa, numerado, con esta estructura:
  1. qué hace y las reglas fijadas;
  2. resultados;
  3. **decisión**, escrita después de correr, con los números.

**5.7 Aportes al repositorio**
- La consigna evalúa la distribución de los aportes. Cada integrante sube las etapas que trabaja, con mensajes claros.

---

### 6. Checklist

- [x] **0. Partición y plan** (21/10, Augusto): descarga, lectura de la base, personas, partición, plan de evaluación y candado de prueba.
- [x] **1. Contexto y calibración** (22/10, `notebooks/01_contexto.ipynb` y `01b_campo_de_vision.ipynb`): límites de grosor 3,47 y 9 píxeles; diámetro del campo de visión 3.262 píxeles; detección del campo de visión con `detect_fov_robust` (desvío 14.2 del plan: la candidata original falló en una imagen; la robusta pasa las 30 y 9 variantes de otras cámaras); las máscaras de sanos están marcadas más anchas que las de los otros grupos, y es la forma de marcar y no la retina: el ancho visible en la foto es igual en los tres grupos (`01c_ancho_visible.ipynb`).
- [x] **2. Mapas de color**. Karolina, 25/10 (`notebooks/02_mapas_color.ipynb`, reglas escritas después de correr): de diez mapas, la tercera componente principal del color por imagen, con vasos claros, separa mejor (área media 0,81) que el verde (0,69); el verde queda como referencia clásica. 26/10 (`02b_signo_componentes.ipynb`): el signo de las componentes se fija por la oscuridad local del verde. 26/10 (`02c_cierre_mapas.ipynb`): la tercera componente gana en las 5 vueltas de la validación cruzada por personas (0,81 afuera, +0,12 sobre el verde); a la mitad o a la cuarta parte de la resolución no pierde (se cierra en la etapa 4); combinar mapas suma (los diez juntos 0,87) y pasan a las etapas 4 y 5 la segunda componente, el verde, el azul y la escala de grises. Funciones en `src/color.py`, `src/stats.py` y `src/split.py`. **27/10, desvío: la elección cambió después de la etapa 3** (`02d_mapas_corregidos.ipynb`): con el fondo corregido el verde es el mejor mapa (0,942) en las 5 vueltas y ningún otro le suma más de 0,0014 al combinarlo; la ventaja de la tercera componente venía de comparar mapas crudos, donde el verde pierde por la iluminación despareja. Mapa principal: verde; sin complementarios de color. El mapa y el preprocesamiento se deciden juntos.
- [x] **3. Mejoramiento y restauración.** Karolina (`03_mejoramiento.ipynb`, 27–30/10): corrección del fondo, ecualización adaptativa, homomórfico y Wiener contra el ruido sobre la tercera componente y el verde; el verde con el fondo corregido es el mejor (0,935; finos 0,813). Augusto (`03b_restauracion.ipynb`, `src/restoration.py`): misma conclusión con más candidatas (0,942); Wiener contra el desenfoque empeora (−0,035) y no se adopta; Wiener contra el ruido y el suavizado de bloques no empeoran el área bajo la curva. **Verificación del 31/10:** agregados al algoritmo final a 1/4 de resolución, Wiener (ventana de 5 píxeles, que a esa resolución equivale a 20) y el suavizado de bloques **empeoran** Matthews en 0,054 (intervalo −0,060 a −0,048) y bajan los vasos finos de 11 % a 4 %: así no se adoptan. *Falta:* probarlos con la ventana ajustada a la resolución de trabajo antes de descartarlos.  *(3/11: probados en la etapa 8 con la ventana ajustada, aplicados a la foto: no empeoran; el suavizado de bloques mejora +0,0001 y no se adopta por criterio.)*
- [x] **4. Realce de vasos y textura.** Leah (`src/enhance.py`, filtros y textura con pruebas; prueba con 2 imágenes) y Karolina (`04_realce.ipynb`, corrida con las 30): con el fondo corregido, el **detector de líneas** es el mejor filtro para el verde (0,957; finos 0,878) y Gabor para la tercera componente (0,882), elegidos en las 5 vueltas. Textura (contraste, homogeneidad y energía de la matriz de coocurrencia) calculada sobre la tercera componente. Resolución elegida: 1/4. **Observación del 31/10:** la resolución se eligió con la tercera componente; con el verde, que es el mapa final, la mitad es mejor (ver etapa 5).
- [x] **5. Segmentación.** Karolina (`05_segmentacion.ipynb`, `src/preprocess.py`, `src/segment.py`): verde → corrección del fondo (gaussiana, σ = 0,02 del diámetro) → detector de líneas a 1/4 → Otsu, sin limpieza: Matthews 0,677 (se reproduce exacto); las combinaciones de color y la textura no la superan. 31/10 (`05b_combinacion_filtros.ipynb`): a la mitad de resolución, **combinar los filtros sobre el verde** con una regresión logística y marcar el 9 % del campo da **Matthews 0,719**, Dice de línea central 0,710 y **vasos finos 26 %** (contra 12 % con Otsu); le gana al detector solo con la misma regla (+0,017, intervalo +0,014 a +0,020) en las 30 imágenes y las 18 personas. **Se adopta por criterio (desvío 14.5 del plan)**; la referencia clásica es el detector de líneas con la misma regla. La prueba 1 (`05c`) no cambió la regla: se mantiene la fracción fija. 31/10 (`05e_ronda_mejoras.ipynb`), **ronda única de mejoras**: agregar cada filtro en cada una de sus escalas por separado (26 mapas) sube Matthews a 0,726 (+0,006, intervalo +0,004 a +0,008), el Dice de línea central a 0,733 y los **vasos finos a 34 %**, con las medidas de línea central mejores en las 30 imágenes; la textura sobre el verde no suma. **Se adopta por la regla fijada antes de correr (desvío 14.6) y el algoritmo queda cerrado.** La función única está en `src/pipeline.py`, con el script `scripts/segmentar.py`, y las máscaras de desarrollo con validación cruzada en `results/cache/mascaras_cv/` (`05d_mascaras_desarrollo.ipynb`). 31/10 (`05f_vasos_finos.ipynb`), **ronda para los vasos finos** (desvío 14.8): entrenar la regresión con un tercio de píxeles de vaso de cada grosor sube los **vasos finos de 34 % a 40 %** (+0,067, intervalo +0,060 a +0,075) con Matthews igual (0,7255); **se adopta**. La resolución completa no ayudó: sola baja los finos a 29 %. El algoritmo queda cerrado. 4/11: la regla de umbral se cerró en la etapa 8 (valor fijo, desvío 14.7). El cuaderno 05 queda como la línea de base inicial (verde, detector de líneas y Otsu: Matthews 0,677); el algoritmo final está en 05b–05f y sus máscaras en `05d`.
- [x] **6. Análisis de errores** (Karolina, `06_analisis_errores.ipynb`; actualizado a la regla final por Leah, 4/11). Con la combinación y el valor fijo (máscaras de `05d`): sensibilidad de línea central **35,7 % en vasos finos**, 83,0 % en medianos y 92,6 % en gruesos (**la limitación principal**; con la fracción fija los finos daban 40,4 %). La retinopatía es peor que el resto en Matthews (−0,076, intervalo −0,108 a −0,048) **y** en Dice de línea central (−0,093, −0,137 a −0,051), lo que dispara la corrección dirigida; **no se aplica (desvío 14.10 del plan)** y se informa como limitación. Sin diferencias por compresión (la aparente viene de la mezcla con el grupo). Sin diferencia clara cerca del disco óptico (Matthews 0,710 contra 0,731, Dice 0,762 contra 0,750).
- [ ] **2e. Color no lineal** (opcional, Augusto): `02e_color_no_lineal.ipynb` y `nonlinear_maps` armados; el cuaderno no se corrió.
- [ ] **Pruebas de mejora agregadas el 31/10**, en este orden de prioridad (detalle en la sección 4.1, etapas 5 y 8):
  1. [x] Umbral con histéresis y limpieza por forma (etapa 5; `05c_histeresis_forma.ipynb`, 31/10): frente a Otsu, la histéresis y la fracción fija casi duplican los vasos finos (12 % → 22–23 %); frente a la fracción fija, la histéresis suma apenas +0,012 en finos (límite inferior +0,0003) con Matthews igual, y la limpieza por forma baja los finos. **Ninguna se adopta**: se mantiene la fracción fija (decisión de criterio por simplicidad).
  2. [x] Curva de compresión .jpg (etapa 8; `08_robustez.ipynb`, 03/11): el algoritmo funciona hasta calidad 50 (Matthews con 90, 70, 50 y 30); la foto a calidad 50 pesa 7,6 veces menos que la original (0,21 MB) con PSNR de 43 dB y SSIM de 0,97; por debajo de 50 casi no se achica y la calidad cae. El suavizado de bloques mejora el algoritmo entre 0,0001 y 0,0016. Por nivel de compresión de origen: terminan en el mismo tamaño. *No se midió la sensibilidad de línea central por nivel.*
  3. [x] Restauración con degradación controlada (etapa 8; `08_robustez.ipynb`, 03/11): filtro inverso, Wiener y mínimos cuadrados restringidos con desenfoque conocido, con y sin ruido. Sin ruido los tres mejoran la imagen; con ruido solo mínimos cuadrados mejora siempre (+3 a +6 dB) y el inverso amplifica el ruido. Dentro del algoritmo, la restauración no cambia la segmentación del desenfoque.
  4. [x] Textura sobre el verde dentro de la combinación (etapa 5; `05e_ronda_mejoras.ipynb`, 31/10): contraste, homogeneidad y energía de la matriz de coocurrencia del verde corregido bajan Matthews (−0,002, intervalo −0,003 a −0,0003): **no se adopta**. En la misma ronda, cada filtro en cada escala por separado sí mejora y se adopta (desvío 14.6). Los patrones binarios locales y las energías de Laws no se probaron, por tiempo.
  5. [ ] Interfaz gráfica (etapa 10), si sobra tiempo.
- [x] **7. Medidas clínicas** (Augusto, 31/10; `src/clinical.py`, `07a_medidas_expertos.ipynb`, `07b_medidas_algoritmo.ipynb`). Parámetros de la tortuosidad fijados solo con los expertos (poda de 5 píxeles, largo mínimo de 25). Con los expertos, la tortuosidad no separa los grupos y la mayor proporción de vasos de los sanos viene del ancho marcado (la longitud no cambia). Con las máscaras de desarrollo, la **concordancia con los expertos es baja**: correlación intraclase media −0,02 con fracción fija y 0,21 con valor fijo (+0,23, intervalo +0,08 a +0,37; **el valor fijo gana el punto 2 del desvío 14.7**). Con el entrenamiento equilibrado de `05f`, el algoritmo mide de 9 % a 15 % menos longitud que los expertos (antes, de 17 % a 22 %) por los vasos finos que todavía pierde, y borra la diferencia de proporción entre sanos y retinopatía de los expertos (que viene de la forma de marcar). La combinación con valor fijo da Matthews 0,730 (`05d`). En prueba (etapa 9): correlación intraclase media 0,15 (−0,05 a 0,29); la diferencia de proporción entre sanos y retinopatía de los expertos desaparece con el algoritmo, como en desarrollo.
- [x] **8. Robustez.** Karolina (`08_robustez.ipynb`: estructura del cuaderno y recompresión JPEG sin restauración) y Leah (03/11; `src/degrade.py` con pruebas, reconstrucción de los pesos por vuelta, desenfoque, ruido, restauración, calidad de la foto, análisis, decisión y `segment_final`): con el algoritmo final y los pesos de la validación cruzada, funciona hasta JPEG calidad 50, desenfoque σ = 4 px (todo lo probado) y ruido σ = 5 niveles; con σ = 20 Matthews cae a 0,41. El Wiener contra el ruido ayuda mucho con ruido fuerte (+0,24 con σ = 20); el suavizado de bloques mejora apenas (+0,0001 en la base) y el Wiener contra el desenfoque no cambia nada. **Regla del umbral: valor fijo** (desvío 14.7: en robustez ninguna pierde; gana por concordancia clínica, 0,21 contra −0,02); valores con todo desarrollo en `models/pesos_combinacion.json` (0,857 la combinación, 0,945 la referencia), aplicados por `src/pipeline.segment_final` y `scripts/segmentar.py`. No se agrega restauración al algoritmo final (desvío 14.9 del plan). Sobre la foto: calidad 50 achica el archivo 7,6 veces con PSNR de 43 dB; con desenfoque y ruido conocidos, mínimos cuadrados restringidos es el único método que mejora la imagen en todas las condiciones (pruebas 2 y 3). Los pesos por vuelta (`08_ajustes_cv.joblib`) se reconstruyeron con `src/pipeline.py`; la corrida JPEG coincide exactamente con la original. En prueba, la robustez se confirma (tolera JPEG hasta calidad 30 y desenfoque; falla con ruido de desvío 10 o más; el Wiener local lo recupera).
- [x] **9. Congelar y prueba** (Leah, 4 y 5/11; `99_prueba.ipynb`, corrido una vez sobre `congelado-test`, commit 46f46eb). **Se confirma la pregunta principal:** Matthews 0,729 contra 0,709 de la referencia clásica, +0,020 (0,012 a 0,028; p < 0,001), a favor en las 15 imágenes y las 10 personas; coincide con desarrollo (0,730 contra 0,704). La mejora está en los vasos finos (41 % contra 26 %). Retinopatía es el grupo más difícil (−0,160 contra sanos). Literatura: sensibilidad, especificidad y exactitud 75,90 %, 97,55 % y 95,57 % (Budai et al., 2013: 70,99 %, 97,45 % y 94,81 %; Odstrcilik et al., 2013: 81,65 %, 96,09 % y 94,48 %).
- [ ] **10. Interfaz** (opcional): cargar una foto y ver la máscara superpuesta y las medidas; es la prueba 5 de la lista de arriba.
- [ ] Informe y presentación

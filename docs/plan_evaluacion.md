# Plan de evaluación

Este documento fija **antes de calcular cualquier resultado** cómo se compara el algoritmo con las máscaras de los expertos, cómo se elige en desarrollo y qué se hace con el conjunto de prueba. Se commitea junto con la partición, para que el historial muestre que el plan es previo a los resultados. Cualquier cambio posterior se agrega al final como desvío, con su fecha y su motivo, y nunca reemplaza lo que dice este texto.

## 1. Conjuntos

- **Desarrollo:** las 30 imágenes con `set == "dev"` en `data/split.csv` (10 por grupo, 18 personas). Con ellas se elige y se ajusta todo.
- **Prueba:** las 15 imágenes con `set == "test"` (5 por grupo, 10 personas). Ninguna persona está en los dos conjuntos.
- Hasta la evaluación final no se calcula nada sobre las imágenes de prueba: ni mapas, ni medidas, ni estadísticas de sus máscaras.
- **Lo que ya se vio antes de la partición** (21/10, sobre las 45 imágenes): formato, tamaño, fecha de toma, nivel de compresión, lado del disco óptico y la proporción de vasos por grupo en las máscaras de los expertos. Hacía falta para armar la partición. Ninguna decisión del algoritmo se toma con esos números.

## 2. Qué recibe y qué entrega el algoritmo

- **Recibe:** solo la imagen a color. No recibe el grupo ni la máscara de los expertos. Si la detección automática del campo de visión pasa su criterio (esquema, etapa 1), tampoco recibe la máscara del campo de visión.
- **Entrega:** un mapa continuo (cuánto se parece cada píxel a un vaso) y una máscara binaria de vasos, del mismo tamaño que la imagen original.

## 3. Referencia y región de evaluación

- **Referencia:** la máscara de vasos de los expertos (`manual1/`), con vaso = valor mayor que 127.
- **Región:** solo los píxeles dentro del campo de visión de la base (`mask/`), aunque el algoritmo use su propio campo de visión. Lo que queda afuera no cuenta.
- **Resolución:** siempre la original (3504 × 2336). Si el algoritmo trabaja con la imagen reducida, su resultado se lleva a la resolución original antes de comparar. Así el costo de reducir queda incluido en la medida.

## 4. Medidas por imagen

En lo que sigue, "vaso" y "fondo" son según los expertos, y "marcado" según el algoritmo.

**Sobre el mapa continuo** (para elegir mapas y pasos, etapas 2 a 4):

| Medida | Qué mide |
|---|---|
| Área bajo la curva de sensibilidad contra falsos positivos | Probabilidad de que un píxel de vaso al azar tenga un valor más alto que un píxel de fondo al azar. 0,5 es azar y 1 es perfecto. |
| La misma área, solo con vasos finos | Lo mismo, usando como vasos solo los finos (sección 5) contra todo el fondo. |

**Sobre la máscara binaria** (desde la etapa 5):

| Medida | Qué mide |
|---|---|
| **Coeficiente de correlación de Matthews (principal)** | Correlación entre la máscara y la referencia. Va de −1 a 1. Tiene en cuenta los cuatro casos (vaso marcado, vaso no marcado, fondo marcado, fondo no marcado), así que no se infla porque haya mucho fondo. |
| Coeficiente de Dice | Superposición: el doble de los píxeles marcados que son vaso, dividido por la suma de marcados y vasos. |
| Sensibilidad | Fracción de los vasos que se marcan. |
| Especificidad | Fracción del fondo que no se marca. |
| Exactitud | Fracción de píxeles bien clasificados. Se reporta solo para comparar con la literatura, porque con ~90 % de fondo engaña. |
| Sensibilidad por grosor | Sensibilidad en vasos finos, medianos y gruesos por separado. |

**Medidas clínicas** (etapa 7), calculadas igual sobre la máscara de los expertos y sobre la del algoritmo: proporción de vasos en el campo de visión, longitud del esqueleto dividida por el diámetro del campo de visión y tortuosidad (definida en la etapa 7 solo con las máscaras de los expertos de desarrollo, antes de mirar las del algoritmo).

## 5. Grosor de los vasos

- **Ancho de cada vaso:** en la máscara de los expertos se calcula el esqueleto (la línea central de cada vaso). En cada punto del esqueleto, el ancho es el doble de la distancia al borde del vaso. Cada píxel de vaso toma el ancho del punto del esqueleto más cercano.
- **Clases:** los límites entre finos, medianos y gruesos son los terciles del ancho en las máscaras de desarrollo. Se fijan en la etapa 1, antes de evaluar cualquier método, y no se cambian.

## 6. Resumen y estadística

- Cada medida se calcula por imagen y se resume con la **media de las imágenes**.
- **Unidad de remuestreo: la persona.** Para el intervalo de confianza se remuestrean personas enteras con reposición (con sus una o dos imágenes) y se recalcula la media. 2.000 remuestreos en desarrollo y 10.000 en prueba, con semilla 2026. Intervalo al 95 % por percentiles.
- **Diferencias entre candidatas:** se calculan imagen por imagen sobre las mismas imágenes y con los mismos remuestreos.
- **No inferioridad:** una candidata es no inferior a otra si el límite inferior del intervalo al 95 % de la diferencia es mayor o igual que −0,02.
- **Valor p de una diferencia:** el doble de la menor de estas dos fracciones: la de remuestreos con diferencia ≤ 0 y la de remuestreos con diferencia ≥ 0.
- **Diferencias entre grupos** (no apareadas): el remuestreo se hace por persona dentro de cada grupo.

## 7. Estimación honesta en desarrollo

Las partes que se ajustan (pesos de la combinación, umbral y tamaño de la limpieza) se evalúan con **validación cruzada por personas**: 5 grupos de personas que reparten los tres grupos clínicos. Se ajusta con 4 y se mide en el que queda afuera. Si el tiempo de cálculo lo permite, también se repite adentro la elección de mapas y pasos (validación cruzada anidada); si no, se declara. Esa es la estimación de desarrollo que se reporta. Los números de desarrollo completo se presentan como optimistas.

## 8. Condiciones para abrir prueba

Prueba se abre **una sola vez**, cuando se cumplan todas estas condiciones:

1. Están cerradas en desarrollo las etapas 1 a 8 del esquema, cada una con su decisión escrita en su cuaderno.
2. Están fijados los parámetros de la sección 9.
3. Está hecha la estimación de la sección 7.
4. Todo está commiteado y la versión se marca con la etiqueta `congelado-test`. La evaluación se corre sobre esa versión.

## 9. Qué se congela

Se completa al cerrar la etapa 8. El valor definitivo es el del commit `congelado-test`.

| Componente | Valor |
|---|---|
| Campo de visión | automático: `detect_fov_robust` (etapa 1, desvío 14.2) |
| Resolución de trabajo | mitad (`SEGMENT_FACTOR = 2`; etapa 5) |
| Mapas de color | verde (etapa 2d) |
| Mejoramiento y restauración | corrección del fondo con una gaussiana de σ = 0,02 del diámetro; sin restauración (etapas 3 y 8, desvío 14.9) |
| Realce y textura | 26 mapas: verde corregido, sombrero de copa, y detector de líneas, filtro adaptado, Gabor y Frangi con la mayor respuesta entre escalas y en cada una de las 5 escalas; sin textura (etapas 4 y 5, desvío 14.6) |
| Combinación, umbral y limpieza | regresión logística con entrenamiento equilibrado por grosor (desvío 14.8); umbral de valor fijo sobre la probabilidad, 0,857 (referencia: 0,945), elegido con todo desarrollo (desvío 14.7, etapa 8); sin limpieza. Pesos y umbrales en `models/pesos_combinacion.json`; se aplica con `src/pipeline.segment_final` |
| Corrección de la etapa 6, si la hubo | ninguna (desvío 14.3: la diferencia de la retinopatía no aparece en el Dice de línea central) |

## 10. Pregunta principal en prueba

**El algoritmo final segmenta mejor que el método clásico de un solo mapa.**

- **Método clásico de referencia:** el canal verde con el mejor filtro de realce de la etapa 4, con la misma regla de umbral y la misma limpieza que el algoritmo final. Así la comparación aísla lo que aportan el color y la combinación de mapas, que es lo que preguntó la devolución.
- **Medida:** coeficiente de Matthews por imagen, media de las 15 imágenes.
- **Procedimiento:** diferencia = algoritmo final − referencia, sobre las mismas imágenes; 10.000 remuestreos de las 10 personas; intervalo al 95 % y valor p (sección 6).
- **Regla de decisión:**
  - **Se confirma** si p < 0,05 y la diferencia favorece al algoritmo final.
  - **Se rechaza** si p < 0,05 y la diferencia favorece a la referencia.
  - En otro caso, **no se muestra diferencia** con estos datos.
- **Si la etapa 5 elige el canal verde solo** (es decir, la combinación no se adoptó), el algoritmo final y la referencia coinciden. La pregunta queda respondida en desarrollo ("la combinación no mejoró") y en prueba se reporta solo el desempeño.
- **Potencia:** con 10 personas la prueba tiene poca potencia. Un resultado "sin diferencia" no se interpreta como "son iguales": se reportan el tamaño de la diferencia y su intervalo.

## 11. Resultados secundarios (descriptivos, sin pruebas de hipótesis)

1. Todas las medidas de la sección 4, para el algoritmo final, la referencia clásica y el umbral simple sobre el canal verde (la estrategia de referencia del anteproyecto).
2. **Por grupo:** Matthews de sanos, retinopatía diabética y glaucoma, y la diferencia entre retinopatía y sanos con su intervalo.
3. **Por nivel de compresión:** Matthews de las imágenes más y menos comprimidas.
4. **Medidas clínicas:** concordancia entre los expertos y el algoritmo (Bland–Altman y correlación intraclase), y la diferencia entre sanos y retinopatía calculada con cada máscara, también dentro de cada nivel de compresión.
5. **Robustez:** las curvas de la etapa 8, repetidas sobre prueba.
6. **Literatura:** como referencia y no como meta, se citan la sensibilidad, la especificidad y la exactitud que reportan en esta base Budai et al. (2013) y Odstrcilik et al. (2013).

## 12. Qué se reporta y qué no se hace

- Se reportan **todos** los resultados de las secciones 10 y 11, sean favorables o no.
- Después de abrir prueba no se cambia nada del algoritmo ni de las medidas para mejorar un resultado.
- **Si aparece un error de código** después de abrir prueba: se corrige, se declara en la sección 14 y se reportan **las dos** corridas, la original y la corregida.

## 13. Cómo se corre

Un solo cuaderno, `notebooks/99_prueba.ipynb`, ejecutado una vez sobre el commit `congelado-test`, calcula todo lo de las secciones 10 y 11. Se commitea con sus salidas tal como quedan.

## 14. Desvíos posteriores a este plan

### 14.1 (21/10/2026, antes de calcular resultados) Lo que ya se vio de prueba y dos imágenes que no se sortearon

**Qué se vio de las imágenes de prueba.** La sección 1 dice que antes de la partición se miró "la proporción de vasos por grupo". Es incompleto. En la revisión del 21/10, antes de la partición, se calcularon e imprimieron para las 45 imágenes:
- con las máscaras de los expertos: la proporción de vasos dentro del campo de visión **imagen por imagen**, la cantidad de píxeles de vaso fuera del campo de visión y los valores presentes en cada máscara (así aparecieron las tres con píxeles grises);
- con las imágenes: el valor medio del rojo, del verde y del azul dentro del campo de visión, y la fracción de píxeles con el rojo saturado.

Después de la partición, como control de integridad, se calcularon mapas de vasos de las 45 imágenes, prueba incluida (sombrero de copa negro del canal verde, a un octavo de la resolución). El objetivo era buscar un mismo ojo fotografiado en dos fechas y asignado a dos personas. No se usaron las máscaras. Ningún par de personas distintas se parece más de lo esperable por azar: la correlación máxima fue 0,28, contra 0,72 a 0,77 de un control con la misma foto alterada.

Ninguna decisión del algoritmo se tomó ni se va a tomar con esos números, y no se guardaron en el repositorio.

**15_h y 15_g no se sortearon.** En sanos y en glaucoma hay una sola persona con un solo ojo: 15_h y 15_g. Con un cupo de 5 imágenes por grupo, que es impar, esa imagen tiene que estar en prueba en todas las particiones válidas, así que fue a prueba con probabilidad 1. No es una filtración, porque no se eligieron por ninguna característica de la imagen ni de su máscara. Las demás imágenes de esos dos grupos sí se sortearon, entre 12 particiones válidas en cada uno. Se mantiene la partición: rehacerla después de commiteada resta más credibilidad de lo que este detalle cambia.

### 14.2 (22/10/2026, antes de calcular resultados) Detección robusta del campo de visión

En la etapa 1 (`notebooks/01_contexto.ipynb`) ninguna candidata de detección automática cumplió la regla (Dice ≥ 0,99 en las 30 imágenes de desarrollo): con 14_h, de periferia oscura, el umbral de Otsu sobre el rojo quedó en 0,954. Con ese resultado a la vista se agregó una tercera candidata, `detect_fov_robust` (umbral de Otsu sobre el logaritmo del brillo, con controles para imágenes sin borde negro), y un criterio extra de robustez: Dice ≥ 0,99 en 9 variantes que simulan otras cámaras (exposición, viñeteo, resolución, escala de grises, fondo gris, etiqueta, compresión y recorte sin borde).

Resultado (`notebooks/01b_campo_de_vision.ipynb`): peor Dice 0,9993 en las 30 imágenes y 0,9964 en el peor caso de las variantes. Se adopta. Efecto sobre prueba: tal como prevé la sección 2, el algoritmo **no recibe la máscara del campo de visión** y la detecta solo. La evaluación sigue usando la máscara de la base (sección 3). No se calculó nada sobre las imágenes de prueba.

### 14.3 (27/10/2026, antes de tener máscaras del algoritmo) Medidas de línea central

**Motivo.** En `notebooks/01c_ancho_visible.ipynb` (desarrollo) el ancho visible de los vasos es igual en los tres grupos, pero los expertos marcaron los de sanos relativamente más anchos (cociente marcado / visible 0,80 contra 0,52 en retinopatía; diferencia 0,28, intervalo 0,20 a 0,37). Las medidas por píxel de la sección 4 tratan distinto a cada grupo por la forma de marcar.

**Qué se agrega** (`src/metrics.py`), calculado igual que el resto, por imagen y dentro del campo de visión de la base:
- **sensibilidad de línea central:** fracción de la línea central de los expertos que cae dentro de la máscara del algoritmo;
- **precisión de línea central:** fracción de la línea central del algoritmo que cae dentro de la máscara de los expertos;
- **Dice de línea central:** 2 · precisión · sensibilidad / (precisión + sensibilidad) (Shit et al., 2021);
- **sensibilidad de línea central por grosor:** la anterior para vasos finos, medianos y gruesos, con la clase de cada punto según su ancho marcado y los límites de la sección 5.

**Dónde se usa.**
1. Sección 4 y resultados secundarios (sección 11, puntos 1 a 3): las cuatro medidas se informan junto a las de píxeles, para el algoritmo final y la referencia clásica, por grupo y por grosor.
2. Etapa 5: la regla que limita la limpieza ("la sensibilidad en vasos finos no cae más de 0,02") se mide sobre la línea central.
3. Etapa 6: la vuelta de corrección por un subgrupo se dispara solo si la diferencia aparece también en el Dice de línea central.

**Qué no cambia.** La medida principal sigue siendo Matthews y la pregunta principal (sección 10) no cambia: compara dos métodos sobre las mismas imágenes, así que la forma de marcar pesa igual en los dos. Las medidas de línea central no se usan para elegir mapas ni pasos en las etapas 2 a 4.

### 14.4 (27/10/2026, antes de tener máscaras del algoritmo) Margen de no inferioridad para Matthews

**Motivo.** En `notebooks/05a_margen_matthews.ipynb` (desarrollo, segmentación tosca que no es candidata) el intervalo al 95 % de la diferencia de Matthews entre candidatas cercanas tiene un semiancho de 0,0002 a 0,004, pero entre métodos distintos es de 0,025 (0,033 en el análisis de la partición del 21/10). Con un margen de −0,02, un método distinto e igual de bueno nunca podría declararse no inferior, y la regla de elegir la candidata más simple entre las no inferiores no funcionaría cuando se comparan métodos distintos.

**Cambio.** Para Matthews y para el Dice de línea central, el margen pasa a **−0,03**. Para el área bajo la curva sigue en −0,02 (sus intervalos son de ± 0,006 a 0,008). Afecta las elecciones en desarrollo (esquema, secciones 5.3 y 5.4); no cambia la pregunta principal en prueba (sección 10), que no usa margen.

### 14.5 (31/10/2026, antes de abrir prueba) Algoritmo final adoptado por criterio: combinación de filtros

**Qué pasó.** En la etapa 5 (`notebooks/05b_combinacion_filtros.ipynb`, desarrollo, validación cruzada por personas) la combinación de los filtros de la etapa 4 sobre el verde, con una regresión logística por píxel y un umbral que marca el 9 % del campo, supera al detector de líneas solo con la misma regla: Matthews +0,017 (intervalo 0,014 a 0,020), en las 30 imágenes y las 18 personas. Como la ventaja es menor que el margen de 0,03 (desvío 14.4), la regla de "la más simple entre las no inferiores" (esquema 5.3) habría elegido el detector solo.

**Decisión.** Se adopta la combinación como algoritmo final, como decisión de criterio tomada después de ver los resultados. Motivos: la ventaja es firme en todas las medidas, grupos y niveles de compresión; y con el detector solo como algoritmo final, el algoritmo y la referencia de la sección 10 coincidirían y la pregunta principal no se podría responder.

**Efecto sobre prueba.**
- La pregunta principal (sección 10) queda como estaba escrita: algoritmo final (combinación) contra el método clásico de referencia (el detector de líneas sobre el verde, con la misma regla de umbral y la misma limpieza).
- La regla de umbral (fracción fija o valor fijo sobre la probabilidad, que dieron lo mismo en desarrollo) se elige en la etapa 8 según cuál aguanta mejor las imágenes que simulan otras cámaras, y se congela antes de abrir prueba. La fracción fija supone que los vasos ocupan alrededor del 9 % del campo; ese supuesto se informa como limitación.
- Los valores de desarrollo son optimistas, porque el mapa, la corrección del fondo, los filtros y la resolución se eligieron con las mismas imágenes; se informan como tales.

### 14.6 (31/10/2026, antes de abrir prueba) Ronda única de mejoras: cada filtro también en cada escala por separado

**Qué pasó.** Después de adoptar la combinación (14.5) se hizo una sola ronda de mejoras (`notebooks/05e_ronda_mejoras.ipynb`, desarrollo, misma validación cruzada por personas y misma regla de fracción que `05b`). Candidatas:
- A: la combinación de 14.5 (6 mapas);
- B: A más el detector de líneas, el filtro adaptado, Gabor y Frangi en cada una de sus 5 escalas por separado (26);
- C: A más contraste, homogeneidad y energía de la matriz de coocurrencia del verde corregido (9). Es la prueba 4 del esquema, sin patrones binarios locales ni energías de Laws, por tiempo;
- D: todo (29).

La regla de adopción se fijó antes de correr: una candidata reemplaza a A solo si mejora Matthews con un intervalo al 95 % que no incluye el cero y no empeora los vasos finos; si cumplen varias, gana la de menos mapas entre las no inferiores a la mejor (margen 0,03); después de la ronda el algoritmo se cierra.

**Resultado.**
- B: Matthews +0,0061 (0,0042 a 0,0080), Dice de línea central +0,022 y vasos finos +0,074 (de 26 % a 34 %), con las dos medidas de línea central mejores en las 30 imágenes.
- C: Matthews −0,0017 (−0,0031 a −0,0003); la textura no suma.
- D: +0,0060, sin ventaja sobre B.

**Decisión.** Se adopta B por la regla fijada (`config.SEGMENT_FEATURES`, 26 mapas). La referencia clásica no cambia.

**Efecto sobre prueba.**
- El algoritmo que se congela es B. Las máscaras de desarrollo de las etapas 6 y 7 se rehicieron con B (`notebooks/05d_mascaras_desarrollo.ipynb`), cada imagen con los pesos y la fracción de la vuelta en la que quedó afuera.
- La elección entre cuatro candidatas se hizo con las mismas 30 imágenes: el valor de desarrollo de B es algo optimista y la medida que vale es la de prueba.
- La candidata B no estaba en el plan ni en el esquema: se agregó al armar la ronda. La textura (tema obligatorio, esquema 5.4) queda probada sobre el mapa final y se informa como resultado negativo.
- Con las 30 imágenes, los pesos se guardan en `models/pesos_combinacion.json` y la fracción elegida sigue siendo 0,09 (`config.SEGMENT_FRACTION` no cambia). Los 26 mapas están muy correlacionados, así que los coeficientes no se interpretan uno por uno.

### 14.7 (31/10/2026, antes de calcular las medidas clínicas) La elección entre fracción fija y valor fijo considera también las medidas clínicas

**Qué pasó.** Al preparar la etapa 7 se vio que, con la fracción fija, la proporción de vasos de las máscaras de desarrollo del algoritmo queda entre 8,9 % y 10 % en todas las imágenes, mientras que la de los expertos va de 6,7 % a 12,5 % (correlación −0,23), y la diferencia entre sanos y los otros grupos desaparece. No es un error: con esa regla la proporción la fija el umbral, no la imagen. Es lo único que se miró de las medidas clínicas del algoritmo; la longitud del esqueleto y la tortuosidad no se calcularon.

**Decisión (antes de calcularlas).** La elección de la etapa 8 entre fracción fija y valor fijo sobre la probabilidad (desvío 14.5), que en desarrollo dieron lo mismo en Matthews, queda así:
1. **Robustez**, como estaba: con las imágenes degradadas de la etapa 8, si en algún nivel de degradación una regla no resulta no inferior a la otra (el límite inferior del intervalo al 95 % de su diferencia en Matthews queda por debajo de −0,03), gana la otra. Si eso no pasa con ninguna, o pasa con las dos, se sigue al punto 2.
2. **Concordancia clínica** (etapa 7): gana la de mayor correlación intraclase media en las tres medidas (proporción de vasos, longitud del esqueleto dividida por el diámetro y tortuosidad) entre los expertos y las máscaras de desarrollo de la combinación.
3. Si esa media difiere en menos de 0,05, queda la fracción fija, que es la que ya se usa.

Para esto, la etapa 7 calcula las medidas con las dos reglas, para la combinación y para la referencia; las máscaras con valor fijo se generan en `05d` con el valor elegido en entrenamiento en cada vuelta, como en `05b`.

### 14.8 (31/10/2026, antes de correr) Ronda para los vasos finos: resolución completa y entrenamiento equilibrado por grosor

**Qué pasó.** Después de cerrar el algoritmo (14.6) se decidió hacer una última ronda dirigida a su limitación principal: detecta un tercio de los vasos finos (34 %), y eso es lo que más baja la concordancia de las medidas clínicas (etapa 7). Esta ronda reabre el cierre de 14.6 y se declara acá.

**Candidatas** (los mismos 26 mapas, la misma validación cruzada por personas y la misma elección de la fracción que `05e`; cuaderno `05f_vasos_finos.ipynb`):
- A: el algoritmo actual (mitad de resolución; los píxeles de vaso para entrenar se sortean al azar, así que la mayoría son de vasos gruesos);
- B: A con entrenamiento equilibrado por grosor: un tercio de los píxeles de vaso de entrenamiento de cada clase (finos, medianos y gruesos);
- C: A a resolución completa;
- D: B a resolución completa.

**Regla de adopción (fijada antes de correr).** Una candidata reemplaza a A si mejora la sensibilidad de línea central en vasos finos con un intervalo al 95 % que no incluye el cero, y si Matthews y el Dice de línea central no son inferiores a los de A (límite inferior del intervalo de la diferencia por encima de −0,03, desvío 14.4). Si cumplen varias, gana la más barata (en este orden: B, C, D) entre las que no son inferiores a la mejor en vasos finos (mismo margen). Si ninguna cumple, queda A. La decisión se toma con la fracción fija; el valor fijo se informa. Después de esta ronda el algoritmo se cierra sin excepciones.

**Efecto.** Si cambia el algoritmo, se rehacen las máscaras de desarrollo (`05d`) y la etapa 7 (`07b`, con los parámetros ya fijados en `07a`), y las etapas 6 y 8 usan la versión nueva.

**Resultado (escrito después de correr, `05f`).** A se reproduce exacto (0,7255). B: vasos finos +0,067 (de 34 % a 40 %, intervalo +0,060 a +0,075), Matthews igual y Dice de línea central +0,004: cumple. C (resolución completa): los vasos finos bajan (−0,051): no cumple. D: finos +0,054, cumple, pero no supera a B. **Se adopta B** (`config.SEGMENT_BALANCED_TRAINING = True`); la resolución queda en la mitad y el algoritmo se cierra.

### 14.9 (3/11/2026, antes de abrir prueba) Cierre de la etapa 8: regla del umbral y restauración

**Regla del umbral.** Con el desvío 14.7 (`notebooks/08_robustez.ipynb`): en robustez ninguna regla deja de ser no inferior a la otra en ningún nivel (el peor caso, ruido σ = 20, da valor fijo − fracción fija = −0,0175, intervalo −0,024 a −0,011); por concordancia clínica gana el valor fijo (correlación intraclase media 0,21 contra −0,02). Se congela el **valor fijo**, elegido con todo desarrollo: 0,857 para la combinación y 0,945 para la referencia clásica, que usa la misma regla (sección 10).

**Restauración (desvío de la regla del esquema 5.4).** Aplicado a la foto antes del algoritmo, el suavizado de bloques es no inferior y mejora la base en +0,0001 (intervalo 0,0000 a 0,0003): por la regla debía adoptarse. **No se adopta**, por criterio: el efecto es despreciable y adoptarlo cambiaría el algoritmo usado en las etapas 5 a 7 antes de congelar. El Wiener contra el ruido no se midió en la base y no cambia nada con ruido leve: tampoco se adopta; se recomienda para fotos con ruido marcado (σ ≥ 10 niveles).

**Efecto sobre prueba.**
- El algoritmo que se congela no incluye restauración y **segmenta con el valor fijo** (antes, `segment_image` usaba la fracción fija por defecto).
- La referencia clásica usa la misma regla con **su propio valor fijo (0,945)**, elegido el 3/11 con todo desarrollo como el de la combinación (`choose_value` con el puntaje del detector de líneas); antes no estaba guardado.
- `notebooks/99_prueba.ipynb` y `scripts/segmentar.py` usan `src/pipeline.segment_final(rgb)` para el algoritmo y `segment_final(rgb, reference=True)` para la referencia, que leen la regla de `config.SEGMENT_THRESHOLD_RULE` y los valores de `models/pesos_combinacion.json`. `segment_image` y `segment_reference` no cambian y siguen sirviendo con umbrales explícitos.
- Las curvas de robustez de la sección 11, punto 5, se repiten sobre prueba con los mismos niveles (`config.ROBUST_*`, `IMAGE_JPEG_QUALITIES` y `RESTORE_*`).
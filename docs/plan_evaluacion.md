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
| Campo de visión | automático o el de la base (etapa 1) |
| Resolución de trabajo | (etapas 2 a 4) |
| Mapas de color | (etapa 2) |
| Mejoramiento y restauración | (etapa 3) |
| Realce y textura | (etapa 4) |
| Combinación, umbral y limpieza | (etapa 5) |
| Corrección de la etapa 6, si la hubo | (etapa 6) |

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

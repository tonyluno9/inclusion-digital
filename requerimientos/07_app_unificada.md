# 07 · App unificada

Una sola aplicación, con su propia ventana e interfaz, que junta todo: señas a subtítulos y voz, entrenamiento, y el
avatar dentro de la app (ya no hace falta Blender para verlo). La app anterior con la ventana de OpenCV sigue
disponible (`iniciar_clasico.bat`) y comparte la misma lógica.

## Arquitectura

| Parte | Dónde | Qué hace |
|---|---|---|
| Motor | `app/servidor_web.py` (`Motor`) | Un hilo lee la cámara y corre `InclusionApp` (segmentación, reconocimiento, grabación, avatar). Las acciones de la interfaz se ejecutan en ese hilo, entre frames. |
| Servidor | `app/servidor_web.py` (`Servidor`) | HTTP de la biblioteca estándar, solo en `127.0.0.1`. `/` interfaz, `/video` cámara (MJPEG), `/eventos` estado y movimiento 3D (Server-Sent Events), `/api/…` acciones y datos. Sin dependencias nuevas. |
| Ventana | `abrir_ventana` | Edge o Chrome en modo aplicación (sin barra de direcciones), con perfil propio en `app/data/navegador/`. |
| Interfaz | `app/web/` | HTML, CSS (Lexend, paleta de [diseno/README.md](../diseno/README.md)) y JavaScript. |
| Avatar | `app/web/js/avatar.js`, `retarget.js` | three.js con el personaje en GLB (`blender/exportar_glb.py`) y el mismo retargeting que Blender. |

## Requerimientos

### RF-26 · Una sola aplicación con su ventana — Debe
- `iniciar.bat` (o `python servidor_web.py`) abre la app en su propia ventana, con el logo y el nombre INCLUSION.
- Al cerrar la ventana, la app termina sola (libera la cámara) en unos segundos.
- Si el puerto está ocupado (la app ya está abierta), lo dice en español y termina sin traceback.
- Funciona sin internet: fuente, librerías 3D y personaje van dentro del proyecto.

### RF-27 · Avatar dentro de la app — Debe
- El personaje se dibuja dentro de la ventana, sobre el escenario de estudio, en reposo natural (brazos abajo, respira).
- En la pantalla **Avatar** imita en vivo a la persona (mismo retargeting que en Blender, RF-23).
- Reproduce clips grabados uno tras otro con transiciones suaves (0.3 s) y vuelve al reposo.
- El retargeting en JavaScript da el mismo resultado que el de Blender (diferencia < 0.5° por hueso).

### RF-28 · Pantallas — Debe
- **Inicio:** qué hace la app, accesos a las tres funciones y estado (cámara, traductor, avatar).
- **Traducir:** cámara, seña reconocida en grande con confianza e historial, oración, avatar que repite cada seña
  reconocida, y panel del interlocutor (dictar con el micrófono o escribir).
- **Entrenar:** palabra y persona, grabar / pausar, deshacer, conteo, señas grabadas (borrar) y botón para entrenar.
- **Avatar:** cámara y avatar en vivo, palabra, grabar / pausar, deshacer, movimientos grabados (ver, borrar).
- **Ayuda:** cómo colocarse, cómo enseñar una seña nueva y teclas.
- Las acciones son las mismas que las teclas de la app clásica (mismo código en `InclusionApp`).
- Teclas: Espacio grabar/pausar, Z deshacer, V voz, S micrófono, F pantalla completa, H ayuda.
- Avisos visuales: barra superior (cámara, traductor, avatar), aviso de encuadre en naranja, destello verde/rojo en
  la cámara al guardar/descartar, marco rojo mientras graba.

### RF-29 · Texto a señas del avatar — Debe (cubre RF-24)
- Lo que dice el interlocutor (dictado o escrito) se divide en palabras y frases que el avatar sabe, la frase más
  larga primero («buenos días» antes que «buenos»), sin importar acentos ni mayúsculas.
- El avatar las hace en orden; las que no sabe se avisan («El avatar no sabe: …»).

### RF-30 · Verificación de las señas — Debería
`python verificar_senas.py` reproduce cada muestra del dataset a varias velocidades por el segmentador real, la
clasifica con un modelo que no la vio (validación cruzada) y lista las muestras que fallan, para regrabarlas.

### RF-31 · Señas de una o dos manos — Debe
- Al grabar (Entrenar y Avatar) se elige si la seña es de **dos manos**, de la **mano derecha** o de la **mano
  izquierda** (botones o tecla `M`). La elección se recuerda por palabra (`data/manos_por_sena.json`, fuera de git).
- Con una mano, la otra no cuenta: no se guarda en la muestra, no alarga ni corta la seña, y el avatar deja ese
  brazo colgando junto al cuerpo con la mano en reposo (en vivo y en el clip, campo `hands`).
- Una muestra a la que le falta una de sus manos en más de la mitad de los frames no se guarda y se explica
  por qué («No vi tu mano izquierda… Si la seña es de una mano, elige «una mano»»). Evita muestras como las de
  «buenas tardes» sin la mano izquierda que hoy confunden al traductor con «hola».

### RF-32 · Revisar y recortar la toma del avatar — Debe
- En la app, la toma no se guarda sola: el avatar la repite en bucle y aparece una línea de tiempo con dos
  extremos. Al arrastrar un extremo el avatar muestra ese instante; al soltarlo repite solo el recorte.
- Pausa, velocidad 1× / ½×, flechas para ajustar un frame (Shift: 10), `Enter` guarda el recorte y `Esc` lo
  descarta. Mientras se revisa no se graba otra toma; deshacer o cambiar de palabra la descarta.
- La versión clásica (OpenCV) sigue guardando cada toma al momento.

### RF-33 · Pantalla de carga y tutorial — Debería
- Al abrir, una portada con el logo y el nombre mientras arrancan la cámara, el traductor y el avatar (al menos
  1.2 s, como máximo 8 s aunque algo no responda).
- La primera vez, un tutorial de 4 pasos con ilustraciones: colocarse, hacer la seña, la traducción y el avatar.
  Se puede volver a ver desde Ayuda. Flechas para avanzar, `Esc` para cerrarlo.

### RF-34 · Diccionario de señas — Debería
- Todas las palabras que la app conoce (muestras del dataset, señas del traductor y movimientos del avatar), una
  sola vez cada una, agrupadas en saludos, cortesía, preguntas, familia, emociones, números y otras
  (`web/datos/categorias.json`, editable).
- Buscador sin acentos ni mayúsculas y filtros por categoría. Cada seña dice si el traductor la reconoce, si el
  avatar la sabe hacer, cuántas muestras tiene y con qué manos se hace.
- Al tocarla, el avatar la hace (también a ½×). Botones para practicarla, grabar muestras o grabar su movimiento
  con la palabra ya puesta, y «Por grabar» con las palabras de la categoría que aún faltan.

### RF-35 · Aprender: práctica con estrellas e insignias — Debería
- La app elige una seña que el traductor reconoce (primero las que el avatar sabe hacer, y más seguido las que menos
  se han acertado); el avatar la enseña (repetir, ½×) y la persona la hace frente a la cámara.
- Si el traductor reconoce esa seña: «¡Bien hecho!» y de 1 a 3 estrellas según la confianza (≥ 75 %: 2; ≥ 90 %: 3).
  Si reconoce otra: «Inténtalo otra vez» con lo que entendió; tras dos fallos el avatar la repite más despacio.
- En práctica las señas no forman oraciones (no se llama a Claude).
- Estrellas, racha de días, señas aprendidas y 9 insignias (primera seña, 10 señas, racha de 3 y de 7 días, saludos,
  primer movimiento del avatar, traductor entrenado, primera oración, 3 categorías). Se guardan en
  `data/progreso.json` (junto al dataset, fuera de git); las reglas están en `modules/progreso.py`.

### RF-36 · Escenarios del avatar y pantallas de estado — Debería
- El avatar se puede ver en 4 escenarios (Estudio, Jade, Aula y Plaza); la elección se recuerda.
- Celebraciones con ilustración al ganar una insignia y al terminar de entrenar el traductor.
- Si la ventana deja de recibir datos del motor por más de 3 s, aviso «Se perdió la conexión», que se quita solo
  cuando vuelve.

### RNF-12 · Seguridad local — Debe
- El servidor solo escucha en `127.0.0.1` (no se ve desde la red).
- Solo sirve archivos de `app/web` (no se puede pedir nada fuera de esa carpeta).
- El perfil del navegador de la app es aparte del personal y no va a git.

## Diseño

Imágenes generadas una vez (Nano Banana 2.1, 1K) y convertidas a recursos con
`diseno/herramientas/preparar_recursos.py`: logo, 20 íconos (máscaras que toman el color del tema), 4 ilustraciones
y 2 fondos. Fuente Lexend (OFL).

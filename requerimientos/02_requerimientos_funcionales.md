# 02 · Requerimientos funcionales

Prioridad: **Debe** / **Debería** / **Podría**. El estado de cada uno está en [05_verificacion.md](05_verificacion.md).

## Captura y detección

### RF-01 · Fuente de video — Debe
La app toma video de la cámara (índice configurable con `--camera N`) o de un archivo (`--video ruta`).
- Si la cámara no abre, muestra un mensaje en español con la causa probable y termina sin traceback.
- El video se muestra en espejo (como un espejo) para que la persona se vea natural.

### RF-02 · Detección de manos y cuerpo — Debe
Por cada frame se detectan hasta 2 manos (21 puntos cada una) y el cuerpo: nariz, hombros, codos y muñecas
(detalle del brazo completo en [RF-17](06_avatar.md)).
- Cada mano ocupa siempre su lugar fijo (izquierda / derecha de la persona) en el vector, aunque solo se vea una.
- Las manos y los brazos detectados se dibujan sobre el video con un color distinto por lado.
- Los modelos de MediaPipe se descargan solos la primera vez; si no hay internet, se informa cómo obtenerlos.

### RF-03 · Segmentación de señas — Debe
Una seña empieza cuando las manos aparecen ≥ 3 frames seguidos y termina cuando desaparecen ≥ 8 frames seguidos
(o al llegar al máximo de 120 frames, ~4 s).
- Parpadeos de detección cortos (≤ 5 frames) dentro de una seña no la parten en dos.
- Movimientos de < 10 frames se descartan.
- La seña se recorta y se lleva a 30 frames. **El mismo código prepara las muestras al grabar y al detectar.**
- La referencia corporal (nariz y hombros) se toma preferentemente de los frames previos a la seña (cuerpo sin tapar
  por los brazos). Codos y muñecas son los de cada frame: son parte del movimiento.

## Reconocimiento y comunicación

### RF-04 · Reconocimiento de la seña — Debe
Al terminar cada seña se clasifica con el modelo entrenado y se obtiene una confianza (0–1).
- Si la confianza < umbral (`MIN_CONFIDENCE`, 0.6) se muestra "no reconocida" en vez de una palabra.
- Sin modelo entrenado, la app funciona y muestra cómo crearlo.
- Un modelo de otra versión de features se rechaza con un mensaje para reentrenar.

### RF-05 · Subtítulos — Debe
La palabra reconocida se muestra en grande (≥ 48 px) en la parte inferior, con barra de confianza,
y se agrega a un historial de las últimas 5 palabras.

### RF-06 · Voz de la seña (TTS) — Debe
La palabra reconocida y la oración final se dicen en voz alta en español.
- Se puede activar/desactivar (`v`); el estado se ve en pantalla.
- Sin internet se usa la voz del sistema operativo si está disponible; si no hay voz, la app sigue sin errores.

### RF-07 · Oración natural — Debería
Tras `SILENCE_SECONDS` (2.5 s) sin manos, las palabras del historial se unen en una oración natural con Claude.
- Sin `ANTHROPIC_API_KEY`, sin internet o con `USE_CLAUDE = False`, se muestran las palabras unidas tal cual.
- Solo se envían las palabras reconocidas (nunca imagen ni puntos).

### RF-08 · Voz a texto del interlocutor (STT) — Debería
Con `s` se graba la voz del interlocutor y con `s` se detiene; el texto aparece en pantalla, grande y con contraste.
- Se intenta Google (en línea) y después Vosk (sin conexión) si está instalado.
- Si faltan paquetes o micrófono, se muestra un aviso en pantalla y la app sigue.

## Entrenamiento y datos

### RF-09 · Grabación de muestras — Debe
Con `t` se pide en la ventana (sin consola) la palabra y el nombre de quien graba; Espacio activa/pausa la grabación.
- Cada seña (manos arriba → manos abajo) se guarda sola como una muestra.
- La confirmación de guardado/descartado es **visual** (destello y mensaje) además del sonido.
- `z` deshace la última muestra.
- Se muestra el contador de muestras de esa palabra.

### RF-10 · Gestión del dataset — Debe
- `i` muestra en pantalla (y en consola) muestras por seña y por persona.
- `x` borra todas las muestras de una seña: hay que escribir la palabra (eso sirve de confirmación).
- Respaldo automático cada 50 muestras en `data/backups/`.
- El CSV se lee y escribe en UTF-8 (palabras con ñ y acentos).

### RF-11 · Entrenamiento — Debe
- `e` entrena en segundo plano sin congelar el video y recarga el modelo al terminar.
- `python train_model.py` entrena y reporta la precisión por validación cruzada **por persona** (o avisa que es optimista si hay una sola persona), por seña y con matriz de confusión.
- Exige ≥ 2 señas con ≥ 5 muestras cada una; si no, explica qué falta.

### RF-12 · Persistencia del modelo — Debe
El modelo se guarda con su versión de features, longitud de secuencia y lista de señas; `r` lo recarga.

## Interfaz

### RF-13 · Ayuda y estado — Debe
- `h` muestra/oculta la lista de teclas sobre el video.
- Siempre se ve el modo actual (DETECCIÓN / ENTRENAMIENTO / AVATAR) y el estado de la voz.

### RF-14 · Control de la ventana — Debe
`f` alterna pantalla completa; `q`, `Esc` o cerrar la ventana con la X terminan la app liberando cámara e hilos.
`Esc` primero cierra la ayuda o la pregunta abierta, si hay una.

### RF-15 · Modo sin ventana para pruebas — Debería
`--headless` procesa el video sin mostrar ventana (para pruebas automáticas y demos con `--video`).

### RF-16 · Exportación móvil — Podría
`python train_tensorflow.py` entrena una red y exporta `model.tflite`, `mean.npy`, `std.npy` y `clases.txt`
con validación separada antes del aumento de datos.

## Avatar

RF-17 a RF-24 (brazo completo, modo avatar, clips por palabra, Blender) están en [06_avatar.md](06_avatar.md).

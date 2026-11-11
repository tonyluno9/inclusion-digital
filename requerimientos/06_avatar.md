# 06 · Avatar: captura de movimiento y reproducción en Blender

Objetivo: que un avatar 3D (personaje con rig de cuerpo y dedos, en Blender) haga las señas de LSM. Así se cubre
también la dirección oyente → persona Sorda.

El avatar **no se entrena con IA: aprende grabando**. Primero el avatar copia en vivo el movimiento de la persona.
Después, la persona presiona grabar, hace la seña y el movimiento queda guardado como clip de esa palabra. Más
adelante, la app reproduce los clips palabra por palabra.

## Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| **A1** | Captura del brazo completo y coordenadas 3D, modo avatar en la app, envío en vivo, grabación de clips por palabra | Hecha |
| **A2** | En Blender: puntos en vivo y clips importados como animación, sin depender del rig | Hecha |
| **A3** | Conectar los puntos al rig del personaje (retargeting) y hornear una acción por palabra | Hecha (falta probar con la webcam) |
| **A4** | Reproducir palabras u oraciones (texto o voz del interlocutor) con transiciones entre clips | Después de A3 |
| **A5** | Expresión facial (marcadores no manuales) | Futuro |

## Requerimientos

### RF-17 · Brazo completo — Debe
El detector lee, por cada lado, hombro, codo y muñeca del cuerpo, además de los 21 puntos de cada mano.
- El lado (izquierdo / derecho) es el **anatómico** de la persona, aunque la imagen esté en espejo.
  - Cada mano va al lado de la muñeca del cuerpo más cercana. Sin cuerpo, se usa la etiqueta de MediaPipe
    **invertida**: MediaPipe etiqueta como si la imagen no estuviera en espejo (comprobado con la forma 3D de la
    mano: los dedos se doblan hacia la palma; ver `motion.hand_side_from_shape`). Con la mano del lado cambiado,
    el personaje la cierra al revés.
  - El cuerpo se decide por geometría: en espejo, el hombro izquierdo de la persona queda a la izquierda de la imagen.
- Un punto con visibilidad < 0.5 se guarda como ausente (ceros).
- La pose se calcula en cada frame (`POSE_EVERY_N_FRAMES = 1`) con el modelo `full` de MediaPipe
  (`POSE_MODEL`; `lite` es más rápido y detecta peor el cuerpo, `heavy` es demasiado lento), y se mantiene
  RNF-01 (≥ 15 fps).
- El reconocedor de señas a subtítulos usa también la posición de codos y muñecas respecto a los hombros (features v4).

### RF-18 · Modo avatar en vivo — Debe
Con `a` se pide la palabra y se entra al modo AVATAR.
- Mientras está en modo avatar, la app envía cada frame en coordenadas 3D por UDP a `127.0.0.1:5005`
  (configurable). El envío nunca bloquea ni detiene la app si nadie escucha.
- En el video se dibujan hombros, codos, muñecas y manos, para que la persona vea qué se está capturando.
- El movimiento enviado en vivo se suaviza (filtro One Euro) para que el avatar no tiemble.
- **Aviso de encuadre:** si en el último segundo los codos se vieron en menos del 30 % de los frames, la barra
  superior dice **"Aléjate: no veo tus codos"** (en naranja, como "No veo tus hombros"). Cuenta siempre en modo
  avatar y, en los otros modos, solo mientras hay manos. En la prueba en vivo, muy cerca de la cámara el cuerpo se
  detectó en el 1 % de los frames; bien encuadrado, en el 100 %.

### RF-19 · Grabación de clips por palabra — Debe
En modo avatar, Espacio activa o pausa la grabación. La seña se detecta igual que en RF-03 (manos arriba → manos abajo).
- El clip incluye ~0.5 s antes de levantar las manos y la bajada de los brazos, para que la animación empiece y
  termine en reposo.
- Se guarda en `app/data/avatar/<palabra>.json`. Si ya existía, la toma anterior queda en `<palabra>.prev.json`.
- `z` deshace la última toma (restaura la anterior, o borra el clip si era la primera).
- La confirmación es visual: destello verde con la duración del clip, o destello rojo si la seña fue muy corta.
- Los huecos cortos (≤ 5 frames) de cada parte se rellenan por interpolación antes de guardar.

### RF-20 · Formato neutral del clip — Debe
El clip guarda los puntos 3D de la persona, no rotaciones de un rig: si el personaje cambia, no hay que regrabar.
Formato en la sección siguiente. Se versiona (`version`) y la app rechaza versiones que no conoce.

### RF-21 · Blender: puntos en vivo — Debe
Un script de Blender (`blender/inclusion_avatar.py`) crea un esqueleto de puntos (empties) y los mueve en vivo con lo
que llega por UDP, sin congelar la interfaz de Blender.

### RF-22 · Blender: importar clips — Debe
El mismo script importa un clip `.json` como animación de esos puntos, a los fps de la escena, con una acción por palabra.

### RF-23 · Retargeting al rig — Debe (etapa A3)
Los huesos del personaje siguen a los puntos y se hornea una acción por palabra.
- Personaje: `blender/personaje/` (FBX de Tripo, 78 huesos, pose T con palmas abajo, mirando a −Y). Escena lista en
  `blender/personaje/avatar_inclusion.blend` (se regenera con `blender/crear_escena.py`).
- Huesos que se mueven (42): columna (3), cabeza, y por lado clavícula, brazo, antebrazo, mano y 3 falanges por dedo.
  Piernas y cadera quedan en reposo (la persona seña sentada).
- **Por dirección, no por posición:** cada hueso apunta como el segmento de la persona (hombro → codo, codo → muñeca,
  muñeca → nudillo medio, cada falange). No importa la estatura del personaje.
- **Giro sobre el eje:** el brazo según el plano en que dobla el codo (con el doblez real del rig como referencia); la
  mano según la línea de nudillos índice → meñique; los dedos según la palma. El antebrazo toma la mitad del giro de la
  muñeca (pronación), porque los huesos de giro del rig no deforman la malla.
- **Pecho y cabeza:** la línea de hombros (y caderas → hombros si se ven) inclina la columna, repartida en 3 vértebras;
  orejas y nariz giran la cabeza.
- **Protecciones:** hombros a < 15 cm = cuerpo mal detectado, se ignora; caderas → hombros a > 40° de la vertical, se
  usa la vertical; giro máximo del pecho 35°, de la cabeza 70° y de la clavícula 25°. Una parte que no se detecta
  conserva su último giro.
- Al hornear, cada punto se suaviza con un promedio móvil de 5 frames. La acción del personaje es `seña_<palabra>`; la
  de los puntos, `puntos_<palabra>`.
- En vivo, el personaje conectado se mueve con cada frame que llega por UDP.
- Perfiles de rig: hoy `Tripo`. Para otro rig basta agregar sus nombres de huesos en `PERFILES`.

**Limitación conocida:** como se copian direcciones y el personaje tiene otras proporciones, los contactos (mano que
toca la cara o el pecho) pueden quedar cerca pero no exactos. Se corrige con IK en una etapa posterior (RF-25).

### RF-25 · Contactos exactos — Podría
Las señas con contacto (mano en la barbilla, el pecho, la otra mano) conservan el contacto en el personaje (IK sobre
la muñeca con la posición relativa al cuerpo). Pendiente.

### RF-24 · Reproducción por palabras — Debería (etapa A4)
Dada una frase, el avatar encadena los clips de sus palabras con transiciones suaves. Pendiente.

### RNF-11 · Privacidad del avatar — Debe
Los clips y el envío en vivo solo contienen coordenadas (nunca imagen). El envío UDP es solo local por defecto.

## Formato del clip (`app/data/avatar/<palabra>.json`)

```json
{
  "format": "inclusion-movimiento",
  "version": 1,
  "word": "hola",
  "person": "angel",
  "created": "2026-11-03T18:00:00",
  "fps": 29.7,
  "duration": 2.4,
  "coords": "metros; origen en el centro de las caderas; x hacia la izquierda de la persona, y hacia arriba, z hacia adelante (hacia la cámara)",
  "pose_names": ["nose", "left_eye_inner", "...", "right_foot_index"],
  "hand_names": ["wrist", "thumb_cmc", "...", "pinky_tip"],
  "frames": [
    {"t": 0.0,
     "pose": [[x, y, z], "... 33 puntos"],
     "vis": [0.99, "... 33 valores"],
     "left": [[x, y, z], "... 21 puntos"],
     "right": null}
  ]
}
```

- **`pose`**: los 33 puntos de MediaPipe Pose (*world landmarks*), con los nombres **anatómicos**: `left_*` es el lado
  izquierdo de la persona. `null` si no se detectó el cuerpo en ese frame.
- **`vis`**: visibilidad 0–1 de cada punto del cuerpo.
- **`left` / `right`**: los 21 puntos de cada mano (*hand world landmarks*) **ya colocados en el cuerpo**: la muñeca de
  la mano coincide con la muñeca del cuerpo (`pose[15]` izquierda, `pose[16]` derecha). `null` si la mano no se
  detectó o si no hay cuerpo en ese frame (no habría dónde colocarla).
- Si MediaPipe pierde el cuerpo unos frames (≤ 5), se conserva el último cuerpo detectado.
- Ejes, derechos (*right-handed*): `x` hacia la izquierda de la persona, `y` hacia arriba, `z` hacia adelante. En
  Blender, con el personaje mirando a −Y: `(X, Y, Z)_blender = (x, −z, y)`.
- `t` en segundos desde el primer frame del clip. Números redondeados a 4 decimales.

## Mensajes en vivo (UDP, JSON por datagrama)

```json
{"type": "frame", "t": 12.345, "pose": [...] , "vis": [...], "left": [...], "right": null}
{"type": "clip", "word": "hola", "path": "C:/.../app/data/avatar/hola.json"}
```

- `frame`: mismo contenido y ejes que un frame del clip, suavizado. `t` es el reloj de la app.
- `clip`: se acaba de guardar un clip; Blender puede importarlo.

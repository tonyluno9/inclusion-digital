# 06 · Avatar: captura de movimiento y reproducción en Blender

Objetivo: que un avatar 3D (personaje con rig de cuerpo y dedos, en Blender) haga las señas de LSM. Así se cubre
también la dirección oyente → persona Sorda.

El avatar **no se entrena con IA: aprende grabando**. Primero el avatar copia en vivo el movimiento de la persona.
Después, la persona presiona grabar, hace la seña y el movimiento queda guardado como clip de esa palabra. Más
adelante, la app reproduce los clips palabra por palabra.

## Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| **A1** | Captura del brazo completo y coordenadas 3D, modo avatar en la app, envío en vivo, grabación de clips por palabra | Esta iteración |
| **A2** | En Blender: puntos en vivo y clips importados como animación, sin depender del rig | Esta iteración |
| **A3** | Conectar los puntos al rig del personaje (retargeting) y hornear una acción por palabra | Siguiente, con el archivo del personaje |
| **A4** | Reproducir palabras u oraciones (texto o voz del interlocutor) con transiciones entre clips | Después de A3 |
| **A5** | Expresión facial (marcadores no manuales) | Futuro |

## Requerimientos

### RF-17 · Brazo completo — Debe
El detector lee, por cada lado, hombro, codo y muñeca del cuerpo, además de los 21 puntos de cada mano.
- El lado (izquierdo / derecho) es el **anatómico** de la persona, aunque la imagen esté en espejo.
  - Las manos usan la etiqueta de MediaPipe, que es correcta con la imagen en espejo.
  - El cuerpo se decide por geometría: en espejo, el hombro izquierdo de la persona queda a la izquierda de la imagen.
- Un punto con visibilidad < 0.5 se guarda como ausente (ceros).
- La pose se calcula en cada frame (`POSE_EVERY_N_FRAMES = 1`) y se mantiene RNF-01 (≥ 15 fps).
- El reconocedor de señas a subtítulos usa también la posición de codos y muñecas respecto a los hombros (features v4).

### RF-18 · Modo avatar en vivo — Debe
Con `a` se pide la palabra y se entra al modo AVATAR.
- Mientras está en modo avatar, la app envía cada frame en coordenadas 3D por UDP a `127.0.0.1:5005`
  (configurable). El envío nunca bloquea ni detiene la app si nadie escucha.
- En el video se dibujan hombros, codos, muñecas y manos, para que la persona vea qué se está capturando.
- El movimiento enviado en vivo se suaviza (filtro One Euro) para que el avatar no tiemble.

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
Los huesos del personaje siguen a los puntos (brazos, antebrazos, manos y 3 falanges por dedo, incluido el giro del
antebrazo según la palma) y se hornea una acción por palabra. Pendiente: necesita el archivo del personaje.

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

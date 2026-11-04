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

### RNF-12 · Seguridad local — Debe
- El servidor solo escucha en `127.0.0.1` (no se ve desde la red).
- Solo sirve archivos de `app/web` (no se puede pedir nada fuera de esa carpeta).
- El perfil del navegador de la app es aparte del personal y no va a git.

## Diseño

Imágenes generadas una vez (Nano Banana 2.1, 1K) y convertidas a recursos con
`diseno/herramientas/preparar_recursos.py`: logo, 20 íconos (máscaras que toman el color del tema), 4 ilustraciones
y 2 fondos. Fuente Lexend (OFL).

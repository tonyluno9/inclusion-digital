# «Pruébalo»: K'ab T'aan en el navegador

La app de K'ab T'aan funcionando dentro del navegador, sin instalar nada: traducir señas con la cámara,
el avatar, Aprender y el Diccionario. El video del visitante **no sale de su navegador**.

## Cómo está hecha

```
sitio/probar/
  index.html, app.css     la interfaz de la app (app/web), con las rutas del sitio
  probar.css, js/pruebalo.js   lo que solo existe en la web: encender la cámara, avisos, tus datos
  js/app.js               el app.js de la app con otro transporte (cambios marcados «Pruébalo:»)
  js/*.js                 copias exactas de app/web/js (sitio/herramientas/copiar_interfaz.py)
  js/motor/               el motor de Python portado a JavaScript (ver la tabla)
  datos/                  categorías del Diccionario; datos/demo/ = traductor y clips de demostración
  tests/                  pruebas de paridad Python ↔ JavaScript
```

| Python (app/) | JavaScript (js/motor/) |
|---|---|
| `modules/landmarks.py` | `landmarks.js`: frame crudo de 147 valores y features de 260, con las cuentas en float32 como numpy |
| `modules/segmenter.py` | `segmentador.js` |
| `modules/gesture_logic.py` + scikit-learn | `traductor.js`: StandardScaler + bosque aleatorio leídos de `modelo.json` |
| `train_model.py` | `entrenamiento.js` + `bosque.js`, en un Web Worker (`entrenador.worker.js`) |
| `modules/landmark_detector.py` | `detector.js` (lógica) + `camara.js` (MediaPipe para web, espejo antes de detectar) |
| `modules/motion.py` | `movimiento.js`: frames 3D del avatar, One Euro, clips |
| `modules/progreso.py` | `progreso.js` |
| `inclusion_app.py` + `servidor_web.py` | `motor.js`: la lógica de la app con el mismo contrato (`accion`, `obtener`, `escuchar`) |
| `tts.py`, `stt.py`, `beep.py` | `voz.js`: voz y dictado del navegador, pitidos con WebAudio |
| `config.py` | `config.js` (mismos valores) |

La interfaz no sabe que no hay servidor: `app.js` llama a `motor.accion(...)` en vez de `fetch('/api/accion')`,
y recibe `{estado, mundo}` en cada cuadro como antes por `/eventos`.

## Datos de demostración (`datos/demo/`)

- `modelo.json`: el traductor de la app exportado con `sitio/herramientas/exportar_modelo.py`. Conoce 4 señas
  (adiós, «c», hola y mucho gusto), entrenado con **82 muestras de una sola persona**: con otras personas puede
  equivocarse. Se publica con permiso de quien grabó, sin su nombre (solo `"personas": 1`).
- `clips/hola.json`: el movimiento del avatar para «hola» (formato «inclusion-movimiento» v1), con `"person": "demo"`.
- `indice.json`: qué modelo y qué clips cargar, y con qué manos se hace cada seña.

Lo que el visitante graba o entrena se guarda en su navegador y tiene prioridad sobre esto; los clips de
demostración no se pueden borrar desde la página (uno propio los reemplaza).

## Pruebas

```powershell
python sitio/herramientas/generar_fixtures.py          # casos desde los módulos reales de app/ (tests/fixtures)
node sitio/probar/tests/landmarks.test.mjs
node sitio/probar/tests/traductor.test.mjs
node sitio/probar/tests/movimiento_progreso.test.mjs
node sitio/probar/tests/app.test.mjs
node sitio/probar/tests/entrenamiento.test.mjs
```

- **Entrenar en el navegador** (`bosque.js`, `entrenamiento.js`, `entrenador.worker.js`): la receta de
  `train_model.py` (mismo aumento de datos; StandardScaler + 200 árboles de Gini con `min_samples_leaf=2` y
  √rasgos por nodo) en un Web Worker. No es el mismo bosque que el de scikit-learn (otro generador de azar), así que
  se mide la exactitud: en 24 señas sintéticas nuevas, JavaScript 100 % y scikit-learn 100 %; con las 82 muestras
  reales, validación cruzada de 5 partes 100 % en ambos (una sola persona: la cifra es optimista). Con 30 muestras
  entrena en ~1.5 s, y la página sigue fluida mientras tanto.

- **La app completa** (`app.test.mjs`): un guion de 60 pasos (señas por la cámara, oración tras el silencio,
  práctica con estrellas e insignias, muestras de una y dos manos con sus rechazos, tomas del avatar grabadas,
  recortadas, descartadas y deshechas, errores de validación y las rutas `/api/...` del Diccionario y del
  progreso) pasa por `InclusionApp` de Python y por `App` de `motor.js`. El estado que recibe la interfaz, los
  resultados, lo que dice la voz, el movimiento del avatar y las muestras guardadas salen iguales en cada paso.
  Única diferencia a propósito: con el traductor *de demostración* no se gana la insignia «Traductor
  entrenado» (en la app el traductor siempre es tuyo; aquí hay que entrenar uno propio).

- **Rasgos**: idénticos bit a bit (diferencia 0) en todos los casos, incluidos huecos, una o dos manos,
  sin cuerpo y manos en reposo. **Probabilidades**: diferencia ≤ 2·10⁻¹⁶, incluso con 300 rasgos puestos justo
  en el umbral de un árbol (y en el float32 vecino de cada lado).
- Con `--datos RUTA` el generador agrega casos con el dataset y el modelo reales en `tests/local/`
  (fuera de git). Con las 82 muestras de la app: la misma seña ganadora en 82 de 82.
- **De punta a punta**: `python sitio/herramientas/prueba_video.py VIDEO.mp4 --modelo app/data/model.pkl`
  pasa los mismos cuadros (PNG, sin pérdida) por la app de Python y por esta página en Chromium, y compara
  puntos, cortes y señas reconocidas. Con `--camara-falsa` también prueba el camino real de la cámara.
  Con un video de prueba de 150 cuadros: las manos y el cuerpo se detectan en los mismos cuadros y del mismo
  lado, con menos de medio píxel de diferencia media; el movimiento 3D del avatar difiere 3 mm en promedio
  (brazos: ≤ 7 mm en x e y; la profundidad z, que MediaPipe estima con una sola cámara, hasta 7.5 cm en algún cuadro).

## Verla en tu computadora

```powershell
python sitio/herramientas/servidor_local.py      # http://127.0.0.1:8790/probar/
```

Opciones en la dirección: `?pose=lite` (modelo de cuerpo rápido) y `?delegado=cpu` (sin tarjeta gráfica).

## Pulido (fase 5)

- **Rendimiento:** meta de 15 cuadros por segundo. Con la tarjeta gráfica de una laptop normal va a ~33 fps
  (30 ms por cuadro, pose «full»). Si va a menos de 15 durante unos segundos, la página ofrece el **modo rápido**
  (pose «lite»), que se cambia sin apagar la cámara y se recuerda; en Ayuda se puede volver al normal.
  Ojo: con «lite» los puntos del cuerpo no son los mismos que en la app (la paridad con Python es con «full»).
- **Cámara:** se enciende solo con el botón, explicando que el video no sale del navegador. Si se niega el
  permiso, dice cómo darlo desde el candado; si no hay cámara, está ocupada o el navegador no da acceso, lo dice.
- **Sin WebGL:** la página funciona igual (traductor, voz, Diccionario, Aprender, Entrenar) con un aviso; solo
  falta el avatar 3D.
- **Celular:** la barra lateral pasa abajo, la página se desplaza y en el Diccionario el avatar queda arriba
  mientras se recorren las señas. Probado a 375 × 812 sin desplazamiento horizontal.
- **Accesibilidad:** la seña reconocida, la oración, el texto del interlocutor, el resultado de Aprender y los
  avisos se anuncian a los lectores de pantalla (`aria-live`); la pantalla abierta lleva `aria-current`; foco
  visible con teclado y sin animaciones si el sistema pide movimiento reducido.

## Qué usa internet

Nada del motor: MediaPipe y sus modelos vienen de `sitio/vendor/mediapipe/`. La **voz** es la del navegador
(algunas voces «en línea» envían el texto a su servicio) y el **dictado** usa el reconocimiento de voz del
navegador (en Chrome y Edge, el audio va a su servicio en internet): la página avisa antes de usarlo. La
oración natural con Claude no está: una página estática no puede guardar una clave en secreto
(`URL_ORACION` en `config.js` es el gancho para un servidor propio).

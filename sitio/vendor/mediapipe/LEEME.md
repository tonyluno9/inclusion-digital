# MediaPipe para web (copia local)

- `vision_bundle.mjs` y `wasm/`: [`@mediapipe/tasks-vision`](https://www.npmjs.com/package/@mediapipe/tasks-vision)
  **0.10.35**, la misma versión que `mediapipe` de Python en la app. Licencia Apache-2.0 (Google).
  Solo se copiaron los archivos que usa `FilesetResolver.forVisionTasks` (con y sin SIMD).
- `modelos/`: los mismos `.task` que descarga la app en `app/data/models/` (Apache-2.0, Google):

  | Archivo | SHA-256 (inicio) |
  |---|---|
  | `hand_landmarker.task` | `fbc2a30080c3c557` |
  | `pose_landmarker_full.task` | `4eaa5eb7a9836522` |
  | `pose_landmarker_lite.task` | `59929e1d1ee95287` |

Están aquí (y no en un CDN) para que «Pruébalo» use versiones fijas, no dependa de que un CDN
responda y no avise a terceros cada vez que alguien abre la página. Se descargan solo cuando el
visitante pulsa «Encender la cámara».

Para actualizar: cambia la versión en la app y aquí a la vez, y vuelve a correr
`python sitio/herramientas/prueba_video.py` para comparar los puntos de ambos lados.

# Plan de Mejoras - Proyecto INCLUSION 🚀

Los requerimientos y su estado viven en [`../requerimientos/`](../requerimientos/). Este archivo es la bitácora y el
orden sugerido para las próximas iteraciones.

## ✅ Iteración 2 (pipeline v2 + requerimientos)

- Requerimientos escritos (RF-01…RF-16, RNF-01…RNF-10) con matriz de verificación.
- Lógica de la app separada del bucle de cámara (`inclusion_app.py`) y probada de punta a punta con frames y teclas simuladas.
- Integración real con MediaPipe probada con una foto de muestra y con un video (`--video --headless --benchmark`).
- Segmentador: ignora manos en reposo, no genera muestras basura tras un corte largo, toma la referencia del cuerpo de los frames previos a la seña.
- Manos con lugar estable aunque la etiqueta izquierda/derecha de MediaPipe parpadee.
- Features con dos bloques: posición respecto al cuerpo y forma de la mano.
- Dataset en UTF-8 (acentos y ñ), escrituras atómicas, conteos en memoria.
- Retroalimentación visual para la persona Sorda: destellos, "Hablando...", "No veo tus hombros", errores de voz en pantalla.
- Interfaz: ayuda (`h`), textos que se ajustan, frames chicos agrandados, caché de la capa de texto (< 1 ms por frame).
- Voz sin internet con la voz del sistema (pyttsx3); servicios en línea apagables en `config.py`.
- Scripts `instalar.bat` / `iniciar.bat`, CI en GitHub Actions, 74 pruebas automáticas.

## ✅ Iteración 3 (avatar, etapas A1 y A2)

- El detector lee el brazo completo (hombros, codos, muñecas) con lados anatómicos, en paralelo con las manos.
- Reconocedor con features v4 (incluye la postura de los brazos). El dataset anterior se migra solo, con respaldo.
- Modo avatar (`a`): envío en vivo por UDP con suavizado One Euro y grabación de un clip 3D por palabra.
- Add-on de Blender: puntos en vivo e importación de clips como acción `seña_<palabra>`.
- Prueba de punta a punta: MediaPipe real → clip → Blender. 103 pruebas.

## ✅ Iteración 4 (avatar, etapa A3)

- Personaje de Tripo en `blender/personaje/`, con escena lista (`avatar_inclusion.blend`).
- Retargeting por direcciones: 42 huesos (columna, cabeza, brazos, manos, 3 falanges por dedo), con el giro del codo,
  la palma y la pronación repartida al antebrazo. En vivo y horneado como `seña_<palabra>`.
- Protecciones contra cuerpos mal detectados y límites de giro.
- Pruebas en Blender: reposo exacto, pose conocida (< 1.5°), en vivo por UDP; revisión con fotos reales de MediaPipe.

## ✅ Iteración 5 (app unificada)

- Una sola aplicación en su ventana (Edge/Chrome en modo app): Inicio, Traducir, Entrenar, Avatar y Ayuda.
- Avatar dentro de la app con three.js: imita en vivo, repite cada seña reconocida y dice en señas lo que escribe o
  dicta el interlocutor. Mismo retargeting que Blender (0.003° de diferencia).
- Identidad visual: logo, 20 íconos, ilustraciones y fondos generados (Nano Banana 2.1) y fuente Lexend.
- `verificar_senas.py`: pasa cada muestra por la cámara simulada con un modelo que no la vio.
- Traductor reentrenado con el dataset corregido: 97.9 % en validación cruzada; 89.4 % por la cámara simulada.
  Las fallas son 5 muestras concretas: «hola» se hace con una mano y «buenas tardes» con dos, y en #27 y #28 no se
  detectó la mano izquierda (parecen «hola»); en #24 apareció una mano izquierda en «hola». **Regrabarlas con la
  versión actual** (que también guarda codos y muñecas del cuerpo) debería subir el acierto.
- 123 pruebas.

## ⏭️ Siguiente

| Prioridad | Tarea | Requerimiento |
| :--- | :--- | :--- |
| **CRÍTICA** | Grabar el dataset del protocolo (3+ personas, 20 muestras por seña) y medir | RNF-02 |
| **ALTA** | Regrabar las muestras que fallan (`python verificar_senas.py`) con la versión que guarda codos | RNF-02 |
| **ALTA** | Grabar el movimiento del avatar para cada seña del vocabulario | RF-27, RF-29 |
| **ALTA** | Probar el modo avatar con la webcam y el personaje en Blender ([checklist](../requerimientos/05_verificacion.md)) | RF-17, RF-18, RF-21, RF-23 |
| **ALTA** | Reproducir frases con el avatar (encadenar clips, desde texto o voz del interlocutor) | RF-24 |
| **MEDIA** | Contactos exactos con IK (mano en la cara, el pecho o la otra mano) | RF-25 |
| **ALTA** | Prueba manual con cámara completa ([checklist](../requerimientos/05_verificacion.md)) | RF-01, RF-06, RF-08, RF-14 |
| **ALTA** | Comparar el Random Forest con un modelo secuencial (GRU o CNN-1D) usando validación por persona | RNF-02 |
| **MEDIA** | Segmentar también por pausas de movimiento (sin bajar las manos) | nuevo RF |
| **MEDIA** | Expresiones faciales (marcadores no manuales) | nuevo RF |
| **BAJA** | App móvil (Flutter + TFLite) | RF-16 |

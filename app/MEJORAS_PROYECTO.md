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

## ⏭️ Siguiente

| Prioridad | Tarea | Requerimiento |
| :--- | :--- | :--- |
| **CRÍTICA** | Grabar el dataset del protocolo (3+ personas, 20 muestras por seña) y medir | RNF-02 |
| **ALTA** | Prueba manual con cámara completa ([checklist](../requerimientos/05_verificacion.md)) | RF-01, RF-06, RF-08, RF-14 |
| **ALTA** | Comparar el Random Forest con un modelo secuencial (GRU o CNN-1D) usando validación por persona | RNF-02 |
| **MEDIA** | Segmentar también por pausas de movimiento (sin bajar las manos) | nuevo RF |
| **MEDIA** | Expresiones faciales (marcadores no manuales) | nuevo RF |
| **BAJA** | App móvil (Flutter + TFLite) | RF-16 |

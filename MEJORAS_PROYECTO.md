# Plan de Mejoras - Proyecto INCLUSION 🚀

## ✅ Hecho (pipeline v2)

- **Migración a MediaPipe Tasks:** la API `mp.solutions` ya no existe en las versiones actuales de MediaPipe.
- **Misma preparación al grabar y al detectar:** cada seña se segmenta (manos arriba → manos abajo), se recorta y se remuestrea a 30 frames. Antes, la detección usaba una ventana deslizante distinta a la del entrenamiento: en una simulación con el dataset viejo, esto bajaba la precisión de ~98% a ~40%.
- **Features respecto al cuerpo:** posición de la mano relativa a los hombros y escalada por su ancho (antes solo forma de la mano respecto a la muñeca, sin trayectoria).
- **Manos en lugar fijo:** izquierda y derecha ya no se intercambian entre frames.
- **Espejo correcto** como aumento de datos al entrenar (para personas zurdas).
- **Evaluación honesta:** `python train_model.py` mide con personas que el modelo no vio.
- **Sin `input()` en consola:** las preguntas aparecen en la ventana de la cámara.
- **Entrenamiento en segundo plano** con la tecla `e`, y deshacer la última muestra con `z`.
- **Claude opcional:** sin `ANTHROPIC_API_KEY` la app sigue funcionando.
- **Configuración centralizada** en `config.py` y **pruebas** en `tests/`.
- **Barra de confianza** y **voz (TTS)**.

## ⏭️ Siguiente

| Prioridad | Tarea | Notas |
| :--- | :--- | :--- |
| **CRÍTICA** | Volver a grabar el dataset con 3+ personas | El dataset viejo (`data/legacy/`) no tiene la posición de las manos en el cuerpo |
| **ALTA** | Modelo secuencial (GRU o CNN-1D sobre 30×126) | Evaluar contra el Random Forest con validación por persona |
| **MEDIA** | Segmentar también por pausas de movimiento | Hoy hay que bajar las manos entre seña y seña |
| **MEDIA** | Expresiones faciales (marcadores no manuales) | Agregar puntos de la cara al frame crudo |
| **BAJA** | App móvil (Flutter + TFLite) | `train_tensorflow.py` ya exporta el modelo |

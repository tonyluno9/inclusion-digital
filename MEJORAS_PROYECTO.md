# Plan de Mejoras - Proyecto INCLUSION 🚀

Este documento detalla las mejoras propuestas para elevar la calidad técnica, funcional y estética del sistema de reconocimiento de señas.

## 1. Experiencia de Usuario (UI/UX) 🎨

### 🔊 Síntesis de Voz (Text-to-Speech)
- **Descripción:** Integrar `pyttsx3` para que el sistema "hable" la palabra detectada.
- **Impacto:** Alta accesibilidad. Permite una comunicación fluida sin que la otra persona tenga que mirar la pantalla constantemente.

### 📊 Feedback de Confianza (Confidence Bar)
- **Descripción:** Añadir un anillo de progreso o una barra que se llene según el `predict_proba` del modelo.
- **Impacto:** Reduce la frustración del usuario al mostrar por qué el sistema no está "seguro" de una seña todavía.

### ⌨️ Interfaz de Entrada Integrada
- **Descripción:** Reemplazar el `input()` de consola por un campo de texto en el overlay de OpenCV (usando una caja de texto estilizada) para nombrar nuevas señas en el modo entrenamiento.
- **Impacto:** Elimina la necesidad de alternar entre la ventana de la cámara y la terminal.

---

## 2. Mejoras Técnicas y de Inteligencia 🤖

### 🌊 Suavizado de Predicciones (Temporal Smoothing)
- **Descripción:** Implementar un búfer de resultados recientes. Una palabra solo se muestra como final si aparece en, por ejemplo, 4 de los últimos 5 frames procesados.
- **Impacto:** Elimina el "parpadeo" entre palabras similares y aumenta la estabilidad visual.

### 🔄 Entrenamiento Automático en Segundo Plano
- **Descripción:** Trigger automático que detecta cambios en `dataset.csv` y ejecuta el script de entrenamiento en un hilo separado (thread), recargando el modelo `.pkl` en caliente.
- **Impacto:** Flujo de trabajo continuo; el usuario puede entrenar y probar inmediatamente sin reiniciar la app.

### 🧠 Modelos de Tiempo Real Avanzados
- **Descripción:** Evaluar el paso de un modelo de Machine Learning tradicional (RandomForest/SVM) a una red neuronal recurrente (LSTM) o un Transformer pequeño para capturar mejor la dinámica de las señas.
- **Impacto:** Mayor precisión en señas que dependen del movimiento y no solo de la posición.

---

## 3. Arquitectura y Código 🛠️

### ⚙️ Sistema de Configuración (config.yaml)
- **Descripción:** Mover constantes como `SEQUENCE_LENGTH`, `MIN_DETECTION_CONFIDENCE`, y rutas de archivos a un archivo de configuración externo.
- **Impacto:** Facilita el ajuste del sistema sin tocar el código fuente.

### 🧵 Multi-threading (Procesamiento Distribuido)
- **Descripción:** Separar la captura de frames, el procesamiento de landmarks y la lógica de predicción en hilos distintos.
- **Impacto:** Mantiene una tasa de FPS alta y constante (60+) incluso si la predicción del modelo se vuelve más pesada.

### 🧪 Pruebas Unitarias y Tipado
- **Descripción:** Añadir Type Hints y tests unitarios para los módulos críticos como `SequenceBuffer` y `FaceDetector`.
- **Impacto:** Código más profesional, mantenible y menos propenso a errores al escalar.

---

## Resumen de Prioridades

| Prioridad | Tarea | Dificultad |
| :--- | :--- | :--- |
| **CRÍTICA** | **Suavizado de Predicciones (Temporal Filter)** | Baja |
| **ALTA** | **Síntesis de Voz (TTS)** | Baja |
| **MEDIA** | **Barra de Confianza en UI** | Media |
| **BAJA** | **Entrenamiento en Segundo Plano** | Alta |

# 03 · Requerimientos no funcionales

### RNF-01 · Rendimiento — Debe
- ≥ 15 fps sostenidos en una laptop sin GPU dedicada (referencia: CPU de 4 núcleos, 2018 o más reciente) con webcam 640×480 o 1280×720.
- La palabra aparece ≤ 1 s después de bajar las manos.
- El entrenamiento con 2 000 muestras termina en < 1 min y no congela la ventana.
- Medición: `python main.py --video <archivo> --headless --benchmark` reporta fps y ms por etapa.

### RNF-02 · Precisión — Debe
Con el protocolo de [04_vocabulario_y_datos.md](04_vocabulario_y_datos.md) (≥ 3 personas, ≥ 20 muestras por seña y persona):
- **≥ 90 %** de exactitud en validación por persona (se prueba con una persona que el modelo no vio).
- **≥ 95 %** de exactitud con la misma persona.
- Ninguna seña individual por debajo de 80 % de *recall*.
Se mide con `python train_model.py`. Mientras no exista ese dataset, el estado es ⏳.

### RNF-03 · Funcionamiento sin internet — Debe
Detección, reconocimiento, subtítulos, grabación y entrenamiento funcionan sin conexión
(después de la primera descarga de modelos). Voz, oración natural y STT en línea se degradan con aviso, sin errores.

### RNF-04 · Privacidad — Debe
- El video se procesa en el equipo; **no se guardan imágenes ni video**. El dataset solo contiene coordenadas de puntos.
- A servicios externos solo se envía texto: palabras reconocidas (Claude, gTTS) y audio del interlocutor solo cuando se presiona `s` (Google STT).
- Cada servicio externo se puede desactivar en `config.py`.
- La clave de API vive en `.env`, que está excluido de git.
- **Riesgo conocido (MediaPipe):** la librería nativa de MediaPipe 0.10.35 incluye un registro de uso de Google
  (`tasks/cc/core/logging/.../clearcut_logging_client.cc`, envía a `https://play.googleapis.com/log`); en la consola
  aparece como `Failed to send to clearcut`. Por su diseño registra el uso de las tareas (no hay evidencia de que mande
  imágenes ni puntos, pero no se ha verificado el contenido). La API de Python no ofrece cómo apagarlo
  (`BaseOptions` solo tiene modelo y delegado). Pendiente: revisar qué envía y, si hace falta, fijar una versión sin
  ese registro o bloquearlo para el proceso de la app.

### RNF-05 · Accesibilidad — Debe
- Toda retroalimentación necesaria para la persona Sorda es **visual** (los sonidos son complementarios).
- Texto principal ≥ 48 px, blanco sobre fondo oscuro; textos secundarios ≥ 18 px con fondo de contraste.
- Los textos largos se ajustan a varias líneas sin salirse de la pantalla.
- Toda la interfaz está en español.

### RNF-06 · Robustez — Debe
La app no termina con traceback por: falta de cámara, falta de internet, paquetes opcionales ausentes, modelo
ausente o de otra versión, dataset vacío o de otro formato, errores de los hilos de voz/IA/entrenamiento.
Los errores se muestran en español en pantalla o consola.

### RNF-07 · Portabilidad — Debe
Windows 10/11 con Python 3.10–3.12 (plataforma principal). Linux y macOS: mejor esfuerzo, sin rutas fijas de Windows.

### RNF-08 · Mantenibilidad — Debe
- Parámetros en `config.py`; nada de números mágicos repetidos en el código.
- Pruebas automáticas que corren **sin cámara ni internet** en < 2 min; CI en GitHub Actions.
- Lógica de la app separada del bucle de cámara para poder probarla con frames y teclas simuladas.

### RNF-09 · Integridad de datos — Debe
- Dataset en CSV UTF-8 con columnas fijas (`label`, `person`, `f0…`); los puntos crudos permiten recalcular features sin regrabar.
- Escrituras que reescriben el archivo (borrar, deshacer) son atómicas (archivo temporal + reemplazo).
- Respaldos automáticos (RF-10).

### RNF-10 · Instalación — Debería
Scripts `instalar.bat` e `iniciar.bat` en Windows; instrucciones en el README de `app/`.

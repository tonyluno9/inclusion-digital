# 05 · Verificación

Estado: ✅ cumplido y verificado · 🟡 implementado, falta verificar con cámara o con datos reales · ⏳ pendiente.

## Cómo correr las pruebas

```bash
cd app
python -m unittest discover -s tests -t .
```

74 pruebas, ~30 s, sin cámara. La prueba de integración con MediaPipe descarga la primera vez los modelos y una foto
de muestra oficial (≈ 14 MB); sin internet se omite. CI: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
(Windows y Ubuntu, Python 3.10–3.12).

## Matriz de trazabilidad

| ID | Requerimiento | Verificación automática (`app/tests/`) | Estado |
|---|---|---|---|
| RF-01 | Fuente de video | `test_integration_mediapipe` (video y archivo inexistente) | 🟡 falta webcam real |
| RF-02 | Detección manos y cuerpo | `test_integration_mediapipe.test_detector_finds_both_hands`, `test_landmarks.test_slots_*` | ✅ |
| RF-03 | Segmentación | `test_segmenter` (6), `test_landmarks`, `test_regression_legacy` (señas reales del dataset viejo: ≥ 95 %) | ✅ |
| RF-04 | Reconocimiento | `test_app.test_full_flow…`, `test_app.test_without_model…`, `test_pipeline` | ✅ (con datos sintéticos) |
| RF-05 | Subtítulos | `test_app.test_full_flow…`, `test_app.test_render_long_texts…` | ✅ |
| RF-06 | Voz (TTS) | `test_tts` (8), `test_app` | 🟡 falta oírla en el equipo |
| RF-07 | Oración natural | `test_coherence` (7), `test_app.test_full_flow…`, `test_more_than_history_words…` | 🟡 falta probar con clave real |
| RF-08 | Voz a texto | `test_stt` (12), `test_app.test_keys…` | 🟡 falta micrófono real |
| RF-09 | Grabación de muestras | `test_app` (flujo completo, sin grabar mientras se escribe), `test_data_collector`, `test_text_input` | ✅ |
| RF-10 | Gestión del dataset | `test_data_collector` (9), `test_app.test_keys…` | ✅ |
| RF-11 | Entrenamiento | `test_app.test_full_flow…`, `test_app.test_training_failure…`, `test_pipeline` | ✅ |
| RF-12 | Persistencia del modelo | `test_pipeline.test_old_model_is_rejected` | ✅ |
| RF-13 | Ayuda y estado | `test_app.test_keys…` | ✅ |
| RF-14 | Control de la ventana | `test_app.test_keys…` (q / Esc) | 🟡 falta probar la X y pantalla completa |
| RF-15 | Modo sin ventana | `test_integration_mediapipe.test_main_runs_headless_on_video` | ✅ |
| RF-16 | Exportación móvil | — (requiere TensorFlow) | ⏳ |
| RNF-01 | Rendimiento | `--benchmark`: **25 fps** con video 1280×720 (detección ~29 ms, interfaz < 1 ms con caché); entrenar 2 000 muestras: **7 s** | ✅ en el equipo de desarrollo |
| RNF-02 | Precisión ≥ 90 % por persona | `test_pipeline` (sintético). Requiere el dataset de ≥ 3 personas | ⏳ falta grabar el dataset |
| RNF-03 | Sin internet | `test_tts` (respaldo con voz local), `test_coherence` (sin clave), `test_stt` | ✅ |
| RNF-04 | Privacidad | `test_pipeline.test_dataset_only_has_coordinates`, `test_coherence` | ✅ |
| RNF-05 | Accesibilidad | `test_app.test_render_long_texts…`, revisión de capturas (texto ajustado, destellos) | 🟡 falta revisión con usuarios Sordos |
| RNF-06 | Robustez | `test_app.test_training_failure…`, `test_stt`, `test_integration…` (video inexistente) | ✅ |
| RNF-07 | Portabilidad | CI en Windows y Ubuntu | 🟡 hasta que corra el primer CI |
| RNF-08 | Mantenibilidad | `config.py`, `InclusionApp` separada del bucle, suite < 2 min, CI | ✅ |
| RNF-09 | Integridad de datos | `test_data_collector` (UTF-8, atómico, respaldos, formato) | ✅ |
| RNF-10 | Instalación | `instalar.bat`, `iniciar.bat` (probado el camino de error) | 🟡 falta correr `instalar.bat` en un equipo limpio |

## Prueba manual con cámara (antes de cada versión)

Marca cada punto. Lo que falle se registra como requerimiento no cumplido.

**Arranque**
- [ ] `iniciar.bat` abre la ventana; la primera vez descarga los modelos (RF-01, RF-02).
- [ ] Sin cámara conectada, aparece el mensaje en español y no hay traceback (RF-01).
- [ ] `h` muestra la ayuda; `Esc` la cierra (RF-13).

**Detección y cuerpo**
- [ ] Al levantar las manos se dibujan en dos colores, sin intercambiarse al moverlas (RF-02).
- [ ] Con los hombros fuera de cuadro aparece "No veo tus hombros" (RF-03).
- [ ] Con las manos apoyadas en la mesa a la vista, no se detectan señas falsas (RF-03).

**Grabación** (`t`, palabra, nombre, Espacio)
- [ ] La palabra con ñ o acento se escribe bien en la ventana (RF-09).
- [ ] Cada seña (manos arriba → abajo) se guarda: destello verde y contador (RF-09, RNF-05).
- [ ] Un movimiento muy corto se descarta con destello rojo (RF-09).
- [ ] `z` deshace la última muestra (RF-09); `i` muestra los conteos (RF-10).

**Entrenamiento y reconocimiento**
- [ ] `e` entrena sin congelar el video y al terminar dice "Modelo entrenado y cargado" (RF-11).
- [ ] En detección, la seña aparece en grande ≤ 1 s después de bajar las manos (RF-04, RF-05, RNF-01).
- [ ] La voz dice la palabra; con `v` se apaga y el indicador cambia (RF-06).
- [ ] Sin internet, la voz usa la del sistema (RF-06, RNF-03).
- [ ] Tras ~2.5 s sin manos aparece la oración y se dice (RF-07).

**Interlocutor y ventana**
- [ ] `s`, hablar, `s`: el texto aparece arriba en grande (RF-08).
- [ ] `f` alterna pantalla completa; cerrar con la X termina la app y apaga la cámara (RF-14).
- [ ] `python main.py --benchmark` reporta ≥ 15 fps (RNF-01).

**Precisión** (con el dataset del protocolo de [04](04_vocabulario_y_datos.md))
- [ ] `python train_model.py` reporta ≥ 90 % en validación por persona y ninguna seña < 80 % (RNF-02).

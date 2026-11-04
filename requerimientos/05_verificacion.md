# 05 · Verificación

Estado: ✅ cumplido y verificado · 🟡 implementado, falta verificar con cámara o con datos reales · ⏳ pendiente.

## Cómo correr las pruebas

```bash
cd app
python -m unittest discover -s tests -t .
```

137 pruebas de Python (incluyen las de JavaScript con Node y las de Blender, si están instalados), 30–60 s, sin cámara. La prueba de integración con MediaPipe descarga la primera vez los modelos y una foto
de muestra oficial (≈ 14 MB); sin internet se omite. Las pruebas de Blender corren si está instalado (variable
`BLENDER_EXE` o `C:\Program Files\Blender Foundation\Blender *`); el CI no lo tiene y las omite. CI: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
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
| RNF-01 | Rendimiento | Detección con manos y pose en paralelo, pose en cada frame, 1280×720: modelo `lite` 20–34 ms, **`full` 31 ms (~32 fps)**, `heavy` 76 ms (descartado); app completa con `--benchmark`: 16–20 fps; avatar (suavizado + UDP) 0.25 ms; entrenar 2 000 muestras: **7 s** | 🟡 medir con la webcam |
| RNF-02 | Precisión ≥ 90 % por persona | `test_pipeline` (sintético). Requiere el dataset de ≥ 3 personas | ⏳ falta grabar el dataset |
| RNF-03 | Sin internet | `test_tts` (respaldo con voz local), `test_coherence` (sin clave), `test_stt` | ✅ |
| RNF-04 | Privacidad | `test_pipeline.test_dataset_only_has_coordinates`, `test_coherence` | 🟡 nuestro código cumple; MediaPipe trae un registro de uso de Google que no se puede apagar desde Python (ver 03) |
| RNF-05 | Accesibilidad | `test_app.test_render_long_texts…`, revisión de capturas (texto ajustado, destellos) | 🟡 falta revisión con usuarios Sordos |
| RNF-06 | Robustez | `test_app.test_training_failure…`, `test_stt`, `test_integration…` (video inexistente) | ✅ |
| RNF-07 | Portabilidad | CI en Windows y Ubuntu | 🟡 hasta que corra el primer CI |
| RNF-08 | Mantenibilidad | `config.py`, `InclusionApp` separada del bucle, suite < 2 min, CI | ✅ |
| RNF-09 | Integridad de datos | `test_data_collector` (UTF-8, atómico, respaldos, formato) | ✅ |
| RNF-10 | Instalación | `instalar.bat`, `iniciar.bat` (probado el camino de error) | 🟡 falta correr `instalar.bat` en un equipo limpio |
| RNF-11 | Privacidad del avatar | `test_motion.test_clip_contains_only_coordinates`; UDP solo a `127.0.0.1` por defecto | ✅ |

### Avatar ([06_avatar.md](06_avatar.md))

| ID | Requerimiento | Verificación automática | Estado |
|---|---|---|---|
| RF-17 | Brazo completo | `test_motion.test_body_sides_are_anatomical`, `test_landmarks.test_arm_features`, `test_landmarks.test_fill_gaps_fills_each_arm_point_alone`, `test_segmenter.test_arms_move_with_the_sign`, `test_integration_mediapipe.test_detector_gives_3d_frame_for_the_avatar`, `test_data_collector.test_migracion_*`, `test_data_collector.test_manos_grabadas_del_lado_cambiado_*`, `test_motion.HandSideTest` (la mano de cada lado tiene la forma de ese lado, también con MediaPipe real) | 🟡 falta confirmar codos con la webcam |
| RF-18 | Modo avatar en vivo | `test_app.test_avatar_live_and_record_clip`, `test_app.test_framing_hint_*` / `test_no_framing_hint_*`, `test_motion.LiveSenderTest`, `test_motion.SmoothingTest`; prueba en vivo observada (29 fps, cuerpo y manos 100 % bien encuadrado) | 🟡 falta probar con la webcam y Blender abiertos |
| RF-19 | Clips por palabra | `test_app.test_avatar_*`, `test_motion.ClipTest`, `test_motion.RecorderTest` | ✅ (con frames simulados) |
| RF-20 | Formato neutral | `test_motion.WorldFrameTest`, `test_motion.test_make_clip_has_the_documented_format`, `test_blender_script.test_clip_real_de_la_app_en_blender` | ✅ |
| RF-21 | Blender: en vivo | `blender/tests/test_inclusion_avatar.py` (UDP real, sin el timer modal) | 🟡 falta ver el panel y el timer en Blender abierto |
| RF-22 | Blender: importar clips | `blender/tests/test_inclusion_avatar.py`, `test_blender_script.test_clip_real_de_la_app_en_blender` | ✅ |
| RF-23 | Retargeting al rig | `blender/tests/test_retarget.py` (vía `test_blender_script.test_retargeting_al_personaje`): reposo sin giros, pose conocida (brazos < 1.5°, dedos y palmas 0°), partes perdidas, horneado y en vivo por UDP; revisión visual con fotos de MediaPipe | 🟡 falta probar con la webcam |
| RF-25 | Contactos exactos | — | ⏳ |

### App unificada ([07_app_unificada.md](07_app_unificada.md))

| ID | Requerimiento | Verificación automática | Estado |
|---|---|---|---|
| RF-26 | Una sola app con su ventana | `test_servidor_web` (interfaz, recursos, cierre al cerrar la ventana); arranque real con Edge en modo app y cierre comprobados | ✅ |
| RF-27 | Avatar dentro de la app | `web/tests/retarget.test.mjs` (mismo resultado que Blender: 0.003°), `test_servidor_web.test_eventos_traen_estado_y_movimiento`; revisión en el navegador (imita en vivo, reproduce clips) | 🟡 falta con la webcam |
| RF-28 | Pantallas | `test_servidor_web.test_estado_y_acciones`, `test_app` (mismas acciones); revisión de las 5 pantallas en el navegador | 🟡 falta con la webcam |
| RF-29 | Texto a señas | `web/tests/texto.test.mjs`; revisión en el navegador («Hola, prueba» → seña «prueba» y aviso de «hola») | ✅ |
| RF-30 | Verificación de señas | `python verificar_senas.py` con el dataset real: 89.4 % por la cámara simulada (ver [MEJORAS](../app/MEJORAS_PROYECTO.md)) | ✅ |
| RF-31 | Una o dos manos | `test_manos_y_tomas` (máscara de la otra mano, rechazo de muestras sin una mano, brazo en reposo del avatar, memoria por palabra, tecla M), `retarget.test.mjs` (olvidarMano); probado en la app con video | 🟡 |
| RF-32 | Recortar la toma del avatar | `test_manos_y_tomas.TomasTest`, `test_servidor_web.test_manos_y_toma_pendiente`; probado en la app con video (arrastrar extremos, ½×, Enter guarda 2.6 s de 4.8 s) | 🟡 |
| RNF-12 | Seguridad local | `test_servidor_web.test_no_sale_de_la_carpeta_web`; servidor en `127.0.0.1` | ✅ |
| RF-24 | Reproducción por palabras | Cubierto por RF-29 (app unificada) | 🟡 falta probar con frases reales |

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

**App unificada** (`iniciar.bat`)
- [ ] Se abre la ventana INCLUSION con el logo; al cerrarla, la app termina (RF-26).
- [ ] Traducir: la seña reconocida aparece en grande y el avatar la repite si tiene movimiento (RF-28, RF-27).
- [ ] Escribir en «El interlocutor dice» hace que el avatar diga en señas las palabras que sabe (RF-29).
- [ ] Entrenar: grabar, deshacer, ver el conteo y entrenar desde el botón (RF-28).
- [ ] Avatar: el personaje te imita en vivo; grabar una palabra y verla en «Movimientos grabados» (RF-27).

**Avatar** (Blender abierto con `blender/inclusion_avatar.py`: Crear puntos → Escuchar en vivo)
- [ ] En la app, `a`, palabra: aparece "● AVATAR" y se dibujan hombros, codos y muñecas (RF-17, RF-18).
- [ ] Al levantar el brazo **derecho**, en Blender se mueve `cuerpo.right_*` y `mano_der.*` (lados anatómicos, RF-17).
- [ ] Los puntos siguen el movimiento sin temblar y sin retraso notable (RF-18).
- [ ] Muy cerca de la cámara aparece "Aléjate: no veo tus codos" y desaparece al alejarse (RF-18).
- [ ] Espacio, seña, manos abajo: destello verde y aparece `app/data/avatar/<palabra>.json` (RF-19).
- [ ] Con "Importar clips automáticamente", el clip queda como acción `seña_<palabra>`; al detener e importarlo, se reproduce (RF-22).
- [ ] `z` deshace la toma (RF-19).
- [ ] Con `blender/personaje/avatar_inclusion.blend` abierto y el personaje conectado, el personaje te sigue en vivo:
      brazos, codos, palmas y dedos; la cabeza gira contigo (RF-23).
- [ ] Al importar el clip de una palabra, el personaje la reproduce con la acción `seña_<palabra>` (RF-23).

**Precisión** (con el dataset del protocolo de [04](04_vocabulario_y_datos.md))
- [ ] `python train_model.py` reporta ≥ 90 % en validación por persona y ninguna seña < 80 % (RNF-02).

# INCLUSION · aplicación

Requerimientos y estado: [`../requerimientos/`](../requerimientos/).

## Instalación

**Windows:** doble clic en `instalar.bat`. Busca Python 3.10–3.12, crea `.venv`, instala dependencias y corre las pruebas.

**Manual (cualquier sistema):**

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Opcional, para voz a texto del interlocutor y exportar a TFLite: `pip install -r requirements-opcional.txt`.
Para armar oraciones con Claude, crea `app/.env` con `ANTHROPIC_API_KEY=...`. Sin la clave, la app muestra las palabras tal cual.

La primera vez que corre, la app descarga los modelos de MediaPipe a `data/models/` (unos 13 MB, de Google).

## Uso

**Windows:** doble clic en `iniciar.bat`, o desde la consola:

```bash
python main.py                    # cámara 0
python main.py --camera 1         # otra cámara
python main.py --video demo.mp4   # un video en vez de la cámara
python main.py --benchmark        # al salir, muestra fps y ms por etapa
```

En la ventana, presiona `h` para ver todas las teclas:

| Tecla | Acción |
|---|---|
| `t` | Entrenar una palabra (pide palabra y nombre en la ventana) |
| Espacio | En entrenamiento: activar o pausar la grabación automática |
| `z` | En entrenamiento: deshacer la última muestra |
| `d` | Modo detección |
| `e` | Entrenar el modelo (en segundo plano) |
| `r` | Recargar el modelo |
| `i` | Estadísticas del dataset |
| `x` | Borrar una seña del dataset |
| `s` | Voz del interlocutor a texto (iniciar / terminar) |
| `v` | Activar o desactivar la voz |
| `f` | Pantalla completa |
| `h` | Ayuda |
| `q` / `Esc` | Salir |

Cómo grabar un buen dataset: [Guia_Entrenamiento.md](Guia_Entrenamiento.md).

Para ver la precisión real del modelo con personas que no vio:

```bash
python train_model.py
```

## Cómo funciona

1. **Detección** (`modules/landmark_detector.py`): MediaPipe Tasks detecta las dos manos y los hombros. Cada mano
   ocupa siempre su lugar (izquierda / derecha), con continuidad entre frames.
2. **Segmentación** (`modules/segmenter.py`): una seña empieza al levantar las manos y termina al bajarlas. Las manos
   apoyadas abajo se ignoran. La seña se recorta y se lleva a 30 frames. **El mismo paso prepara las muestras al grabar
   y al detectar.** La referencia del cuerpo se toma de los frames previos, donde los brazos no tapan los hombros.
3. **Features** (`modules/landmarks.py`): por frame, la posición de cada mano respecto a los hombros (trayectoria y
   altura) y la forma de la mano respecto a su muñeca (configuración de los dedos), sin depender de la distancia a la cámara.
4. **Modelo** (`train_model.py`): Random Forest con aumento de datos (espejo para personas zurdas, versión sin cuerpo
   visible, variaciones de corte y ruido). La evaluación es por persona.
5. **App** (`inclusion_app.py`): toda la lógica, separada del bucle de cámara (`main.py`) para poder probarla completa
   con frames y teclas simuladas.

El dataset (`data/dataset_v2.csv`) guarda los puntos crudos, así que si cambian las features no hay que volver a grabar.

## Configuración

Todo en [`config.py`](config.py): cámara, segmentación, umbral de confianza, silencio para armar la oración,
servicios en línea (`USE_CLAUDE`, `USE_ONLINE_TTS`, `USE_ONLINE_STT`) y nombres con acento (`DISPLAY_NAMES`).

## Pruebas

```bash
python -m unittest discover -s tests -t .
```

Corren sin cámara. Detalle de qué verifica cada una: [05_verificacion.md](../requerimientos/05_verificacion.md).

## Dataset anterior

`data/legacy/dataset_v1.csv` es el dataset de la versión anterior (11 señas, una persona). Usa otro formato
(solo la forma de la mano respecto a la muñeca, sin posición en el cuerpo), así que no sirve para el modelo actual.
Se conserva como referencia y para la prueba de regresión del segmentador.

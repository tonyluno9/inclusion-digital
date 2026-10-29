# INCLUSION — Reconocimiento de Lengua de Señas Mexicana

App de escritorio que reconoce señas de LSM con la cámara, las muestra como subtítulo,
las lee en voz alta y (opcionalmente) arma una oración con Claude.

## Instalación

Python 3.10 – 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Opcional: voz a texto del interlocutor y exportar a TFLite → `pip install -r requirements-opcional.txt`.
Para armar oraciones con Claude, crea un archivo `.env` con `ANTHROPIC_API_KEY=...`
(sin él la app muestra las palabras tal cual).

La primera vez que corre, la app descarga los modelos de MediaPipe (≈ 13 MB, de Google) a `data/models/`.

## Uso

```bash
python main.py
```

| Tecla | Acción |
|---|---|
| `t` | Entrenar una palabra (pide palabra y nombre en la ventana) |
| Espacio | En entrenamiento: activar / pausar la grabación automática |
| `z` | En entrenamiento: deshacer la última muestra |
| `d` | Modo detección |
| `e` | Entrenar el modelo (en segundo plano) |
| `r` | Recargar el modelo |
| `i` | Estadísticas del dataset |
| `x` | Borrar una seña del dataset |
| `s` | Grabar la voz del interlocutor |
| `v` | Activar / desactivar la voz |
| `f` | Pantalla completa |
| `q` | Salir |

Para ver qué tan bien funciona el modelo con muestras que no vio:

```bash
python train_model.py
```

Si el dataset tiene varias personas, la precisión se mide con una persona que no
estuvo en el entrenamiento (lo que pasará con usuarios reales).

## Cómo funciona

1. **Detección** (`modules/landmark_detector.py`): MediaPipe Tasks detecta las dos manos y
   los hombros. Cada mano va siempre en su lugar fijo (izquierda / derecha).
2. **Segmentación** (`modules/segmenter.py`): una seña empieza cuando aparecen las manos y
   termina cuando se bajan. Se recorta y se lleva a 30 frames. **Este paso es idéntico al
   grabar y al detectar**, para que el modelo vea las señas siempre de la misma forma.
3. **Features** (`modules/landmarks.py`): posición de la mano respecto al centro de los
   hombros, dividida entre el ancho de hombros. Conserva la trayectoria y la altura de la
   seña sin depender de la distancia a la cámara.
4. **Modelo** (`train_model.py`): Random Forest con aumento de datos (espejo para personas
   zurdas, ruido y variaciones de corte).

El dataset (`data/dataset_v2.csv`) guarda los puntos crudos, así que si cambian las features
no hay que volver a grabar.

## Pruebas

```bash
python -m unittest discover -s tests -t .
```

## Dataset anterior

`data/legacy/dataset_v1.csv` es el dataset de la versión anterior (11 señas, una persona).
Usa otro formato: solo forma de la mano respecto a la muñeca, sin posición en el cuerpo,
por lo que no sirve para el modelo nuevo y hay que volver a grabar. Se conserva como referencia.

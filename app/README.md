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

La primera vez que corre, la app descarga los modelos de MediaPipe a `data/models/` (unos 25 MB, de Google).

## Uso

**Windows:** doble clic en `iniciar.bat` (o en el acceso directo INCLUSION del Escritorio, que crea `instalar.bat`
o `crear_acceso_directo.bat`). Se abre INCLUSION en su propia ventana, con cinco pantallas:

| Pantalla | Para qué |
|---|---|
| **Inicio** | Qué hace la app y el estado de la cámara, el traductor y el avatar |
| **Aprender** | El avatar te enseña una seña y el traductor te califica: estrellas, racha e insignias |
| **Diccionario** | Todas las señas por categoría, con buscador; el avatar hace la que toques |
| **Traducir** | Tus señas se vuelven subtítulos y voz; el avatar repite cada seña. Lo que el interlocutor dicta o escribe, el avatar lo dice en señas |
| **Entrenar** | Grabar ejemplos de una seña y entrenar el traductor |
| **Avatar** | El avatar te imita en vivo; grabar el movimiento de cada palabra |
| **Ayuda** | Cómo colocarse, cómo enseñar una seña nueva y teclas |

Teclas: `Espacio` grabar / pausar, `Z` deshacer, `V` voz, `S` micrófono, `F` pantalla completa, `H` ayuda.
Al cerrar la ventana, la app termina sola.

Desde la consola:

```bash
python servidor_web.py                    # cámara 0, en su ventana
python servidor_web.py --camera 1         # otra cámara
python servidor_web.py --video demo.mp4   # un video en vez de la cámara (se repite)
python verificar_senas.py                 # comprobar que cada seña grabada se reconozca
```

Cómo está hecha: [07_app_unificada.md](../requerimientos/07_app_unificada.md) (motor en Python, interfaz web en
`web/`, avatar con three.js).

### Versión clásica (ventana de OpenCV)

`iniciar_clasico.bat`, o:

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
| `a` | Avatar: grabar el movimiento de una palabra (pide la palabra) |
| Espacio | En entrenamiento o avatar: activar o pausar la grabación automática |
| `z` | En entrenamiento o avatar: deshacer la última toma |
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

## Avatar

El avatar aprende grabando: en modo avatar (`a`) la app manda tu movimiento en vivo a Blender (UDP
`127.0.0.1:5005`) y, con Espacio, cada seña (manos arriba → abajo) se guarda como clip en
`data/avatar/<palabra>.json`, con el movimiento 3D de cuerpo, brazos y dedos a su velocidad real.

En Blender se usa [`../blender/inclusion_avatar.py`](../blender/README.md): crea los puntos, los mueve en vivo e importa
los clips como animación, también en el personaje (`../blender/personaje/avatar_inclusion.blend`), que te sigue en vivo y
guarda una acción por palabra. Encadenar palabras en frases es la siguiente etapa
([06_avatar.md](../requerimientos/06_avatar.md)).

## Cómo funciona

1. **Detección** (`modules/landmark_detector.py`): MediaPipe Tasks detecta las dos manos y el cuerpo (hombros, codos,
   muñecas), en paralelo. Izquierda y derecha son siempre las de la persona: cada mano va al lado de la muñeca del
   cuerpo más cercana, con continuidad entre frames. También
   arma el frame 3D para el avatar (`modules/motion.py`).
2. **Segmentación** (`modules/segmenter.py`): una seña empieza al levantar las manos y termina al bajarlas. Las manos
   apoyadas abajo se ignoran. La seña se recorta y se lleva a 30 frames. **El mismo paso prepara las muestras al grabar
   y al detectar.** La referencia del cuerpo se toma de los frames previos, donde los brazos no tapan los hombros.
3. **Features** (`modules/landmarks.py`): por frame, la posición de cada mano respecto a los hombros (trayectoria y
   altura), la forma de la mano respecto a su muñeca (configuración de los dedos) y la postura de codos y muñecas, sin
   depender de la distancia a la cámara.
4. **Modelo** (`train_model.py`): Random Forest con aumento de datos (espejo para personas zurdas, versión sin cuerpo
   visible, variaciones de corte y ruido). La evaluación es por persona.
5. **App** (`inclusion_app.py`): toda la lógica, separada del bucle de cámara (`main.py`) para poder probarla completa
   con frames y teclas simuladas.

El dataset (`data/dataset_v2.csv`) guarda los puntos crudos, así que si cambian las features no hay que volver a grabar.
Un dataset del formato anterior (sin codos) se respalda y se convierte solo al abrir la app; esas muestras quedan con
los codos en cero, así que conviene regrabarlas.

## Configuración

Todo en [`config.py`](config.py): cámara, segmentación, umbral de confianza, silencio para armar la oración,
servicios en línea (`USE_CLAUDE`, `USE_ONLINE_TTS`, `USE_ONLINE_STT`), avatar (`AVATAR_UDP_PORT`, carpeta de clips) y
nombres con acento (`DISPLAY_NAMES`).

## Pruebas

```bash
python -m unittest discover -s tests -t .
```

Corren sin cámara. Detalle de qué verifica cada una: [05_verificacion.md](../requerimientos/05_verificacion.md).

## Dataset anterior

`data/legacy/dataset_v1.csv` es el dataset de la versión anterior (11 señas, una persona). Usa otro formato
(solo la forma de la mano respecto a la muñeca, sin posición en el cuerpo), así que no sirve para el modelo actual.
Se conserva como referencia y para la prueba de regresión del segmentador.

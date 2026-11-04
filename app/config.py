import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")

DATASET_PATH = os.path.join(DATA_DIR, "dataset_v2.csv")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
MODEL_PATH = os.path.join(DATA_DIR, "model.pkl")
VOSK_MODEL_PATH = os.path.join(DATA_DIR, "vosk-model-small-es-0.42")

# Versión de las features del modelo. Si cambia, el modelo guardado ya no sirve
# (el dataset sí: guarda los puntos crudos).
FEATURE_VERSION = 4

# Toda seña se recorta y se remuestrea a este número de frames,
# igual al grabar que al detectar.
SEQUENCE_LENGTH = 30

# Cámara
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
POSE_EVERY_N_FRAMES = 1     # la pose (hombros, codos, muñecas) se calcula 1 de cada N frames
POSE_MODEL = "full"         # modelo de pose de MediaPipe: "lite" (rápido), "full" o "heavy" (más preciso)

# Segmentación de señas (en frames, ~30 fps)
SEGMENT_START_FRAMES = 3    # frames seguidos con manos para empezar una seña
SEGMENT_END_FRAMES = 8      # frames seguidos sin manos para terminarla
SEGMENT_MIN_FRAMES = 10     # más corto que esto se descarta
SEGMENT_MAX_FRAMES = 120    # más largo que esto se corta a la fuerza (~4 s)
SEGMENT_CONTEXT_FRAMES = 15 # frames sin manos de los que sale la referencia del cuerpo
RESTING_HAND_MARGIN = 1.5   # mano más abajo de hombros + 1.5 anchos de hombro = en reposo

# Avatar (ver requerimientos/06_avatar.md)
AVATAR_DIR = os.path.join(DATA_DIR, "avatar")   # un clip de movimiento por palabra
AVATAR_UDP_HOST = "127.0.0.1"   # a dónde se envía el movimiento en vivo (Blender)
AVATAR_UDP_PORT = 5005
AVATAR_PREROLL_FRAMES = 15      # frames antes de levantar las manos que entran al clip (~0.5 s)

# Detección
MIN_CONFIDENCE = 0.6        # debajo de esto no se muestra la predicción
SILENCE_SECONDS = 2.5       # sin manos este tiempo => se arma la oración
SUBTITLE_HISTORY = 5        # palabras visibles en el historial
BACKUP_EVERY = 50           # respaldo del dataset cada N muestras

# Servicios en línea (cada uno se puede apagar; ver requerimientos RNF-04)
USE_CLAUDE = True           # oración natural con Claude (requiere ANTHROPIC_API_KEY)
USE_ONLINE_TTS = True       # voz de Google (gTTS); si no, voz del sistema
USE_ONLINE_STT = True       # voz a texto de Google; si no, solo Vosk local

# Cómo se muestra y se dice cada etiqueta (las etiquetas se guardan sin acentos)
DISPLAY_NAMES = {
    "adios": "adiós",
    "buenos dias": "buenos días",
    "denada": "de nada",
    "perdon": "perdón",
}


def display_name(label):
    return DISPLAY_NAMES.get(label, label)

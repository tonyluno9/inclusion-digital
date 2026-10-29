import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")

DATASET_PATH = os.path.join(DATA_DIR, "dataset_v2.csv")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
MODEL_PATH = os.path.join(DATA_DIR, "model.pkl")
VOSK_MODEL_PATH = os.path.join(DATA_DIR, "vosk-model-small-es-0.42")

# Versión del formato de datos. Si cambia, el modelo guardado ya no sirve.
FEATURE_VERSION = 2

# Toda seña se recorta y se remuestrea a este número de frames,
# igual al grabar que al detectar.
SEQUENCE_LENGTH = 30

# Segmentación de señas (en frames, ~30 fps)
SEGMENT_START_FRAMES = 3    # frames seguidos con manos para empezar una seña
SEGMENT_END_FRAMES = 8      # frames seguidos sin manos para terminarla
SEGMENT_MIN_FRAMES = 10     # más corto que esto se descarta
SEGMENT_MAX_FRAMES = 90     # más largo que esto se corta a la fuerza

# Detección
MIN_CONFIDENCE = 0.6        # debajo de esto no se muestra la predicción
SILENCE_SECONDS = 2.5       # sin manos este tiempo => se arma la oración
BACKUP_EVERY = 50           # respaldo del dataset cada N muestras

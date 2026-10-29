"""
Formato de datos compartido por la grabación, el entrenamiento y la detección.

Frame "crudo" (RAW_FRAME_SIZE = 135 valores), lo que guarda el dataset:
    [0:63]    mano izquierda: 21 puntos x (x, y, z)
    [63:126]  mano derecha:   21 puntos x (x, y, z)
    [126:135] cuerpo: nariz, hombro izquierdo, hombro derecho (x, y, z)
x e y van en unidades de la altura de la imagen (x ya viene multiplicada por
ancho/alto), así el formato no depende de la resolución de la cámara.
Una mano o el cuerpo ausentes se guardan como ceros.

Las features (FEATURE_FRAME_SIZE = 126 valores) se calculan a partir del frame
crudo: posición de cada punto de la mano respecto al centro de los hombros,
dividida entre el ancho de hombros. Así se conserva hacia dónde se mueve la
mano y a qué altura está, sin depender de la distancia a la cámara.
"""
import numpy as np

HAND_POINTS = 21
HAND_SIZE = HAND_POINTS * 3          # 63
HANDS_SIZE = HAND_SIZE * 2           # 126
POSE_POINTS = (0, 11, 12)            # índices de MediaPipe Pose: nariz, hombros
POSE_SIZE = len(POSE_POINTS) * 3     # 9
RAW_FRAME_SIZE = HANDS_SIZE + POSE_SIZE
FEATURE_FRAME_SIZE = HANDS_SIZE

# Ancho de hombros típico (en alturas de imagen) cuando no se ve el cuerpo
DEFAULT_SCALE = 0.3
MAX_GAP_FRAMES = 5


def hands_present(frame) -> bool:
    return bool(np.any(np.asarray(frame)[:HANDS_SIZE] != 0))


def _slots(width):
    slots = [(0, HAND_SIZE), (HAND_SIZE, HANDS_SIZE)]
    if width >= RAW_FRAME_SIZE:
        slots.append((HANDS_SIZE, RAW_FRAME_SIZE))
    return slots


def fill_gaps(frames, max_gap=MAX_GAP_FRAMES):
    """Rellena por interpolación huecos cortos en los que MediaPipe perdió una
    mano (o el cuerpo) a mitad de la seña. Los huecos largos quedan en cero."""
    frames = np.array(frames, dtype=np.float32)
    for start, end in _slots(frames.shape[1]):
        block = frames[:, start:end]
        present = np.any(block != 0, axis=1)
        idx = np.flatnonzero(present)
        for a, b in zip(idx[:-1], idx[1:]):
            gap = b - a - 1
            if 0 < gap <= max_gap:
                for k in range(1, gap + 1):
                    t = k / (gap + 1)
                    block[a + k] = (1 - t) * block[a] + t * block[b]
    return frames


def trim(frames):
    """Quita los frames sin manos al principio y al final."""
    frames = np.asarray(frames, dtype=np.float32)
    present = np.any(frames[:, :HANDS_SIZE] != 0, axis=1)
    idx = np.flatnonzero(present)
    if len(idx) == 0:
        return frames[:0]
    return frames[idx[0]:idx[-1] + 1]


def resample(frames, length):
    """Lleva una secuencia de cualquier duración a `length` frames
    (vecino más cercano: no mezcla una mano presente con una ausente)."""
    frames = np.asarray(frames)
    idx = np.round(np.linspace(0, len(frames) - 1, length)).astype(int)
    return frames[idx]


def prepare_sequence(frames, length, min_frames):
    """Paso único que usan tanto la grabación como la detección:
    recortar, rellenar huecos y remuestrear. Devuelve None si es muy corta."""
    if len(frames) == 0:
        return None
    frames = trim(frames)
    if len(frames) < min_frames:
        return None
    return resample(fill_gaps(frames), length)


def _body_reference(seq):
    pose = seq[:, HANDS_SIZE:RAW_FRAME_SIZE].reshape(len(seq), len(POSE_POINTS), 3)
    shoulders = pose[:, 1:3, :2]
    valid = np.all(np.any(shoulders != 0, axis=2), axis=1)
    if valid.any():
        left = np.median(shoulders[valid, 0], axis=0)
        right = np.median(shoulders[valid, 1], axis=0)
        scale = float(np.linalg.norm(left - right))
        if scale > 1e-3:
            return (left + right) / 2, scale
    # Sin cuerpo visible: centrar en las manos con una escala típica
    hands = seq[:, :HANDS_SIZE].reshape(-1, 3)
    hands = hands[np.any(hands != 0, axis=1)]
    center = hands[:, :2].mean(axis=0) if len(hands) else np.zeros(2, dtype=np.float32)
    return center, DEFAULT_SCALE


def sequence_features(seq):
    """(T, 135) crudo -> (T, 126) features normalizadas respecto al cuerpo."""
    seq = np.asarray(seq, dtype=np.float32)
    center, scale = _body_reference(seq)
    hands = seq[:, :HANDS_SIZE].reshape(len(seq), 2, HAND_POINTS, 3).copy()
    present = np.any(hands != 0, axis=(2, 3))
    hands[..., :2] -= center
    hands /= scale
    hands[~present] = 0
    return hands.reshape(len(seq), FEATURE_FRAME_SIZE)


def mirror_features(feat):
    """Versión espejo de una o varias secuencias de features: intercambia la
    mano izquierda con la derecha e invierte x (para personas zurdas)."""
    feat = np.asarray(feat, dtype=np.float32)
    shape = feat.shape
    hands = feat.reshape(*shape[:-1], 2, HAND_POINTS, 3)[..., ::-1, :, :].copy()
    hands[..., 0] *= -1
    return hands.reshape(shape)

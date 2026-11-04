"""
Formato de datos compartido por la grabación, el entrenamiento y la detección.

Frame "crudo" (RAW_FRAME_SIZE = 147 valores), lo que guarda el dataset:
    [0:63]    mano izquierda: 21 puntos x (x, y, z)
    [63:126]  mano derecha:   21 puntos x (x, y, z)
    [126:147] cuerpo: nariz, hombro izq., hombro der., codo izq., codo der.,
              muñeca izq., muñeca der. (x, y, z)
x e y van en unidades de la altura de la imagen (x ya viene multiplicada por
ancho/alto), así el formato no depende de la resolución de la cámara.
Izquierda y derecha son las de la persona (ver landmark_detector.py).
Una mano o un punto del cuerpo ausentes se guardan como ceros.

El formato anterior (135 valores, sin codos ni muñecas del cuerpo) es un prefijo
de este: `upgrade_raw` lo completa con ceros.

Las features (FEATURE_FRAME_SIZE = 260 valores) se calculan a partir del frame
crudo, en tres bloques:
  - posición (126): cada punto de la mano respecto al centro de los hombros,
    dividida entre el ancho de hombros. Conserva hacia dónde se mueve la mano y
    a qué altura está, sin depender de la distancia a la cámara.
  - forma (126): cada punto respecto a su muñeca, dividido entre el tamaño de la
    mano. Describe la configuración de los dedos sin importar dónde esté la mano.
  - brazos (8): codos y muñecas del cuerpo (x, y) respecto a los hombros, igual
    que la posición. Distingue señas con el mismo recorrido de la mano pero con
    el brazo en otra postura.
"""
import numpy as np

HAND_POINTS = 21
HAND_SIZE = HAND_POINTS * 3          # 63
HANDS_SIZE = HAND_SIZE * 2           # 126
# Índices de MediaPipe Pose: nariz, hombros, codos, muñecas (pares izquierda, derecha)
POSE_POINTS = (0, 11, 12, 13, 14, 15, 16)
POSE_SIZE = len(POSE_POINTS) * 3     # 21
BODY_SIZE = 9                        # nariz y hombros: la referencia del cuerpo
ARMS_START = HANDS_SIZE + BODY_SIZE  # codos y muñecas: se mueven con la seña
RAW_FRAME_SIZE = HANDS_SIZE + POSE_SIZE
OLD_RAW_FRAME_SIZE = HANDS_SIZE + BODY_SIZE   # 135, formato anterior
ARM_FEATURES = 8                     # 2 codos y 2 muñecas, (x, y)
FEATURE_FRAME_SIZE = HANDS_SIZE * 2 + ARM_FEATURES

# Ancho de hombros típico (en alturas de imagen) cuando no se ve el cuerpo
DEFAULT_SCALE = 0.3
MAX_GAP_FRAMES = 5


def assign_slots(detections, previous, max_jump=0.25):
    """Decide en qué lugar (0 = izquierda, 1 = derecha) va cada mano detectada.

    detections: lista de (slot según MediaPipe, confianza, (x, y) de la muñeca).
    previous: [(x, y) o None, (x, y) o None], muñecas del frame anterior.
    La etiqueta izquierda/derecha de MediaPipe a veces parpadea; si una mano
    sigue cerca de donde estaba, conserva su lugar.
    """
    def dist(a, b):
        return float(np.hypot(a[0] - b[0], a[1] - b[1]))

    def by_label():
        order = sorted(range(len(detections)), key=lambda i: -detections[i][1])
        slots, used = [None] * len(detections), set()
        for i in order:
            slot = detections[i][0]
            if slot in used:
                slot = 1 - slot
            used.add(slot)
            slots[i] = slot
        return slots

    detections = detections[:2]
    known = [s for s in (0, 1) if previous[s] is not None]
    if not detections or not known:
        return by_label()

    if len(detections) == 1:
        wrist = detections[0][2]
        best = min(known, key=lambda s: dist(wrist, previous[s]))
        return [best] if dist(wrist, previous[best]) < max_jump else by_label()

    a, b = detections[0][2], detections[1][2]
    if len(known) == 2:
        keep = dist(a, previous[0]) + dist(b, previous[1])
        swap = dist(a, previous[1]) + dist(b, previous[0])
        if min(keep, swap) < 2 * max_jump:
            return [0, 1] if keep <= swap else [1, 0]
        return by_label()

    s = known[0]
    near = 0 if dist(a, previous[s]) <= dist(b, previous[s]) else 1
    if dist(detections[near][2], previous[s]) >= max_jump:
        return by_label()
    slots = [1 - s, 1 - s]
    slots[near] = s
    return slots


def hands_present(frame) -> bool:
    return bool(np.any(np.asarray(frame)[:HANDS_SIZE] != 0))


HAND_SLOTS = {"izquierda": 0, "derecha": 1}


def keep_hands(frame, mode):
    """Con una sola mano ("derecha" o "izquierda"), borra la otra del frame
    crudo. Con "dos" lo deja igual."""
    if mode not in HAND_SLOTS:
        return frame
    frame = np.array(frame, dtype=np.float32)
    other = 1 - HAND_SLOTS[mode]
    frame[other * HAND_SIZE:(other + 1) * HAND_SIZE] = 0
    return frame


def hand_coverage(frames):
    """Fracción de los frames en que se ve cada mano: {"izquierda": f, "derecha": f}."""
    frames = np.asarray(frames)
    if len(frames) == 0:
        return {side: 0.0 for side in HAND_SLOTS}
    return {side: float(np.mean(np.any(frames[:, s * HAND_SIZE:(s + 1) * HAND_SIZE] != 0, axis=1)))
            for side, s in HAND_SLOTS.items()}


def missing_hands(frames, mode, min_coverage):
    """Manos que la seña necesita (las dos, o solo la elegida) y que se vieron
    en menos de `min_coverage` de los frames."""
    needed = tuple(HAND_SLOTS) if mode == "dos" else (mode,)
    coverage = hand_coverage(frames)
    return [side for side in needed if coverage[side] < min_coverage]


def upgrade_raw(frames):
    """Completa frames del formato anterior (135 valores) con ceros en codos y
    muñecas del cuerpo. Los frames que ya tienen el formato actual no cambian."""
    frames = np.asarray(frames, dtype=np.float32)
    if frames.shape[-1] == RAW_FRAME_SIZE:
        return frames
    if frames.shape[-1] != OLD_RAW_FRAME_SIZE:
        raise ValueError(f"frame de {frames.shape[-1]} valores: se esperaban {RAW_FRAME_SIZE} u {OLD_RAW_FRAME_SIZE}")
    pad = np.zeros(frames.shape[:-1] + (RAW_FRAME_SIZE - OLD_RAW_FRAME_SIZE,), dtype=np.float32)
    return np.concatenate([frames, pad], axis=-1)


def _slots(width):
    """Partes que se rellenan por separado: cada mano, nariz y hombros juntos, y
    cada codo y muñeca (se puede perder uno sin el otro)."""
    slots = [(0, HAND_SIZE), (HAND_SIZE, HANDS_SIZE)]
    if width >= RAW_FRAME_SIZE:
        slots.append((HANDS_SIZE, ARMS_START))
        slots += [(i, i + 3) for i in range(ARMS_START, RAW_FRAME_SIZE, 3)]
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


def pose_valid(frame) -> bool:
    """True si el frame trae ambos hombros."""
    frame = np.asarray(frame)
    if len(frame) < RAW_FRAME_SIZE:
        return False
    return bool(np.any(frame[HANDS_SIZE + 3:HANDS_SIZE + 6] != 0) and np.any(frame[HANDS_SIZE + 6:HANDS_SIZE + 9] != 0))


def elbows_visible(frame) -> bool:
    """True si el frame trae al menos un codo."""
    frame = np.asarray(frame)
    if len(frame) < RAW_FRAME_SIZE:
        return False
    return bool(np.any(frame[ARMS_START:ARMS_START + 6] != 0))


def drop_resting_hands(frame, body, margin):
    """Quita las manos cuya muñeca está más de `margin` anchos de hombro por
    debajo de la línea de los hombros (manos apoyadas en la mesa o las piernas,
    que no están haciendo una seña). `body` es la pose del cuerpo (sus primeros
    9 valores son nariz y hombros)."""
    if body is None:
        return frame
    shoulders = np.asarray(body, dtype=np.float32)[3:9].reshape(2, 3)
    width = float(np.linalg.norm(shoulders[0, :2] - shoulders[1, :2]))
    if width < 1e-3:
        return frame
    limit = shoulders[:, 1].mean() + margin * width
    out = None
    for start in (0, HAND_SIZE):
        wrist_y = frame[start + 1]
        if np.any(frame[start:start + HAND_SIZE] != 0) and wrist_y > limit:
            if out is None:
                out = np.array(frame, dtype=np.float32, copy=True)
            out[start:start + HAND_SIZE] = 0
    return frame if out is None else out


def body_reference_pose(frames, min_valid=3):
    """Mediana de la pose del cuerpo en frames donde se ven ambos hombros.
    Devuelve None si no hay suficientes. Como referencia solo se usan nariz y
    hombros; codos y muñecas van incluidos para que el tamaño coincida."""
    frames = np.asarray(frames, dtype=np.float32)
    if len(frames) == 0 or frames.shape[1] < RAW_FRAME_SIZE:
        return None
    pose = frames[:, HANDS_SIZE:RAW_FRAME_SIZE]
    shoulders = pose[:, 3:9].reshape(len(pose), 2, 3)[..., :2]
    valid = np.all(np.any(shoulders != 0, axis=2), axis=1)
    if valid.sum() < min_valid:
        return None
    return np.median(pose[valid], axis=0)


def prepare_sequence(frames, length, min_frames, body=None):
    """Paso único que usan tanto la grabación como la detección:
    recortar, rellenar huecos y remuestrear. Devuelve None si es muy corta.

    `body` es la pose de referencia tomada antes de la seña (con las manos
    abajo, los brazos no tapan los hombros). Si se da, reemplaza nariz y
    hombros en todos los frames de la seña; codos y muñecas siguen siendo los
    de cada frame, porque son parte del movimiento."""
    if len(frames) == 0:
        return None
    frames = trim(frames)
    if len(frames) < min_frames:
        return None
    out = resample(fill_gaps(frames), length)
    if body is not None and out.shape[1] >= RAW_FRAME_SIZE:
        out = out.copy()
        out[:, HANDS_SIZE:ARMS_START] = np.asarray(body, dtype=np.float32)[:BODY_SIZE]
    return out


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
    """(T, 147) crudo -> (T, 260) features: posición respecto al cuerpo, forma
    de la mano y postura de los brazos."""
    seq = np.asarray(seq, dtype=np.float32)
    center, scale = _body_reference(seq)
    hands = seq[:, :HANDS_SIZE].reshape(len(seq), 2, HAND_POINTS, 3)
    present = np.any(hands != 0, axis=(2, 3))

    position = hands.copy()
    position[..., :2] -= center
    position /= scale
    position[~present] = 0

    shape = hands - hands[:, :, :1, :]                     # respecto a la muñeca
    size = np.linalg.norm(shape[:, :, 9, :2], axis=-1)     # muñeca -> nudillo del dedo medio
    shape = shape / np.maximum(size, 1e-3)[..., None, None]
    shape[~present] = 0

    arms = seq[:, ARMS_START:RAW_FRAME_SIZE].reshape(len(seq), 4, 3)[..., :2]   # codos, muñecas
    seen = np.any(arms != 0, axis=-1)
    arms = (arms - center) / scale
    arms[~seen] = 0

    hands_part = np.concatenate([position, shape], axis=1).reshape(len(seq), HANDS_SIZE * 2)
    return np.concatenate([hands_part, arms.reshape(len(seq), ARM_FEATURES)], axis=1)


def mirror_features(feat):
    """Versión espejo de una o varias secuencias de features: intercambia el
    lado izquierdo con el derecho e invierte x (para personas zurdas)."""
    feat = np.asarray(feat, dtype=np.float32)
    lead = feat.shape[:-1]
    blocks = feat[..., :HANDS_SIZE * 2].reshape(*lead, 2, 2, HAND_POINTS, 3)   # bloque, mano, punto, xyz
    hands = blocks[..., ::-1, :, :].copy()
    hands[..., 0] *= -1
    arms = feat[..., HANDS_SIZE * 2:].reshape(*lead, 2, 2, 2)                  # codo/muñeca, lado, xy
    arms = arms[..., ::-1, :].copy()
    arms[..., 0] *= -1
    return np.concatenate([hands.reshape(*lead, HANDS_SIZE * 2), arms.reshape(*lead, ARM_FEATURES)], axis=-1)

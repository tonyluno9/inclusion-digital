"""Señas sintéticas en formato crudo para probar el pipeline sin cámara."""
import numpy as np

from modules.landmarks import ARMS_START, HAND_POINTS, HAND_SIZE, HANDS_SIZE, RAW_FRAME_SIZE

_SHAPE = np.random.RandomState(7).normal(0, 0.15, (HAND_POINTS, 3))
_SHAPE[0] = 0  # muñeca

TRAJECTORIES = {
    "arriba": lambda t: np.stack([0.3 + 0 * t, 0.8 - 1.2 * t], axis=1),
    "derecha": lambda t: np.stack([-0.2 + 1.0 * t, 0.2 + 0 * t], axis=1),
    "circulo": lambda t: np.stack([0.3 + 0.4 * np.cos(2 * np.pi * t), 0.2 + 0.4 * np.sin(2 * np.pi * t)], axis=1),
}


def make_sign(label, n_frames, center=(0.9, 0.6), scale=0.3, hand_slot=1, mirrored=False, rng=None, noise=0.01):
    """Una seña con el cuerpo en `center` y ancho de hombros `scale`.
    `mirrored` simula a una persona zurda: trayectoria en espejo."""
    rng = rng or np.random
    t = np.linspace(0, 1, n_frames)
    path = TRAJECTORIES[label](t)
    shape = _SHAPE.copy()
    if mirrored:
        path = path * (-1, 1)
        shape[:, 0] *= -1
    frames = np.zeros((n_frames, RAW_FRAME_SIZE), dtype=np.float32)
    cx, cy = center
    off = hand_slot * HAND_SIZE
    for i in range(n_frames):
        pts = np.zeros((HAND_POINTS, 3))
        pts[:, :2] = (path[i] + shape[:, :2] + rng.normal(0, noise, (HAND_POINTS, 2))) * scale + (cx, cy)
        pts[:, 2] = shape[:, 2] * scale
        frames[i, off:off + HAND_SIZE] = pts.reshape(-1)
        frames[i, HANDS_SIZE:] = body_pose(center, scale)
        # El brazo que seña sigue a la mano: muñeca del cuerpo en la muñeca de
        # la mano y codo abajo, entre el hombro y la muñeca
        side = hand_slot
        shoulder = np.array((cx + (side - 0.5) * scale, cy))
        wrist = pts[0, :2]
        elbow = (shoulder + wrist) / 2 + (0, 0.5 * scale)
        frames[i, ARMS_START + side * 3: ARMS_START + side * 3 + 2] = elbow
        frames[i, ARMS_START + 6 + side * 3: ARMS_START + 6 + side * 3 + 2] = wrist
    return frames


def body_pose(center=(0.9, 0.6), scale=0.3):
    """Pose del cuerpo (21 valores) con los brazos abajo, en reposo."""
    cx, cy = center
    left, right = cx - scale / 2, cx + scale / 2
    pose = [(cx, cy - 0.6 * scale, -0.5), (left, cy, -0.3), (right, cy, -0.3),
            (left, cy + 0.9 * scale, -0.2), (right, cy + 0.9 * scale, -0.2),     # codos
            (left, cy + 1.7 * scale, -0.2), (right, cy + 1.7 * scale, -0.2)]     # muñecas
    return np.array(pose, dtype=np.float32).reshape(-1)


def stream(sign, pad=20):
    """Frames sin manos (pero con cuerpo, brazos abajo) antes y después de la seña."""
    empty = np.zeros((pad, RAW_FRAME_SIZE), dtype=np.float32)
    shoulders = sign[0, HANDS_SIZE + 3:HANDS_SIZE + 9].reshape(2, 3)
    scale = float(shoulders[1, 0] - shoulders[0, 0])
    center = (float(shoulders[:, 0].mean()), float(shoulders[0, 1]))
    empty[:, HANDS_SIZE:] = body_pose(center, abs(scale) or 0.3)
    return np.concatenate([empty, sign, empty])

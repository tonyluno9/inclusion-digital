"""Señas sintéticas en formato crudo para probar el pipeline sin cámara."""
import numpy as np

from modules.landmarks import HAND_POINTS, HAND_SIZE, HANDS_SIZE, RAW_FRAME_SIZE

_SHAPE = np.random.RandomState(7).normal(0, 0.15, (HAND_POINTS, 3))
_SHAPE[0] = 0  # muñeca

TRAJECTORIES = {
    "arriba": lambda t: np.stack([0.3 + 0 * t, 0.8 - 1.2 * t], axis=1),
    "derecha": lambda t: np.stack([-0.2 + 1.0 * t, 0.2 + 0 * t], axis=1),
    "circulo": lambda t: np.stack([0.3 + 0.4 * np.cos(2 * np.pi * t), 0.2 + 0.4 * np.sin(2 * np.pi * t)], axis=1),
}


def make_sign(label, n_frames, center=(0.9, 0.6), scale=0.3, hand_slot=1, mirrored=False, rng=None):
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
        pts[:, :2] = (path[i] + shape[:, :2] + rng.normal(0, 0.01, (HAND_POINTS, 2))) * scale + (cx, cy)
        pts[:, 2] = shape[:, 2] * scale
        frames[i, off:off + HAND_SIZE] = pts.reshape(-1)
        pose = [(cx, cy - 0.6 * scale, -0.5), (cx - scale / 2, cy, -0.3), (cx + scale / 2, cy, -0.3)]
        frames[i, HANDS_SIZE:] = np.array(pose).reshape(-1)
    return frames


def stream(sign, pad=20):
    """Frames sin manos (pero con cuerpo) antes y después de la seña."""
    empty = np.zeros((pad, RAW_FRAME_SIZE), dtype=np.float32)
    empty[:, HANDS_SIZE:] = sign[0, HANDS_SIZE:]
    return np.concatenate([empty, sign, empty])

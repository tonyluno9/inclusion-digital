"""Movimiento 3D para el avatar: coordenadas, suavizado, clips por palabra y envío en vivo.

Un frame de movimiento ("world") es un dict:
    {"pose": (33, 3) o None, "vis": (33,) o None, "left": (21, 3) o None, "right": (21, 3) o None}
en metros, con origen en el centro de las caderas y ejes de la persona:
x hacia su izquierda, y hacia arriba, z hacia adelante (hacia la cámara).
`left_*` y `left` son siempre el lado izquierdo de la persona. Las manos ya
van colocadas en el cuerpo: su muñeca coincide con la del cuerpo. Sin cuerpo
no hay dónde ponerlas, así que también quedan en None.

El formato del clip y de los mensajes UDP está en requerimientos/06_avatar.md.
"""
import json
import math
import os
import re
import socket
import time
from collections import deque

import numpy as np

CLIP_FORMAT = "inclusion-movimiento"
CLIP_VERSION = 1
COORDS = ("metros; origen en el centro de las caderas; x hacia la izquierda de la persona, "
          "y hacia arriba, z hacia adelante (hacia la cámara)")

POSE_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner", "right_eye",
    "right_eye_outer", "left_ear", "right_ear", "mouth_left", "mouth_right", "left_shoulder",
    "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist", "left_pinky",
    "right_pinky", "left_index", "right_index", "left_thumb", "right_thumb", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]
HAND_NAMES = [
    "wrist", "thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip", "index_finger_mcp", "index_finger_pip",
    "index_finger_dip", "index_finger_tip", "middle_finger_mcp", "middle_finger_pip", "middle_finger_dip",
    "middle_finger_tip", "ring_finger_mcp", "ring_finger_pip", "ring_finger_dip", "ring_finger_tip",
    "pinky_mcp", "pinky_pip", "pinky_dip", "pinky_tip",
]
POSE_LR_PAIRS = [(1, 4), (2, 5), (3, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16), (17, 18),
                 (19, 20), (21, 22), (23, 24), (25, 26), (27, 28), (29, 30), (31, 32)]
LEFT_WRIST, RIGHT_WRIST = 15, 16
PARTS = ("pose", "left", "right")


def empty_world():
    return {"pose": None, "vis": None, "left": None, "right": None}


def world_frame(pose, vis, hands):
    """Arma un frame de movimiento a partir de los world landmarks de MediaPipe
    calculados sobre la imagen en espejo (pose ya en orden anatómico).

    En la imagen en espejo, x de MediaPipe apunta a la derecha de la persona,
    y hacia abajo y z se aleja de la cámara: invertir los tres ejes deja x a la
    izquierda de la persona, y arriba y z hacia adelante."""
    out = empty_world()
    if pose is not None:
        out["pose"] = -np.asarray(pose, dtype=np.float32)
        out["vis"] = np.asarray(vis, dtype=np.float32) if vis is not None else np.ones(len(pose), np.float32)
    if out["pose"] is None:
        return out
    for side, wrist in (("left", LEFT_WRIST), ("right", RIGHT_WRIST)):
        hand = hands[0 if side == "left" else 1]
        if hand is None:
            continue
        hand = -np.asarray(hand, dtype=np.float32)
        out[side] = hand - hand[0] + out["pose"][wrist]
    return out


class OneEuroFilter:
    """Filtro One Euro (Casiez et al., 2012): suaviza mucho cuando el punto está
    quieto (quita el temblor) y poco cuando se mueve rápido (no se atrasa)."""

    def __init__(self, min_cutoff=1.5, beta=0.5, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self._x = self._dx = self._t = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        x = np.asarray(x, dtype=np.float32)
        if self._x is None or self._x.shape != x.shape or t <= self._t:
            self._x, self._dx, self._t = x, np.zeros_like(x), t
            return x
        dt = t - self._t
        dx = (x - self._x) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        self._dx = a_d * dx + (1 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * np.abs(self._dx)
        a = self._alpha(cutoff, dt)
        self._x = a * x + (1 - a) * self._x
        self._t = t
        return self._x


class LiveSmoother:
    """Un filtro por parte; si una parte desaparece, su filtro empieza de nuevo."""

    def __init__(self, **kwargs):
        self.filters = {part: OneEuroFilter(**kwargs) for part in PARTS}

    def __call__(self, world, t):
        out = dict(world)
        for part in PARTS:
            if world[part] is None:
                self.filters[part].reset()
            else:
                out[part] = self.filters[part](world[part], t)
        return out


def fill_short_gaps(frames, max_gap=5):
    """Rellena por interpolación los huecos cortos de cada parte (pose y manos)
    en una lista de frames de movimiento. Los huecos largos quedan en None."""
    frames = [dict(f) for f in frames]
    for part in PARTS:
        idx = [i for i, f in enumerate(frames) if f[part] is not None]
        for a, b in zip(idx[:-1], idx[1:]):
            gap = b - a - 1
            if 0 < gap <= max_gap:
                for k in range(1, gap + 1):
                    w = k / (gap + 1)
                    frames[a + k][part] = (1 - w) * frames[a][part] + w * frames[b][part]
                    if part == "pose":
                        va, vb = frames[a]["vis"], frames[b]["vis"]
                        frames[a + k]["vis"] = (1 - w) * va + w * vb
    return frames


class MotionRecorder:
    """Junta los frames de movimiento de una seña, con unos frames de antes
    (para que la animación empiece en reposo)."""

    def __init__(self, preroll_frames=15, max_frames=600):
        self._recent = deque(maxlen=max(1, preroll_frames))
        self.max_frames = max_frames
        self.frames = None

    @property
    def recording(self):
        return self.frames is not None

    def push(self, world, t):
        item = (t, world)
        if self.frames is None:
            self._recent.append(item)
        elif len(self.frames) < self.max_frames:
            self.frames.append(item)

    def begin(self):
        self.frames = list(self._recent)
        self._recent.clear()

    def cancel(self):
        self.frames = None

    def finish(self):
        """Devuelve [(t, frame)] desde el inicio y deja de grabar."""
        frames, self.frames = self.frames or [], None
        return frames


def _rounded(a):
    return None if a is None else np.round(np.asarray(a, dtype=np.float64), 4).tolist()


def frame_to_json(world, t):
    return {"t": round(float(t), 4), "pose": _rounded(world["pose"]), "vis": _rounded(world["vis"]),
            "left": _rounded(world["left"]), "right": _rounded(world["right"])}


def make_clip(timed_frames, word, person="anonimo"):
    """Clip listo para guardar a partir de [(t, frame)]. Rellena huecos cortos."""
    if not timed_frames:
        raise ValueError("el clip no tiene frames")
    t0 = timed_frames[0][0]
    times = [t - t0 for t, _ in timed_frames]
    frames = fill_short_gaps([f for _, f in timed_frames])
    duration = times[-1]
    fps = (len(times) - 1) / duration if duration > 0 else 30.0
    return {
        "format": CLIP_FORMAT,
        "version": CLIP_VERSION,
        "word": word,
        "person": person,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "fps": round(fps, 2),
        "duration": round(duration, 3),
        "coords": COORDS,
        "pose_names": POSE_NAMES,
        "hand_names": HAND_NAMES,
        "frames": [frame_to_json(f, t) for t, f in zip(times, frames)],
    }


def validate_clip(clip):
    if not isinstance(clip, dict) or clip.get("format") != CLIP_FORMAT:
        raise ValueError("no es un clip de movimiento de INCLUSION")
    if clip.get("version") != CLIP_VERSION:
        raise ValueError(f"versión de clip {clip.get('version')} no soportada (se espera {CLIP_VERSION})")
    if not clip.get("frames"):
        raise ValueError("el clip no tiene frames")
    return clip


class ClipStore:
    """Un archivo por palabra en `directory`: <palabra>.json, y la toma anterior
    en <palabra>.prev.json para poder deshacer."""

    def __init__(self, directory):
        self.directory = directory

    @staticmethod
    def filename(word):
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", word.strip().lower()) or "_"

    def path(self, word):
        return os.path.join(self.directory, self.filename(word) + ".json")

    def _prev(self, word):
        return os.path.join(self.directory, self.filename(word) + ".prev.json")

    def save(self, clip):
        os.makedirs(self.directory, exist_ok=True)
        path, prev = self.path(clip["word"]), self._prev(clip["word"])
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clip, f, ensure_ascii=False, separators=(",", ":"))
        if os.path.exists(path):
            os.replace(path, prev)
        elif os.path.exists(prev):
            os.remove(prev)
        os.replace(tmp, path)
        return path

    def undo(self, word):
        """Deshace la última toma: vuelve la anterior o borra el clip.
        Devuelve "restaurado", "borrado" o None si no había clip."""
        path, prev = self.path(word), self._prev(word)
        if not os.path.exists(path):
            return None
        if os.path.exists(prev):
            os.replace(prev, path)
            return "restaurado"
        os.remove(path)
        return "borrado"

    def load(self, word):
        with open(self.path(word), encoding="utf-8") as f:
            return validate_clip(json.load(f))

    def words(self):
        if not os.path.isdir(self.directory):
            return []
        names = [n[:-5] for n in os.listdir(self.directory) if n.endswith(".json") and not n.endswith(".prev.json")]
        return sorted(names)


class LiveSender:
    """Envía frames de movimiento por UDP (un JSON por datagrama). Nunca lanza
    errores ni bloquea: si nadie escucha, los datagramas se pierden."""

    def __init__(self, host="127.0.0.1", port=5005):
        self.address = (host, port)
        self.sent = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)

    def _send(self, message):
        try:
            self._sock.sendto(json.dumps(message, separators=(",", ":")).encode("utf-8"), self.address)
            self.sent += 1
        except OSError:
            pass

    def send_frame(self, world, t):
        self._send({"type": "frame", **frame_to_json(world, t)})

    def send_clip(self, word, path):
        self._send({"type": "clip", "word": word, "path": os.path.abspath(path)})

    def close(self):
        self._sock.close()

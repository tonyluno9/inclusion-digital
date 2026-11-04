import os
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import urllib.request

# Menos ruido de MediaPipe/TensorFlow Lite en la consola
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from modules.landmarks import HAND_SIZE, HANDS_SIZE, POSE_POINTS, RAW_FRAME_SIZE, assign_slots
from modules.motion import POSE_LR_PAIRS, empty_world, world_frame

_MODEL_URLS = {
    "hand_landmarker.task":
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
    **{f"pose_landmarker_{v}.task":
       f"https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_{v}/float16/latest/"
       f"pose_landmarker_{v}.task" for v in ("lite", "full", "heavy")},
}

HAND_CONNECTIONS = [(c.start, c.end) for c in vision.HandLandmarksConnections.HAND_CONNECTIONS]
_HAND_COLORS = ((255, 160, 60), (60, 200, 255))  # BGR: izquierda, derecha


def ensure_model(models_dir, name):
    """Descarga el modelo de MediaPipe la primera vez (≈ 5-8 MB, de Google)."""
    path = os.path.join(models_dir, name)
    if not os.path.exists(path):
        os.makedirs(models_dir, exist_ok=True)
        print(f"[Detector] Descargando {name}...")
        tmp_path = path + ".part"
        try:
            urllib.request.urlretrieve(_MODEL_URLS[name], tmp_path)
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError(
                f"No se pudo descargar el modelo {name} ({e}). Conéctate a internet la primera vez, "
                f"o descárgalo de {_MODEL_URLS[name]} y guárdalo en {path}") from e
        os.replace(tmp_path, path)
    return path


_ARM_CHAINS = ((11, 13, 15), (12, 14, 16))    # hombro, codo, muñeca (izquierda, derecha)
MIN_VISIBILITY = 0.5
WORLD_HOLD_FRAMES = 5
WRIST_MATCH = 0.15     # mano a menos de esto (alturas de imagen) de una muñeca del cuerpo = ese lado


def hand_slot_hint(label, wrist, pose_wrists):
    """Lado (0 = izquierda, 1 = derecha de la persona) de una mano detectada.

    Primero, la muñeca del cuerpo más cercana (los lados del cuerpo son
    anatómicos). Si no se ve el cuerpo, la etiqueta de MediaPipe, invertida:
    MediaPipe etiqueta como si la imagen no estuviera en espejo, y main.py la
    voltea (comprobado con la forma 3D de la mano, ver test_integration_mediapipe)."""
    if all(p is not None for p in pose_wrists):
        dists = [float(np.hypot(wrist[0] - p[0], wrist[1] - p[1])) for p in pose_wrists]
        side = int(np.argmin(dists))
        if dists[side] < WRIST_MATCH:
            return side
    return 1 if label == "Left" else 0


def anatomical_order(shoulder_x_left, shoulder_x_right):
    """Índices de MediaPipe Pose reordenados para que `left_*` sea el lado
    izquierdo de la persona. La imagen llega en espejo: ahí el hombro izquierdo
    de la persona queda a la izquierda de la imagen. Si MediaPipe los etiquetó
    al revés, se intercambian todos los pares izquierda/derecha."""
    order = list(range(33))
    if shoulder_x_left > shoulder_x_right:
        for a, b in POSE_LR_PAIRS:
            order[a], order[b] = b, a
    return order


class LandmarkDetector:
    """Detecta manos, hombros, codos y muñecas con la API Tasks de MediaPipe.

    Izquierda y derecha son siempre las de la persona:
    - cuerpo: se decide por la posición de los hombros (`anatomical_order`);
    - manos: por la muñeca del cuerpo más cercana (`hand_slot_hint`), y
      `assign_slots` mantiene cada mano en su lugar entre frames.

    Además del frame crudo para el reconocedor, `self.world` guarda el frame en
    coordenadas 3D para el avatar (ver modules/motion.py).
    """

    def __init__(self, models_dir, min_detection_confidence=0.5, min_tracking_confidence=0.5,
                 pose_every=1, pose_model="full"):
        hand_options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=ensure_model(models_dir, "hand_landmarker.task")),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        pose_options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=ensure_model(models_dir, f"pose_landmarker_{pose_model}.task")),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        self.hands = vision.HandLandmarker.create_from_options(hand_options)
        self.pose = vision.PoseLandmarker.create_from_options(pose_options)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pose")
        self._last_ts = 0
        # Con pose_every > 1 la pose se reutiliza entre cálculos (más rápido, codos menos precisos)
        self.pose_every = max(1, pose_every)
        self._frame_count = 0
        self._prev_wrists = [None, None]
        self._wrist_age = [0, 0]
        self._last_pose = np.zeros(RAW_FRAME_SIZE - HANDS_SIZE, dtype=np.float32)
        self._last_arms = [[], []]          # puntos en pantalla de cada brazo, para dibujarlos
        self._pose_wrists = [None, None]    # muñecas del cuerpo (x·aspecto, y), para ubicar las manos
        self._last_world_pose = None
        self._last_vis = None
        self._world_age = 0                 # frames desde el último cuerpo 3D válido
        self.world = empty_world()

    def _timestamp(self):
        # La API VIDEO exige timestamps estrictamente crecientes
        ts = int(time.monotonic() * 1000)
        self._last_ts = max(ts, self._last_ts + 1)
        return self._last_ts

    def process(self, frame):
        """Devuelve (frame con manos y brazos dibujados, frame crudo de 147 valores)."""
        h, w = frame.shape[:2]
        aspect = w / h
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = self._timestamp()
        run_pose = self._frame_count % self.pose_every == 0
        self._frame_count += 1
        # Manos y pose a la vez: MediaPipe suelta el GIL mientras calcula
        pending = self._pool.submit(self.pose.detect_for_video, image, ts) if run_pose else None
        hand_result = self.hands.detect_for_video(image, ts)
        pose_result = pending.result() if pending else None

        raw = np.zeros(RAW_FRAME_SIZE, dtype=np.float32)
        if run_pose:
            self._update_pose(pose_result, aspect, w, h)

        # Cada mano va a su lugar fijo (izquierda / derecha), con continuidad
        # entre frames por si la detección parpadea.
        hands = list(zip(hand_result.hand_landmarks, hand_result.handedness))[:2]
        detections = []
        for lm, hd in hands:
            wrist = (lm[0].x * aspect, lm[0].y)
            detections.append((hand_slot_hint(hd[0].category_name, wrist, self._pose_wrists), hd[0].score, wrist))
        slots = assign_slots(detections, self._prev_wrists)
        # Recordar cada muñeca unos frames aunque la mano se pierda un momento
        self._wrist_age = [age + 1 for age in self._wrist_age]
        for (landmarks, _), slot, det in zip(hands, slots, detections):
            self._prev_wrists[slot] = det[2]
            self._wrist_age[slot] = 0
        self._prev_wrists = [w if age <= 5 else None for w, age in zip(self._prev_wrists, self._wrist_age)]
        world_hands = [None, None]
        hand_world = hand_result.hand_world_landmarks or [None] * len(hands)
        for (landmarks, _), slot, world_lm in zip(hands, slots, hand_world):
            offset = slot * HAND_SIZE
            wrist_z = landmarks[0].z
            for i, lm in enumerate(landmarks):
                raw[offset + i * 3: offset + i * 3 + 3] = (lm.x * aspect, lm.y, lm.z - wrist_z)
            if world_lm is not None:
                world_hands[slot] = [(p.x, p.y, p.z) for p in world_lm]

        raw[HANDS_SIZE:] = self._last_pose

        for side, points in enumerate(self._last_arms):
            for a, b in zip(points[:-1], points[1:]):
                cv2.line(frame, a, b, _HAND_COLORS[side], 4, cv2.LINE_AA)
            for p in points:
                cv2.circle(frame, p, 6, (255, 255, 255), -1, cv2.LINE_AA)
        for (landmarks, _), slot in zip(hands, slots):
            self._draw_hand(frame, landmarks, _HAND_COLORS[slot])

        self.world = world_frame(self._last_world_pose, self._last_vis, world_hands)
        return frame, raw

    def _update_pose(self, pose_result, aspect, w, h):
        self._last_pose[:] = 0
        self._last_arms = [[], []]
        self._pose_wrists = [None, None]
        # MediaPipe a veces pierde el cuerpo un frame: para el avatar se conserva
        # el último cuerpo 3D unos frames (el reconocedor rellena sus propios huecos)
        self._world_age += 1
        if self._world_age > WORLD_HOLD_FRAMES:
            self._last_world_pose = None
            self._last_vis = None
        if not pose_result.pose_landmarks:
            return
        pose = pose_result.pose_landmarks[0]
        order = anatomical_order(pose[11].x, pose[12].x)
        pose = [pose[i] for i in order]

        def visible(i):
            return (pose[i].visibility or 0) > MIN_VISIBILITY

        shoulders_visible = visible(11) and visible(12)
        for k, i in enumerate(POSE_POINTS):
            # Nariz y hombros solo con ambos hombros (son la referencia del cuerpo);
            # codos y muñecas cada uno por su cuenta
            if (k < 3 and shoulders_visible) or (k >= 3 and visible(i)):
                lm = pose[i]
                self._last_pose[k * 3: k * 3 + 3] = (lm.x * aspect, lm.y, lm.z)
        for side, chain in enumerate(_ARM_CHAINS):
            pts = []
            for i in chain:
                if not visible(i):
                    break
                pts.append((int(pose[i].x * w), int(pose[i].y * h)))
            self._last_arms[side] = pts
            wrist = pose[chain[2]]
            if visible(chain[2]):
                self._pose_wrists[side] = (wrist.x * aspect, wrist.y)

        if pose_result.pose_world_landmarks:
            world = pose_result.pose_world_landmarks[0]
            self._last_world_pose = [(world[i].x, world[i].y, world[i].z) for i in order]
            self._last_vis = [float(p.visibility or 0) for p in pose]
            self._world_age = 0

    @staticmethod
    def _draw_hand(frame, landmarks, color):
        h, w = frame.shape[:2]
        pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
        for a, b in HAND_CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], color, 2, cv2.LINE_AA)
        for p in pts:
            cv2.circle(frame, p, 3, (255, 255, 255), -1, cv2.LINE_AA)

    def close(self):
        self.hands.close()
        self.pose.close()
        self._pool.shutdown(wait=True)

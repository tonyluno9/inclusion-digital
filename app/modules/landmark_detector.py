import os
import time
import urllib.error
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

_MODEL_URLS = {
    "hand_landmarker.task":
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
    "pose_landmarker_lite.task":
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
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


class LandmarkDetector:
    """Detecta manos (y hombros como referencia) con la API Tasks de MediaPipe.

    Cada mano va siempre en su posición fija del vector según MediaPipe la
    clasifique como izquierda o derecha. MediaPipe asume imagen en espejo; como
    main.py voltea el frame, la etiqueta puede quedar invertida respecto a la
    mano real, pero es consistente, que es lo que importa para el modelo.
    """

    def __init__(self, models_dir, min_detection_confidence=0.5, min_tracking_confidence=0.5,
                 pose_every=2):
        hand_options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=ensure_model(models_dir, "hand_landmarker.task")),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        pose_options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=ensure_model(models_dir, "pose_landmarker_lite.task")),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        self.hands = vision.HandLandmarker.create_from_options(hand_options)
        self.pose = vision.PoseLandmarker.create_from_options(pose_options)
        self._last_ts = 0
        # Los hombros se mueven poco: la pose se calcula cada `pose_every` frames
        self.pose_every = max(1, pose_every)
        self._frame_count = 0
        self._prev_wrists = [None, None]
        self._wrist_age = [0, 0]
        self._last_pose = np.zeros(RAW_FRAME_SIZE - HANDS_SIZE, dtype=np.float32)

    def _timestamp(self):
        # La API VIDEO exige timestamps estrictamente crecientes
        ts = int(time.monotonic() * 1000)
        self._last_ts = max(ts, self._last_ts + 1)
        return self._last_ts

    def process(self, frame):
        """Devuelve (frame con las manos dibujadas, frame crudo de 135 valores)."""
        h, w = frame.shape[:2]
        aspect = w / h
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = self._timestamp()
        hand_result = self.hands.detect_for_video(image, ts)
        run_pose = self._frame_count % self.pose_every == 0
        self._frame_count += 1
        pose_result = self.pose.detect_for_video(image, ts) if run_pose else None

        raw = np.zeros(RAW_FRAME_SIZE, dtype=np.float32)

        # Cada mano va a su lugar fijo (izquierda / derecha), con continuidad
        # entre frames por si la etiqueta de MediaPipe parpadea.
        hands = list(zip(hand_result.hand_landmarks, hand_result.handedness))[:2]
        detections = [(0 if hd[0].category_name == "Left" else 1, hd[0].score,
                       (lm[0].x * aspect, lm[0].y)) for lm, hd in hands]
        slots = assign_slots(detections, self._prev_wrists)
        # Recordar cada muñeca unos frames aunque la mano se pierda un momento
        self._wrist_age = [age + 1 for age in self._wrist_age]
        for (landmarks, _), slot, det in zip(hands, slots, detections):
            self._prev_wrists[slot] = det[2]
            self._wrist_age[slot] = 0
        self._prev_wrists = [w if age <= 5 else None for w, age in zip(self._prev_wrists, self._wrist_age)]
        for (landmarks, _), slot, det in zip(hands, slots, detections):
            offset = slot * HAND_SIZE
            wrist_z = landmarks[0].z
            for i, lm in enumerate(landmarks):
                raw[offset + i * 3: offset + i * 3 + 3] = (lm.x * aspect, lm.y, lm.z - wrist_z)
            self._draw_hand(frame, landmarks, _HAND_COLORS[slot])

        if run_pose:
            self._last_pose[:] = 0
            if pose_result.pose_landmarks:
                pose = pose_result.pose_landmarks[0]
                shoulders_visible = all((pose[i].visibility or 0) > 0.5 for i in (11, 12))
                if shoulders_visible:
                    for k, i in enumerate(POSE_POINTS):
                        lm = pose[i]
                        self._last_pose[k * 3: k * 3 + 3] = (lm.x * aspect, lm.y, lm.z)
        raw[HANDS_SIZE:] = self._last_pose

        return frame, raw

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

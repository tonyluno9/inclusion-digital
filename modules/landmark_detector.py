import os
import time
import urllib.request

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from modules.landmarks import HAND_SIZE, HANDS_SIZE, POSE_POINTS, RAW_FRAME_SIZE

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
        urllib.request.urlretrieve(_MODEL_URLS[name], tmp_path)
        os.replace(tmp_path, path)
    return path


class LandmarkDetector:
    """Detecta manos (y hombros como referencia) con la API Tasks de MediaPipe.

    Cada mano va siempre en su posición fija del vector según MediaPipe la
    clasifique como izquierda o derecha. MediaPipe asume imagen en espejo; como
    main.py voltea el frame, la etiqueta puede quedar invertida respecto a la
    mano real, pero es consistente, que es lo que importa para el modelo.
    """

    def __init__(self, models_dir, min_detection_confidence=0.5, min_tracking_confidence=0.5):
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
        pose_result = self.pose.detect_for_video(image, ts)

        raw = np.zeros(RAW_FRAME_SIZE, dtype=np.float32)

        # Asignar cada mano a su posición fija; si ambas llegan con la misma
        # etiqueta, la de mayor confianza se queda y la otra va a la libre.
        hands = []
        for landmarks, handedness in zip(hand_result.hand_landmarks, hand_result.handedness):
            cat = handedness[0]
            hands.append((cat.score, 0 if cat.category_name == "Left" else 1, landmarks))
        hands.sort(key=lambda item: -item[0])
        used = set()
        for _, slot, landmarks in hands[:2]:
            if slot in used:
                slot = 1 - slot
            used.add(slot)
            offset = slot * HAND_SIZE
            wrist_z = landmarks[0].z
            for i, lm in enumerate(landmarks):
                raw[offset + i * 3: offset + i * 3 + 3] = (lm.x * aspect, lm.y, lm.z - wrist_z)
            self._draw_hand(frame, landmarks, _HAND_COLORS[slot])

        if pose_result.pose_landmarks:
            pose = pose_result.pose_landmarks[0]
            shoulders_visible = all((pose[i].visibility or 0) > 0.5 for i in (11, 12))
            if shoulders_visible:
                for k, i in enumerate(POSE_POINTS):
                    lm = pose[i]
                    raw[HANDS_SIZE + k * 3: HANDS_SIZE + k * 3 + 3] = (lm.x * aspect, lm.y, lm.z)

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

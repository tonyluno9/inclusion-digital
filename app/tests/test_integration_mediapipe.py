"""Integración con MediaPipe real (sin cámara): usa una foto de muestra oficial de
MediaPipe con dos manos visibles. Se omite si no están los modelos o la foto y no
hay internet para descargarlos."""
import os
import tempfile
import unittest
import urllib.request

import cv2
import numpy as np

import config as C

SAMPLE_URL = "https://storage.googleapis.com/mediapipe-tasks/hand_landmarker/woman_hands.jpg"
ASSETS_DIR = os.path.join(C.DATA_DIR, "test_assets")
SAMPLE_PATH = os.path.join(ASSETS_DIR, "woman_hands.jpg")


def _sample_frame():
    if not os.path.exists(SAMPLE_PATH):
        os.makedirs(ASSETS_DIR, exist_ok=True)
        urllib.request.urlretrieve(SAMPLE_URL, SAMPLE_PATH)
    img = cv2.resize(cv2.imread(SAMPLE_PATH), (480, 720))
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[:, 400:880] = img
    return frame


def setUpModule():
    global DETECTOR_CLS, SIGN_FRAME
    try:
        from modules.landmark_detector import LandmarkDetector, ensure_model
        for name in ("hand_landmarker.task", "pose_landmarker_lite.task"):
            ensure_model(C.MODELS_DIR, name)
        SIGN_FRAME = _sample_frame()
    except Exception as e:  # sin internet la primera vez
        raise unittest.SkipTest(f"MediaPipe o la foto de muestra no disponibles: {e}")
    DETECTOR_CLS = LandmarkDetector


class MediaPipeIntegrationTest(unittest.TestCase):
    def test_detector_finds_both_hands(self):
        """RF-02: dos manos, cada una en su lugar. (En esta foto un brazo tapa un
        hombro, por eso no se exige la pose; ver RF-03 sobre la referencia previa.)"""
        from modules.landmarks import HAND_SIZE, HANDS_SIZE
        det = DETECTOR_CLS(C.MODELS_DIR, pose_every=1)
        try:
            for _ in range(5):
                _, raw = det.process(cv2.flip(SIGN_FRAME, 1))
        finally:
            det.close()
        self.assertTrue(np.any(raw[:HAND_SIZE]) and np.any(raw[HAND_SIZE:HANDS_SIZE]))

    def test_detector_gives_3d_frame_for_the_avatar(self):
        """RF-17, RF-20 con MediaPipe real: cuerpo 3D (33 puntos) y manos pegadas a
        las muñecas del cuerpo, en metros. Usa la foto sin bordes: ahí se ven los codos."""
        from modules.landmarks import ARMS_START, RAW_FRAME_SIZE
        from modules.motion import hand_side_from_shape
        det = DETECTOR_CLS(C.MODELS_DIR, pose_every=1)
        try:
            for _ in range(5):
                _, raw = det.process(cv2.flip(cv2.imread(SAMPLE_PATH), 1))
            world = det.world
        finally:
            det.close()
        self.assertEqual(raw.shape, (RAW_FRAME_SIZE,))
        self.assertTrue(np.any(raw[ARMS_START:]))                 # se ven codos o muñecas
        self.assertEqual(world["pose"].shape, (33, 3))
        self.assertEqual(world["vis"].shape, (33,))
        self.assertLess(np.abs(world["pose"]).max(), 2.0)         # metros, no píxeles
        for side, wrist in (("left", 15), ("right", 16)):
            self.assertEqual(world[side].shape, (21, 3))
            np.testing.assert_allclose(world[side][0], world["pose"][wrist], atol=1e-5)
            self.assertLess(np.linalg.norm(world[side][12] - world[side][0]), 0.3)   # mano de tamaño real
            # La mano en el lugar izquierdo tiene forma de mano izquierda (y viceversa):
            # si no, el personaje la cierra al revés
            self.assertEqual(hand_side_from_shape(world[side]), side)

    def test_app_records_a_real_sample(self):
        """RF-01..RF-03, RF-09 con MediaPipe real: aparecen manos -> se guarda una muestra."""
        from inclusion_app import InclusionApp
        from modules.data_collector import DataCollector
        from modules.gesture_logic import GestureLogic
        from tests.test_app import FakeSTT, FakeTTS

        with tempfile.TemporaryDirectory() as tmp:
            collector = DataCollector(os.path.join(tmp, "d.csv"), os.path.join(tmp, "b"))
            logic = GestureLogic(os.path.join(tmp, "m.pkl"), C.FEATURE_VERSION, C.SEQUENCE_LENGTH)
            det = DETECTOR_CLS(C.MODELS_DIR, pose_every=C.POSE_EVERY_N_FRAMES, pose_model=C.POSE_MODEL)
            app = InclusionApp(det, FakeTTS(), FakeSTT(), collector=collector, logic=logic, background=False)
            app.mode, app.label, app.person, app.armed = "TRAINING", "hola", "test", True
            app.hands = "derecha"                       # la foto es de una sola mano
            blank = np.zeros_like(SIGN_FRAME)
            try:
                for frame in [blank] * 10 + [SIGN_FRAME] * 25 + [blank] * 12:
                    out = app.process_frame(frame.copy(), render=True)
            finally:
                det.close()
            self.assertEqual(out.shape, SIGN_FRAME.shape)
            self.assertEqual(collector.count("hola"), 1)

    def test_main_runs_headless_on_video(self):
        """RF-01, RF-15, RNF-01, RNF-06: main.py procesa un video sin ventana, reporta rendimiento
        y termina con código 1 (sin traceback) si el video no existe."""
        from unittest import mock
        import main
        with tempfile.TemporaryDirectory() as tmp:
            # Datos de la app en un temporal: la prueba nunca toca el dataset ni los clips reales
            datos = {"DATASET_PATH": os.path.join(tmp, "dataset.csv"), "BACKUP_DIR": os.path.join(tmp, "backups"),
                     "MODEL_PATH": os.path.join(tmp, "model.pkl"), "AVATAR_DIR": os.path.join(tmp, "avatar")}
            path = os.path.join(tmp, "demo.avi")
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (1280, 720))
            blank = np.zeros_like(SIGN_FRAME)
            for frame in [blank] * 10 + [SIGN_FRAME] * 30 + [blank] * 15:
                writer.write(frame)
            writer.release()
            with mock.patch.multiple(C, **datos):
                self.assertEqual(main.main(["--video", path, "--headless", "--benchmark"]), 0)
            self.assertEqual(sorted(os.listdir(tmp)), ["demo.avi"])   # solo leyó, no escribió nada
        self.assertEqual(main.main(["--video", os.path.join(tmp, "no_existe.mp4"), "--headless"]), 1)


if __name__ == "__main__":
    unittest.main()

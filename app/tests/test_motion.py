"""Movimiento 3D para el avatar (requerimientos/06_avatar.md)."""
import json
import os
import socket
import tempfile
import unittest

import numpy as np

from modules.landmark_detector import anatomical_order
from modules.motion import (CLIP_FORMAT, CLIP_VERSION, HAND_NAMES, POSE_NAMES, ClipStore, LiveSender, LiveSmoother,
                            MotionRecorder, OneEuroFilter, empty_world, fill_short_gaps, make_clip, validate_clip,
                            world_frame)


def fake_world(seed=0, hands=True):
    rng = np.random.RandomState(seed)
    pose = rng.normal(0, 0.3, (33, 3))
    hand = rng.normal(0, 0.05, (21, 3))
    return world_frame(pose, np.full(33, 0.9), [hand, hand] if hands else [None, None])


class WorldFrameTest(unittest.TestCase):
    def test_axes_are_the_persons(self):
        """RF-20: con la imagen en espejo, invertir los tres ejes de MediaPipe da
        x a la izquierda de la persona, y arriba y z hacia la cámara."""
        pose = np.zeros((33, 3))
        pose[11] = (-0.2, -0.5, 0.1)    # MediaPipe: x a la derecha (en espejo), y abajo, z lejos de la cámara
        out = world_frame(pose, None, [None, None])
        np.testing.assert_allclose(out["pose"][11], (0.2, 0.5, -0.1))
        self.assertEqual(out["vis"].shape, (33,))
        self.assertIsNone(out["left"])

    def test_hands_are_attached_to_the_body_wrists(self):
        """RF-20: la muñeca de cada mano coincide con la muñeca del cuerpo de su lado."""
        pose = np.zeros((33, 3))
        pose[15], pose[16] = (0.3, -0.1, -0.2), (-0.3, -0.1, -0.2)
        hand = np.random.RandomState(1).normal(0, 0.05, (21, 3))
        out = world_frame(pose, None, [hand, hand])
        np.testing.assert_allclose(out["left"][0], out["pose"][15], atol=1e-6)
        np.testing.assert_allclose(out["right"][0], out["pose"][16], atol=1e-6)
        # La forma de la mano se conserva (solo cambia de lugar y de ejes)
        np.testing.assert_allclose(out["left"] - out["left"][0], -(hand - hand[0]), atol=1e-6)

    def test_hand_without_body_is_left_out(self):
        """RF-20: sin cuerpo no hay dónde colocar la mano: queda ausente (en Blender
        no salta al origen)."""
        hand = np.random.RandomState(2).normal(0, 0.05, (21, 3))
        out = world_frame(None, None, [None, hand])
        self.assertIsNone(out["pose"])
        self.assertIsNone(out["right"])

    def test_body_sides_are_anatomical(self):
        """RF-17: en la imagen en espejo el hombro izquierdo de la persona está a la
        izquierda; si MediaPipe lo etiquetó al revés, se intercambian todos los pares."""
        same = anatomical_order(0.4, 0.6)
        self.assertEqual(same, list(range(33)))
        swapped = anatomical_order(0.6, 0.4)
        self.assertEqual(swapped[11:17], [12, 11, 14, 13, 16, 15])
        self.assertEqual(swapped[0], 0)                       # la nariz no tiene par
        self.assertEqual(sorted(swapped), list(range(33)))


class SmoothingTest(unittest.TestCase):
    def test_one_euro_removes_jitter_but_follows_movement(self):
        """RF-18: quieto, el temblor baja; al moverse, no se queda atrás."""
        rng = np.random.RandomState(0)
        f = OneEuroFilter()
        t = np.arange(120) / 30
        noisy = 0.5 + rng.normal(0, 0.01, 120)
        out = np.array([f(np.array([x]), ti)[0] for x, ti in zip(noisy, t)])
        self.assertLess(np.std(out[30:]), 0.5 * np.std(noisy[30:]))

        f.reset()
        step = np.where(t < 2, 0.0, 0.3)                   # movimiento brusco de 30 cm
        out = np.array([f(np.array([x]), ti)[0] for x, ti in zip(step, t)])
        self.assertGreater(out[60 + 6], 0.25)               # 0.2 s después ya casi llegó

    def test_smoother_resets_when_a_part_disappears(self):
        s = LiveSmoother()
        w = fake_world()
        s(w, 0.0)
        gone = dict(w, left=None)
        self.assertIsNone(s(gone, 0.033)["left"])
        far = dict(w, left=w["left"] + 1.0)
        np.testing.assert_allclose(s(far, 0.066)["left"], far["left"])   # sin arrastrar la posición vieja


class ClipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ClipStore(os.path.join(self.tmp.name, "avatar"))

    def tearDown(self):
        self.tmp.cleanup()

    def timed(self, n=40):
        return [(10.0 + i / 30, fake_world(i)) for i in range(n)]

    def test_short_gaps_are_filled(self):
        """RF-19: huecos de ≤ 5 frames se interpolan; los largos quedan vacíos."""
        frames = [fake_world(i) for i in range(20)]
        for i in (3, 4):
            frames[i] = dict(frames[i], left=None)
        for i in range(8, 16):
            frames[i] = dict(frames[i], pose=None, vis=None)
        out = fill_short_gaps(frames)
        np.testing.assert_allclose(out[3]["left"], frames[2]["left"] + (frames[5]["left"] - frames[2]["left"]) / 3,
                                   atol=1e-6)
        self.assertIsNone(out[10]["pose"])
        self.assertIsNotNone(out[3]["pose"])

    def test_make_clip_has_the_documented_format(self):
        """RF-20: formato, versión, nombres, tiempos desde 0 y redondeo."""
        clip = make_clip(self.timed(), "hola", "ana")
        self.assertEqual((clip["format"], clip["version"]), (CLIP_FORMAT, CLIP_VERSION))
        self.assertEqual((clip["word"], clip["person"]), ("hola", "ana"))
        self.assertEqual(clip["pose_names"], POSE_NAMES)
        self.assertEqual(len(POSE_NAMES), 33)
        self.assertEqual(len(HAND_NAMES), 21)
        self.assertAlmostEqual(clip["fps"], 30, places=0)
        self.assertAlmostEqual(clip["duration"], 39 / 30, places=2)
        first = clip["frames"][0]
        self.assertEqual(first["t"], 0.0)
        self.assertEqual(len(first["pose"]), 33)
        self.assertEqual(len(first["left"]), 21)
        self.assertEqual(first["pose"][0][0], round(first["pose"][0][0], 4))
        json.dumps(clip)                                  # serializable tal cual
        validate_clip(clip)

    def test_validate_rejects_unknown_versions(self):
        clip = make_clip(self.timed(5), "hola")
        with self.assertRaises(ValueError):
            validate_clip(dict(clip, version=99))
        with self.assertRaises(ValueError):
            validate_clip(dict(clip, format="otra-cosa"))
        with self.assertRaises(ValueError):
            validate_clip(dict(clip, frames=[]))

    def test_save_keeps_previous_take_and_undo(self):
        """RF-19: una toma nueva guarda la anterior; z restaura y después borra."""
        first = make_clip(self.timed(10), "buenos días")
        second = make_clip(self.timed(20), "buenos días")
        path = self.store.save(first)
        self.assertTrue(path.endswith("buenos días.json"))
        self.store.save(second)
        self.assertEqual(len(self.store.load("buenos días")["frames"]), 20)
        self.assertEqual(self.store.words(), ["buenos días"])      # la toma anterior no cuenta como palabra
        self.assertEqual(self.store.undo("buenos días"), "restaurado")
        self.assertEqual(len(self.store.load("buenos días")["frames"]), 10)
        self.assertEqual(self.store.undo("buenos días"), "borrado")
        self.assertIsNone(self.store.undo("buenos días"))
        self.assertEqual(self.store.words(), [])
        self.assertEqual(os.listdir(self.store.directory), [])

    def test_filenames_are_safe(self):
        self.assertEqual(ClipStore.filename(' ¿Qué? / hola* '), "¿qué_ _ hola_")

    def test_clip_contains_only_coordinates(self):
        """RNF-11: el clip solo tiene números, nombres y metadatos (nunca imagen)."""
        clip = make_clip(self.timed(5), "hola")
        allowed = {"format", "version", "word", "person", "created", "fps", "duration", "coords",
                   "pose_names", "hand_names", "frames"}
        self.assertEqual(set(clip), allowed)
        self.assertEqual(set(clip["frames"][0]), {"t", "pose", "vis", "left", "right"})


class RecorderTest(unittest.TestCase):
    def test_recording_includes_preroll(self):
        """RF-19: el clip empieza unos frames antes de que se levanten las manos."""
        rec = MotionRecorder(preroll_frames=5)
        for i in range(20):
            rec.push(empty_world(), i)
        rec.begin()
        for i in range(20, 30):
            rec.push(empty_world(), i)
        frames = rec.finish()
        self.assertEqual([t for t, _ in frames], list(range(15, 30)))
        self.assertFalse(rec.recording)

    def test_cancel_and_limit(self):
        rec = MotionRecorder(preroll_frames=2, max_frames=10)
        rec.begin()
        for i in range(50):
            rec.push(empty_world(), i)
        self.assertEqual(len(rec.frames), 10)
        rec.cancel()
        self.assertEqual(rec.finish(), [])


class LiveSenderTest(unittest.TestCase):
    def test_frames_and_clip_messages_arrive(self):
        """RF-18: los mensajes llegan por UDP como JSON."""
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.bind(("127.0.0.1", 0))
        rx.settimeout(2)
        sender = LiveSender("127.0.0.1", rx.getsockname()[1])
        try:
            sender.send_frame(fake_world(), 12.5)
            sender.send_clip("hola", "data/avatar/hola.json")
            frame = json.loads(rx.recv(65535).decode("utf-8"))
            clip = json.loads(rx.recv(65535).decode("utf-8"))
        finally:
            sender.close()
            rx.close()
        self.assertEqual(frame["type"], "frame")
        self.assertEqual(frame["t"], 12.5)
        self.assertEqual(len(frame["pose"]), 33)
        self.assertEqual(len(frame["right"]), 21)
        self.assertEqual(clip["type"], "clip")
        self.assertTrue(os.path.isabs(clip["path"]))

    def test_nobody_listening_is_not_an_error(self):
        """RF-18: sin Blender abierto, enviar no falla ni bloquea."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        sender = LiveSender("127.0.0.1", port)
        for _ in range(50):
            sender.send_frame(fake_world(), 0.0)
        sender.close()

    def test_datagram_fits(self):
        """Un frame completo con ambas manos cabe holgado en un datagrama."""
        from modules.motion import frame_to_json
        size = len(json.dumps({"type": "frame", **frame_to_json(fake_world(), 1.0)}).encode("utf-8"))
        self.assertLess(size, 16000)


if __name__ == "__main__":
    unittest.main()

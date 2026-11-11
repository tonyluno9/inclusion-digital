"""Señas de una o dos manos (RF-31) y revisión / recorte de la toma del avatar (RF-32)."""
import json
import os
import unittest

import numpy as np

import config as C
from modules.landmarks import HAND_SIZE, hand_coverage, keep_hands, missing_hands
from modules.motion import ARM_POINTS, make_clip, rest_arm, resting_side, trim_clip, world_frame
from tests.synthetic import make_sign, stream
import tests.test_app as base


def two_hands(n, rng=None):
    """Seña de dos manos: la derecha sube y la izquierda se mueve hacia un lado."""
    right = make_sign("arriba", n, hand_slot=1, rng=rng)
    left = make_sign("derecha", n, hand_slot=0, rng=rng)
    both = right.copy()
    both[:, :HAND_SIZE] = left[:, :HAND_SIZE]
    return both


class FuncionesTest(unittest.TestCase):
    def test_keep_hands_borra_solo_la_otra_mano(self):
        frame = two_hands(1)[0]
        derecha = keep_hands(frame, "derecha")
        self.assertTrue(np.all(derecha[:HAND_SIZE] == 0))
        np.testing.assert_array_equal(derecha[HAND_SIZE:], frame[HAND_SIZE:])
        izquierda = keep_hands(frame, "izquierda")
        self.assertTrue(np.all(izquierda[HAND_SIZE:2 * HAND_SIZE] == 0))
        np.testing.assert_array_equal(keep_hands(frame, "dos"), frame)
        self.assertTrue(np.any(frame[:HAND_SIZE] != 0))          # no cambia el original

    def test_cobertura_y_manos_faltantes(self):
        una = make_sign("arriba", 20, hand_slot=1)
        self.assertEqual(hand_coverage(una), {"izquierda": 0.0, "derecha": 1.0})
        self.assertEqual(missing_hands(una, "dos", 0.5), ["izquierda"])
        self.assertEqual(missing_hands(una, "derecha", 0.5), [])
        self.assertEqual(missing_hands(una, "izquierda", 0.5), ["izquierda"])
        self.assertEqual(missing_hands(two_hands(20), "dos", 0.5), [])
        self.assertEqual(hand_coverage(una[:0]), {"izquierda": 0.0, "derecha": 0.0})

    def test_brazo_en_reposo(self):
        pose = np.zeros((33, 3))
        pose[11], pose[12] = (-0.18, -0.45, 0), (0.18, -0.45, 0)   # en ejes de MediaPipe (se invierten)
        hand = np.random.RandomState(1).normal(0, 0.05, (21, 3))
        world = world_frame(pose, np.full(33, 0.2), [hand, hand])
        self.assertEqual(resting_side("derecha"), "left")
        self.assertEqual(resting_side("izquierda"), "right")
        self.assertIsNone(resting_side("dos"))
        out = rest_arm(world, "left")
        self.assertIsNone(out["left"])
        self.assertIsNotNone(out["right"])
        shoulder, elbow, wrist = (out["pose"][i] for i in ARM_POINTS["left"][:3])
        self.assertLess(elbow[1], shoulder[1] - 0.2)             # el codo cuelga bajo el hombro
        self.assertLess(wrist[1], elbow[1] - 0.2)                # y la muñeca bajo el codo
        self.assertGreater(elbow[0], shoulder[0])                # un poco hacia afuera (x = izquierda)
        self.assertEqual(out["vis"][ARM_POINTS["left"][1]], 1.0)
        np.testing.assert_array_equal(out["pose"][ARM_POINTS["right"][2]], world["pose"][ARM_POINTS["right"][2]])
        self.assertIsNotNone(world["left"])                      # no cambia el original
        sin_cuerpo = rest_arm({"pose": None, "vis": None, "left": hand, "right": hand}, "right")
        self.assertIsNone(sin_cuerpo["right"])

    def test_recortar_clip(self):
        vacio = {"pose": None, "vis": None, "left": None, "right": None}
        clip = make_clip([(i / 10, vacio) for i in range(21)], "hola", hands="derecha")   # 2 s a 10 fps
        self.assertEqual(clip["hands"], "derecha")
        corto = trim_clip(clip, 0.5, 1.5)
        self.assertEqual(len(corto["frames"]), 11)
        self.assertEqual(corto["frames"][0]["t"], 0.0)
        self.assertAlmostEqual(corto["duration"], 1.0)
        self.assertAlmostEqual(corto["fps"], 10.0)
        self.assertEqual(corto["trimmed_from"], [0.5, 1.5])
        self.assertEqual(len(clip["frames"]), 21)                # no cambia el original
        with self.assertRaises(ValueError):
            trim_clip(clip, 1.0, 1.0)


class ManosEnLaAppTest(unittest.TestCase):
    setUp, tearDown, feed, keys, type_answer, enter_avatar = (
        base.AppTest.setUp, base.AppTest.tearDown, base.AppTest.feed, base.AppTest.keys, base.AppTest.type_answer, base.AppTest.enter_avatar)

    def train(self, word):
        self.app.train_word(word, "ana")
        self.app.toggle_recording()

    def test_dos_manos_rechaza_la_muestra_sin_una_mano(self):
        """RF-31: en una seña de dos manos, si una casi no se vio, no se guarda y se explica por qué."""
        self.train("buenas tardes")
        self.assertEqual(self.app.hands, "dos")
        self.feed(stream(make_sign("arriba", 30)))
        self.assertEqual(self.collector.count("buenas tardes"), 0)
        self.assertEqual(self.app.flash, (40, 40, 230))
        self.assertIn("No vi tu mano izquierda", self.app.status)
        self.assertIn("una mano", self.app.status)
        self.feed(stream(two_hands(30)))
        self.assertEqual(self.collector.count("buenas tardes"), 1)

    def test_una_mano_ignora_la_otra(self):
        """RF-31: con «mano derecha», la izquierda no se graba aunque se mueva."""
        self.train("hola")
        self.app.set_hands("derecha")
        self.feed(stream(two_hands(30)))
        self.assertEqual(self.collector.count("hola"), 1)
        with open(self.collector.file_path, encoding="utf-8") as f:
            fila = f.read().strip().splitlines()[-1].split(",")
        guardada = np.array(fila[2:], dtype=np.float32).reshape(C.SEQUENCE_LENGTH, -1)
        self.assertTrue(np.all(guardada[:, :HAND_SIZE] == 0))    # la izquierda no se guardó
        self.assertTrue(np.all(np.any(guardada[:, HAND_SIZE:2 * HAND_SIZE] != 0, axis=1)))
        # Solo la izquierda (la mano que no cuenta): no es una seña
        self.feed(stream(make_sign("derecha", 30, hand_slot=0)))
        self.assertEqual(self.collector.count("hola"), 1)

    def test_las_manos_se_recuerdan_por_palabra(self):
        """RF-31: al volver a una palabra se recupera con qué manos se hace (también al reiniciar)."""
        self.app.train_word("hola", "ana")
        self.app.set_hands("derecha")
        self.app.train_word("buenas tardes", "ana")
        self.app.set_hands("dos")
        self.app.avatar_word("hola")
        self.assertEqual(self.app.hands, "derecha")
        with open(self.app.hands_path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"hola": "derecha", "buenas tardes": "dos"})
        self.assertEqual(os.path.dirname(self.app.hands_path), self.tmp.name)   # junto al dataset
        otra = type(self.app)(self.detector, self.tts, self.stt, collector=self.collector, logic=self.logic,
                              clips=self.clips, sender=self.sender, background=False)
        otra.train_word("buenas tardes")
        self.assertEqual(otra.hands, "dos")
        otra.train_word("hola")
        self.assertEqual(otra.hands, "derecha")
        with self.assertRaises(ValueError):
            otra.set_hands("tres")

    def test_tecla_m_cambia_las_manos(self):
        self.app.train_word("hola", "ana")
        self.keys("m")
        self.assertEqual(self.app.hands, "derecha")
        self.keys("m")
        self.assertEqual(self.app.hands, "izquierda")
        self.keys("m")
        self.assertEqual(self.app.hands, "dos")
        self.assertEqual(self.app.state()["manos"], "dos")

    def test_avatar_de_una_mano_deja_el_otro_brazo_abajo(self):
        """RF-31: en el avatar, el brazo de la mano que no cuenta queda en reposo, en vivo y en el clip."""
        self.enter_avatar("hola")
        self.app.set_hands("izquierda")
        self.keys(" ")
        self.feed(stream(make_sign("arriba", 30, hand_slot=0)))
        self.assertIsNone(self.app.live_world["right"])
        clip = self.clips.load("hola")
        self.assertEqual(clip["hands"], "izquierda")
        codo, hombro = ARM_POINTS["right"][1], ARM_POINTS["right"][0]
        for f in clip["frames"]:
            self.assertIsNone(f["right"])
            self.assertLess(f["pose"][codo][1], f["pose"][hombro][1] - 0.2)


class TomasTest(unittest.TestCase):
    """RF-32: en la app web, la toma del avatar se revisa y se recorta antes de guardarla."""
    setUp, tearDown, feed, keys, type_answer, enter_avatar = (
        base.AppTest.setUp, base.AppTest.tearDown, base.AppTest.feed, base.AppTest.keys, base.AppTest.type_answer, base.AppTest.enter_avatar)

    def grabar(self):
        self.app.review_takes = True
        self.enter_avatar("hola")
        self.app.set_hands("derecha")
        self.keys(" ")
        self.feed(stream(make_sign("arriba", 30), pad=20))

    def test_la_toma_queda_pendiente_y_se_guarda_recortada(self):
        self.grabar()
        self.assertEqual(self.clips.words(), [])                 # todavía no se guarda
        toma = self.app.pending_take
        self.assertIsNotNone(toma)
        self.assertFalse(self.app.armed)                         # no se graba otra encima
        estado = self.app.state()
        self.assertTrue(estado["toma_pendiente"])
        self.assertEqual(estado["toma_seq"], 1)
        self.assertFalse(self.app.toggle_recording())            # primero guardar o descartar
        self.assertIn("guarda o descarta", self.app.status)

        inicio, fin = 0.3, toma["duration"] - 0.2
        ruta = self.app.save_take(inicio, fin)
        self.assertIsNone(self.app.pending_take)
        guardado = self.clips.load("hola")
        self.assertEqual(ruta, self.app.last_clip)
        self.assertLess(guardado["duration"], toma["duration"])
        self.assertAlmostEqual(guardado["duration"], fin - inicio, delta=0.05)
        self.assertEqual(self.app.state()["seq_clip"], 1)
        self.assertEqual(self.sender.clips, [("hola", ruta)])
        self.assertTrue(self.app.toggle_recording())             # ya se puede grabar otra

    def test_guardar_sin_recortar_y_descartar(self):
        self.grabar()
        duracion = self.app.pending_take["duration"]
        self.app.save_take()
        self.assertAlmostEqual(self.clips.load("hola")["duration"], duracion)
        self.keys(" ")
        self.feed(stream(make_sign("derecha", 40), pad=20))
        self.assertIsNotNone(self.app.pending_take)
        self.assertTrue(self.app.discard_take())
        self.assertIsNone(self.app.pending_take)
        self.assertAlmostEqual(self.clips.load("hola")["duration"], duracion)   # la anterior sigue
        self.assertFalse(self.app.discard_take())
        with self.assertRaises(ValueError):
            self.app.save_take()

    def test_deshacer_o_cambiar_de_palabra_descarta_la_toma(self):
        self.grabar()
        self.keys("z")
        self.assertIsNone(self.app.pending_take)
        self.assertEqual(self.clips.words(), [])
        self.keys(" ")
        self.feed(stream(make_sign("arriba", 30), pad=20))
        self.assertIsNotNone(self.app.pending_take)
        self.app.avatar_word("gracias")
        self.assertIsNone(self.app.pending_take)

    def test_la_app_clasica_guarda_sin_revisar(self):
        self.enter_avatar("hola")
        self.assertFalse(self.app.review_takes)
        self.app.set_hands("derecha")
        self.keys(" ")
        self.feed(stream(make_sign("arriba", 30), pad=20))
        self.assertEqual(self.clips.words(), ["hola"])
        self.assertIsNone(self.app.pending_take)


if __name__ == "__main__":
    unittest.main()

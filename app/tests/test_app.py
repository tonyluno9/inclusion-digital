"""La app completa (InclusionApp) con frames y teclas simuladas, sin cámara."""
import os
import tempfile
import unittest

import numpy as np

import config as C
from inclusion_app import InclusionApp
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from tests.synthetic import make_sign, stream

FRAME = np.zeros((720, 1280, 3), dtype=np.uint8)


class FakeDetector:
    """Devuelve los frames crudos que se le den, en orden."""
    def __init__(self):
        self.queue = []
        self.idle = None

    def process(self, frame):
        raw = self.queue.pop(0) if self.queue else self.idle
        return frame, raw


class FakeTTS:
    def __init__(self):
        self.enabled, self.speaking, self.last_error, self.said = True, False, "", []

    def speak(self, text):
        if self.enabled and text:
            self.said.append(text)

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled


class FakeSTT:
    def __init__(self):
        self.is_recording, self.last_error, self.results = False, "", []

    def start_recording(self):
        self.is_recording = True

    def stop_recording(self):
        self.is_recording = False
        self.results.append("¿en qué le puedo ayudar?")

    def get_result(self):
        return self.results.pop(0) if self.results else None


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.detector, self.tts, self.stt, self.clock = FakeDetector(), FakeTTS(), FakeSTT(), Clock()
        self.collector = DataCollector(os.path.join(self.tmp.name, "dataset.csv"), os.path.join(self.tmp.name, "b"))
        self.logic = GestureLogic(os.path.join(self.tmp.name, "model.pkl"), C.FEATURE_VERSION, C.SEQUENCE_LENGTH)
        self.sentences = []

        def coherence(words, enabled=True):
            self.sentences.append(list(words))
            return "Oración: " + " ".join(words)

        self.app = InclusionApp(self.detector, self.tts, self.stt, collector=self.collector, logic=self.logic,
                                coherence=coherence, clock=self.clock, background=False)
        idle = stream(make_sign("arriba", 1), pad=1)[0]
        self.detector.idle = idle

    def tearDown(self):
        self.tmp.cleanup()

    def feed(self, frames, render=False):
        self.detector.queue.extend(frames)
        while self.detector.queue:
            self.clock.t += 1 / 30
            self.app.process_frame(FRAME.copy(), render=render)

    def keys(self, text):
        for ch in text:
            self.assertTrue(self.app.handle_key(ch.encode("latin-1")[0] if ord(ch) < 256 else ord(ch)))

    def type_answer(self, text):
        prompt = self.app.prompt
        self.assertIsNotNone(prompt)
        for _ in range(len(prompt.text)):
            self.app.handle_key(8)
        self.keys(text)
        self.app.handle_key(13)

    def record(self, label, person, sign, n, rng):
        self.keys("t")
        self.type_answer(label)
        self.type_answer(person)
        self.assertEqual(self.app.mode, "TRAINING")
        self.keys(" ")
        self.assertTrue(self.app.armed)
        for _ in range(n):
            self.feed(stream(make_sign(sign, rng.randint(20, 45), rng=rng)))

    def test_full_flow_record_train_detect_sentence(self):
        """RF-09, RF-11, RF-04, RF-05, RF-06, RF-07 de punta a punta."""
        rng = np.random.RandomState(3)
        self.record("hola", "ana", "arriba", 7, rng)
        self.assertEqual(self.collector.count("hola"), 7)
        self.assertEqual(self.app.flash, (80, 220, 80))          # confirmación visual (RNF-05)

        self.record("adiós", "ana", "derecha", 7, rng)           # acento: UTF-8 (RF-10)
        self.assertEqual(self.collector.count("adiós"), 7)
        self.keys("z")
        self.assertEqual(self.collector.count("adiós"), 6)

        self.keys("e")                                           # entrenar (síncrono en pruebas)
        self.assertFalse(self.app.training)
        self.assertTrue(self.app.reload_pending)
        self.keys("d")
        self.assertIsNotNone(self.logic.model)
        self.assertEqual(sorted(self.logic.classes), ["adiós", "hola"])

        self.feed(stream(make_sign("arriba", 25, rng=rng)))
        self.assertEqual(self.app.prediction, "hola")
        self.feed(stream(make_sign("derecha", 40, rng=rng)))
        self.assertEqual(self.app.prediction, "adiós")
        self.assertEqual(self.app.history, ["hola", "adiós"])
        self.assertEqual(self.tts.said[-2:], ["hola", "adiós"])

        self.clock.t += C.SILENCE_SECONDS + 0.1                  # pausa: se arma la oración
        self.feed([self.detector.idle])
        self.assertEqual(self.sentences, [["hola", "adiós"]])
        self.assertEqual(self.app.sentence, "Oración: hola adiós")
        self.assertEqual(self.tts.said[-1], "Oración: hola adiós")
        self.assertEqual(self.app.history, [])

    def test_no_recording_while_typing(self):
        """H5: con una pregunta abierta no se graban muestras."""
        rng = np.random.RandomState(0)
        self.record("hola", "ana", "arriba", 1, rng)
        self.keys("t")
        self.feed(stream(make_sign("arriba", 30, rng=rng)))
        self.assertEqual(self.collector.count("hola"), 1)
        self.app.handle_key(27)                                  # Esc cancela la pregunta
        self.assertIsNone(self.app.prompt)
        self.assertEqual(self.app.label, "hola")                 # la etiqueta no cambió
        self.assertFalse(self.app.armed)

    def test_more_than_history_words_reach_sentence(self):
        """H6: todas las palabras llegan a la oración, no solo las visibles."""
        self.app.pending_words = [f"p{i}" for i in range(7)]
        self.app.history = self.app.pending_words[-C.SUBTITLE_HISTORY:]
        self.clock.t += C.SILENCE_SECONDS + 1
        self.feed([self.detector.idle])
        self.assertEqual(len(self.sentences[0]), 7)

    def test_training_failure_does_not_get_stuck(self):
        """H1: si entrenar falla, se puede volver a intentar."""
        def boom(*a, **k):
            raise RuntimeError("falla")
        self.app.trainer = boom
        self.keys("e")
        self.assertFalse(self.app.training)
        self.assertFalse(self.app.reload_pending)

    def test_without_model_explains_what_to_do(self):
        """RF-04: sin modelo, la app funciona y explica cómo crearlo."""
        self.assertEqual(self.app._segment(self.detector.idle)[:10], "Sin modelo")

    def test_keys_help_stats_voice_stt_and_quit(self):
        """RF-13, RF-10, RF-06, RF-08, RF-14."""
        self.keys("H")                                           # mayúscula también
        self.assertEqual(self.app.panel[0], "Teclas")
        self.feed([self.detector.idle], render=True)
        self.assertTrue(self.app.handle_key(27))                 # Esc cierra la ayuda
        self.assertIsNone(self.app.panel)
        self.keys("i")
        self.assertIn("Dataset", self.app.panel[0])
        self.keys("v")
        self.assertFalse(self.tts.enabled)
        self.keys("s")
        self.assertTrue(self.stt.is_recording)
        self.keys("s")
        self.feed([self.detector.idle], render=True)
        self.assertEqual(self.app.stt_text, "¿en qué le puedo ayudar?")
        self.assertFalse(self.app.handle_key(ord("q")))
        self.app.panel = None
        self.assertFalse(self.app.handle_key(27))

    def test_render_long_texts_and_prompt(self):
        """RNF-05: textos largos y la pregunta se dibujan sin errores."""
        self.app.sentence = "una oración muy larga " * 12
        self.app.stt_text = "el interlocutor habla mucho " * 10
        self.app.history = ["buenos días", "gracias", "por favor", "de nada", "mucho gusto"]
        self.app.prediction, self.app.confidence = "buenos dias", 0.87
        for size, expected in [((480, 640), (720, 960)), ((720, 1280), (720, 1280))]:
            out = self.app.process_frame(np.zeros((*size, 3), np.uint8), render=True)
            self.assertEqual(out.shape, (*expected, 3))   # lo chico se agranda para leerse bien
            self.assertGreater(out.mean(), 1)
        self.keys("t")
        self.keys("niño")
        out = self.app.process_frame(FRAME.copy(), render=True)
        self.assertEqual(self.app.prompt.text, "niño")


if __name__ == "__main__":
    unittest.main()

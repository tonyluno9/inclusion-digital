"""De punta a punta sin cámara: grabar -> entrenar -> detectar con otra persona."""
import os
import tempfile
import unittest

import numpy as np

import config as C
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from modules.segmenter import SignSegmenter
from tests.synthetic import TRAJECTORIES, make_sign, stream
from train_model import train


def capture(frames):
    seg = SignSegmenter(C.SEQUENCE_LENGTH, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES,
                        C.SEGMENT_MIN_FRAMES, C.SEGMENT_MAX_FRAMES, C.SEGMENT_CONTEXT_FRAMES,
                        C.RESTING_HAND_MARGIN)
    outs = [o for o in (seg.update(f) for f in frames) if o is not None]
    assert len(outs) == 1, len(outs)
    return outs[0]


class PipelineTest(unittest.TestCase):
    def test_record_train_detect(self):
        """RF-03, RF-04, RF-11 y RNF-02 con datos sintéticos: grabar, entrenar y reconocer a otra
        persona (más lejos, en otra posición, a otra velocidad y zurda)."""
        rng = np.random.RandomState(0)
        with tempfile.TemporaryDirectory() as tmp:
            dataset = os.path.join(tmp, "dataset.csv")
            model = os.path.join(tmp, "model.pkl")
            collector = DataCollector(dataset, os.path.join(tmp, "backups"), backup_every=10)

            # "ana" graba cerca de la cámara con la mano derecha, a velocidades distintas
            for label in TRAJECTORIES:
                for _ in range(8):
                    sign = make_sign(label, rng.randint(20, 50), center=(0.9, 0.6), scale=0.4, rng=rng)
                    collector.save_sequence(label, capture(stream(sign)), "ana")
            self.assertTrue(os.listdir(os.path.join(tmp, "backups")))
            self.assertEqual(collector.remove_last(), "circulo")
            self.assertEqual(collector.count(), 23)
            self.assertEqual(DataCollector(dataset, tmp).count(), 23)   # conteos coinciden con el archivo
            self.assertTrue(train(dataset, model, evaluate=False))

            # "beto" está más lejos, en otra posición, va más rápido o más
            # lento, y a veces es zurdo
            logic = GestureLogic(model, C.FEATURE_VERSION, C.SEQUENCE_LENGTH, C.MIN_CONFIDENCE)
            cases = [(label, n, left) for label in TRAJECTORIES for n in (15, 35, 70) for left in (False, True)]
            hits = 0
            for label, n, left in cases:
                sign = make_sign(label, n, center=(0.6, 0.45), scale=0.22,
                                 hand_slot=0 if left else 1, mirrored=left, rng=rng)
                pred, _ = logic.predict(capture(stream(sign)))
                hits += pred == label
            self.assertGreaterEqual(hits / len(cases), 0.9, f"{hits}/{len(cases)}")

    def test_dataset_only_has_coordinates(self):
        """RNF-04: el dataset solo guarda etiqueta, persona y números (nada de imágenes)."""
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "d.csv")
            DataCollector(path, tmp).save_sequence("hola", capture(stream(make_sign("arriba", 30))), "ana")
            with open(path, encoding="utf-8") as f:
                header, row = list(csv.reader(f))
            self.assertEqual(header[:2], ["label", "person"])
            self.assertEqual(len(row), 2 + C.SEQUENCE_LENGTH * 135)
            [float(v) for v in row[2:]]

    def test_old_model_is_rejected(self):
        """RF-12: un modelo de otra versión de features no se usa."""
        with tempfile.TemporaryDirectory() as tmp:
            import joblib
            path = os.path.join(tmp, "model.pkl")
            joblib.dump({"pipeline": None, "feature_version": 1}, path)
            self.assertIsNone(GestureLogic(path, C.FEATURE_VERSION, C.SEQUENCE_LENGTH).model)


if __name__ == "__main__":
    unittest.main()

"""Regresión con el dataset real de la versión anterior (data/legacy/dataset_v1.csv).

Simula la cámara: cada seña grabada se acelera o se alarga (0.6x a 2x) y se
rodea de frames sin manos. El segmentador debe entregar exactamente una seña y
el modelo reconocerla. Con la ventana deslizante de la versión anterior este
mismo experimento daba ~40 %; con el segmentador, ~99 %.
"""
import os
import unittest

import numpy as np

import config as C
from modules.landmarks import prepare_sequence, resample
from modules.segmenter import SignSegmenter

LEGACY = os.path.join(C.DATA_DIR, "legacy", "dataset_v1.csv")


@unittest.skipUnless(os.path.exists(LEGACY), "no está el dataset legacy")
class LegacyRegressionTest(unittest.TestCase):
    def test_segmenter_on_real_signs_at_any_speed(self):
        """RF-03 / RF-04: misma preparación al grabar y detectar, con señas reales a distintas velocidades."""
        import pandas as pd
        from sklearn.ensemble import RandomForestClassifier

        df = pd.read_csv(LEGACY)
        df = df[~df.person.str.endswith("_espejo")]
        X = df.drop(columns=["label", "person"]).values.astype(np.float32).reshape(len(df), 30, 126)
        y = df.label.values
        rng = np.random.RandomState(1)
        idx = rng.permutation(len(X))
        cut = int(0.75 * len(X))
        train, test = idx[:cut], idx[cut:]

        prepared = np.array([prepare_sequence(s, 30, 5) for s in X[train]])
        model = RandomForestClassifier(150, n_jobs=-1, random_state=0)
        model.fit(prepared.reshape(len(prepared), -1), y[train])

        hits = 0
        for i in test:
            n = max(12, int(round(30 * rng.uniform(0.6, 2.0))))
            frames = np.concatenate([np.zeros((15, 126)), resample(X[i], n), np.zeros((15, 126))]).astype(np.float32)
            seg = SignSegmenter(30, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES, C.SEGMENT_MIN_FRAMES,
                                C.SEGMENT_MAX_FRAMES, C.SEGMENT_CONTEXT_FRAMES, C.RESTING_HAND_MARGIN)
            outs = [o for o in (seg.update(f) for f in frames) if o is not None]
            if len(outs) == 1:
                hits += model.predict([outs[0].reshape(-1)])[0] == y[i]
        self.assertGreaterEqual(hits / len(test), 0.95, f"{hits}/{len(test)}")


if __name__ == "__main__":
    unittest.main()

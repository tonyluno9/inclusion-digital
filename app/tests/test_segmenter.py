import unittest

import numpy as np

from modules.landmarks import HAND_SIZE
from modules.segmenter import SignSegmenter
from tests.synthetic import make_sign, stream


def run(segmenter, frames):
    return [out for out in (segmenter.update(f) for f in frames) if out is not None]


class SegmenterTest(unittest.TestCase):
    def make(self):
        return SignSegmenter(length=30, start_frames=3, end_frames=8, min_frames=10, max_frames=90)

    def test_one_sign_one_segment_any_speed(self):
        for n in (15, 30, 60):
            outs = run(self.make(), stream(make_sign("arriba", n)))
            self.assertEqual(len(outs), 1, n)
            self.assertEqual(outs[0].shape[0], 30)

    def test_two_signs_two_segments(self):
        frames = np.concatenate([stream(make_sign("arriba", 30)), stream(make_sign("derecha", 30))])
        self.assertEqual(len(run(self.make(), frames)), 2)

    def test_short_flicker_ignored(self):
        self.assertEqual(run(self.make(), stream(make_sign("arriba", 2))), [])

    def test_short_dropout_does_not_split(self):
        sign = make_sign("circulo", 40)
        sign[15:19, HAND_SIZE:2 * HAND_SIZE] = 0  # MediaPipe pierde la mano 4 frames
        self.assertEqual(len(run(self.make(), stream(sign))), 1)

    def test_max_length_forces_cut_without_junk_tail(self):
        """RF-03 / H4: tras un corte forzado no se genera una segunda seña con el resto."""
        outs = run(self.make(), stream(make_sign("arriba", 200)))
        self.assertEqual(len(outs), 1)

    def test_resting_hand_is_ignored(self):
        """RF-03 / M2: una mano apoyada abajo (visible) no cuenta como seña."""
        sign = make_sign("arriba", 30, hand_slot=1)
        resting = make_sign("arriba", 1, hand_slot=0, center=(0.9, 0.6), noise=0)[0]
        resting[:63].reshape(21, 3)[:, 1] += 0.6   # muy por debajo de los hombros
        frames = stream(sign)
        frames[:, :63] = resting[:63]               # la mano izquierda descansa todo el tiempo
        outs = run(self.make(), frames)
        self.assertEqual(len(outs), 1)
        self.assertTrue(np.all(outs[0][:, :63] == 0))

    def test_body_reference_from_idle_frames(self):
        """RF-03: la referencia del cuerpo viene de los frames sin manos, no de la seña."""
        sign = make_sign("arriba", 30)
        frames = stream(sign)
        idle_pose = frames[0, 126:].copy()
        frames[20:50, 126:] = 0          # durante la seña los brazos tapan los hombros
        outs = run(self.make(), frames)
        np.testing.assert_allclose(outs[0][:, 126:], np.tile(idle_pose, (30, 1)))


if __name__ == "__main__":
    unittest.main()

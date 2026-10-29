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

    def test_max_length_forces_cut(self):
        outs = run(self.make(), stream(make_sign("arriba", 200)))
        self.assertGreaterEqual(len(outs), 2)


if __name__ == "__main__":
    unittest.main()

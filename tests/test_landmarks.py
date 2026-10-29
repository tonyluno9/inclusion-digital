import unittest

import numpy as np

from modules.landmarks import (HAND_SIZE, RAW_FRAME_SIZE, fill_gaps, hands_present, mirror_features,
                               prepare_sequence, resample, sequence_features, trim)
from tests.synthetic import make_sign


class LandmarksTest(unittest.TestCase):
    def test_trim_removes_frames_without_hands(self):
        sign = make_sign("arriba", 20)
        empty = np.zeros((5, RAW_FRAME_SIZE), dtype=np.float32)
        out = trim(np.concatenate([empty, sign, empty]))
        self.assertEqual(len(out), 20)
        self.assertTrue(hands_present(out[0]) and hands_present(out[-1]))

    def test_resample_any_length(self):
        for n in (12, 30, 77):
            self.assertEqual(resample(make_sign("arriba", n), 30).shape, (30, RAW_FRAME_SIZE))

    def test_fill_gaps_short_gap_only(self):
        sign = make_sign("derecha", 30)
        short, long_ = sign.copy(), sign.copy()
        short[10:13, HAND_SIZE:2 * HAND_SIZE] = 0
        long_[10:20, HAND_SIZE:2 * HAND_SIZE] = 0
        filled = fill_gaps(short)
        self.assertTrue(all(hands_present(f) for f in filled[10:13]))
        np.testing.assert_allclose(filled[11], (sign[10] + sign[12]) / 2, atol=0.05)
        self.assertFalse(any(hands_present(f) for f in fill_gaps(long_)[10:20]))

    def test_prepare_rejects_short(self):
        self.assertIsNone(prepare_sequence(make_sign("arriba", 5), 30, 10))

    def test_features_ignore_distance_and_position(self):
        near = sequence_features(make_sign("circulo", 30, center=(0.9, 0.6), scale=0.4, rng=np.random.RandomState(0)))
        far = sequence_features(make_sign("circulo", 30, center=(0.5, 0.4), scale=0.2, rng=np.random.RandomState(0)))
        self.assertLess(np.abs(near - far).max(), 1e-3)

    def test_absent_hand_stays_zero(self):
        feat = sequence_features(make_sign("arriba", 30, hand_slot=1))
        self.assertTrue(np.all(feat[:, :HAND_SIZE] == 0))

    def test_mirror_matches_left_handed_signer(self):
        right = sequence_features(make_sign("derecha", 30, hand_slot=1, rng=np.random.RandomState(0)))
        left = sequence_features(make_sign("derecha", 30, hand_slot=0, mirrored=True, rng=np.random.RandomState(0)))
        np.testing.assert_allclose(mirror_features(right), left, atol=0.1)
        np.testing.assert_allclose(mirror_features(mirror_features(right)), right)


if __name__ == "__main__":
    unittest.main()

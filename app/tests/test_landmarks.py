import unittest

import numpy as np

from modules.landmarks import (HAND_SIZE, assign_slots, RAW_FRAME_SIZE, fill_gaps, hands_present, mirror_features,
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
        """RF-03: las features no dependen de la distancia ni de la posición en la imagen."""
        near = sequence_features(make_sign("circulo", 30, center=(0.9, 0.6), scale=0.4, rng=np.random.RandomState(0)))
        far = sequence_features(make_sign("circulo", 30, center=(0.5, 0.4), scale=0.2, rng=np.random.RandomState(0)))
        self.assertLess(np.abs(near - far).max(), 1e-3)

    def test_absent_hand_stays_zero(self):
        feat = sequence_features(make_sign("arriba", 30, hand_slot=1))
        self.assertTrue(np.all(feat[:, :HAND_SIZE] == 0))

    def test_mirror_matches_left_handed_signer(self):
        """RF-11: el espejo del aumento de datos equivale a una persona zurda."""
        right = sequence_features(make_sign("derecha", 30, hand_slot=1, noise=0))
        left = sequence_features(make_sign("derecha", 30, hand_slot=0, mirrored=True, noise=0))
        np.testing.assert_allclose(mirror_features(right), left, atol=1e-4)
        np.testing.assert_allclose(mirror_features(mirror_features(right)), right)

    def test_slots_by_label_without_history(self):
        """RF-02: sin historial, cada mano va al lugar que dice MediaPipe."""
        self.assertEqual(assign_slots([(1, 0.9, (0.5, 0.5))], [None, None]), [1])
        self.assertEqual(assign_slots([(0, 0.9, (0.5, 0.5)), (0, 0.6, (0.8, 0.5))], [None, None]), [0, 1])

    def test_slots_keep_continuity_when_label_flickers(self):
        """RF-02 / M1: si la etiqueta parpadea, la mano conserva su lugar."""
        self.assertEqual(assign_slots([(0, 0.9, (0.52, 0.5))], [None, (0.5, 0.5)]), [1])
        both = assign_slots([(1, 0.9, (0.31, 0.5)), (0, 0.9, (0.71, 0.5))], [(0.3, 0.5), (0.7, 0.5)])
        self.assertEqual(both, [0, 1])

    def test_slots_fall_back_to_label_after_big_jump(self):
        self.assertEqual(assign_slots([(0, 0.9, (0.1, 0.1))], [None, (0.9, 0.9)]), [0])


if __name__ == "__main__":
    unittest.main()

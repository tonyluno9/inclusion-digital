"""verificar_senas.py (RF-30): cada muestra pasa por la cámara simulada y un modelo que no la vio."""
import contextlib
import io
import os
import tempfile
import unittest

import numpy as np

import config as C
import verificar_senas as vs
from modules.data_collector import DataCollector
from modules.landmarks import prepare_sequence
from tests.synthetic import make_sign


class VerificarSenasTest(unittest.TestCase):
    def test_senas_distintas_se_reconocen_por_la_camara_simulada(self):
        rng = np.random.RandomState(1)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "dataset.csv")
            dc = DataCollector(ruta, os.path.join(tmp, "b"))
            for sena, persona in [("arriba", "ana"), ("derecha", "ana"), ("arriba", "luis"), ("derecha", "luis")]:
                for _ in range(6):
                    muestra = make_sign(sena, rng.randint(25, 40), rng=rng)
                    dc.save_sequence(sena, prepare_sequence(muestra, C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES),
                                     person=persona)
            with contextlib.redirect_stdout(io.StringIO()) as salida:
                acierto, fallas = vs.verificar(ruta)
        self.assertGreater(acierto, 0.9)
        self.assertIn("Total:", salida.getvalue())
        self.assertLess(len(fallas), 5)

    def test_la_simulacion_entrega_una_sola_sena(self):
        """Cada velocidad produce exactamente una seña por el segmentador real."""
        muestra = prepare_sequence(make_sign("circulo", 30), C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES)
        for v in vs.VELOCIDADES:
            self.assertEqual(len(vs.simular_camara(muestra, v)), 1, f"velocidad {v}")


if __name__ == "__main__":
    unittest.main()

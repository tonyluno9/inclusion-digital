"""DataCollector: persistencia UTF-8, conteos, deshacer, borrado y respaldos."""
import csv
import os
import tempfile
import unittest

import numpy as np

import config as C
from modules.data_collector import DataCollector
from modules.landmarks import OLD_RAW_FRAME_SIZE, RAW_FRAME_SIZE
from train_model import load_dataset

SEQ = np.zeros((C.SEQUENCE_LENGTH, RAW_FRAME_SIZE), dtype=np.float32)


class DataCollectorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.path = os.path.join(self.dir, "datos", "dataset.csv")
        self.backup = os.path.join(self.dir, "respaldo")

    def make(self, backup_every=50):
        return DataCollector(self.path, self.backup, backup_every=backup_every)

    def test_etiquetas_con_enie_y_acentos_ida_y_vuelta(self):
        """RF-10: etiquetas con ñ/acentos se guardan en UTF-8 y se leen igual."""
        dc = self.make()
        for label in ("  Niño ", "CAFÉ", "año"):
            dc.save_sequence(label, SEQ)
        with open(self.path, newline="", encoding="utf-8") as f:
            labels = [r[0] for r in list(csv.reader(f))[1:]]
        self.assertEqual(labels, ["niño", "café", "año"])
        self.assertEqual(self.make().count("niño"), 1)
        self.assertEqual(dc.count("NIÑO "), 1)

    def test_load_dataset_conserva_acentos_y_null(self):
        """RF-10: train_model.load_dataset no convierte la etiqueta 'null' en NaN."""
        import train_model
        dc = self.make()
        for label in ("null", "niño", "none", "na"):
            dc.save_sequence(label, SEQ, person="Ana_espejo")
        raw, y, groups = train_model.load_dataset(self.path)
        self.assertEqual(list(y), ["null", "niño", "none", "na"])
        self.assertEqual(raw.shape, (4, C.SEQUENCE_LENGTH, RAW_FRAME_SIZE))
        self.assertEqual(set(groups), {"ana"})

    def test_conteos_en_memoria_coinciden_con_el_archivo(self):
        """RF-10: los conteos en memoria igualan a los de un DataCollector nuevo."""
        dc = self.make()
        dc.save_sequence("hola", SEQ, "ana")
        dc.save_sequence("hola", SEQ, "luis")
        dc.save_sequence("adios", SEQ, "ana")
        fresh = self.make()
        self.assertEqual(dc.stats(), fresh.stats())
        self.assertEqual(dc.count(), 3)
        self.assertEqual(fresh.count(), 3)
        self.assertEqual(fresh.count("hola"), 2)
        self.assertEqual(fresh.count("nada"), 0)

    def test_persona_vacia_es_anonimo(self):
        """RF-09: sin nombre de persona se usa 'anonimo'."""
        dc = self.make()
        dc.save_sequence("hola", SEQ, "  ")
        self.assertEqual(dc.stats()[1], {"anonimo": 1})

    def test_remove_last(self):
        """RF-09: deshacer borra la última muestra y actualiza conteos."""
        dc = self.make()
        self.assertIsNone(dc.remove_last())
        dc.save_sequence("hola", SEQ)
        dc.save_sequence("adios", SEQ)
        self.assertEqual(dc.remove_last(), "adios")
        self.assertEqual(dc.count(), 1)
        self.assertEqual(dc.count("adios"), 0)
        self.assertEqual(self.make().stats(), dc.stats())
        self.assertEqual(dc.remove_last(), "hola")
        self.assertIsNone(dc.remove_last())

    def test_delete_label_ignora_mayusculas_y_espacios(self):
        """RF-10: borrar una seña no distingue mayúsculas ni espacios."""
        dc = self.make()
        for label in ("hola", "hola", "adios"):
            dc.save_sequence(label, SEQ)
        self.assertEqual(dc.delete_label("  HOLA "), 2)
        self.assertEqual(dc.count("hola"), 0)
        self.assertEqual(dc.count(), 1)
        self.assertEqual(dc.delete_label("inexistente"), 0)
        self.assertEqual(self.make().stats(), dc.stats())

    def test_reescritura_atomica_sin_tmp(self):
        """RNF-09: la reescritura atómica no deja archivo .tmp."""
        dc = self.make()
        dc.save_sequence("hola", SEQ)
        dc.save_sequence("adios", SEQ)
        dc.remove_last()
        dc.delete_label("hola")
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        self.assertTrue(os.path.isfile(self.path))
        with open(self.path, newline="", encoding="utf-8") as f:
            self.assertEqual(len(list(csv.reader(f))), 1)  # solo encabezado

    def test_respaldo_cada_n_muestras(self):
        """RF-10: se crea un respaldo cada backup_every muestras."""
        dc = self.make(backup_every=2)
        dc.save_sequence("a", SEQ)
        self.assertFalse(os.path.isdir(self.backup))
        dc.save_sequence("b", SEQ)
        self.assertEqual(len(os.listdir(self.backup)), 1)
        self.assertTrue(os.listdir(self.backup)[0].endswith(".csv"))

    def write_old_format(self, rows):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        width = C.SEQUENCE_LENGTH * OLD_RAW_FRAME_SIZE
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["label", "person"] + [f"f{i}" for i in range(width)])
            for label, person, value in rows:
                w.writerow([label, person] + [f"{value:.5f}"] * width)

    def test_migracion_del_formato_sin_codos(self):
        """RNF-09 / RF-17: un dataset del formato anterior se respalda y se convierte
        al abrirlo; las muestras viejas conservan sus valores y se pueden agregar nuevas."""
        self.write_old_format([("hola", "tony", 0.25), ("buenas tardes", "tony", 0.5)])
        dc = DataCollector(self.path, self.backup, sequence_length=C.SEQUENCE_LENGTH)
        self.assertEqual(dc.migrated, 2)
        self.assertEqual(dc.count(), 2)
        backups = os.listdir(self.backup)
        self.assertEqual(len(backups), 1)
        self.assertIn("formato135", backups[0])

        raw, y, groups = load_dataset(self.path)
        self.assertEqual(raw.shape, (2, C.SEQUENCE_LENGTH, RAW_FRAME_SIZE))
        np.testing.assert_allclose(raw[0, :, :OLD_RAW_FRAME_SIZE], 0.25)
        self.assertTrue(np.all(raw[:, :, OLD_RAW_FRAME_SIZE:] == 0))
        self.assertEqual(list(y), ["hola", "buenas tardes"])

        dc.save_sequence("hola", SEQ, person="tony")             # ya no choca con el formato
        self.assertEqual(dc.count("hola"), 2)
        again = DataCollector(self.path, self.backup, sequence_length=C.SEQUENCE_LENGTH)
        self.assertEqual(again.migrated, 0)                      # no se migra dos veces

    def test_entrenar_lee_el_formato_anterior_sin_migrar(self):
        """RF-11: train_model.py acepta un dataset viejo que no se ha abierto con la app."""
        self.write_old_format([("hola", "tony", 0.1)])
        raw, _, _ = load_dataset(self.path)
        self.assertEqual(raw.shape, (1, C.SEQUENCE_LENGTH, RAW_FRAME_SIZE))

    def test_formato_distinto_lanza_value_error(self):
        """RNF-09: un CSV con otro número de columnas se rechaza sin tocarlo."""
        dc = self.make()
        dc.save_sequence("hola", SEQ)
        with self.assertRaises(ValueError):
            dc.save_sequence("hola", np.zeros((C.SEQUENCE_LENGTH, 10)))
        self.assertEqual(dc.count(), 1)


if __name__ == "__main__":
    unittest.main()

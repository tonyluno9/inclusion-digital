import os
import csv
import shutil
import time

import numpy as np


class DataCollector:
    """Guarda cada seña grabada como una fila: label, person, f0..fN
    (la secuencia cruda ya recortada y remuestreada, aplanada)."""

    def __init__(self, file_path, backup_dir, backup_every=50):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self.backup_every = backup_every
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def _read_rows(self):
        if not os.path.isfile(self.file_path):
            return None, []
        with open(self.file_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            return header, list(reader)

    def _write_rows(self, header, rows):
        with open(self.file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    def save_sequence(self, label, sequence, person="anonimo"):
        values = np.asarray(sequence, dtype=np.float32).reshape(-1)
        file_exists = os.path.isfile(self.file_path)
        with open(self.file_path, mode="a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["label", "person"] + [f"f{i}" for i in range(len(values))])
            writer.writerow([label.lower().strip(), person.strip()] + [f"{v:.5f}" for v in values])
        self._auto_backup()

    def count(self):
        _, rows = self._read_rows()
        return len(rows)

    def remove_last(self):
        """Borra la última muestra guardada. Devuelve su label o None."""
        header, rows = self._read_rows()
        if not rows:
            return None
        last = rows.pop()
        self._write_rows(header, rows)
        return last[0]

    def delete_label(self, label):
        """Borra todas las muestras de una seña. Devuelve cuántas borró."""
        header, rows = self._read_rows()
        target = label.lower().strip()
        kept = [r for r in rows if r[0] != target]
        if len(kept) != len(rows):
            self._write_rows(header, kept)
        return len(rows) - len(kept)

    def stats(self):
        """{label: n} y {persona: n}"""
        _, rows = self._read_rows()
        labels, persons = {}, {}
        for r in rows:
            labels[r[0]] = labels.get(r[0], 0) + 1
            persons[r[1]] = persons.get(r[1], 0) + 1
        return labels, persons

    def _auto_backup(self):
        try:
            n = self.count()
            if n > 0 and n % self.backup_every == 0:
                os.makedirs(self.backup_dir, exist_ok=True)
                name = os.path.basename(self.file_path).replace(".csv", f"_{int(time.time())}.csv")
                backup_path = os.path.join(self.backup_dir, name)
                shutil.copy2(self.file_path, backup_path)
                print(f"[BACKUP] Dataset respaldado en {backup_path}")
        except Exception as e:
            print(f"[BACKUP] No se pudo respaldar: {e}")

import os
import csv
import json
import shutil
import time
from collections import Counter

import numpy as np

from modules.landmarks import HAND_SIZE, HANDS_SIZE, OLD_RAW_FRAME_SIZE, RAW_FRAME_SIZE

MANOS_ANATOMICAS = "anatomicas"   # marca del .meta.json: manos en el lado real de la persona


class DataCollector:
    """Guarda cada seña grabada como una fila: label, person, f0..fN
    (la secuencia cruda ya recortada y remuestreada, aplanada).

    El CSV es UTF-8. Los conteos se mantienen en memoria para no releer el
    archivo en cada muestra, y las reescrituras (deshacer, borrar) son atómicas.

    Con `sequence_length`, al abrir un dataset de versiones anteriores se
    respalda y se corrige:
    - formato de 135 valores (sin codos): se completa con ceros;
    - manos grabadas con el lado cambiado (antes de usar las muñecas del cuerpo
      para ubicarlas): se intercambian. Un archivo `.meta.json` al lado del CSV
      marca que ya está corregido.
    """

    def __init__(self, file_path, backup_dir, backup_every=50, sequence_length=None):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self.backup_every = backup_every
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self._labels = Counter()
        self._persons = Counter()
        self._order = []          # (label, person) en el orden del archivo
        self.migrated = 0         # muestras convertidas del formato anterior al abrir
        self.hands_fixed = 0      # muestras con las manos cambiadas de lado al abrir
        self.meta_path = os.path.splitext(self.file_path)[0] + ".meta.json"
        if sequence_length:
            self._migrate(sequence_length)
            self._fix_hand_sides(sequence_length)
        self._load_counts()

    def _backup(self, tag):
        os.makedirs(self.backup_dir, exist_ok=True)
        name = os.path.basename(self.file_path).replace(".csv", f"_{tag}_{int(time.time())}.csv")
        path = os.path.join(self.backup_dir, name)
        shutil.copy2(self.file_path, path)
        return path

    def _write_meta(self):
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump({"manos": MANOS_ANATOMICAS}, f)

    def _fix_hand_sides(self, sequence_length):
        if os.path.isfile(self.meta_path):
            with open(self.meta_path, encoding="utf-8") as f:
                if json.load(f).get("manos") == MANOS_ANATOMICAS:
                    return
        header, rows = self._read_rows()
        if header is None or len(header) - 2 != sequence_length * RAW_FRAME_SIZE:
            return
        if rows:
            backup = self._backup("manos_cambiadas")
            for r in rows:
                for start in range(2, len(r), RAW_FRAME_SIZE):
                    left, right = r[start:start + HAND_SIZE], r[start + HAND_SIZE:start + HANDS_SIZE]
                    r[start:start + HANDS_SIZE] = right + left
            self._write_rows(header, rows)
            self.hands_fixed = len(rows)
            print(f"[DATASET] {len(rows)} muestras con las manos corregidas de lado (respaldo en {backup})")
        self._write_meta()

    def _migrate(self, sequence_length):
        header, rows = self._read_rows()
        if header is None or len(header) - 2 != sequence_length * OLD_RAW_FRAME_SIZE:
            return
        backup = self._backup("formato135")
        pad = ["0"] * (RAW_FRAME_SIZE - OLD_RAW_FRAME_SIZE)
        new_rows = []
        for r in rows:
            values = r[2:]
            frames = [values[i:i + OLD_RAW_FRAME_SIZE] for i in range(0, len(values), OLD_RAW_FRAME_SIZE)]
            new_rows.append(r[:2] + [v for fr in frames for v in fr + pad])
        width = sequence_length * RAW_FRAME_SIZE
        self._write_rows(["label", "person"] + [f"f{i}" for i in range(width)], new_rows)
        self.migrated = len(new_rows)
        print(f"[DATASET] {len(new_rows)} muestras convertidas al formato con codos (respaldo en {backup})")

    def _read_rows(self):
        if not os.path.isfile(self.file_path):
            return None, []
        with open(self.file_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            return header, [r for r in reader if r]

    def _load_counts(self):
        _, rows = self._read_rows()
        self._order = [(r[0], r[1]) for r in rows]
        self._recount()

    def _recount(self):
        self._labels = Counter(label for label, _ in self._order)
        self._persons = Counter(person for _, person in self._order)

    def _write_rows(self, header, rows):
        tmp_path = self.file_path + ".tmp"
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        os.replace(tmp_path, self.file_path)

    def save_sequence(self, label, sequence, person="anonimo"):
        label = label.lower().strip()
        person = person.lower().strip() or "anonimo"
        values = np.asarray(sequence, dtype=np.float32).reshape(-1)
        file_exists = os.path.isfile(self.file_path)
        if file_exists:
            with open(self.file_path, newline="", encoding="utf-8") as f:
                header = next(csv.reader(f), [])
            if len(header) != len(values) + 2:
                raise ValueError(
                    f"{self.file_path} tiene otro formato ({len(header) - 2} valores por muestra, "
                    f"esta tiene {len(values)}). Muévelo o bórralo para empezar un dataset nuevo.")
        with open(self.file_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["label", "person"] + [f"f{i}" for i in range(len(values))])
            writer.writerow([label, person] + [f"{v:.5f}" for v in values])
        if not file_exists:
            self._write_meta()       # un dataset nuevo ya nace con las manos en su lado
        self._order.append((label, person))
        self._labels[label] += 1
        self._persons[person] += 1
        self._auto_backup()

    def count(self, label=None):
        return len(self._order) if label is None else self._labels.get(label.lower().strip(), 0)

    def remove_last(self):
        """Borra la última muestra guardada. Devuelve su label o None."""
        header, rows = self._read_rows()
        if not rows:
            return None
        last = rows.pop()
        self._write_rows(header, rows)
        self._order = [(r[0], r[1]) for r in rows]
        self._recount()
        return last[0]

    def delete_label(self, label):
        """Borra todas las muestras de una seña. Devuelve cuántas borró."""
        header, rows = self._read_rows()
        target = label.lower().strip()
        kept = [r for r in rows if r[0] != target]
        if len(kept) != len(rows):
            self._write_rows(header, kept)
            self._order = [(r[0], r[1]) for r in kept]
            self._recount()
        return len(rows) - len(kept)

    def stats(self):
        """{label: n} y {persona: n}"""
        return dict(self._labels), dict(self._persons)

    def _auto_backup(self):
        try:
            n = len(self._order)
            if n > 0 and n % self.backup_every == 0:
                os.makedirs(self.backup_dir, exist_ok=True)
                name = os.path.basename(self.file_path).replace(".csv", f"_{int(time.time())}.csv")
                backup_path = os.path.join(self.backup_dir, name)
                shutil.copy2(self.file_path, backup_path)
                print(f"[BACKUP] Dataset respaldado en {backup_path}")
        except Exception as e:
            print(f"[BACKUP] No se pudo respaldar: {e}")

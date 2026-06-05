import os
import csv

class DataCollector:
    def __init__(self, file_path="data/dataset.csv"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def save_sequence(self, label, sequence, person="anonimo"):
        file_exists = os.path.isfile(self.file_path)

        with open(self.file_path, mode='a', newline='') as f:
            writer = csv.writer(f)

            if not file_exists:
                headers = ['label', 'person'] + [f'f{i}' for i in range(len(sequence))]
                writer.writerow(headers)

            row = [label.lower().strip(), person] + list(sequence)
            writer.writerow(row)

        # Backup automático cada 50 muestras
        self._auto_backup()

    def _auto_backup(self):
        try:
            import shutil, time
            df_len = sum(1 for _ in open(self.file_path)) - 1
            if df_len > 0 and df_len % 50 == 0:
                backup_path = self.file_path.replace('.csv', f'_backup_{int(time.time())}.csv')
                shutil.copy2(self.file_path, backup_path)
                print(f"[BACKUP] Dataset respaldado en {backup_path}")
        except Exception:
            pass

    def get_persons(self):
        """Devuelve lista de personas únicas en el dataset"""
        if not os.path.isfile(self.file_path):
            return []
        persons = set()
        with open(self.file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'person' in row:
                    persons.add(row['person'])
        return sorted(list(persons))

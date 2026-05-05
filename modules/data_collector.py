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

            row = [label, person] + list(sequence)
            writer.writerow(row)

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

import os
import csv

class DataCollector:
    def __init__(self, file_path="data/dataset.csv"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
    def save_sequence(self, label, sequence):
        file_exists = os.path.isfile(self.file_path)
        
        with open(self.file_path, mode='a', newline='') as f:
            writer = csv.writer(f)
            
            # Escribir cabecera la primera vez
            if not file_exists:
                headers = ['label'] + [f'f{i}' for i in range(len(sequence))]
                writer.writerow(headers)
            
            # Añadir etiqueta y vector numérico
            row = [label] + list(sequence)
            writer.writerow(row)

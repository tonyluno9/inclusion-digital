"""Borra todas las muestras de una seña del dataset (también disponible con 'x' en main.py)."""
import config as C
from modules.data_collector import DataCollector


def clear_word():
    collector = DataCollector(C.DATASET_PATH, C.BACKUP_DIR, C.BACKUP_EVERY)
    labels, _ = collector.stats()
    if not labels:
        print("El dataset no existe o está vacío.")
        return
    print(f"Señas disponibles: {sorted(labels)}")
    word = input("Ingresa la palabra que quieres BORRAR del dataset: ").strip()
    if not word:
        print("Operación cancelada.")
        return
    removed = collector.delete_label(word)
    if removed:
        print(f"¡Éxito! Se borraron {removed} muestras de '{word}'.")
        print("Recuerda volver a entrenar (tecla 'e' o python train_model.py).")
    else:
        print(f"No se encontró la palabra '{word}' en el dataset.")


if __name__ == "__main__":
    clear_word()

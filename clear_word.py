import pandas as pd
import os

def clear_word():
    dataset_path = "data/dataset.csv"
    if not os.path.exists(dataset_path):
        print("El dataset no existe todavía.")
        return

    word_to_delete = input("Ingresa la palabra que quieres BORRAR del dataset: ").strip().upper()
    
    if not word_to_delete:
        print("Operación cancelada.")
        return

    df = pd.read_csv(dataset_path)
    # Convertir labels a mayúsculas para evitar errores de coincidencia
    df['label'] = df['label'].str.upper()
    
    before_count = len(df)
    df_filtered = df[df['label'] != word_to_delete]
    after_count = len(df_filtered)

    if before_count == after_count:
        print(f"No se encontró la palabra '{word_to_delete}' en el dataset.")
    else:
        df_filtered.to_csv(dataset_path, index=False)
        deleted = before_count - after_count
        print(f"¡Éxito! Se borraron {deleted} muestras de la palabra '{word_to_delete}'.")
        print("Recuerda volver a ejecutar train_model.py para aplicar los cambios.")

if __name__ == "__main__":
    clear_word()

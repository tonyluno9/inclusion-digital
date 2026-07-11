import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def train_tf():
    dataset_path = os.path.join(BASE_DIR, "data", "dataset.csv")
    model_path = os.path.join(BASE_DIR, "data", "model.tflite")

    if not os.path.exists(dataset_path):
        print("[TF] Error: No se encontró el dataset.")
        return False

    df = pd.read_csv(dataset_path)
    if len(df) < 5:
        print("[TF] Dataset muy pequeño.")
        return False

    # Preparar datos
    drop_cols = [c for c in df.columns if c in ['label', 'person'] or df[c].dtype not in ['float64', 'int64']]
    X = df.drop(drop_cols, axis=1).values.astype(np.float32)
    y_labels = df['label'].values

    # Codificar etiquetas
    clases = sorted(list(set(y_labels)))
    label_to_idx = {l: i for i, l in enumerate(clases)}
    y = np.array([label_to_idx[l] for l in y_labels])

    print(f"[TF] {len(X)} muestras | {len(clases)} señas: {clases}")

    # Guardar clases para usarlas en Flutter
    clases_path = os.path.join(BASE_DIR, "data", "clases.txt")
    with open(clases_path, 'w') as f:
        f.write('\n'.join(clases))
    print(f"[TF] Clases guardadas en {clases_path}")

    # Normalizar
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-8
    X_norm = (X - mean) / std

    # Guardar normalización para Flutter
    np.save(os.path.join(BASE_DIR, "data", "mean.npy"), mean)
    np.save(os.path.join(BASE_DIR, "data", "std.npy"), std)

    # Data augmentation
    X_aug = [X_norm]
    y_aug = [y]
    for _ in range(4):
        noise = np.random.normal(0, 0.002, X_norm.shape).astype(np.float32)
        X_aug.append(X_norm + noise)
        y_aug.append(y)
    X_norm = np.concatenate(X_aug)
    y = np.concatenate(y_aug)

    print(f"[TF] Dataset aumentado: {len(X_norm)} muestras")

    # Importar TensorFlow
    try:
        import tensorflow as tf
    except ImportError:
        print("[TF] Instalando TensorFlow...")
        os.system("py -m pip install tensorflow")
        import tensorflow as tf

    # Construir red neuronal
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(X_norm.shape[1],)),
        tf.keras.layers.Dense(256, activation='relu'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(len(clases), activation='softmax')
    ])

    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )

    print("[TF] Entrenando red neuronal...")
    model.fit(
        X_norm, y,
        epochs=50,
        batch_size=32,
        validation_split=0.2,
        verbose=1
    )

    # Exportar a TFLite
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()

    with open(model_path, 'wb') as f:
        f.write(tflite_model)

    print(f"[TF] Modelo TFLite guardado en {model_path}")
    print(f"[TF] Tamaño: {len(tflite_model) / 1024:.1f} KB")
    return True

if __name__ == "__main__":
    train_tf()

"""Entrena una red neuronal y la exporta a TFLite (para una futura app móvil).
Requiere: pip install -r requirements-opcional.txt"""
import os
import sys

import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

import config as C
from train_model import augment, features, load_dataset


def train_tf():
    if not os.path.exists(C.DATASET_PATH):
        print("[TF] Error: No se encontró el dataset.")
        return False
    try:
        import tensorflow as tf
    except ImportError:
        print("[TF] TensorFlow no está instalado: pip install -r requirements-opcional.txt")
        return False

    raw, y_labels, groups = load_dataset(C.DATASET_PATH)
    clases = sorted(set(y_labels))
    label_to_idx = {l: i for i, l in enumerate(clases)}
    y = np.array([label_to_idx[l] for l in y_labels])
    print(f"[TF] {len(raw)} muestras | {len(clases)} señas: {clases}")

    with open(os.path.join(C.DATA_DIR, "clases.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(clases))

    # Separar validación ANTES de aumentar datos (si no, se valida con copias
    # de las mismas muestras de entrenamiento y la precisión sale inflada).
    rng = np.random.RandomState(42)
    persons = np.unique(groups)
    if len(persons) >= 2:
        val_person = persons[-1]
        val_mask = groups == val_person
        print(f"[TF] Validando con la persona '{val_person}' (no se usa para entrenar)")
    else:
        val_mask = np.zeros(len(raw), dtype=bool)
        val_mask[rng.permutation(len(raw))[:max(1, len(raw) // 5)]] = True
        print("[TF] Solo hay una persona: la validación será optimista.")

    X_train, y_train = augment(raw[~val_mask], y[~val_mask], rng)
    X_train = X_train.reshape(len(X_train), -1)
    X_val = features(raw[val_mask]).reshape(int(val_mask.sum()), -1)
    y_val = y[val_mask]

    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0) + 1e-8
    np.save(os.path.join(C.DATA_DIR, "mean.npy"), mean)
    np.save(os.path.join(C.DATA_DIR, "std.npy"), std)
    X_train = (X_train - mean) / std
    X_val = (X_val - mean) / std

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(X_train.shape[1],)),
        tf.keras.layers.Dense(256, activation='relu'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(len(clases), activation='softmax')
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

    print("[TF] Entrenando red neuronal...")
    model.fit(X_train, y_train, epochs=50, batch_size=32, shuffle=True,
              validation_data=(X_val, y_val), verbose=1)

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()
    model_path = os.path.join(C.DATA_DIR, "model.tflite")
    with open(model_path, 'wb') as f:
        f.write(tflite_model)

    print(f"[TF] Modelo TFLite guardado en {model_path} ({len(tflite_model) / 1024:.1f} KB)")
    return True


if __name__ == "__main__":
    train_tf()

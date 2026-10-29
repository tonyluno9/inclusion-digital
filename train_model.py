import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

import config as C
from modules.landmarks import RAW_FRAME_SIZE, mirror_features, resample, sequence_features

MIN_SAMPLES_PER_SIGN = 5


def load_dataset(dataset_path):
    """Devuelve X (n, T, 126) features, y (labels) y groups (persona)."""
    df = pd.read_csv(dataset_path)
    values = df.drop(columns=["label", "person"]).values.astype(np.float32)
    if values.shape[1] != C.SEQUENCE_LENGTH * RAW_FRAME_SIZE:
        raise ValueError(
            f"El dataset tiene {values.shape[1]} columnas y se esperaban "
            f"{C.SEQUENCE_LENGTH * RAW_FRAME_SIZE}. ¿Es un dataset de la versión anterior?")
    raw = values.reshape(len(df), C.SEQUENCE_LENGTH, RAW_FRAME_SIZE)
    X = np.stack([sequence_features(seq) for seq in raw])
    y = df["label"].astype(str).values
    groups = df["person"].astype(str).str.replace("_espejo", "", regex=False).values
    return X, y, groups


def augment(X, y, rng, mirror=True, copies=2):
    """Espejo (personas zurdas), ruido pequeño y variaciones de dónde empieza
    y termina la seña (el segmentador nunca corta exactamente igual)."""
    Xs, ys = [X], [y]
    if mirror:
        Xs.append(mirror_features(X))
        ys.append(y)
    base_X, base_y = np.concatenate(Xs), np.concatenate(ys)
    T = base_X.shape[1]
    for _ in range(copies):
        out = np.empty_like(base_X)
        for i, seq in enumerate(base_X):
            a = rng.randint(0, 4)
            b = T - rng.randint(0, 4)
            out[i] = resample(seq[a:b], T)
        out += rng.normal(0, 0.01, out.shape).astype(np.float32) * (out != 0)
        Xs.append(out)
        ys.append(base_y)
    return np.concatenate(Xs), np.concatenate(ys)


def make_pipeline():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1, min_samples_leaf=2)),
    ])


def fit(X, y, rng):
    X_aug, y_aug = augment(X, y, rng)
    model = make_pipeline()
    model.fit(X_aug.reshape(len(X_aug), -1), y_aug)
    return model


def evaluate_model(X, y, groups, rng):
    """Precisión con muestras que el modelo no vio. Si hay varias personas,
    se prueba siempre con una persona que no estuvo en el entrenamiento."""
    persons = np.unique(groups)
    if len(persons) >= 2:
        splitter = GroupKFold(n_splits=min(5, len(persons)))
        splits = splitter.split(X, y, groups)
        print(f"[EVAL] Validación por persona ({len(persons)} personas): mide qué tan bien funciona con gente nueva.")
    else:
        splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
        splits = splitter.split(X, y)
        print("[EVAL] Solo hay UNA persona en el dataset: esta precisión es optimista.")
        print("[EVAL] Con otra persona probablemente será menor. Graba con más gente.")

    y_true, y_pred = [], []
    for train_idx, test_idx in splits:
        model = fit(X[train_idx], y[train_idx], rng)
        y_true.extend(y[test_idx])
        y_pred.extend(model.predict(X[test_idx].reshape(len(test_idx), -1)))
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    acc = float((y_true == y_pred).mean())
    print(classification_report(y_true, y_pred, zero_division=0))
    print(f"[EVAL] Precisión: {acc:.1%}")
    return acc


def train(dataset_path=C.DATASET_PATH, model_path=C.MODEL_PATH, evaluate=True):
    if not os.path.exists(dataset_path):
        print("[TRAIN] Error: No se encontró el dataset. Graba señas con 't'.")
        return False

    try:
        X, y, groups = load_dataset(dataset_path)
    except ValueError as e:
        print(f"[TRAIN] Error: {e}")
        return False

    labels, counts = np.unique(y, return_counts=True)
    few = [f"{l} ({n})" for l, n in zip(labels, counts) if n < MIN_SAMPLES_PER_SIGN]
    if len(labels) < 2 or few:
        print(f"[TRAIN] Se necesitan al menos 2 señas con {MIN_SAMPLES_PER_SIGN} muestras cada una.")
        if few:
            print(f"[TRAIN] Faltan muestras de: {', '.join(few)}")
        return False

    print(f"[TRAIN] {len(X)} muestras | {len(labels)} señas | personas: {sorted(set(groups))}")
    rng = np.random.RandomState(42)
    if evaluate:
        evaluate_model(X, y, groups, rng)

    print("[TRAIN] Entrenando modelo final con todas las muestras...")
    model = fit(X, y, rng)
    joblib.dump({
        "pipeline": model,
        "feature_version": C.FEATURE_VERSION,
        "sequence_length": C.SEQUENCE_LENGTH,
    }, model_path)
    print(f"[TRAIN] Modelo guardado en {model_path}")
    return True


if __name__ == "__main__":
    train()

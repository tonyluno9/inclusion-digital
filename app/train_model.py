import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

import config as C
from modules.landmarks import (HANDS_SIZE, OLD_RAW_FRAME_SIZE, RAW_FRAME_SIZE, mirror_features, resample,
                               sequence_features, upgrade_raw)

MIN_SAMPLES_PER_SIGN = 5
# Deja núcleos libres para que la cámara no se congele al entrenar desde la app
N_JOBS = max(1, (os.cpu_count() or 2) - 2)


def load_dataset(dataset_path):
    """Devuelve raw (n, T, 147), y (labels) y groups (persona).
    Acepta también el formato anterior (sin codos), que completa con ceros."""
    df = pd.read_csv(dataset_path, encoding="utf-8", keep_default_na=False,
                     dtype={"label": str, "person": str})
    values = df.drop(columns=["label", "person"]).values.astype(np.float32)
    for frame_size in (RAW_FRAME_SIZE, OLD_RAW_FRAME_SIZE):
        if values.shape[1] == C.SEQUENCE_LENGTH * frame_size:
            break
    else:
        raise ValueError(
            f"El dataset tiene {values.shape[1]} columnas y se esperaban "
            f"{C.SEQUENCE_LENGTH * RAW_FRAME_SIZE}. ¿Es un dataset de la versión anterior?")
    raw = upgrade_raw(values.reshape(len(df), C.SEQUENCE_LENGTH, frame_size))
    y = df["label"].values
    groups = df["person"].str.replace("_espejo", "", regex=False).values
    return raw, y, groups


def features(raw):
    return np.stack([sequence_features(seq) for seq in raw])


def augment(raw, y, rng, mirror=True, copies=1):
    """Aumento de datos, sobre features:
    - sin cuerpo: la misma seña como se vería si no se detectan los hombros;
    - espejo: para personas zurdas;
    - variaciones de dónde empieza y termina la seña, más ruido pequeño."""
    no_body = raw.copy()
    no_body[:, :, HANDS_SIZE:] = 0
    X = np.concatenate([features(raw), features(no_body)])
    Y = np.concatenate([y, y])
    if mirror:
        X = np.concatenate([X, mirror_features(X)])
        Y = np.concatenate([Y, Y])
    Xs, ys = [X], [Y]
    T = X.shape[1]
    for _ in range(copies):
        out = np.empty_like(X)
        for i, seq in enumerate(X):
            a = rng.randint(0, 4)
            b = T - rng.randint(0, 4)
            out[i] = resample(seq[a:b], T)
        out += rng.normal(0, 0.01, out.shape).astype(np.float32) * (out != 0)
        Xs.append(out)
        ys.append(Y)
    return np.concatenate(Xs), np.concatenate(ys)


def make_pipeline():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=N_JOBS, min_samples_leaf=2)),
    ])


def fit(raw, y, rng):
    X_aug, y_aug = augment(raw, y, rng)
    model = make_pipeline()
    model.fit(X_aug.reshape(len(X_aug), -1), y_aug)
    return model


def evaluate_model(raw, y, groups, rng):
    """Precisión con muestras que el modelo no vio. Si hay varias personas,
    se prueba siempre con una persona que no estuvo en el entrenamiento."""
    persons = np.unique(groups)
    if len(persons) >= 2:
        splits = GroupKFold(n_splits=min(5, len(persons))).split(raw, y, groups)
        print(f"[EVAL] Validación por persona ({len(persons)} personas): mide qué tan bien funciona con gente nueva.")
    else:
        n_splits = max(2, min(5, int(np.unique(y, return_counts=True)[1].min())))
        splits = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=0).split(raw, y)
        print("[EVAL] Solo hay UNA persona en el dataset: esta precisión es optimista.")
        print("[EVAL] Con otra persona probablemente será menor. Graba con más gente (ver requerimientos RNF-02).")

    y_true, y_pred = [], []
    for train_idx, test_idx in splits:
        model = fit(raw[train_idx], y[train_idx], rng)
        X_test = features(raw[test_idx])
        y_true.extend(y[test_idx])
        y_pred.extend(model.predict(X_test.reshape(len(test_idx), -1)))
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    acc = float((y_true == y_pred).mean())

    labels = sorted(set(y_true))
    print(classification_report(y_true, y_pred, labels=labels, zero_division=0))
    print("[EVAL] Matriz de confusión (filas = seña real, columnas = predicha):")
    cm = pd.DataFrame(confusion_matrix(y_true, y_pred, labels=labels), index=labels, columns=labels)
    print(cm.to_string())
    print(f"\n[EVAL] Precisión: {acc:.1%}")
    return acc


def check_dataset(y):
    """Devuelve un mensaje de error o "" si alcanza para entrenar."""
    labels, counts = np.unique(y, return_counts=True)
    few = [f"{l} ({n})" for l, n in zip(labels, counts) if n < MIN_SAMPLES_PER_SIGN]
    if len(labels) < 2 or few:
        msg = f"Se necesitan al menos 2 señas con {MIN_SAMPLES_PER_SIGN} muestras cada una."
        if few:
            msg += f" Faltan muestras de: {', '.join(few)}"
        return msg
    return ""


def train(dataset_path=C.DATASET_PATH, model_path=C.MODEL_PATH, evaluate=True):
    if not os.path.exists(dataset_path):
        print("[TRAIN] Error: No se encontró el dataset. Graba señas con 't'.")
        return False

    try:
        raw, y, groups = load_dataset(dataset_path)
    except (ValueError, UnicodeDecodeError, pd.errors.ParserError) as e:
        print(f"[TRAIN] Error al leer el dataset: {e}")
        return False

    problem = check_dataset(y)
    if problem:
        print(f"[TRAIN] {problem}")
        return False

    labels = sorted(set(y))
    print(f"[TRAIN] {len(raw)} muestras | {len(labels)} señas | personas: {sorted(set(groups))}")
    rng = np.random.RandomState(42)
    if evaluate:
        evaluate_model(raw, y, groups, rng)

    print("[TRAIN] Entrenando modelo final con todas las muestras...")
    model = fit(raw, y, rng)
    tmp_path = model_path + ".tmp"
    joblib.dump({
        "pipeline": model,
        "feature_version": C.FEATURE_VERSION,
        "sequence_length": C.SEQUENCE_LENGTH,
        "labels": labels,
        "persons": sorted(set(groups)),
        "samples": int(len(raw)),
    }, tmp_path)
    os.replace(tmp_path, model_path)
    print(f"[TRAIN] Modelo guardado en {model_path}")
    return True


if __name__ == "__main__":
    train()

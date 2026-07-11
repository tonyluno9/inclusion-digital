import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def train():
    dataset_path = os.path.join(BASE_DIR, "data", "dataset.csv")
    model_path = os.path.join(BASE_DIR, "data", "model.pkl")

    if not os.path.exists(dataset_path):
        print("[TRAIN] Error: No se encontró el dataset.")
        return False

    df = pd.read_csv(dataset_path)
    if len(df) < 5:
        print("[TRAIN] Dataset muy pequeño. Recolecta más muestras.")
        return False

    # Quitar columnas no numéricas
    drop_cols = [c for c in df.columns if c in ['label', 'person'] or not df[c].dtype in ['float64', 'int64']]
    X = df.drop(drop_cols, axis=1)
    y = df['label']

    clases = y.unique()
    muestras = len(df)
    print(f"[TRAIN] {muestras} muestras | {len(clases)} señas: {list(clases)}")
    print("[TRAIN] Entrenando modelo...")

    model_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('rf', RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1, max_depth=15, min_samples_leaf=3))
    ])

    # Data augmentation: ruido gaussiano
    import numpy as np
    print(f"[TRAIN] Aplicando data augmentation...")
    X_aug = X.copy()
    y_aug = y.copy()

    for _ in range(4):  # 4 copias con ruido
        noise = np.random.normal(0, 0.002, X.shape)
        X_noisy = X + noise
        X_aug = pd.concat([X_aug, pd.DataFrame(X_noisy, columns=X.columns)], ignore_index=True)
        y_aug = pd.concat([y_aug, y], ignore_index=True)

    X = X_aug
    y = y_aug
    print(f"[TRAIN] Dataset aumentado: {len(X_aug)} muestras (original + 4x ruido)")

    model_pipeline.fit(X, y)
    joblib.dump(model_pipeline, model_path)
    print(f"[TRAIN] Modelo guardado correctamente.")
    return True

if __name__ == "__main__":
    train()
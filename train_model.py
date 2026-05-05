import pandas as pd
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
        ('rf', RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1))
    ])

    model_pipeline.fit(X, y)
    joblib.dump(model_pipeline, model_path)
    print(f"[TRAIN] Modelo guardado correctamente.")
    return True

if __name__ == "__main__":
    train()
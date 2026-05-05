import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

def train():
    dataset_path = os.path.join(BASE_DIR, "data", "dataset.csv")
    model_path = os.path.join(BASE_DIR, "data", "model.pkl")
    
    if not os.path.exists(dataset_path):
        print(f"Error: No se encontró el dataset.")
        return

    df = pd.read_csv(dataset_path)
    if len(df) < 5:
        print("Dataset muy pequeño. Recolecta más muestras (al menos 5-10 por palabra).")
        return
        
    X = df.drop('label', axis=1)
    y = df['label']
    
    # PIPELINE: Primero normaliza los datos (crucial para evitar sesgos) y luego entrena
    model_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('rf', RandomForestClassifier(n_estimators=200, random_state=42))
    ])

    print("\nEntrenando IA con Normalización...")
    model_pipeline.fit(X, y)
        
    joblib.dump(model_pipeline, model_path)
    print(f"[ÉXITO] Modelo inteligente guardado en {model_path}.")

if __name__ == "__main__":
    train()

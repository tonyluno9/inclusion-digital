import joblib
import os
import numpy as np

class GestureLogic:
    def __init__(self, model_path="data/model.pkl"):
        self.model_path = model_path
        self.model = None
        self.load_model()
        
    def load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                print("[Gestures] Modelo cargado en memoria exitosamente.")
            except Exception as e:
                print(f"[Gestures] Error al cargar el modelo: {e}")
                self.model = None
        else:
            self.model = None
                
    def predict(self, sequence):
        if self.model is None:
            return "", 0.0
            
        try:
            # Reestructurar para el modelo (Pipeline ya incluye el scaler)
            probs = self.model.predict_proba([sequence])[0]
            confidence = max(probs)
            prediction = self.model.predict([sequence])[0]
            
            if confidence < 0.6: # Un poco más exigente para evitar parpadeo
                return "", confidence
                
            return prediction, confidence
        except Exception as e:
            if "Total size" in str(e) or "features" in str(e):
                print(f"[Gestures] Error de dimensión: {e}. Probablemente necesitas re-entrenar el modelo.")
            return "", 0.0

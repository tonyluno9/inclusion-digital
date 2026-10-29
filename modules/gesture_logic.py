import os

import joblib
import numpy as np

from modules.landmarks import sequence_features


class GestureLogic:
    """Carga el modelo entrenado y clasifica una seña ya segmentada."""

    def __init__(self, model_path, feature_version, min_confidence=0.6):
        self.model_path = model_path
        self.feature_version = feature_version
        self.min_confidence = min_confidence
        self.model = None
        self.classes = []
        self.load_model()

    def load_model(self):
        self.model = None
        if not os.path.exists(self.model_path):
            print("[Gestures] No hay modelo todavía. Graba señas y entrena con 'e'.")
            return
        try:
            bundle = joblib.load(self.model_path)
        except Exception as e:
            print(f"[Gestures] Error al cargar el modelo: {e}")
            return
        if not isinstance(bundle, dict) or bundle.get("feature_version") != self.feature_version:
            print("[Gestures] El modelo guardado es de una versión anterior. Reentrena con 'e'.")
            return
        self.model = bundle["pipeline"]
        self.classes = list(self.model.classes_)
        print(f"[Gestures] Modelo cargado: {len(self.classes)} señas.")

    def predict(self, raw_sequence):
        """raw_sequence: (SEQUENCE_LENGTH, 135). Devuelve (seña o "", confianza)."""
        if self.model is None:
            return "", 0.0
        features = sequence_features(raw_sequence).reshape(1, -1)
        probs = self.model.predict_proba(features)[0]
        best = int(np.argmax(probs))
        confidence = float(probs[best])
        if confidence < self.min_confidence:
            return "", confidence
        return self.classes[best], confidence

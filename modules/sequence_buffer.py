from collections import deque
import numpy as np

class SequenceBuffer:
    def __init__(self, max_len=30, features_per_frame=126):
        """
        Buffer deslizante para mantener dinámicamente un tamaño fijo de fotogramas secuenciales.
        Solo manos: 126 features por frame (2 manos x 21 puntos x 3 coordenadas)
        30 frames x 126 features = 3780 features totales
        """
        self.max_len = max_len
        self.features_per_frame = features_per_frame
        self.buffer = deque(maxlen=max_len)

    def add_frame(self, landmarks):
        if not landmarks or len(landmarks) != self.features_per_frame:
            self.buffer.append(np.zeros(self.features_per_frame))
        else:
            self.buffer.append(np.array(landmarks))

    def is_full(self):
        return len(self.buffer) == self.max_len

    def get_sequence(self):
        if not self.is_full():
            return None
        # Vector 1D de (3780,) para Random Forest
        return np.array(self.buffer).flatten()

    def clear(self):
        self.buffer.clear()
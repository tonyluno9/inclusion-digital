from collections import deque
import numpy as np

class SequenceBuffer:
    def __init__(self, max_len=30, features_per_frame=204):
        """
        Buffer deslizante para mantener dinámicamente un tamaño fijo de fotogramas secuenciales.
        Hands (126) + Face (78) = 204
        """
        self.max_len = max_len
        self.features_per_frame = features_per_frame
        self.buffer = deque(maxlen=max_len)
        
    def add_frame(self, landmarks):
        # Si no detectamos mano (arreglo vacío), insertamos ceros 
        # para que la forma temporal se respete.
        if not landmarks or len(landmarks) != self.features_per_frame:
            self.buffer.append(np.zeros(self.features_per_frame))
        else:
            self.buffer.append(np.array(landmarks))
            
    def is_full(self):
        return len(self.buffer) == self.max_len
        
    def get_sequence(self):
        if not self.is_full():
            return None
        # Convertimos la matriz (30, 63) a un vector 1D de (1890,) para Random Forest
        return np.array(self.buffer).flatten()

    def clear(self):
        self.buffer.clear()

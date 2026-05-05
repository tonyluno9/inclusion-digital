import cv2
import numpy as np
import mediapipe as mp

# Solución robusta para evitar errores de importación de attributes en algunas versiones de Python
try:
    import mediapipe.solutions.hands as mp_hands
    import mediapipe.solutions.drawing_utils as mp_drawing
except (ImportError, AttributeError):
    try:
        from mediapipe.python.solutions import hands as mp_hands
        from mediapipe.python.solutions import drawing_utils as mp_drawing
    except (ImportError, AttributeError):
        # LAST RESORT: Try accessing it if it was somehow loaded
        if hasattr(mp, 'solutions'):
            mp_hands = mp.solutions.hands
            mp_drawing = mp.solutions.drawing_utils
        else:
            raise ImportError("Could not find MediaPipe solutions. Please check your installation.")

Hands = mp_hands.Hands
HandConnections = mp_hands.HAND_CONNECTIONS
WristId = mp_hands.HandLandmark.WRIST
draw_landmarks = mp_drawing.draw_landmarks

class HandDetector:
    def __init__(self, max_num_hands=2, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self.hands = Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
    def process(self, frame):
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_rgb.flags.writeable = False
        results = self.hands.process(img_rgb)
        img_rgb.flags.writeable = True
        
        all_landmarks = []
        
        # Procesar hasta 2 manos
        if results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                if i >= 2: break # Solo nos interesan las primeras 2
                
                draw_landmarks(frame, hand_landmarks, HandConnections)
                
                # Normalizar respecto a la muñeca de CADA mano
                wrist = hand_landmarks.landmark[WristId]
                for lm in hand_landmarks.landmark:
                    all_landmarks.extend([
                        lm.x - wrist.x,
                        lm.y - wrist.y,
                        lm.z - wrist.z
                    ])
        
        # Rellenar con ceros si falta alguna mano (para mantener el tamaño del vector fijo en 126)
        # 1 mano = 63 valores. 2 manos = 126 valores.
        while len(all_landmarks) < 126:
            all_landmarks.append(0.0)
            
        return frame, all_landmarks[:126]

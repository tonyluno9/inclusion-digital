import cv2
import mediapipe as mp

try:
    import mediapipe.solutions.face_mesh as mp_face_mesh
    import mediapipe.solutions.drawing_utils as mp_drawing
    import mediapipe.solutions.drawing_styles as mp_drawing_styles
except (ImportError, AttributeError):
    try:
        from mediapipe.python.solutions import face_mesh as mp_face_mesh
        from mediapipe.python.solutions import drawing_utils as mp_drawing
        from mediapipe.python.solutions import drawing_styles as mp_drawing_styles
    except (ImportError, AttributeError):
        raise ImportError("Could not find MediaPipe FaceMesh solutions.")

class FaceDetector:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self.face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)

    def analyze_emotion(self, face_landmarks):
        # Índices clave: 
        # 0: Labio superior (centro), 17: Labio inferior (centro)
        # 61: Comisura izquierda, 291: Comisura derecha
        # 13: Labio superior (interno), 14: Labio inferior (interno)
        # 70/105/107: Ceja izq, 334/336/337: Ceja der
        # 159: Ojo izq (sup), 386: Ojo der (sup)
        
        up_lip = face_landmarks.landmark[13]
        low_lip = face_landmarks.landmark[14]
        left_corner = face_landmarks.landmark[61]
        right_corner = face_landmarks.landmark[291]
        
        # Puntos de las cejas y ojos para detectar enojo
        left_eyebrow = face_landmarks.landmark[107]
        right_eyebrow = face_landmarks.landmark[336]
        left_eye = face_landmarks.landmark[159]
        right_eye = face_landmarks.landmark[386]
        
        # Apertura de boca
        mouth_open = abs(up_lip.y - low_lip.y)
        # Altura media de las comisuras vs el centro del labio
        corners_y = (left_corner.y + right_corner.y) / 2
        smile_factor = up_lip.y - corners_y
        
        # Factor de enojo: cejas bajas y más juntas (fruncir el ceño)
        eyebrow_height = (abs(left_eyebrow.y - left_eye.y) + abs(right_eyebrow.y - right_eye.y)) / 2
        eyebrow_gap = abs(left_eyebrow.x - right_eyebrow.x)
        
        # Umbrales ajustados para mayor sensibilidad
        if mouth_open > 0.05:
            return "SORPRENDIDO"
        elif eyebrow_height < 0.025 or eyebrow_gap < 0.05: # Cejas bajas o muy juntas
            return "ENOJADO"
        elif smile_factor > 0.012: # Un poco más sensible a la sonrisa
            return "FELIZ"
        elif smile_factor < -0.005:
            return "TRISTE / SERIO"
        else:
            return "NEUTRAL"

    def process(self, frame):
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_rgb.flags.writeable = False
        results = self.face_mesh.process(img_rgb)
        img_rgb.flags.writeable = True

        face_features = []
        emotion = "NEUTRAL"

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                emotion = self.analyze_emotion(face_landmarks)
                
                # Dibujar malla facial
                mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style()
                )
                
                key_indices = [
                    0, 13, 14, 17, 37, 39, 40, 61, 78, 80, 81, 82, 87, 88, 91, 95, 
                    70, 105, 107, 334, 336, 337,
                    159, 145, 386, 374
                ]
                
                nose_bridge = face_landmarks.landmark[1]
                for idx in key_indices:
                    lm = face_landmarks.landmark[idx]
                    face_features.extend([
                        lm.x - nose_bridge.x,
                        lm.y - nose_bridge.y,
                        lm.z - nose_bridge.z
                    ])
                break
        
        while len(face_features) < 78:
            face_features.append(0.0)
            
        return frame, face_features[:78], emotion

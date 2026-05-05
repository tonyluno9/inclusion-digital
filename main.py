import os
import cv2
import time
import sys
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from modules.hand_detector import HandDetector
from modules.face_detector import FaceDetector
from modules.sequence_buffer import SequenceBuffer
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from ui.display import DisplayUI
from modules.tts import TTSEngine
from modules.beep import beep_start, beep_stop, beep_error
from modules.stt import STTController


def main():
    SEQUENCE_LENGTH = 30
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Inicialización de módulos
    detector = HandDetector()
    face_detector = FaceDetector()
    buffer = SequenceBuffer(max_len=SEQUENCE_LENGTH, features_per_frame=204)
    collector = DataCollector(file_path=os.path.join(DATA_DIR, "dataset.csv"))
    logic = GestureLogic(model_path=os.path.join(DATA_DIR, "model.pkl"))
    tts = TTSEngine(lang="es")
    STT_MODEL_PATH = os.path.join(DATA_DIR, "vosk-model-small-es-0.42")
    stt = STTController(model_path=STT_MODEL_PATH)
    stt_text = ""

    
    # Estado de la app
    mode = "DETECTION" # "DETECTION" o "TRAINING"
    label_to_train = ""
    is_recording = False
    recording_data = [] # Para grabación manual libre
    prediction = "..."
    current_confidence = 0.0
    action_status = ""
    
    # Iniciar cámara (Resolución nativa)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    # Ajustes de ventana (Ajustable por defecto)
    win_name = "Inclusion Vision HD"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    full_screen = False

    print("\n--- SISTEMA DE SEÑAS CINEMÁTICO ---")
    print("'f': Pantalla completa")
    print("'t': Entrenar nuevas palabras")
    print("'r': Recargar modelo")
    print("'q': Salir")
    print("------------------------------------\n")

    last_prediction_time = time.time()
    prediction = "" 

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame = cv2.flip(frame, 1) # Espejo
        frame, hand_landmarks = detector.process(frame)
        frame, face_landmarks, emotion = face_detector.process(frame)
        
        # Combinar manos y rostro para detectar expresiones (126 + 78 = 204 valores)
        combined_landmarks = hand_landmarks + face_landmarks
        
        # Modo detección: usar el buffer deslizante
        if not is_recording:
            buffer.add_frame(combined_landmarks)
        
        # LÓGICA DE DETECCIÓN AUTOMÁTICA
        if mode != "TRAINING":
            action_status = ""
            if max(hand_landmarks) == 0:
                prediction = ""
            elif buffer.is_full() and (time.time() - last_prediction_time > 0.2):
                sequence = buffer.get_sequence()
                if sequence is not None:
                    pred, conf = logic.predict(sequence)
                    current_confidence = conf
                    if pred and pred != prediction:  # solo habla si la predicción CAMBIÓ
                        prediction = pred
                        tts.speak(prediction)
                    last_prediction_time = time.time()
                
        # MODO ENTRENAMIENTO (Grabación Manual Libre)
        else:
            if is_recording:
                # Esperar a que detecte manos para empezar a capturar datos reales
                if len(recording_data) == 0 and max(hand_landmarks) == 0:
                    action_status = "ESPERANDO MANOS PARA INICIAR..."
                else:
                    recording_data.append(combined_landmarks)
                    action_status = f"GRABANDO '{label_to_train}'... ({len(recording_data)} f)"
            else:
                action_status = f"Listo para '{label_to_train}'. Espacio p/ INICIAR"
                prediction = "MODO ENTRENAMIENTO"
                    
        # Recoger resultado STT si hay
        stt_result = stt.get_result()
        if stt_result:
            stt_text = stt_result

        # Dibujar Interfaz Gráfica
        frame = DisplayUI.draw_info(
            frame=frame,
            mode=mode,
            current_word=prediction if mode == "DETECTION" else label_to_train,
            action_status=action_status,
            buffer_size=len(recording_data) if is_recording else 0,
            max_buffer=SEQUENCE_LENGTH,
            emotion=emotion,
            confidence=current_confidence,
            is_recording=is_recording,
            stt_text=stt_text,
            stt_recording=stt.is_recording
        )
        
        cv2.imshow(win_name, frame)
        tts.process()

        
        # Teclado
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('f'):
            full_screen = not full_screen
            prop = cv2.WINDOW_FULLSCREEN if full_screen else cv2.WINDOW_NORMAL
            cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, prop)
        elif key == ord('t'):
            mode = "TRAINING"
            buffer.clear()
            recording_data = [] 
            is_recording = False
            prediction = "..."
            new_label = input("\nIngresa la palabra a entrenar: ").strip()
            if new_label:
                label_to_train = new_label
        elif key == ord(' '):
            if mode == "TRAINING":
                if label_to_train == "":
                    print("\nError: Primero presiona 't' y ponle nombre.")
                else:
                    if not is_recording:
                        # INICIAR GRABACIÓN
                        is_recording = True
                        recording_data = []
                        buffer.clear()
                        beep_start()
                    else:
                        # TERMINAR GRABACIÓN Y REMUESTREAR
                        is_recording = False
                        if len(recording_data) > 10:
                            indices = np.linspace(0, len(recording_data)-1, SEQUENCE_LENGTH)
                            resampled = []
                            for i in indices:
                                resampled.extend(recording_data[int(i)])
                            collector.save_sequence(label_to_train, resampled)
                            print(f"\n[OK] Seña '{label_to_train}' guardada ({len(recording_data)} f -> 30)")
                            beep_stop()
                        else:
                            print("\n[!] Error: Grabación muy corta. Intenta de nuevo.")
                            beep_error()
                        recording_data = []
        elif key == ord('d'):
            mode = "DETECTION"
            buffer.clear()
            print("\nCambiando a DETECCIÓN.")
            logic.load_model()
        elif key == ord('r'):
            print("\nRecargando modelo...")
            logic.load_model()
            prediction = "..."
        elif key == ord('v') or key == ord('V'):
            estado = tts.toggle()
            print(f"[TTS] {'Activado' if estado else 'Desactivado'}")
        elif key == ord('s'):
            if not stt.is_recording:
                stt_text = ""
                stt.start_recording()
            else:
                stt.stop_recording()


    tts.shutdown()
    cap.release()

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

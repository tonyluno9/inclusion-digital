import os
import cv2
import time
import sys
import numpy as np
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from modules.hand_detector import HandDetector
from modules.sequence_buffer import SequenceBuffer
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from ui.display import DisplayUI
from modules.tts import TTSEngine
from modules.beep import beep_start, beep_stop, beep_error
from modules.stt import STTController
from train_model import train
from clear_word import clear_word
from modules.coherence import make_coherent

from modules.coherence import make_coherent


def main():
    SEQUENCE_LENGTH = 30
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)

    # Inicialización de módulos
    detector = HandDetector()
    buffer = SequenceBuffer(max_len=SEQUENCE_LENGTH, features_per_frame=126)
    collector = DataCollector(file_path=os.path.join(DATA_DIR, "dataset.csv"))
    logic = GestureLogic(model_path=os.path.join(DATA_DIR, "model.pkl"))
    tts = TTSEngine(lang="es")
    STT_MODEL_PATH = os.path.join(DATA_DIR, "vosk-model-small-es-0.42")
    stt = STTController(model_path=STT_MODEL_PATH)
    stt_text = ""

    # Estado de la app
    mode = "DETECTION"
    label_to_train = ""
    is_recording = False
    recording_data = []
    prediction = ""
    current_confidence = 0.0
    action_status = ""
    current_person = "anonimo"
    prediction_counter = {}
    CONFIRM_THRESHOLD = 5 # veces consecutivas para confirmar
    save_mirror = False
    subtitle_history = []
    last_sign_time = time.time()
    coherent_sentence = [""]
    coherence_loading = [False]
    SILENCE_THRESHOLD = 2.5

    # Iniciar cámara
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    win_name = "Inclusion Vision HD"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    full_screen = False

    print("\n--- SISTEMA DE SEÑAS ---")
    print("'t': Entrenar nuevas palabras")
    print("'d': Modo detección")
    print("'r': Recargar modelo")
    print("'e': Entrenar modelo")
    print("'i': Estadísticas del dataset")
    print("'s': Grabar voz (STT)")
    print("'v': Activar/desactivar voz (TTS)")
    print("'f': Pantalla completa")
    print("'x': Borrar seña del dataset")
    print("'q': Salir")
    print("------------------------\n")

    last_prediction_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame, hand_landmarks = detector.process(frame)

        # Modo detección: buffer deslizante solo con manos
        if not is_recording:
            buffer.add_frame(hand_landmarks)

        # LÓGICA DE DETECCIÓN AUTOMÁTICA
        if mode != "TRAINING":
            action_status = ""
            if max(hand_landmarks) == 0:
                prediction = ""
                current_confidence = 0.0
                prediction_counter = {}
                # NO limpiar subtitle_history aquí, lo limpia la coherencia
            else:
                last_sign_time = time.time()
                if buffer.is_full() and (time.time() - last_prediction_time > 0.2):
                    sequence = buffer.get_sequence()
                    if sequence is not None:
                        pred, conf = logic.predict(sequence)
                        current_confidence = conf

                        if pred:
                            prediction_counter[pred] = prediction_counter.get(pred, 0) + 1
                            # Limpiar contadores de otras palabras
                            for k in list(prediction_counter.keys()):
                                if k != pred:
                                    prediction_counter[k] = 0

                            # Confirmar solo si aparece CONFIRM_THRESHOLD veces seguidas
                            if prediction_counter[pred] >= CONFIRM_THRESHOLD:
                                if pred != prediction:
                                    prediction = pred
                                    tts.speak(prediction)
                                    subtitle_history.append(pred)
                                    if len(subtitle_history) > 5:
                                        subtitle_history.pop(0)
                                prediction_counter[pred] = 0  # reset para permitir repetición
                        else:
                            prediction_counter = {}

                        last_prediction_time = time.time()

            # LÓGICA DE COHERENCIA AUTOMÁTICA (Tras silencio)
            if (subtitle_history and 
                time.time() - last_sign_time > SILENCE_THRESHOLD and 
                not coherence_loading[0]):
                
                words_to_process = subtitle_history.copy()
                subtitle_history = []
                coherence_loading[0] = True
                coherent_sentence[0] = ""

                def run_coherence_thread(words):
                    result = make_coherent(words)
                    coherent_sentence[0] = result
                    tts.speak(result)
                    coherence_loading[0] = False

                threading.Thread(
                    target=run_coherence_thread,
                    args=(words_to_process,),
                    daemon=True
                ).start()

        # MODO ENTRENAMIENTO
        else:
            if is_recording:
                if len(recording_data) == 0 and max(hand_landmarks) == 0:
                    action_status = "ESPERANDO MANOS PARA INICIAR..."
                else:
                    recording_data.append(hand_landmarks)
                    action_status = f"GRABANDO '{label_to_train}'... ({len(recording_data)} f)"
            else:
                action_status = f"Listo para '{label_to_train}'. Espacio p/ INICIAR"
                prediction = "MODO ENTRENAMIENTO"

        # Recoger resultado STT
        stt_result = stt.get_result()
        if stt_result:
            stt_text = stt_result

        # Dibujar interfaz
        frame = DisplayUI.draw_info(
            frame=frame,
            mode=mode,
            current_word=prediction if mode == "DETECTION" else label_to_train,
            action_status=action_status,
            buffer_size=len(recording_data) if is_recording else 0,
            max_buffer=SEQUENCE_LENGTH,
            confidence=current_confidence,
            is_recording=is_recording,
            stt_text=stt_text,
            stt_recording=stt.is_recording,
            subtitle_history=subtitle_history,
            coherent_sentence=coherent_sentence[0],
            coherence_loading=coherence_loading[0]
        )

        cv2.imshow(win_name, frame)
        tts.process()

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
            prediction = ""
            new_label = input("\nIngresa la palabra a entrenar: ").strip()
            if new_label:
                label_to_train = new_label
            new_person = input("Ingresa tu nombre (quien graba): ").strip()
            if new_person:
                current_person = new_person
            mirror_input = input("¿Guardar también versión espejo? (s/n): ").strip().lower()
            save_mirror = mirror_input == 's'
            print(f"[OK] Grabando '{label_to_train}' como '{current_person}' | Espejo: {'Sí' if save_mirror else 'No'}")
        elif key == ord(' '):
            if mode == "TRAINING":
                if label_to_train == "":
                    print("\nError: Primero presiona 't' y ponle nombre.")
                else:
                    if not is_recording:
                        is_recording = True
                        recording_data = []
                        buffer.clear()
                        beep_start()
                    else:
                        is_recording = False
                        if len(recording_data) > 10:
                            indices = np.linspace(0, len(recording_data)-1, SEQUENCE_LENGTH)
                            resampled = []
                            for i in indices:
                                resampled.extend(recording_data[int(i)])
                            collector.save_sequence(label_to_train, resampled, person=current_person)
                            print(f"\n[OK] Seña '{label_to_train}' guardada ({len(recording_data)} f -> 30)")

                            if save_mirror:
                                mirrored = []
                                for i, val in enumerate(resampled):
                                    if i % 3 == 0: # Coordenada X
                                        mirrored.append(-val)
                                    else:
                                        mirrored.append(val)
                                collector.save_sequence(label_to_train, mirrored, person=current_person + "_espejo")
                                print(f"[OK] Versión espejo guardada.")
                            beep_stop()
                        else:
                            print("\n[!] Error: Grabación muy corta. Intenta de nuevo.")
                            beep_error()
                        recording_data = []
        elif key == ord('d'):
            mode = "DETECTION"
            buffer.clear()
            prediction = ""
            print("\nCambiando a DETECCIÓN.")
            logic.load_model()
        elif key == ord('r'):
            print("\nRecargando modelo...")
            logic.load_model()
            prediction = ""
        elif key == ord('e'):
            print("\n[TRAIN] Iniciando entrenamiento...")
            mode = "DETECTION"
            buffer.clear()
            prediction = ""
            exito = train()
            if exito:
                logic.load_model()
                print("[TRAIN] Modelo recargado y listo.")
            else:
                print("[TRAIN] Entrenamiento fallido.")
        elif key == ord('i'):
            import pandas as pd
            dataset_path = os.path.join(DATA_DIR, "dataset.csv")
            if not os.path.exists(dataset_path):
                print("\n[INFO] No hay dataset todavía.")
            else:
                df = pd.read_csv(dataset_path)
                print("\n--- ESTADÍSTICAS DEL DATASET ---")
                print(f"Total de muestras: {len(df)}")
                print(f"Señas únicas: {df['label'].nunique()}")
                print("\nMuestras por seña:")
                print(df['label'].value_counts().to_string())
                if 'person' in df.columns:
                    print(f"\nPersonas que grabaron: {list(df['person'].unique())}")
                    print("\nMuestras por persona:")
                    print(df['person'].value_counts().to_string())
                print("--------------------------------\n")
        elif key == ord('x'):
            print("\n--- BORRAR SEÑA DEL DATASET ---")
            import pandas as pd
            dataset_path = os.path.join(DATA_DIR, "dataset.csv")
            if not os.path.exists(dataset_path):
                print("[X] No hay dataset todavía.")
            else:
                df = pd.read_csv(dataset_path)
                senas = df['label'].unique()
                print(f"Señas disponibles: {list(senas)}")
                word = input("Ingresa la palabra a borrar (o Enter para cancelar): ").strip()
                if word:
                    before = len(df)
                    df_filtered = df[df['label'].str.upper() != word.upper()]
                    after = len(df_filtered)
                    if before == after:
                        print(f"[X] No se encontró '{word}' en el dataset.")
                    else:
                        df_filtered.to_csv(dataset_path, index=False)
                        print(f"[X] Eliminadas {before - after} muestras de '{word}'.")
                        print("[X] Recuerda reentrenar con 'E'.")
                else:
                    print("[X] Cancelado.")
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
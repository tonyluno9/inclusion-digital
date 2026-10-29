import os
import sys
import time
import threading
from types import SimpleNamespace

import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

import config as C
from modules.landmark_detector import LandmarkDetector
from modules.landmarks import hands_present
from modules.segmenter import SignSegmenter
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from modules.tts import TTSEngine
from modules.beep import beep_start, beep_stop, beep_error
from modules.stt import STTController
from modules.coherence import make_coherent
from ui.display import DisplayUI
from ui.text_input import TextPrompt
from train_model import train

HELP = """
--- SISTEMA DE SEÑAS ---
't': Entrenar una palabra (pide palabra y nombre en pantalla)
Espacio: (entrenamiento) empezar / pausar la grabación automática
'z': (entrenamiento) deshacer la última muestra
'd': Modo detección
'e': Entrenar modelo
'r': Recargar modelo
'i': Estadísticas del dataset
'x': Borrar una seña del dataset
's': Grabar voz (STT)
'v': Activar/desactivar voz (TTS)
'f': Pantalla completa
'q': Salir
------------------------
"""


def main():
    os.makedirs(C.DATA_DIR, exist_ok=True)

    detector = LandmarkDetector(C.MODELS_DIR)
    segmenter = SignSegmenter(C.SEQUENCE_LENGTH, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES,
                              C.SEGMENT_MIN_FRAMES, C.SEGMENT_MAX_FRAMES)
    collector = DataCollector(C.DATASET_PATH, C.BACKUP_DIR, C.BACKUP_EVERY)
    logic = GestureLogic(C.MODEL_PATH, C.FEATURE_VERSION, C.MIN_CONFIDENCE)
    tts = TTSEngine(lang="es")
    stt = STTController(model_path=C.VOSK_MODEL_PATH)

    st = SimpleNamespace(
        mode="DETECTION",
        label="",
        person="anonimo",
        armed=False,              # entrenamiento: guardar cada seña que se detecte
        prediction="",
        confidence=0.0,
        subtitle_history=[],
        last_sign_time=time.time(),
        coherent_sentence="",
        coherence_loading=False,
        stt_text="",
        prompt=None,
        status="",
        status_until=0.0,
        training=False,
        reload_pending=False,
    )

    def notify(text, seconds=3.0):
        print(f"[INFO] {text}")
        st.status = text
        st.status_until = time.time() + seconds

    # --- Flujo de preguntas en pantalla ---
    def ask_label():
        def on_label(word):
            if not word:
                st.prompt = None
                return
            st.label = word.lower()
            st.prompt = TextPrompt("¿Quién graba? (tu nombre)", on_person, initial=st.person)
        st.prompt = TextPrompt("Palabra a entrenar:", on_label, initial=st.label)

    def on_person(person):
        st.prompt = None
        if person is None:
            return
        if person:
            st.person = person.lower()
        st.mode = "TRAINING"
        st.armed = False
        st.prediction = ""
        segmenter.reset()
        notify(f"'{st.label}' por {st.person}: Espacio para empezar")

    def ask_delete():
        labels, _ = collector.stats()
        print(f"Señas disponibles: {sorted(labels)}")

        def on_word(word):
            st.prompt = None
            if not word:
                return
            removed = collector.delete_label(word)
            if removed:
                notify(f"Borradas {removed} muestras de '{word}'. Reentrena con 'e'.")
            else:
                notify(f"No se encontró '{word}'.")
        st.prompt = TextPrompt("Seña a BORRAR del dataset:", on_word)

    def start_training():
        if st.training:
            notify("Ya se está entrenando...")
            return
        st.training = True
        notify("Entrenando modelo (ver consola)...", seconds=600)

        def run():
            ok = train(C.DATASET_PATH, C.MODEL_PATH, evaluate=False)
            st.training = False
            st.reload_pending = ok
            notify("Modelo entrenado y cargado." if ok else "Entrenamiento fallido (ver consola).")
        threading.Thread(target=run, daemon=True).start()

    def start_coherence(words):
        st.coherence_loading = True
        st.coherent_sentence = ""

        def run():
            result = make_coherent(words)
            st.coherent_sentence = result
            tts.speak(result)
            st.coherence_loading = False
        threading.Thread(target=run, daemon=True).start()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    win_name = "Inclusion Vision HD"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    full_screen = False
    print(HELP)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame, raw = detector.process(frame)
        present = hands_present(raw)
        if present:
            st.last_sign_time = time.time()

        if st.reload_pending:
            st.reload_pending = False
            logic.load_model()

        # --- Segmentación: el mismo camino al grabar y al detectar ---
        capturing_before = segmenter.active
        sequence = None
        if st.mode == "DETECTION" or st.armed:
            sequence = segmenter.update(raw)
        finished = capturing_before and not segmenter.active

        action_status = ""
        if st.mode == "TRAINING":
            if not capturing_before and segmenter.active:
                beep_start()
            if finished:
                if sequence is not None:
                    collector.save_sequence(st.label, sequence, person=st.person)
                    n = collector.stats()[0].get(st.label, 0)
                    beep_stop()
                    notify(f"Muestra guardada: '{st.label}' ({n} en total)")
                else:
                    beep_error()
                    notify("Seña muy corta, no se guardó.")
            if segmenter.active:
                action_status = f"GRABANDO '{st.label}'... baja las manos al terminar"
            elif st.armed:
                action_status = f"'{st.label}': levanta las manos y haz la seña"
            else:
                action_status = f"'{st.label}': Espacio para empezar a grabar"
        else:
            if finished and sequence is not None:
                pred, conf = logic.predict(sequence)
                st.confidence = conf
                if pred:
                    st.prediction = pred
                    tts.speak(pred)
                    st.subtitle_history.append(pred)
                    st.subtitle_history = st.subtitle_history[-5:]
                elif logic.model is not None:
                    st.prediction = ""
                    notify(f"Seña no reconocida ({conf:.0%})", seconds=1.5)
            if logic.model is None:
                action_status = "Sin modelo: graba señas con 't' y entrena con 'e'"

            # Oración coherente tras un silencio sin manos
            if (st.subtitle_history and not st.coherence_loading
                    and time.time() - st.last_sign_time > C.SILENCE_SECONDS):
                words = st.subtitle_history
                st.subtitle_history = []
                start_coherence(words)

        stt_result = stt.get_result()
        if stt_result:
            st.stt_text = stt_result

        if st.status and time.time() > st.status_until:
            st.status = ""

        frame = DisplayUI.draw_info(
            frame=frame,
            mode=st.mode,
            current_word=st.prediction if st.mode == "DETECTION" else st.label,
            action_status=action_status,
            capture_progress=segmenter.captured / C.SEGMENT_MAX_FRAMES,
            confidence=st.confidence,
            is_capturing=segmenter.active,
            armed=st.armed,
            stt_text=st.stt_text,
            stt_recording=stt.is_recording,
            subtitle_history=st.subtitle_history,
            coherent_sentence=st.coherent_sentence,
            coherence_loading=st.coherence_loading,
            prompt=st.prompt,
            status_message=st.status,
        )
        cv2.imshow(win_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 255:
            continue

        # Mientras hay una pregunta en pantalla, todas las teclas van a ella
        if st.prompt is not None:
            st.prompt.handle_key(key)
            continue

        if key == ord('q'):
            break
        elif key == ord('f'):
            full_screen = not full_screen
            prop = cv2.WINDOW_FULLSCREEN if full_screen else cv2.WINDOW_NORMAL
            cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, prop)
        elif key == ord('t'):
            ask_label()
        elif key == ord(' ') and st.mode == "TRAINING":
            st.armed = not st.armed
            segmenter.reset()
            notify("Grabación activada" if st.armed else "Grabación en pausa")
        elif key == ord('z') and st.mode == "TRAINING":
            removed = collector.remove_last()
            notify(f"Se deshizo la última muestra ('{removed}')" if removed else "No hay muestras.")
        elif key == ord('d'):
            st.mode = "DETECTION"
            st.armed = False
            st.prediction = ""
            segmenter.reset()
            logic.load_model()
            notify("Modo detección")
        elif key == ord('r'):
            logic.load_model()
            st.prediction = ""
            notify("Modelo recargado")
        elif key == ord('e'):
            start_training()
        elif key == ord('i'):
            labels, persons = collector.stats()
            print("\n--- ESTADÍSTICAS DEL DATASET ---")
            print(f"Total de muestras: {sum(labels.values())}")
            for label, n in sorted(labels.items(), key=lambda kv: -kv[1]):
                print(f"  {label}: {n}")
            print(f"Personas: {persons}")
            print("--------------------------------\n")
            notify(f"{sum(labels.values())} muestras, {len(labels)} señas, {len(persons)} personas")
        elif key == ord('x'):
            ask_delete()
        elif key in (ord('v'), ord('V')):
            estado = tts.toggle()
            notify(f"Voz {'activada' if estado else 'desactivada'}")
        elif key == ord('s'):
            if not stt.is_recording:
                st.stt_text = ""
                stt.start_recording()
            else:
                stt.stop_recording()

    tts.shutdown()
    detector.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

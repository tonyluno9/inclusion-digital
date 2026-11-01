"""INCLUSION: reconocimiento de Lengua de Señas Mexicana.

Uso:
    python main.py                       # cámara 0
    python main.py --camera 1            # otra cámara
    python main.py --video demo.mp4      # archivo de video
    python main.py --video demo.mp4 --headless --benchmark
"""
import argparse
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import cv2

import config as C

WINDOW = "INCLUSION - Lengua de Señas"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Reconocimiento de Lengua de Señas Mexicana")
    parser.add_argument("--camera", type=int, default=C.CAMERA_INDEX, help="índice de la cámara (0, 1, ...)")
    parser.add_argument("--video", help="usar un archivo de video en vez de la cámara")
    parser.add_argument("--headless", action="store_true", help="no mostrar ventana (pruebas)")
    parser.add_argument("--benchmark", action="store_true", help="al terminar, mostrar ms por etapa")
    parser.add_argument("--max-frames", type=int, default=0, help="terminar tras N frames (0 = sin límite)")
    return parser.parse_args(argv)


def open_source(args):
    if args.video:
        if not os.path.exists(args.video):
            print(f"Error: no existe el video {args.video}")
            return None
        cap = cv2.VideoCapture(args.video)
    else:
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened() and sys.platform == "win32":
            cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, C.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, C.CAMERA_HEIGHT)
    if not cap.isOpened():
        print(f"Error: no se pudo abrir la cámara {args.camera}. Revisa que esté conectada, que otra app "
              "no la esté usando y que Windows le dé permiso (Configuración > Privacidad > Cámara). "
              "Puedes probar otra con --camera 1.")
        return None
    return cap


def _safe_console():
    # La consola de Windows (cp1252) no tiene todos los caracteres: reemplazar en vez de fallar
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def main(argv=None):
    _safe_console()
    args = parse_args(argv)
    os.makedirs(C.DATA_DIR, exist_ok=True)

    from modules.landmark_detector import LandmarkDetector
    from modules.stt import STTController
    from modules.tts import TTSEngine
    from inclusion_app import InclusionApp

    cap = open_source(args)
    if cap is None:
        return 1
    try:
        detector = LandmarkDetector(C.MODELS_DIR, pose_every=C.POSE_EVERY_N_FRAMES)
    except RuntimeError as e:
        print(f"Error: {e}")
        cap.release()
        return 1

    tts = TTSEngine(lang="es", use_online=C.USE_ONLINE_TTS)
    stt = STTController(model_path=C.VOSK_MODEL_PATH, use_online=C.USE_ONLINE_STT)
    app = InclusionApp(detector, tts, stt)

    if not args.headless:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, C.CAMERA_WIDTH, C.CAMERA_HEIGHT)
    print("INCLUSION iniciado. Presiona 'h' en la ventana para ver las teclas.")

    full_screen = False
    frames = 0
    start = time.perf_counter()
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                if not args.video:
                    print("Error: la cámara dejó de enviar imagen.")
                break
            frame = app.process_frame(frame, render=not args.headless or args.benchmark)
            frames += 1
            if args.max_frames and frames >= args.max_frames:
                break
            if args.headless:
                continue

            cv2.imshow(WINDOW, frame)
            key = cv2.waitKey(1)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break                       # cerraron la ventana con la X
            key = key & 0xFF if key != -1 else 255
            if key in (ord("f"), ord("F")) and app.prompt is None:
                full_screen = not full_screen
                prop = cv2.WINDOW_FULLSCREEN if full_screen else cv2.WINDOW_NORMAL
                cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, prop)
            elif not app.handle_key(key):
                break
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.perf_counter() - start
        tts.shutdown()
        stt.stop_recording()
        detector.close()
        cap.release()
        cv2.destroyAllWindows()

    if args.benchmark and frames:
        print(f"\n[BENCHMARK] {frames} frames en {elapsed:.1f} s = {frames / elapsed:.1f} fps")
        for line in app.benchmark_summary():
            print(f"[BENCHMARK] {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""K'ab T'aan como aplicación de escritorio: interfaz web en una ventana propia.

    python servidor_web.py                    # cámara 0, abre la ventana
    python servidor_web.py --camera 1
    python servidor_web.py --video demo.mp4   # un video en vez de la cámara (se repite)
    python servidor_web.py --sin-ventana      # solo el servidor (pruebas)

Arquitectura (ver requerimientos/07_app_unificada.md):
- `Motor`: un hilo lee la cámara y corre `InclusionApp` (la misma lógica de la app clásica:
  segmentación, reconocimiento, grabación, avatar). Las acciones de la interfaz se ejecutan
  en ese mismo hilo, entre frames, así la lógica nunca corre en dos hilos a la vez.
- Servidor HTTP de la biblioteca estándar (sin dependencias nuevas):
    /           la interfaz (app/web)
    /video      la cámara con los puntos dibujados (MJPEG)
    /eventos    estado de la app y movimiento 3D para el avatar (Server-Sent Events)
    /api/...    acciones (POST) y datos: clips, dataset (GET)
- La ventana es Edge o Chrome en modo aplicación (sin barra de direcciones). Al cerrarla,
  la app termina sola.
"""
import argparse
import json
import mimetypes
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import cv2

import config as C
from modules.motion import frame_to_json

WEB_DIR = os.path.join(BASE_DIR, "web")
PUERTO = 8765
ANCHO_VIDEO = 960
CIERRE_SIN_VENTANA = 8.0     # segundos sin la ventana conectada para terminar
TIPOS = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".glb": "model/gltf-binary",
         ".json": "application/json", ".ttf": "font/ttf", ".ico": "image/x-icon", ".html": "text/html",
         ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml"}


class Motor:
    """Corre la app sobre la cámara (o un video) en un hilo propio."""

    def __init__(self, app, abrir_fuente, es_video=False):
        self.app = app
        self._abrir = abrir_fuente
        self._es_video = es_video
        self._acciones = queue.Queue()
        self._cambio = threading.Condition()
        self.frame_id = 0
        self.jpeg = None
        self.estado = {}
        self.mundo = None
        self.camara_ok = False
        self.fps = 0.0
        self.activo = True
        self.hilo = threading.Thread(target=self._correr, name="motor", daemon=True)

    def iniciar(self):
        self.hilo.start()
        return self

    def detener(self):
        self.activo = False
        with self._cambio:
            self._cambio.notify_all()

    def ejecutar(self, fn, timeout=15.0):
        """Ejecuta `fn()` en el hilo del motor y devuelve su resultado."""
        if threading.current_thread() is self.hilo or not self.hilo.is_alive():
            return fn()
        futuro = Future()
        self._acciones.put((fn, futuro))
        return futuro.result(timeout=timeout)

    def _atender_acciones(self):
        while True:
            try:
                fn, futuro = self._acciones.get_nowait()
            except queue.Empty:
                return
            try:
                futuro.set_result(fn())
            except Exception as e:      # el error vuelve a quien pidió la acción
                futuro.set_exception(e)

    def esperar_frame(self, ultimo, timeout=1.0):
        with self._cambio:
            if self.frame_id == ultimo and self.activo:
                self._cambio.wait(timeout)
            return self.frame_id

    def _correr(self):
        cap, ultimo_intento, tiempos = None, 0.0, []
        intervalo = 0.0
        while self.activo:
            if cap is None:
                self._atender_acciones()
                if time.monotonic() - ultimo_intento < 2.0:
                    time.sleep(0.05)
                    continue
                ultimo_intento = time.monotonic()
                cap = self._abrir()
                self.camara_ok = cap is not None
                if cap is None:
                    self._publicar(None)
                    continue
                fps = cap.get(cv2.CAP_PROP_FPS) if self._es_video else 0
                intervalo = 1.0 / fps if fps and fps > 1 else 0.0
            t0 = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                if self._es_video:              # el video de prueba se repite
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                cap.release()
                cap, self.camara_ok = None, False
                continue
            try:
                frame = self.app.process_frame(frame, render=False)
            except Exception as e:              # un frame raro no tumba la app
                print(f"[MOTOR] Error procesando un frame: {type(e).__name__}: {e}")
                continue
            self._atender_acciones()
            self._publicar(frame)
            tiempos = (tiempos + [time.monotonic()])[-30:]
            if len(tiempos) > 1:
                self.fps = (len(tiempos) - 1) / (tiempos[-1] - tiempos[0] + 1e-9)
            if intervalo:                       # un video va a su velocidad real
                time.sleep(max(0.0, intervalo - (time.monotonic() - t0)))
        if cap is not None:
            cap.release()

    def _publicar(self, frame):
        jpeg = None
        if frame is not None:
            h, w = frame.shape[:2]
            if w > ANCHO_VIDEO:
                frame = cv2.resize(frame, (ANCHO_VIDEO, int(h * ANCHO_VIDEO / w)), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
            jpeg = buf.tobytes() if ok else None
        estado = self.app.state()
        estado.update({"camara": self.camara_ok, "fps": round(self.fps, 1)})
        mundo = frame_to_json(self.app.live_world, 0.0) if self.app.live_world is not None else None
        with self._cambio:
            self.jpeg, self.estado, self.mundo = jpeg, estado, mundo
            self.frame_id += 1
            self._cambio.notify_all()


# Acciones que puede pedir la interfaz: nombre -> función(app, datos)
def _texto(datos, clave):
    valor = str(datos.get(clave, "")).strip()
    if not valor:
        raise ValueError(f"falta '{clave}'")
    return valor[:60]


def _segundos(datos, clave):
    valor = datos.get(clave)
    return None if valor is None else max(0.0, float(valor))


ACCIONES = {
    "modo_deteccion": lambda app, d: app.detection_mode(bool(d.get("practica"))),
    "entrenar_palabra": lambda app, d: app.train_word(_texto(d, "palabra"), str(d.get("persona", ""))),
    "avatar_palabra": lambda app, d: app.avatar_word(str(d.get("palabra", ""))[:60]),
    "grabar": lambda app, d: app.toggle_recording(),
    "deshacer": lambda app, d: app.undo(),
    "entrenar_modelo": lambda app, d: app.start_training(),
    "recargar_modelo": lambda app, d: app.reload_model(),
    "voz": lambda app, d: app.toggle_voice(),
    "escuchar": lambda app, d: app.toggle_listening(),
    "borrar_sena": lambda app, d: app.delete_sign(_texto(d, "palabra")),
    "borrar_clip": lambda app, d: app.delete_clip(_texto(d, "palabra")),
    "texto_interlocutor": lambda app, d: app.interlocutor_text(str(d.get("texto", ""))[:300]),
    "manos": lambda app, d: app.set_hands(str(d.get("modo", ""))),
    "guardar_toma": lambda app, d: app.save_take(_segundos(d, "inicio"), _segundos(d, "fin")) and True,
    "descartar_toma": lambda app, d: app.discard_take(),
    "practica": lambda app, d: app.practice_result(_texto(d, "palabra"), bool(d.get("acierto")),
                                                   float(d.get("confianza") or 0.0)),
}


class Manejador(BaseHTTPRequestHandler):
    server_version = "KabTaan"

    def log_message(self, fmt, *args):     # sin una línea por petición en la consola
        pass

    @property
    def motor(self):
        return self.server.motor

    # ------------------------------------------------------------- respuestas
    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta, tipo=None):
        if not os.path.isfile(ruta):
            return self._json({"error": "no existe"}, 404)
        tipo = tipo or TIPOS.get(os.path.splitext(ruta)[1].lower()) or mimetypes.guess_type(ruta)[0] \
            or "application/octet-stream"
        with open(ruta, "rb") as f:
            cuerpo = f.read()
        self.send_response(200)
        self.send_header("Content-Type", tipo + ("; charset=utf-8" if tipo.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(cuerpo)

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        url = urlparse(self.path)
        ruta = unquote(url.path)
        try:
            if ruta == "/video":
                return self._video()
            if ruta == "/eventos":
                return self._eventos()
            if ruta == "/api/clips":
                return self._json({"clips": self.motor.app.clips.words()})
            if ruta.startswith("/api/clip/"):
                palabra = ruta[len("/api/clip/"):]
                return self._archivo(self.motor.app.clips.path(palabra), "application/json")
            if ruta == "/api/toma":
                toma = self.motor.app.pending_take
                return self._json(toma) if toma is not None else self._json({"error": "no hay toma"}, 404)
            if ruta == "/api/diccionario":
                return self._json({"palabras": self.motor.ejecutar(self.motor.app.vocabulary)})
            if ruta == "/api/progreso":
                return self._json(self.motor.ejecutar(self.motor.app.progress_summary))
            if ruta == "/api/dataset":
                senas, personas = self.motor.app.collector.stats()
                return self._json({"senas": senas, "personas": personas})
            if ruta == "/api/estado":
                return self._json(self.motor.estado)
            return self._estatico(ruta)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _estatico(self, ruta):
        if ruta in ("", "/"):
            ruta = "/index.html"
        completo = os.path.realpath(os.path.join(WEB_DIR, ruta.lstrip("/")))
        if not completo.startswith(os.path.realpath(WEB_DIR) + os.sep):
            return self._json({"error": "ruta no permitida"}, 403)
        return self._archivo(completo)

    def _video(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        visto = -1
        while self.motor.activo:
            visto = self.motor.esperar_frame(visto)
            jpeg = self.motor.jpeg
            if jpeg is None:
                continue
            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                             + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")

    def _eventos(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.server.ventanas(+1)
        try:
            visto = -1
            while self.motor.activo:
                visto = self.motor.esperar_frame(visto)
                datos = json.dumps({"estado": self.motor.estado, "mundo": self.motor.mundo},
                                   ensure_ascii=False, separators=(",", ":"))
                self.wfile.write(b"data: " + datos.encode("utf-8") + b"\n\n")
                self.wfile.flush()
        finally:
            self.server.ventanas(-1)

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        if urlparse(self.path).path != "/api/accion":
            return self._json({"error": "no existe"}, 404)
        try:
            largo = int(self.headers.get("Content-Length", 0))
            datos = json.loads(self.rfile.read(largo) or b"{}")
            nombre = datos.get("accion", "")
            if nombre == "cerrar":
                self._json({"ok": True})
                threading.Thread(target=self.server.cerrar, daemon=True).start()
                return
            if nombre not in ACCIONES:
                return self._json({"ok": False, "error": f"acción desconocida: {nombre}"}, 400)
            resultado = self.motor.ejecutar(lambda: ACCIONES[nombre](self.motor.app, datos))
            self._json({"ok": True, "resultado": resultado, "aviso": self.motor.app.status})
        except ValueError as e:
            self._json({"ok": False, "error": str(e)}, 400)
        except Exception as e:
            print(f"[SERVIDOR] Error en la acción: {type(e).__name__}: {e}")
            self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, motor, puerto=PUERTO, cerrar_sin_ventana=True):
        super().__init__(("127.0.0.1", puerto), Manejador)
        self.motor = motor
        self._ventanas = 0
        self._hubo_ventana = False
        self._sin_ventana_desde = None
        self._candado = threading.Lock()
        self.cerrar_sin_ventana = cerrar_sin_ventana

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/"

    def ventanas(self, delta):
        with self._candado:
            self._ventanas += delta
            if delta > 0:
                self._hubo_ventana = True
            self._sin_ventana_desde = time.monotonic() if self._ventanas == 0 else None

    def vigilar(self):
        """Termina la app cuando la ventana lleva unos segundos cerrada."""
        while self.motor.activo:
            time.sleep(1.0)
            with self._candado:
                cerrada = (self.cerrar_sin_ventana and self._hubo_ventana and self._sin_ventana_desde is not None
                           and time.monotonic() - self._sin_ventana_desde > CIERRE_SIN_VENTANA)
            if cerrada:
                print("[APP] La ventana se cerró: terminando.")
                self.cerrar()
                return

    def cerrar(self):
        self.motor.detener()
        self.shutdown()


def abrir_ventana(url):
    """Edge o Chrome en modo aplicación (ventana propia sin barra de direcciones)."""
    candidatos = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        shutil.which("msedge") or "", shutil.which("google-chrome") or "", shutil.which("chromium") or "",
    ]
    perfil = os.path.join(C.DATA_DIR, "navegador")      # perfil aparte: no toca el navegador personal
    for exe in candidatos:
        if exe and os.path.isfile(exe):
            subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={perfil}", "--window-size=1440,900",
                              "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"])
            return exe
    webbrowser.open(url)
    return "navegador predeterminado"


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="K'ab T'aan: señas a subtítulos y avatar, en una sola ventana")
    p.add_argument("--camera", type=int, default=C.CAMERA_INDEX, help="índice de la cámara (0, 1, ...)")
    p.add_argument("--video", help="usar un archivo de video en vez de la cámara (se repite)")
    p.add_argument("--puerto", type=int, default=PUERTO)
    p.add_argument("--sin-ventana", action="store_true", help="no abrir la ventana (pruebas)")
    p.add_argument("--datos", help="carpeta de datos alternativa (dataset, modelo, clips), para pruebas")
    return p.parse_args(argv)


def usar_carpeta_datos(carpeta):
    """Dataset, modelo, respaldos y clips en otra carpeta (para probar sin tocar los datos reales)."""
    carpeta = os.path.abspath(carpeta)
    os.makedirs(carpeta, exist_ok=True)
    C.DATASET_PATH = os.path.join(carpeta, "dataset_v2.csv")
    C.BACKUP_DIR = os.path.join(carpeta, "backups")
    C.MODEL_PATH = os.path.join(carpeta, "model.pkl")
    C.AVATAR_DIR = os.path.join(carpeta, "avatar")


def crear_app():
    from inclusion_app import InclusionApp
    from modules.landmark_detector import LandmarkDetector
    from modules.stt import STTController
    from modules.tts import TTSEngine
    detector = LandmarkDetector(C.MODELS_DIR, pose_every=C.POSE_EVERY_N_FRAMES, pose_model=C.POSE_MODEL)
    tts = TTSEngine(lang="es", use_online=C.USE_ONLINE_TTS)
    stt = STTController(model_path=C.VOSK_MODEL_PATH, use_online=C.USE_ONLINE_STT)
    return InclusionApp(detector, tts, stt, review_takes=True)


def main(argv=None):
    from main import _safe_console, open_source
    _safe_console()
    args = parse_args(argv)
    if args.video and not os.path.exists(args.video):
        print(f"Error: no existe el video {args.video}")
        return 1
    os.makedirs(C.DATA_DIR, exist_ok=True)
    if args.datos:
        usar_carpeta_datos(args.datos)
    try:
        app = crear_app()
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    motor = Motor(app, lambda: open_source(args), es_video=bool(args.video)).iniciar()
    try:
        servidor = Servidor(motor, args.puerto, cerrar_sin_ventana=not args.sin_ventana)
    except OSError:
        print(f"Error: el puerto {args.puerto} está ocupado. ¿K'ab T'aan ya está abierto? Prueba con --puerto 8766.")
        motor.detener()
        return 1
    print(f"K'ab T'aan en {servidor.url}")
    threading.Thread(target=servidor.vigilar, daemon=True).start()
    if not args.sin_ventana:
        print(f"[APP] Ventana: {abrir_ventana(servidor.url)}")
    try:
        servidor.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        motor.detener()
        motor.hilo.join(timeout=3)
        app.tts.shutdown()
        app.stt.stop_recording()
        app.detector.close()
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

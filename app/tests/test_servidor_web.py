"""Servidor de la app unificada (servidor_web.py), con la lógica real de la app y detector,
voz y cámara simulados (RF-26 a RF-29, requerimientos/07_app_unificada.md)."""
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import numpy as np

import servidor_web as sw
from inclusion_app import InclusionApp
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from modules.motion import ClipStore, make_clip
import config as C
from tests.synthetic import make_sign, stream
from tests.test_app import FRAME, FakeDetector, FakeSender, FakeSTT, FakeTTS


class CamaraFalsa:
    def __init__(self):
        self.abierta = True

    def read(self):
        time.sleep(0.005)
        return True, FRAME.copy()

    def get(self, _prop):
        return 0

    def set(self, *_):
        return True

    def release(self):
        self.abierta = False


class ServidorWebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.detector = FakeDetector()
        self.detector.idle = stream(make_sign("arriba", 1), pad=1)[0]
        self.detector.with_world = True
        self.clips = ClipStore(os.path.join(d, "avatar"))
        self.app = InclusionApp(self.detector, FakeTTS(), FakeSTT(),
                                collector=DataCollector(os.path.join(d, "dataset.csv"), os.path.join(d, "b")),
                                logic=GestureLogic(os.path.join(d, "model.pkl"), C.FEATURE_VERSION, C.SEQUENCE_LENGTH),
                                clips=self.clips, sender=FakeSender(), background=False)
        self.iniciar(lambda: CamaraFalsa())

    def iniciar(self, abrir, cerrar_sin_ventana=False):
        self.motor = sw.Motor(self.app, abrir).iniciar()
        self.servidor = sw.Servidor(self.motor, 0, cerrar_sin_ventana=cerrar_sin_ventana)
        self.hilo = threading.Thread(target=self.servidor.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.hilo.start()
        self.url = self.servidor.url
        self.esperar(lambda: self.motor.frame_id > 2)

    def tearDown(self):
        if self.motor.activo:
            self.servidor.cerrar()
        self.servidor.server_close()
        self.motor.hilo.join(timeout=3)
        self.tmp.cleanup()

    def esperar(self, condicion, timeout=5.0):
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            if condicion():
                return True
            time.sleep(0.02)
        self.fail("no se cumplió a tiempo")

    def get(self, ruta):
        with urllib.request.urlopen(self.url + ruta.lstrip("/"), timeout=5) as r:
            return r.status, r.headers.get("Content-Type"), r.read()

    def accion(self, **datos):
        req = urllib.request.Request(self.url + "api/accion", data=json.dumps(datos).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def crudo(self, ruta, maximo):
        """Primeros bytes de una respuesta que no termina (video o eventos)."""
        con = http.client.HTTPConnection("127.0.0.1", self.servidor.server_address[1], timeout=5)
        con.request("GET", ruta)
        r = con.getresponse()
        datos = r.read1(maximo) if hasattr(r, "read1") else r.read(maximo)
        while len(datos) < maximo:
            parte = r.read1(maximo - len(datos))
            if not parte:
                break
            datos += parte
        con.close()
        return r.getheader("Content-Type"), datos

    # ------------------------------------------------------------------ pruebas
    def test_interfaz_y_recursos(self):
        """RF-26: la interfaz, su JavaScript y el personaje se sirven con su tipo."""
        estado, tipo, html = self.get("/")
        self.assertEqual(estado, 200)
        self.assertIn("text/html", tipo)
        self.assertIn(b"<title>K'ab T'aan</title>", html)
        self.assertIn("javascript", self.get("/js/app.js")[1])
        self.assertEqual(self.get("/assets/modelos/personaje.glb")[1], "model/gltf-binary")

    def test_no_sale_de_la_carpeta_web(self):
        """RNF-12: no se puede pedir un archivo fuera de app/web."""
        con = http.client.HTTPConnection("127.0.0.1", self.servidor.server_address[1], timeout=5)
        con.request("GET", "/..%2Fconfig.py")
        r = con.getresponse()
        self.assertIn(r.status, (403, 404))
        self.assertNotIn(b"CAMERA_INDEX", r.read())
        con.close()

    def test_estado_y_acciones(self):
        """RF-28: los botones de la interfaz usan las mismas acciones que las teclas."""
        _, _, crudo = self.get("/api/estado")
        estado = json.loads(crudo)
        self.assertTrue(estado["camara"])
        self.assertEqual(estado["modo"], "DETECTION")
        codigo, r = self.accion(accion="entrenar_palabra", palabra="Hola", persona="Ana")
        self.assertEqual((codigo, r["ok"]), (200, True))
        self.assertEqual((self.app.mode, self.app.label, self.app.person), ("TRAINING", "hola", "ana"))
        self.assertTrue(self.accion(accion="grabar")[1]["resultado"])
        self.assertTrue(self.app.armed)
        self.assertEqual(self.accion(accion="desconocida")[0], 400)
        self.assertEqual(self.accion(accion="entrenar_palabra", palabra="  ")[0], 400)
        self.accion(accion="avatar_palabra", palabra="")
        self.assertEqual((self.app.mode, self.app.label), ("AVATAR", ""))
        self.assertFalse(self.accion(accion="grabar")[1]["resultado"])   # sin palabra no se graba
        self.accion(accion="texto_interlocutor", texto="buenos días")
        self.esperar(lambda: self.motor.estado.get("interlocutor") == "buenos días")
        self.assertEqual(self.motor.estado["seq_texto"], 1)

    def test_eventos_traen_estado_y_movimiento(self):
        """RF-27: en modo avatar, cada evento trae el frame 3D para el avatar de la app."""
        self.accion(accion="avatar_palabra", palabra="")
        self.esperar(lambda: self.motor.mundo is not None)
        tipo, datos = self.crudo("/eventos", 2000)
        self.assertIn("text/event-stream", tipo)
        primero = json.loads(datos.split(b"\n\n")[0][len(b"data: "):])
        self.assertEqual(primero["estado"]["modo"], "AVATAR")
        self.assertEqual(len(primero["mundo"]["pose"]), 33)

    def test_video_mjpeg(self):
        """RF-26: la cámara llega como video MJPEG."""
        tipo, datos = self.crudo("/video", 4000)
        self.assertIn("multipart/x-mixed-replace", tipo)
        self.assertTrue(datos.startswith(b"--frame"))
        self.assertIn(b"\xff\xd8", datos)                      # inicio de un JPEG

    def test_clips_y_datos(self):
        """RF-29: lista de clips, un clip y el dataset."""
        frames = [(i / 30, self.detector.world or {"pose": None, "vis": None, "left": None, "right": None})
                  for i in range(10)]
        self.clips.save(make_clip(frames, "buenos días"))
        self.assertEqual(json.loads(self.get("/api/clips")[2])["clips"], ["buenos días"])
        clip = json.loads(self.get("/api/clip/" + urllib.request.quote("buenos días"))[2])
        self.assertEqual(clip["word"], "buenos días")
        self.assertEqual(json.loads(self.get("/api/dataset")[2]), {"senas": {}, "personas": {}})
        codigo, r = self.accion(accion="borrar_clip", palabra="buenos días")
        self.assertTrue(r["resultado"])
        self.assertEqual(self.clips.words(), [])

    def test_manos_y_toma_pendiente(self):
        """RF-31, RF-32: elegir las manos de la seña; revisar, recortar y guardar o descartar la toma."""
        self.accion(accion="avatar_palabra", palabra="hola")
        codigo, r = self.accion(accion="manos", modo="derecha")
        self.assertEqual((codigo, r["resultado"]), (200, "derecha"))
        self.esperar(lambda: self.motor.estado.get("manos") == "derecha")
        self.assertEqual(self.accion(accion="manos", modo="tres")[0], 400)
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.get("/api/toma")
        self.assertEqual(err.exception.code, 404)
        self.assertEqual(self.accion(accion="guardar_toma")[0], 400)

        vacio = {"pose": None, "vis": None, "left": None, "right": None}
        toma = make_clip([(i / 10, vacio) for i in range(21)], "hola", hands="derecha")
        self.motor.ejecutar(lambda: setattr(self.app, "pending_take", toma))
        self.assertEqual(json.loads(self.get("/api/toma")[2])["duration"], 2.0)
        codigo, r = self.accion(accion="guardar_toma", inicio=0.5, fin=1.5)
        self.assertEqual((codigo, r["ok"]), (200, True))
        self.assertAlmostEqual(self.clips.load("hola")["duration"], 1.0)
        self.assertIsNone(self.app.pending_take)

        self.motor.ejecutar(lambda: setattr(self.app, "pending_take", toma))
        self.assertTrue(self.accion(accion="descartar_toma")[1]["resultado"])
        self.assertAlmostEqual(self.clips.load("hola")["duration"], 1.0)

    def test_sin_camara_la_app_responde(self):
        """RNF-06: sin cámara la interfaz carga y avisa."""
        self.servidor.cerrar()
        self.servidor.server_close()
        self.motor.hilo.join(timeout=3)
        self.motor = sw.Motor(self.app, lambda: None).iniciar()
        self.servidor = sw.Servidor(self.motor, 0, cerrar_sin_ventana=False)
        threading.Thread(target=self.servidor.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.url = self.servidor.url
        self.esperar(lambda: self.motor.frame_id > 0)
        self.assertFalse(json.loads(self.get("/api/estado")[2])["camara"])
        self.assertEqual(self.get("/")[0], 200)

    def test_cerrar_la_ventana_termina_la_app(self):
        """RF-26: al cerrar la ventana, la app termina sola."""
        self.servidor.cerrar()
        self.servidor.server_close()
        self.motor.hilo.join(timeout=3)
        viejo = sw.CIERRE_SIN_VENTANA
        sw.CIERRE_SIN_VENTANA = 0.3
        try:
            self.iniciar(lambda: CamaraFalsa(), cerrar_sin_ventana=True)
            vigia = threading.Thread(target=self.servidor.vigilar, daemon=True)
            vigia.start()
            self.servidor.ventanas(+1)
            time.sleep(0.4)
            self.assertTrue(self.motor.activo)                  # con la ventana abierta sigue
            self.servidor.ventanas(-1)
            vigia.join(timeout=5)
            self.assertFalse(self.motor.activo)
        finally:
            sw.CIERRE_SIN_VENTANA = viejo


if __name__ == "__main__":
    unittest.main()

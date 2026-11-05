"""Aprender: progreso, racha e insignias (RF-35), modo práctica y Diccionario (RF-34)."""
import json
import os
import tempfile
import unittest
from datetime import date, timedelta

import numpy as np

import config as C
import tests.test_app as base
from modules.motion import make_clip
from modules.progreso import INSIGNIAS, Progreso, estrellas_por_confianza, normalizar
from tests.synthetic import make_sign, stream


class Dia:
    def __init__(self, d):
        self.d = d

    def __call__(self):
        return self.d


class ProgresoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.tmp.name, "sub", "progreso.json")
        self.dia = Dia(date(2026, 11, 4))
        self.p = Progreso(self.ruta, hoy=self.dia)

    def tearDown(self):
        self.tmp.cleanup()

    def test_normalizar_igual_que_la_app_web(self):
        self.assertEqual(normalizar("¡Adiós!"), "adios")
        self.assertEqual(normalizar("  Buenos   DÍAS "), "buenos dias")
        self.assertEqual(normalizar("niño"), "nino")             # como norm() de texto.js

    def test_estrellas(self):
        self.assertEqual([estrellas_por_confianza(c) for c in (0.95, 0.9, 0.8, 0.75, 0.6)], [3, 3, 2, 2, 1])

    def test_intentos_estrellas_y_guardado(self):
        self.assertEqual(self.p.registrar_intento("Adiós", True, 0.93), 3)
        self.assertEqual(self.p.registrar_intento("adios", False, 0.4), 0)
        self.assertEqual(self.p.registrar_intento("hola", True, 0.7), 1)
        r = self.p.resumen()
        self.assertEqual((r["estrellas"], r["aciertos"], r["intentos"]), (4, 2, 3))
        self.assertEqual(r["aprendidas"], ["adios", "hola"])
        self.assertEqual(r["palabras"]["adios"], {"aciertos": 1, "intentos": 2, "mejor": 3})
        self.assertTrue(r["practico_hoy"])
        self.p.guardar()
        self.assertFalse(os.path.exists(self.ruta + ".tmp"))
        otra = Progreso(self.ruta, hoy=self.dia)
        self.assertEqual(otra.resumen()["estrellas"], 4)

    def test_archivo_danado_empieza_de_cero(self):
        os.makedirs(os.path.dirname(self.ruta))
        with open(self.ruta, "w", encoding="utf-8") as f:
            f.write("{no es json")
        self.assertEqual(Progreso(self.ruta).resumen()["estrellas"], 0)

    def test_racha(self):
        inicio = self.dia.d
        for k in range(3):                                         # 3 días seguidos
            self.dia.d = inicio + timedelta(days=k)
            self.p.registrar_intento("hola", True, 0.9)
        self.assertEqual(self.p.racha(), 3)
        self.dia.d = inicio + timedelta(days=3)                    # hoy aún no practica: sigue viva
        self.assertEqual(self.p.racha(), 3)
        self.assertFalse(self.p.resumen()["practico_hoy"])
        self.dia.d = inicio + timedelta(days=5)                    # se saltó un día: se rompe
        self.assertEqual(self.p.racha(), 0)
        self.p.registrar_intento("hola", False)                    # un fallo no cuenta como día
        self.assertEqual(self.p.racha(), 0)

    def test_insignias(self):
        categorias = {"saludos": ["hola", "adiós", "buenos dias"], "cortesia": ["gracias"], "numeros": ["uno"]}
        conocidas = ["hola", "adios", "gracias", "uno"]
        self.assertEqual(self.p.evaluar(categorias, conocidas), [])
        self.p.registrar_intento("hola", True, 0.9)
        self.assertEqual(self.p.evaluar(categorias, conocidas), ["primera_sena"])
        self.p.registrar_intento("adios", True, 0.9)               # todos los saludos que conoce el traductor
        self.p.registrar_intento("gracias", True, 0.9)
        self.assertEqual(self.p.evaluar(categorias, conocidas), ["saludos"])
        self.p.registrar_intento("uno", True, 0.9)                 # tercera categoría
        self.p.registrar_oracion()
        self.assertEqual(self.p.evaluar(categorias, conocidas, clips=1, modelo=True),
                         ["primer_movimiento", "traductor", "conversacion", "explorador"])
        self.assertEqual(self.p.evaluar(categorias, conocidas, clips=1, modelo=True), [])   # no se repiten
        for k in range(10):
            self.p.registrar_intento(f"palabra {k}", True, 0.9)
        self.assertIn("diez_senas", self.p.evaluar(categorias, conocidas))
        inicio = self.dia.d
        for k in range(1, 7):
            self.dia.d = inicio + timedelta(days=k)
            self.p.registrar_intento("hola", True, 0.9)
        self.assertEqual(self.p.evaluar(categorias, conocidas), ["racha_3", "racha_7"])
        r = self.p.resumen()
        self.assertEqual(len(r["insignias"]), len(INSIGNIAS))
        self.assertTrue(all(i["ganada"] for i in r["insignias"]))

    def test_saludos_pide_al_menos_dos(self):
        self.p.registrar_intento("hola", True, 0.9)
        self.assertNotIn("saludos", self.p.evaluar({"saludos": ["hola"]}, ["hola"]))


class AprenderEnLaAppTest(unittest.TestCase):
    setUp, tearDown, feed, keys, type_answer = (
        base.AppTest.setUp, base.AppTest.tearDown, base.AppTest.feed, base.AppTest.keys, base.AppTest.type_answer)

    def entrenar(self):
        rng = np.random.RandomState(0)
        self.app.train_word("arriba", "ana")
        self.app.set_hands("derecha")
        self.app.toggle_recording()
        for _ in range(6):
            self.feed(stream(make_sign("arriba", rng.randint(25, 40), rng=rng)))
        self.app.train_word("derecha", "ana")
        self.app.toggle_recording()
        for _ in range(6):
            self.feed(stream(make_sign("derecha", rng.randint(25, 40), rng=rng)))
        self.app.start_training()
        self.app.reload_model()
        return rng

    def test_practica_no_arma_oraciones(self):
        """RF-35: en Aprender se reconoce la seña, pero no se acumula en la oración."""
        rng = self.entrenar()
        self.app.detection_mode(practice=True)
        self.assertTrue(self.app.state()["practica"])
        seq = self.app.word_seq
        self.feed(stream(make_sign("arriba", 30, rng=rng)))
        self.assertEqual(self.app.word_seq, seq + 1)
        self.assertEqual(self.app.prediction, "arriba")
        self.assertEqual((self.app.pending_words, self.app.history), ([], []))
        self.clock.t += C.SILENCE_SECONDS + 1
        self.feed([self.detector.idle] * 3)
        self.assertEqual(self.sentences, [])
        self.app.detection_mode()                                  # Traducir: vuelve a armar oraciones
        self.assertFalse(self.app.practice)
        self.feed(stream(make_sign("arriba", 30, rng=rng)))
        self.assertEqual(self.app.history, ["arriba"])

    def test_resultado_de_practica_y_resumen(self):
        self.entrenar()
        r = self.app.practice_result("Arriba", True, 0.95)
        self.assertEqual(r["estrellas"], 3)
        self.assertIn("primera_sena", r["nuevas"])
        self.assertIn("traductor", r["nuevas"])
        self.assertEqual(r["resumen"]["aprendidas"], ["arriba"])
        self.assertTrue(os.path.exists(self.app.progreso.ruta))
        self.assertEqual(os.path.dirname(self.app.progreso.ruta), self.tmp.name)    # junto al dataset
        self.assertEqual(self.app.progress_summary()["nuevas"], [])

    def test_oracion_cuenta_para_conversacion(self):
        self.entrenar()
        self.app.detection_mode()
        self.feed(stream(make_sign("arriba", 30)))
        self.clock.t += C.SILENCE_SECONDS + 1
        self.feed([self.detector.idle] * 3)
        self.assertEqual(len(self.sentences), 1)
        self.assertEqual(self.app.progreso.datos["oraciones"], 1)
        self.assertIn("conversacion", self.app.progress_summary()["nuevas"])

    def test_vocabulario_une_dataset_traductor_y_avatar(self):
        """RF-34: cada palabra una sola vez, con lo que la app sabe de ella."""
        self.entrenar()
        vacio = {"pose": None, "vis": None, "left": None, "right": None}
        self.clips.save(make_clip([(i / 30, vacio) for i in range(5)], "adiós"))
        voc = {v["clave"]: v for v in self.app.vocabulary()}
        self.assertEqual(sorted(voc), ["adios", "arriba", "derecha"])
        self.assertEqual(voc["arriba"]["muestras"], 6)
        self.assertTrue(voc["arriba"]["traductor"])
        self.assertEqual(voc["arriba"]["manos"], "derecha")
        self.assertIsNone(voc["arriba"]["movimiento"])
        self.assertEqual(voc["adios"]["movimiento"], "adiós")
        self.assertFalse(voc["adios"]["traductor"])
        self.assertEqual(voc["adios"]["muestras"], 0)

    def test_categorias_validas(self):
        with open(C.CATEGORIAS_PATH, encoding="utf-8") as f:
            datos = json.load(f)
        ids = [c["id"] for c in datos["categorias"]]
        self.assertEqual(ids, ["saludos", "cortesia", "preguntas", "familia", "emociones", "numeros"])
        for c in datos["categorias"]:
            self.assertTrue(os.path.isfile(os.path.join(C.BASE_DIR, "web", "assets", "img", "categorias",
                                                        c["id"] + ".png")))
            for p in c["palabras"]:
                self.assertEqual(normalizar(p), p, f"«{p}» debe ir normalizada")
        for i, _, _ in INSIGNIAS:
            self.assertTrue(os.path.isfile(os.path.join(C.BASE_DIR, "web", "assets", "img", "insignias", i + ".png")))


if __name__ == "__main__":
    unittest.main()

"""Pruebas de JavaScript de la app web (app/web/tests/*.test.mjs), con Node.

- retarget.test.mjs: el retargeting del avatar en la app da lo mismo que el de Blender (RF-23, RF-27).
- texto.test.mjs: texto del interlocutor -> señas del avatar (RF-24).
- diccionario.test.mjs: Diccionario por categorías y qué seña practicar en Aprender (RF-34, RF-35).

Se omiten si Node no está instalado.
"""
import glob
import os
import shutil
import subprocess
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js no está instalado")
class WebJsTest(unittest.TestCase):
    def test_pruebas_de_javascript(self):
        pruebas = sorted(glob.glob(os.path.join(WEB, "tests", "*.test.mjs")))
        self.assertGreaterEqual(len(pruebas), 2)
        for prueba in pruebas:
            with self.subTest(os.path.basename(prueba)):
                r = subprocess.run([NODE, prueba], capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=120)
                self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
                self.assertIn("TODO OK", r.stdout)


if __name__ == "__main__":
    unittest.main()

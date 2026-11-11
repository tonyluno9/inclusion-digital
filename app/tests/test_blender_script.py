"""Add-on de Blender (RF-21, RF-22): corre la prueba interna de Blender en modo background.

Se omite si no hay Blender (variable BLENDER_EXE, rutas típicas de Windows o `blender` en PATH).
"""
import glob
import os
import re
import shutil
import subprocess
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRUEBA = os.path.join(RAIZ, "blender", "tests", "test_inclusion_avatar.py")
PRUEBA_RIG = os.path.join(RAIZ, "blender", "tests", "test_retarget.py")


def _version(ruta):
    m = re.search(r"Blender (\d+(?:\.\d+)*)", ruta)
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def buscar_blender():
    env = os.environ.get("BLENDER_EXE")
    if env and os.path.isfile(env):
        return env
    patron = r"C:\Program Files\Blender Foundation\Blender *\blender.exe"
    candidatos = sorted(glob.glob(patron), key=_version, reverse=True)
    if candidatos:
        return candidatos[0]
    return shutil.which("blender")


BLENDER = buscar_blender()


@unittest.skipUnless(BLENDER and os.path.isfile(PRUEBA), "Blender no está instalado")
class BlenderScriptTest(unittest.TestCase):
    def test_addon_en_blender_background(self):
        """RF-21, RF-22: puntos, importación de clips y UDP funcionan dentro de Blender."""
        r = subprocess.run(
            [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", PRUEBA],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, cwd=RAIZ)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("TODO OK", r.stdout)

    def test_retargeting_al_personaje(self):
        """RF-23: el personaje de blender/personaje/ toma la pose de los puntos, en vivo y horneada."""
        r = subprocess.run(
            [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", PRUEBA_RIG],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, cwd=RAIZ)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("TODO OK", r.stdout)

    def test_clip_real_de_la_app_en_blender(self):
        """RF-17 a RF-22 de punta a punta: MediaPipe real -> clip de la app -> Blender.
        Cada punto queda en (x, -z, y) y las manos pegadas a las muñecas del cuerpo."""
        import cv2
        import config as C
        from modules.motion import ClipStore, make_clip
        foto = os.path.join(C.DATA_DIR, "test_assets", "woman_hands.jpg")
        if not os.path.exists(foto) or not os.path.exists(os.path.join(C.MODELS_DIR, "hand_landmarker.task")):
            self.skipTest("faltan la foto de muestra o los modelos (los descarga test_integration_mediapipe)")
        from modules.landmark_detector import LandmarkDetector
        det = LandmarkDetector(C.MODELS_DIR)
        frames = []
        try:
            img = cv2.flip(cv2.imread(foto), 1)
            for i in range(12):
                det.process(img.copy())
                frames.append((i / 30, det.world))
        finally:
            det.close()
        clip = make_clip(frames, "prueba real")
        last = clip["frames"][-1]
        self.assertIsNotNone(last["pose"])
        self.assertIsNotNone(last["right"])

        with tempfile.TemporaryDirectory() as tmp:
            path = ClipStore(tmp).save(clip)
            check = os.path.join(tmp, "check.py")
            x, y, z = last["right"][0]
            with open(check, "w", encoding="utf-8") as f:
                f.write(f"""
import sys, bpy
sys.path.insert(0, {os.path.join(RAIZ, "blender")!r})
import inclusion_avatar as ia
ia.register()
esc = bpy.context.scene
esc.render.fps = 30
accion, n = ia.importar_clip({path!r}, esc, inicio=1)
esc.frame_set(12)
e = bpy.data.objects["mano_der.wrist"].matrix_world.translation
c = bpy.data.objects["cuerpo.right_wrist"].matrix_world.translation
esperado = ({x!r}, {-z!r}, {y!r})
ok = all(abs(a - b) < 1e-3 for a, b in zip(e, esperado)) and (e - c).length < 1e-3
print("POS", tuple(e), esperado, tuple(c))
print("E2E OK" if ok and accion.name == "puntos_prueba_real" else "E2E FALLA")
sys.exit(0 if ok else 1)
""")
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", check],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=180, cwd=RAIZ)
        self.assertIn("E2E OK", r.stdout, r.stdout[-3000:] + r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()

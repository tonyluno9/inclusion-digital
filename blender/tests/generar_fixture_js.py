"""Datos de referencia para probar app/web/js/retarget.js contra el retargeting de Blender.

    blender -b --factory-startup --python blender/tests/generar_fixture_js.py

Escribe app/web/tests/fixture_retarget.json con frames (reposo y pose conocida) y, para cada
uno, dónde quedan las cabezas y colas de los huesos del perfil después del retargeting de
Blender, en ejes de glTF.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Euler

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import test_retarget as tr  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(AQUI))
SALIDA = os.path.join(RAIZ, "app", "web", "tests", "fixture_retarget.json")


def gltf(p):
    return [round(p.x, 6), round(p.z, 6), round(-p.y, 6)]


def huesos_posados(arm, perfil):
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    return {n: {"cabeza": gltf(mw @ arm.pose.bones[n].head), "cola": gltf(mw @ arm.pose.bones[n].tail)}
            for n in tr.ia.huesos_del_perfil(perfil)}


def caso(arm, perfil, rotaciones):
    tr.reposo(arm)
    for nombre, grados in rotaciones.items():
        arm.pose.bones[nombre].rotation_quaternion = Euler([math.radians(g) for g in grados]).to_quaternion()
    frame = tr.frame_desde_rig(arm, perfil, posado=bool(rotaciones))
    tr.reposo(arm)
    tr.ia.Retarget(arm, perfil).aplicar(frame)
    return {"frame": frame, "huesos": huesos_posados(arm, perfil)}


arm = tr.cargar_personaje()
perfil = tr.ia.PERFILES["Tripo"]
datos = {"reposo": caso(arm, perfil, {}), "pose": caso(arm, perfil, tr.POSE_PRUEBA)}
os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
with open(SALIDA, "w", encoding="utf-8") as f:
    json.dump(datos, f)
print("FIXTURE", SALIDA)

"""Exporta el personaje de blender/personaje/*.fbx a app/web/assets/modelos/personaje.glb (para la app).

    blender -b --factory-startup --python blender/exportar_glb.py

El GLB lleva la malla, el rig y la textura. La app lo dibuja con three.js y mueve sus
huesos con el mismo retargeting que el add-on de Blender (app/web/js/retarget.js).
"""
import glob
import json
import os

import bpy

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SALIDA = os.path.join(RAIZ, "app", "web", "assets", "modelos", "personaje.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=glob.glob(os.path.join(AQUI, "personaje", "*.fbx"))[0])
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
arm.name = "Personaje"
os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=SALIDA, export_format='GLB', export_skins=True, export_animations=False,
                          export_yup=True, export_apply=False, use_selection=False)

# Geometría de reposo del rig (cabeza y cola de cada hueso) en ejes de glTF (Y arriba):
# (X, Y, Z)_gltf = (X, Z, -Y)_blender. El GLB no guarda las colas, y el retargeting las usa
# para la dirección de la última falange de cada dedo.
def gltf(p):
    p = arm.matrix_world @ p
    return [round(p.x, 6), round(p.z, 6), round(-p.y, 6)]


reposo = {b.name: {"cabeza": gltf(b.head_local), "cola": gltf(b.tail_local)} for b in arm.data.bones}
with open(os.path.join(os.path.dirname(SALIDA), "personaje_reposo.json"), "w", encoding="utf-8") as f:
    json.dump(reposo, f)
print("GLB", SALIDA, os.path.getsize(SALIDA))

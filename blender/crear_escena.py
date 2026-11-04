"""Crea blender/personaje/avatar_inclusion.blend: el personaje listo para usar con la app.

    blender -b --factory-startup --python blender/crear_escena.py

La escena trae el personaje de blender/personaje/*.fbx (con su textura dentro del
.blend), ya conectado a los puntos, una cámara que encuadra el torso (donde se
ven las señas) y el add-on como texto que se registra al abrir el archivo.
"""
import glob
import math
import os
import sys

import bpy

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import inclusion_avatar as ia  # noqa: E402

SALIDA = os.path.join(AQUI, "personaje", "avatar_inclusion.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
ia.register()
esc = bpy.context.scene
esc.name = "INCLUSION"
esc.render.fps = 30

bpy.ops.import_scene.fbx(filepath=glob.glob(os.path.join(AQUI, "personaje", "*.fbx"))[0])
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
arm.name = "Personaje"
bpy.context.view_layer.objects.active = arm
bpy.ops.inclusion.conectar_personaje()
bpy.ops.inclusion.crear_puntos()
bpy.data.collections[ia.COLECCION].hide_render = True
bpy.ops.file.pack_all()

camara = bpy.data.objects.new("Camara_torso", bpy.data.cameras.new("Camara_torso"))
esc.collection.objects.link(camara)
alto = max((arm.matrix_world @ b.head_local).z for b in arm.data.bones)      # cima de la cabeza
camara.location = (0, -alto * 1.7, alto * 0.74)
camara.rotation_euler = (math.radians(90), 0, 0)
camara.data.lens = 50
esc.camera = camara
luz = bpy.data.objects.new("Luz", bpy.data.lights.new("Luz", 'SUN'))
luz.rotation_euler = (math.radians(50), 0, math.radians(20))
esc.collection.objects.link(luz)
esc.world = bpy.data.worlds.new("Fondo")
esc.world.color = (0.12, 0.12, 0.14)

texto = bpy.data.texts.new("inclusion_avatar.py")
with open(os.path.join(AQUI, "inclusion_avatar.py"), encoding="utf-8") as f:
    texto.from_string(f.read())
texto.use_module = True        # se registra al abrir (si Blender permite scripts)

# Al abrir: el script ya visible en Scripting (listo para Run Script) y la barra
# lateral de la vista 3D abierta (pestaña INCLUSION)
for pantalla in bpy.data.screens:
    for area in pantalla.areas:
        if area.type == 'TEXT_EDITOR':
            area.spaces.active.text = texto
        elif area.type == 'VIEW_3D':
            area.spaces.active.show_region_ui = True

bpy.ops.wm.save_as_mainfile(filepath=SALIDA, compress=True)
print("ESCENA", SALIDA)

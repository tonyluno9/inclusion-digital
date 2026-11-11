"""Prueba del add-on INCLUSION Avatar (RF-21, RF-22). Corre DENTRO de Blender:

    blender -b --factory-startup --python-exit-code 1 --python blender/tests/test_inclusion_avatar.py
"""
import importlib.util
import json
import os
import socket
import sys
import tempfile
import traceback

import bpy

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA_ADDON = os.path.join(RAIZ, "blender", "inclusion_avatar.py")

spec = importlib.util.spec_from_file_location("inclusion_avatar", RUTA_ADDON)
ia = importlib.util.module_from_spec(spec)
sys.modules["inclusion_avatar"] = ia
spec.loader.exec_module(ia)

fallos = []


def comprobar(cond, msg):
    print(("  ok    " if cond else "  FALLA ") + msg)
    if not cond:
        fallos.append(msg)


def casi(a, b, tol=1e-4):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def parte(base, n):
    """n puntos; el punto i vale (base + i*0.001, base + 0.5, base + 0.25)."""
    return [[round(base + i * 0.001, 4), round(base + 0.5, 4), round(base + 0.25, 4)]
            for i in range(n)]


def clip_sintetico(palabra="hola", version=1):
    frames = [
        {"t": 0.0, "pose": parte(0.0, 33), "vis": [1.0] * 33,
         "left": parte(1.0, 21), "right": None},
        {"t": 0.5, "pose": parte(0.1, 33), "vis": [1.0] * 33,
         "left": None, "right": parte(2.0, 21)},
        {"t": 1.0, "pose": None, "vis": None,
         "left": parte(1.2, 21), "right": parte(2.2, 21)},
    ]
    return {"format": "inclusion-movimiento", "version": version, "word": palabra,
            "person": "prueba", "created": "2026-11-03T18:00:00", "fps": 30.0,
            "duration": 1.0, "coords": "metros", "pose_names": ia.NOMBRES_CUERPO,
            "hand_names": ia.NOMBRES_MANO, "frames": frames}


def main():
    ia.register()
    esc = bpy.context.scene
    esc.render.fps = 24
    esc.render.fps_base = 1.0

    print("Funciones puras")
    comprobar(ia.convertir_ejes((1, 2, 3)) == (1.0, -3.0, 2.0), "convertir_ejes (x,-z,y)")
    comprobar(len(ia.NOMBRES_CUERPO) == 33 and len(ia.NOMBRES_MANO) == 21, "listas 33 y 21")
    comprobar(ia.parsear_mensaje(b"no es json") is None, "JSON inválido se ignora")
    comprobar(ia.parsear_mensaje(b'{"type": "otro"}') is None, "tipo desconocido se ignora")
    comprobar(ia.nombre_accion("hola mundo") == "seña_hola_mundo", "nombre de acción")

    print("Crear puntos")
    n = ia.crear_puntos(esc)
    col = bpy.data.collections[ia.COLECCION]
    empties = [o for o in col.objects if o.type == 'EMPTY']
    comprobar(n == 75 and len(empties) == 75, f"75 empties (hay {len(empties)})")
    comprobar("cuerpo.left_shoulder" in bpy.data.objects, "cuerpo.left_shoulder")
    comprobar("mano_izq.wrist" in bpy.data.objects, "mano_izq.wrist")
    comprobar("mano_der.index_finger_tip" in bpy.data.objects, "mano_der.index_finger_tip")
    ia.crear_puntos(esc)
    empties2 = [o for o in bpy.data.collections[ia.COLECCION].objects if o.type == 'EMPTY']
    comprobar(len(empties2) == 75, "idempotente: sigue habiendo 75 empties")
    comprobar(sum(1 for o in bpy.data.objects if o.type == 'EMPTY') == 75, "sin empties duplicados")
    esqueleto = bpy.data.objects.get(ia.MALLA_ESQUELETO)
    comprobar(esqueleto is not None and len(esqueleto.data.vertices) == 75, "malla de esqueleto con 75 vértices")
    comprobar(sum(1 for o in bpy.data.objects if o.name.startswith(ia.MALLA_ESQUELETO)) == 1,
              "una sola malla de esqueleto")

    print("Importar clip")
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "hola.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(clip_sintetico(), f)
        accion, nk = ia.importar_clip(ruta, esc, inicio=1)
        comprobar(accion.name == "puntos_hola", f"acción '{accion.name}'")
        comprobar(len(accion.slots) > 0, f"{len(accion.slots)} slots en una sola acción")
        obj = bpy.data.objects["cuerpo.left_shoulder"]  # índice 11
        comprobar(obj.animation_data and obj.animation_data.action == accion, "empty usa la acción")
        # fps 24: t=0 -> 1, t=0.5 -> 13, t=1.0 -> 25
        esc.frame_set(1)
        p = parte(0.0, 33)[11]
        comprobar(casi(obj.location, (p[0], -p[2], p[1])), f"cuerpo frame 1 {tuple(obj.location)}")
        esc.frame_set(13)
        p = parte(0.1, 33)[11]
        comprobar(casi(obj.location, (p[0], -p[2], p[1])), f"cuerpo frame 13 {tuple(obj.location)}")
        mano = bpy.data.objects["mano_izq.index_finger_tip"]  # índice 8
        esc.frame_set(25)
        p = parte(1.2, 21)[8]
        comprobar(casi(mano.location, (p[0], -p[2], p[1])), f"mano_izq frame 25 {tuple(mano.location)}")

        def frames_clave(o):
            fc = [c for c in o.animation_data.action.layers[0].strips[0]
                  .channelbag(o.animation_data.action_slot).fcurves if c.data_path == "location"]
            return sorted({int(round(k.co[0])) for c in fc for k in c.keyframe_points})

        comprobar(frames_clave(obj) == [1, 13], f"cuerpo null en último frame: {frames_clave(obj)}")
        comprobar(frames_clave(mano) == [1, 25], f"mano_izq null en frame 13: {frames_clave(mano)}")
        comprobar(frames_clave(bpy.data.objects["mano_der.wrist"]) == [13, 25], "mano_der null en frame 1")
        comprobar(esc.frame_start == 1 and esc.frame_end == 25, f"rango {esc.frame_start}-{esc.frame_end}")

        # Reimportar reemplaza, no duplica
        ia.importar_clip(ruta, esc, inicio=1)
        comprobar(len([a for a in bpy.data.actions if a.name.startswith("puntos_hola")]) == 1,
                  "reimportar no duplica la acción")

        # Versión desconocida
        mala = os.path.join(tmp, "mala.json")
        with open(mala, "w", encoding="utf-8") as f:
            json.dump(clip_sintetico(version=99), f)
        try:
            ia.importar_clip(mala, esc)
            comprobar(False, "versión desconocida debería rechazarse")
        except ia.ClipInvalido as e:
            comprobar("versión" in str(e).lower(), f"versión rechazada: {e}")
        otro = os.path.join(tmp, "otro.json")
        with open(otro, "w", encoding="utf-8") as f:
            json.dump({"format": "otra-cosa", "version": 1}, f)
        try:
            ia.cargar_clip(otro)
            comprobar(False, "formato desconocido debería rechazarse")
        except ia.ClipInvalido:
            comprobar(True, "formato desconocido rechazado")

    print("UDP en vivo")
    # Quitar animación para que el valor en vivo no lo pise la acción
    for o in bpy.data.objects:
        if o.animation_data:
            o.animation_data.action = None
    esc.inc_auto_importar = False
    s0 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s0.bind(("127.0.0.1", 0))
    puerto = s0.getsockname()[1]
    s0.close()
    esc.inc_host, esc.inc_puerto = "127.0.0.1", puerto
    antes_mano_i = tuple(bpy.data.objects["mano_izq.index_finger_tip"].location)
    ia.Estado.frames = 0
    ia.Estado.sock = ia.abrir_socket(esc.inc_host, esc.inc_puerto)
    ia.Estado.activo = True
    envio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", puerto)
    envio.sendto(b"basura {{", dest)
    envio.sendto(b'{"type": "raro"}', dest)
    f1 = {"type": "frame", "t": 1.0, "pose": parte(5.0, 33), "vis": [1.0] * 33,
          "left": parte(6.0, 21), "right": None}
    f2 = {"type": "frame", "t": 2.0, "pose": parte(0.3, 33), "vis": [1.0] * 33,
          "left": None, "right": parte(0.7, 21)}
    envio.sendto(json.dumps(f1).encode(), dest)
    envio.sendto(json.dumps(f2).encode(), dest)
    import time
    time.sleep(0.2)
    n = ia.procesar_datagramas(esc)
    comprobar(n == 2, f"2 frames válidos drenados ({n})")
    comprobar(ia.Estado.frames == 2, "contador de frames")
    hombro = bpy.data.objects["cuerpo.left_shoulder"]
    p = parte(0.3, 33)[11]
    comprobar(casi(hombro.location, (p[0], -p[2], p[1])), f"se aplicó solo el último frame {tuple(hombro.location)}")
    mano_i = bpy.data.objects["mano_izq.index_finger_tip"]
    comprobar(casi(mano_i.location, antes_mano_i), "left null no movió la mano izquierda")
    mano_d = bpy.data.objects["mano_der.index_finger_tip"]
    p = parte(0.7, 21)[8]
    comprobar(casi(mano_d.location, (p[0], -p[2], p[1])), "mano derecha movida")

    # El esqueleto visual sigue a los empties (Hook)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = bpy.data.objects[ia.MALLA_ESQUELETO].evaluated_get(dg)
    v = ev.data.vertices[11].co
    comprobar(casi(v, tuple(hombro.location), 1e-3), f"hook mueve el vértice del hombro {tuple(v)}")

    # Aviso de clip con importación automática
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "adios.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(clip_sintetico("adios"), f)
        esc.inc_auto_importar = True
        envio.sendto(json.dumps({"type": "clip", "word": "adios", "path": ruta}).encode(), dest)
        time.sleep(0.2)
        ia.procesar_datagramas(esc)
        comprobar("puntos_adios" in bpy.data.actions, "aviso 'clip' importa automáticamente")

    envio.close()
    ia.cerrar_socket()
    comprobar(ia.Estado.sock is None and not ia.Estado.activo, "socket liberado")
    ia.unregister()


try:
    main()
except Exception:
    traceback.print_exc()
    fallos.append("excepción no controlada")

if fallos:
    print(f"\nFALLARON {len(fallos)} comprobaciones")
    sys.exit(1)
print("\nTODO OK")

"""Retargeting de los puntos al rig del personaje (RF-23), dentro de Blender:

    blender -b --factory-startup --python-exit-code 1 --python blender/tests/test_retarget.py

Usa el personaje de blender/personaje/. Sale con código != 0 si algo falla.
"""
import glob
import json
import math
import os
import sys
import tempfile

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import inclusion_avatar as ia  # noqa: E402

FALLAS = []


def comprobar(cond, texto):
    print(("ok    " if cond else "FALLA ") + texto)
    if not cond:
        FALLAS.append(texto)


def cargar_personaje():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ia.register()
    fbx = glob.glob(os.path.join(os.path.dirname(AQUI), "personaje", "*.fbx"))[0]
    bpy.ops.import_scene.fbx(filepath=fbx)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    bpy.context.scene.inc_personaje = arm
    return arm


def a_clip(v):
    """Coordenadas de Blender -> del clip (inversa de convertir_ejes)."""
    return [v.x, v.z, -v.y]


def frame_desde_rig(arm, perfil, posado=True):
    """Frame del clip con los puntos del propio rig (posado o en reposo):
    como si una persona con las proporciones del personaje hiciera esa pose."""
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    pb, bones = arm.pose.bones, arm.data.bones

    def cabeza(n):
        return mw @ (pb[n].head if posado else bones[n].head_local)

    def cola(n):
        return mw @ (pb[n].tail if posado else bones[n].tail_local)

    pose = [[0.0, 0.0, 0.0] for _ in range(33)]
    vis = [0.0] * 33
    manos = {}
    for s, clave, i_h, i_c, i_m in ia.LADOS:
        lado = perfil["lados"][s]
        for i, h in ((i_h, lado["brazo"]), (i_c, lado["antebrazo"]), (i_m, lado["mano"])):
            pose[i], vis[i] = a_clip(cabeza(h)), 1.0
        pts = [None] * 21
        pts[0] = a_clip(cabeza(lado["mano"]))
        for dedo, cadena in lado["dedos"].items():
            idx = ia.CADENAS_DEDO[dedo]
            for k, h in enumerate(cadena):
                pts[idx[k]] = a_clip(cabeza(h))
            pts[idx[3]] = a_clip(cola(cadena[2]))
        manos[clave] = pts
    # Orejas a los lados y nariz al frente (un poco abajo), girando con la cabeza
    n = perfil["cabeza"]
    giro = (pb[n].matrix.to_3x3() @ bones[n].matrix_local.to_3x3().inverted()) if posado else Matrix.Identity(3)
    giro = mw.to_3x3() @ giro
    head = cabeza(n)
    b = ia.CABEZA_INCLINACION
    pose[7] = a_clip(head + giro @ Vector((0.05, 0, 0)))
    pose[8] = a_clip(head + giro @ Vector((-0.05, 0, 0)))
    pose[0] = a_clip(head + giro @ (Vector((0, -math.cos(b), -math.sin(b))) * 0.06))
    for i, h in ((23, perfil["caderas"][0]), (24, perfil["caderas"][1])):
        pose[i] = a_clip(cabeza(h))
    for i in (0, 7, 8, 23, 24):
        vis[i] = 1.0
    return {"t": 0.0, "pose": pose, "vis": vis, "left": manos["left"], "right": manos["right"]}


def convertir(p):
    return ia.convertir_ejes(p)


def angulo(a, b):
    return math.degrees(a.angle(b)) if a.length > 1e-9 and b.length > 1e-9 else 0.0


def segmentos(arm, perfil):
    """Dirección (cabeza -> cola) de los huesos resueltos, en espacio de mundo."""
    bpy.context.view_layer.update()
    mw = arm.matrix_world.to_3x3()
    return {n: mw @ (arm.pose.bones[n].tail - arm.pose.bones[n].head) for n in ia.huesos_del_perfil(perfil)}


def reposo(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
        pb.rotation_mode = 'QUATERNION'
    bpy.context.view_layer.update()


def prueba_reposo(arm, perfil):
    reposo(arm)
    rt = ia.Retarget(arm, perfil)
    bases = rt.bases(rt.resolver(frame_desde_rig(arm, perfil, posado=False)))
    peor = max((math.degrees(q.angle) if q.angle <= math.pi else 360 - math.degrees(q.angle), n)
               for n, q in bases.items())
    comprobar(len(bases) == len(ia.huesos_del_perfil(perfil)), f"resuelve los {len(bases)} huesos del perfil")
    comprobar(peor[0] < 0.5, f"en reposo ningún hueso gira (peor: {peor[1]} {peor[0]:.3f}°)")


POSE_PRUEBA = {   # hueso: rotación local (grados XYZ) con la que se arma la pose de referencia
    "L_Upperarm": (0, 0, -65), "L_Forearm": (0, 0, 80), "L_Hand": (0, 50, 10),
    "L_Index1": (60, 0, 0), "L_Index2": (50, 0, 0), "L_Mid1": (70, 0, 0), "L_Thumb1": (0, 20, 30),
    "R_Upperarm": (30, 0, 50), "R_Forearm": (0, 0, -70), "R_Hand": (20, -40, 0),
    "R_Pinky1": (80, 0, 0), "R_Pinky2": (60, 0, 0), "R_Ring1": (60, 0, 0),
    "Spine02": (10, 0, 5), "Head": (15, 20, 0),
}


def prueba_pose_conocida(arm, perfil):
    reposo(arm)
    for nombre, grados in POSE_PRUEBA.items():
        arm.pose.bones[nombre].rotation_quaternion = Euler([math.radians(g) for g in grados]).to_quaternion()
    frame = frame_desde_rig(arm, perfil)
    esperado = segmentos(arm, perfil)
    mano_esperada = {s: arm.pose.bones[perfil["lados"][s]["mano"]].matrix.to_quaternion() for s in "LR"}

    reposo(arm)
    rt = ia.Retarget(arm, perfil)
    rt.aplicar(frame)
    obtenido = segmentos(arm, perfil)
    errores = {n: angulo(esperado[n], obtenido[n]) for n in esperado}
    brazos = [n for n in errores if any(k in n for k in ("Upperarm", "Forearm", "Hand"))]
    dedos = [n for n in errores if any(k in n for k in ("Thumb", "Index", "Mid", "Ring", "Pinky"))]
    peor_brazo = max(brazos, key=errores.get)
    peor_dedo = max(dedos, key=errores.get)
    # El antebrazo gira sobre la línea codo -> muñeca, que no es exactamente el eje del hueso
    comprobar(errores[peor_brazo] < 1.5, f"brazos apuntan igual (peor {peor_brazo}: {errores[peor_brazo]:.2f}°)")
    comprobar(errores[peor_dedo] < 1.0, f"dedos apuntan igual (peor {peor_dedo}: {errores[peor_dedo]:.2f}°)")
    for s in "LR":
        q = arm.pose.bones[perfil["lados"][s]["mano"]].matrix.to_quaternion()
        dif = math.degrees(mano_esperada[s].rotation_difference(q).angle)
        dif = min(dif, 360 - dif)
        comprobar(dif < 1.0, f"orientación completa de la mano {s} (palma incluida): {dif:.2f}°")
    comprobar(errores["Head"] < 1.0, f"la cabeza sigue a orejas y nariz ({errores['Head']:.2f}°)")
    # El pecho: no se sabe qué vértebra dobló (se reparte), pero los hombros deben quedar igual
    bpy.context.view_layer.update()
    hombros = [Vector(convertir(frame["pose"][i])) for i in (11, 12, 23, 24)]
    pb = arm.pose.bones
    obt = [arm.matrix_world @ pb[n].head for n in ("L_Upperarm", "R_Upperarm", "L_Thigh", "R_Thigh")]
    linea = angulo(hombros[0] - hombros[1], obt[0] - obt[1])
    centro_esp = (hombros[0] + hombros[1]) / 2 - (hombros[2] + hombros[3]) / 2
    centro_obt = (obt[0] + obt[1]) / 2 - (obt[2] + obt[3]) / 2
    # Inclinación: hasta ~25 % de error, porque las vértebras giran sobre puntos más altos que la cadera
    comprobar(linea < 1.0 and angulo(centro_esp, centro_obt) < 3.0,
              f"el pecho deja los hombros igual (línea {linea:.2f}°, inclinación {angulo(centro_esp, centro_obt):.2f}°)")
    # La pronación se reparte: el antebrazo izquierdo gira sobre su eje, no solo la mano
    ante = arm.pose.bones["L_Forearm"].matrix_basis.to_quaternion()
    giro_y = abs(math.degrees(ante.to_swing_twist('Y')[1]))
    comprobar(giro_y > 5, f"el antebrazo toma parte del giro de la muñeca ({giro_y:.1f}°)")


def prueba_partes_ausentes(arm, perfil):
    reposo(arm)
    rt = ia.Retarget(arm, perfil)
    frame = frame_desde_rig(arm, perfil, posado=False)
    rt.resolver(frame)
    sin_mano = dict(frame, left=None)
    giros = rt.resolver(sin_mano)
    comprobar("L_Index1" in giros, "una mano perdida conserva su último giro")
    sin_nada = {"t": 0, "pose": None, "vis": None, "left": None, "right": None}
    comprobar(len(rt.resolver(sin_nada)) == len(giros), "un frame vacío no rompe ni borra la pose")


def prueba_hornear(arm, perfil):
    reposo(arm)
    for nombre, grados in POSE_PRUEBA.items():
        arm.pose.bones[nombre].rotation_quaternion = Euler([math.radians(g) for g in grados]).to_quaternion()
    posado = frame_desde_rig(arm, perfil)
    reposo(arm)
    quieto = frame_desde_rig(arm, perfil, posado=False)
    frames = []
    for i in range(31):           # de reposo a la pose y de regreso, 1 s a 30 fps
        w = 1 - abs(i - 15) / 15
        fr = {"t": i / 30, "vis": quieto["vis"]}
        for clave in ("pose", "left", "right"):
            fr[clave] = [[(1 - w) * a + w * b for a, b in zip(p, q)] for p, q in zip(quieto[clave], posado[clave])]
        frames.append(fr)
    clip = {"format": "inclusion-movimiento", "version": 1, "word": "prueba", "fps": 30, "duration": 1.0,
            "frames": frames}
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "prueba.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(clip, f)
        esc = bpy.context.scene
        esc.render.fps = 30
        ia.importar_clip(ruta, esc, inicio=1)
    accion = bpy.data.actions.get("seña_prueba")
    comprobar(accion is not None and arm.animation_data.action == accion, "acción 'seña_prueba' en el personaje")
    comprobar("puntos_prueba" in bpy.data.actions, "y 'puntos_prueba' en los puntos")
    canal = accion.layers[0].strips[0].channelbag(arm.animation_data.action_slot)
    curvas = {fc.data_path for fc in canal.fcurves}
    comprobar(len(curvas) == len(ia.huesos_del_perfil(perfil)), f"{len(curvas)} huesos con keyframes")
    valores = [kp.co[1] for fc in canal.fcurves for kp in fc.keyframe_points]
    comprobar(all(math.isfinite(v) for v in valores), "sin NaN")
    esc.frame_set(16)             # el frame de la pose completa
    bpy.context.view_layer.update()
    mano = arm.pose.bones["L_Index1"]
    comprobar(mano.matrix_basis.to_quaternion().angle > math.radians(20), "a mitad del clip el índice está doblado")
    medio = arm.pose.bones["L_Upperarm"].matrix_basis.to_quaternion()
    esc.frame_set(1)
    bpy.context.view_layer.update()
    inicio = arm.pose.bones["L_Upperarm"].matrix_basis.to_quaternion()

    def grados(q):
        return math.degrees(min(q.angle, 2 * math.pi - q.angle))
    comprobar(grados(inicio) < 0.2 * grados(medio),
              f"empieza cerca del reposo ({grados(inicio):.1f}° contra {grados(medio):.1f}° a la mitad)")


def prueba_en_vivo(arm, perfil):
    """RF-21 + RF-23: un frame que llega por UDP mueve los puntos y el personaje."""
    import socket
    reposo(arm)
    for nombre, grados in POSE_PRUEBA.items():
        arm.pose.bones[nombre].rotation_quaternion = Euler([math.radians(g) for g in grados]).to_quaternion()
    frame = frame_desde_rig(arm, perfil)
    esperado = segmentos(arm, perfil)
    reposo(arm)
    esc = bpy.context.scene
    rx = ia.abrir_socket("127.0.0.1", 0)
    ia.Estado.sock, ia.Estado.activo, ia.Estado.retarget = rx, True, None
    try:
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tx.sendto(json.dumps(dict(frame, type="frame")).encode("utf-8"), rx.getsockname())
        tx.close()
        n = 0
        for _ in range(50):
            n = ia.procesar_datagramas(esc)
            if n:
                break
    finally:
        ia.cerrar_socket()
    comprobar(n == 1, "llegó el frame en vivo")
    obtenido = segmentos(arm, perfil)
    peor = max(angulo(esperado[h], obtenido[h]) for h in ("L_Upperarm", "R_Hand", "L_Index1"))
    comprobar(peor < 1.5, f"en vivo el personaje toma la pose ({peor:.2f}°)")


def main():
    arm = cargar_personaje()
    perfil_nombre = ia.detectar_perfil(b.name for b in arm.data.bones)
    comprobar(perfil_nombre == "Tripo", f"perfil detectado: {perfil_nombre}")
    perfil = ia.PERFILES["Tripo"]
    bpy.ops.inclusion.conectar_personaje()
    comprobar(bpy.context.scene.inc_personaje == arm, "Conectar personaje encuentra el rig")
    prueba_reposo(arm, perfil)
    prueba_pose_conocida(arm, perfil)
    prueba_partes_ausentes(arm, perfil)
    prueba_hornear(arm, perfil)
    prueba_en_vivo(arm, perfil)
    ia.unregister()
    if FALLAS:
        print(f"{len(FALLAS)} FALLAS")
        sys.exit(1)
    print("TODO OK")


if __name__ == "__main__":
    main()

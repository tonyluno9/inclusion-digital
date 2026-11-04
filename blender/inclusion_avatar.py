"""INCLUSION · Avatar LSM para Blender (RF-21, RF-22, RF-23).

Add-on de un solo archivo:
  * Crea un esqueleto de puntos (empties) para cuerpo (33) y manos (21 + 21).
  * Escucha por UDP los frames que envía la app y mueve los puntos en vivo.
  * Importa clips ``.json`` (formato ``inclusion-movimiento``, version 1) como
    animación de esos puntos, con una acción por palabra.
  * Conecta un personaje con rig (perfil conocido, p. ej. el de Tripo): en vivo
    lo mueve con la persona y al importar un clip hornea su acción ``seña_<palabra>``.

Ejes: el clip usa x = izquierda de la persona, y = arriba, z = hacia adelante.
En Blender (personaje mirando a -Y): (X, Y, Z) = (x, -z, y).

Instalación: Edit > Preferences > Add-ons > Install from Disk, o abrir el
archivo en el Text Editor y pulsar "Run Script".
"""

bl_info = {
    "name": "INCLUSION Avatar LSM",
    "author": "Proyecto INCLUSION",
    "version": (1, 1, 0),
    "blender": (4, 4, 0),
    "location": "Vista 3D > Barra lateral (N) > INCLUSION",
    "description": "Puntos en vivo (UDP) e importación de clips de Lengua de Señas Mexicana",
    "category": "Animation",
}

import json
import math
import os
import re
import socket

try:
    import bpy
    from bpy.props import BoolProperty, IntProperty, PointerProperty, StringProperty
    from bpy.types import Operator, Panel
    from bpy_extras.io_utils import ImportHelper
    from mathutils import Matrix, Quaternion, Vector
except ImportError:  # permite probar las funciones puras fuera de Blender
    bpy = None
    Operator = Panel = ImportHelper = object

    def StringProperty(**_kw):
        return None

# ---------------------------------------------------------------------------
# Constantes del formato
# ---------------------------------------------------------------------------
FORMATO = "inclusion-movimiento"
VERSION = 1

COLECCION = "INCLUSION_Puntos"
MALLA_ESQUELETO = "INCLUSION_Esqueleto"

NOMBRES_CUERPO = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee",
    "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]
NOMBRES_MANO = [
    "wrist",
    "thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip",
    "index_finger_mcp", "index_finger_pip", "index_finger_dip", "index_finger_tip",
    "middle_finger_mcp", "middle_finger_pip", "middle_finger_dip", "middle_finger_tip",
    "ring_finger_mcp", "ring_finger_pip", "ring_finger_dip", "ring_finger_tip",
    "pinky_mcp", "pinky_pip", "pinky_dip", "pinky_tip",
]
N_CUERPO = len(NOMBRES_CUERPO)  # 33
N_MANO = len(NOMBRES_MANO)      # 21

CONEXIONES_CUERPO = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8), (9, 10),
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    (11, 23), (12, 24), (23, 24), (23, 25), (24, 26), (25, 27), (26, 28),
    (27, 29), (28, 30), (29, 31), (30, 32), (27, 31), (28, 32),
]
CONEXIONES_MANO = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
    (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
]

# Grupos: (clave del frame, prefijo del empty, nombres, radio en metros)
GRUPOS = (
    ("pose", "cuerpo", NOMBRES_CUERPO, 0.020),
    ("left", "mano_izq", NOMBRES_MANO, 0.015),
    ("right", "mano_der", NOMBRES_MANO, 0.015),
)


# ---------------------------------------------------------------------------
# Funciones puras (sin bpy)
# ---------------------------------------------------------------------------
class ClipInvalido(ValueError):
    """El clip o mensaje no cumple el formato; el texto está en español."""


def convertir_ejes(p):
    """(x, y, z) de la app -> (X, Y, Z) de Blender: (x, -z, y)."""
    return (float(p[0]), -float(p[2]), float(p[1]))


def nombre_punto(prefijo, nombre):
    return f"{prefijo}.{nombre}"


def todos_los_puntos():
    """Lista de (clave, indice, nombre_de_empty, radio) en orden estable."""
    salida = []
    for clave, prefijo, nombres, radio in GRUPOS:
        for i, n in enumerate(nombres):
            salida.append((clave, i, nombre_punto(prefijo, n), radio))
    return salida


def _es_punto(p):
    return (isinstance(p, (list, tuple)) and len(p) == 3
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    and math.isfinite(v) for v in p))


def validar_parte(valor, n, etiqueta):
    """Una parte (pose/left/right) debe ser None o lista de n puntos [x, y, z]."""
    if valor is None:
        return
    if not isinstance(valor, list) or len(valor) != n:
        raise ClipInvalido(f"'{etiqueta}' debe ser null o una lista de {n} puntos.")
    for p in valor:
        if not _es_punto(p):
            raise ClipInvalido(f"'{etiqueta}' contiene un punto que no es [x, y, z] numérico.")


def validar_frame(fr, etiqueta="frame"):
    if not isinstance(fr, dict):
        raise ClipInvalido(f"{etiqueta}: no es un objeto.")
    t = fr.get("t")
    if t is not None and (not isinstance(t, (int, float)) or isinstance(t, bool)):
        raise ClipInvalido(f"{etiqueta}: 't' debe ser numérico.")
    validar_parte(fr.get("pose"), N_CUERPO, f"{etiqueta}.pose")
    validar_parte(fr.get("left"), N_MANO, f"{etiqueta}.left")
    validar_parte(fr.get("right"), N_MANO, f"{etiqueta}.right")


def validar_clip(datos):
    """Valida un clip ya cargado. Lanza ClipInvalido (mensaje en español)."""
    if not isinstance(datos, dict):
        raise ClipInvalido("El archivo no contiene un objeto JSON.")
    if datos.get("format") != FORMATO:
        raise ClipInvalido(
            f"Formato no reconocido: se esperaba '{FORMATO}' y el archivo dice "
            f"'{datos.get('format')}'.")
    if datos.get("version") != VERSION:
        raise ClipInvalido(
            f"Versión del clip no compatible: este script entiende la versión "
            f"{VERSION} y el archivo es la versión {datos.get('version')}.")
    fps = datos.get("fps")
    if fps is not None and (not isinstance(fps, (int, float)) or fps <= 0):
        raise ClipInvalido("'fps' del clip debe ser un número positivo.")
    frames = datos.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ClipInvalido("El clip no tiene frames.")
    for i, fr in enumerate(frames):
        if not isinstance(fr.get("t") if isinstance(fr, dict) else None, (int, float)):
            raise ClipInvalido(f"frame {i}: falta 't' numérico.")
        validar_frame(fr, f"frame {i}")
    return datos


def cargar_clip(ruta):
    """Lee y valida un archivo de clip."""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except OSError as e:
        raise ClipInvalido(f"No se pudo leer el archivo: {e}") from e
    except ValueError as e:
        raise ClipInvalido(f"El archivo no es un JSON válido: {e}") from e
    return validar_clip(datos)


def parsear_mensaje(datagrama):
    """bytes/str -> dict de mensaje válido (type 'frame' o 'clip'), o None si se ignora."""
    try:
        if isinstance(datagrama, (bytes, bytearray)):
            datagrama = bytes(datagrama).decode("utf-8")
        msg = json.loads(datagrama)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict):
        return None
    tipo = msg.get("type")
    if tipo == "frame":
        try:
            validar_frame(msg, "frame")
        except ClipInvalido:
            return None
        return msg
    if tipo == "clip":
        if isinstance(msg.get("path"), str) and msg["path"]:
            return msg
        return None
    return None


def frame_de_tiempo(t, fps_escena, inicio=1):
    """Número de frame de Blender para el tiempo t (s) del clip."""
    return int(inicio) + int(round(float(t) * float(fps_escena)))


def nombre_accion_puntos(palabra):
    """Acción de los puntos de una palabra: 'puntos_<palabra>'."""
    return "puntos_" + nombre_accion(palabra)[len("seña_"):]


def nombre_accion(palabra):
    """Nombre de la acción de una palabra: 'seña_<palabra>' (sin caracteres raros)."""
    limpia = re.sub(r"[^\w\-]+", "_", str(palabra or "sin_nombre"), flags=re.UNICODE).strip("_")
    return "seña_" + (limpia or "sin_nombre")


def posiciones_frame(frame):
    """Itera (nombre_de_empty, (X, Y, Z)) para las partes presentes de un frame."""
    for clave, prefijo, nombres, _ in GRUPOS:
        parte = frame.get(clave)
        if parte is None:
            continue
        for n, p in zip(nombres, parte):
            yield nombre_punto(prefijo, n), convertir_ejes(p)


# ---------------------------------------------------------------------------
# Funciones con bpy
# ---------------------------------------------------------------------------
def _coleccion(escena):
    col = bpy.data.collections.get(COLECCION)
    if col is None:
        col = bpy.data.collections.new(COLECCION)
    if col.name not in escena.collection.children:
        try:
            escena.collection.children.link(col)
        except RuntimeError:
            pass
    return col


def crear_puntos(escena=None):
    """Crea (o reutiliza) los 75 empties y la malla de huesos. Devuelve cuántos empties existen."""
    escena = escena or bpy.context.scene
    col = _coleccion(escena)
    empties = {}
    for _clave, _i, nombre, radio in todos_los_puntos():
        obj = bpy.data.objects.get(nombre)
        if obj is None:
            obj = bpy.data.objects.new(nombre, None)
            obj.empty_display_type = 'SPHERE'
            obj.empty_display_size = radio
        if obj.name not in col.objects:
            col.objects.link(obj)
        empties[nombre] = obj
    _crear_esqueleto_visual(col, empties)
    return len(empties)


def _crear_esqueleto_visual(col, empties):
    """Malla de aristas (un vértice por punto) con un Hook por empty."""
    if bpy.data.objects.get(MALLA_ESQUELETO) is not None:
        obj = bpy.data.objects[MALLA_ESQUELETO]
        if obj.name not in col.objects:
            col.objects.link(obj)
        return obj
    puntos = todos_los_puntos()
    indice = {nombre: k for k, (_c, _i, nombre, _r) in enumerate(puntos)}
    verts = [tuple(empties[nombre].location) for (_c, _i, nombre, _r) in puntos]
    aristas = []
    for clave, prefijo, nombres, _ in GRUPOS:
        conex = CONEXIONES_CUERPO if clave == "pose" else CONEXIONES_MANO
        for a, b in conex:
            aristas.append((indice[nombre_punto(prefijo, nombres[a])],
                            indice[nombre_punto(prefijo, nombres[b])]))
    malla = bpy.data.meshes.new(MALLA_ESQUELETO)
    malla.from_pydata(verts, aristas, [])
    malla.update()
    obj = bpy.data.objects.new(MALLA_ESQUELETO, malla)
    col.objects.link(obj)
    obj.hide_select = True
    for k, (_c, _i, nombre, _r) in enumerate(puntos):
        emp = empties[nombre]
        mod = obj.modifiers.new(f"Hook.{nombre}", 'HOOK')
        mod.object = emp
        mod.vertex_indices_set([k])
        mod.matrix_inverse = Matrix.Translation(emp.location).inverted()
    return obj


def obtener_empties():
    """Dict nombre -> objeto de los empties que existan."""
    return {n: bpy.data.objects[n] for (_c, _i, n, _r) in todos_los_puntos()
            if n in bpy.data.objects}


def aplicar_frame(msg, empties=None):
    """Mueve los empties según un frame en vivo. Partes null no se tocan. Devuelve puntos movidos."""
    empties = empties if empties is not None else obtener_empties()
    movidos = 0
    for nombre, pos in posiciones_frame(msg):
        obj = empties.get(nombre)
        if obj is not None:
            obj.location = pos
            movidos += 1
    return movidos


def _fps_escena(escena):
    return escena.render.fps / (escena.render.fps_base or 1.0)


def soltar_acciones(empties=None, escena=None):
    """Quita la animación asignada a los puntos y al personaje (las acciones
    quedan guardadas), para que el movimiento en vivo no lo pise un clip."""
    empties = empties if empties is not None else obtener_empties()
    objetos = list(empties.values())
    arm = personaje(escena or bpy.context.scene)
    if arm is not None:
        objetos.append(arm)
    for obj in objetos:
        if obj.animation_data is not None:
            obj.animation_data.action = None


def importar_clip(ruta, escena=None, inicio=None, asignar=True):
    """Importa un clip como acción 'seña_<palabra>' con un slot por empty.

    Con asignar=False la acción solo se guarda (se usa en vivo, para que los
    puntos sigan a la persona). Devuelve (accion, n_keyframes). Reimportar la
    misma palabra reemplaza la acción.
    """
    escena = escena or bpy.context.scene
    datos = cargar_clip(ruta)
    if inicio is None:
        inicio = getattr(escena, "inc_inicio", 1)
    palabra = datos.get("word") or os.path.splitext(os.path.basename(ruta))[0]
    nombre = nombre_accion_puntos(palabra)
    fps = _fps_escena(escena)

    crear_puntos(escena)
    empties = obtener_empties()

    # Reemplazo: soltar y borrar la acción anterior de esa palabra
    previa = bpy.data.actions.get(nombre)
    if previa is not None:
        for obj in empties.values():
            ad = obj.animation_data
            if ad is not None and ad.action == previa:
                ad.action = None
        bpy.data.actions.remove(previa)

    # Valores por empty: nombre -> [(frame, (X, Y, Z))]
    series = {}
    for fr in datos["frames"]:
        f = frame_de_tiempo(fr["t"], fps, inicio)
        for n, pos in posiciones_frame(fr):
            series.setdefault(n, []).append((f, pos))

    accion = bpy.data.actions.new(nombre)
    accion.use_fake_user = True
    capa = accion.layers.new("Capa")
    tira = capa.strips.new(type='KEYFRAME')
    total = 0
    for n, serie in series.items():
        obj = empties.get(n)
        if obj is None:
            continue
        slot = accion.slots.new(id_type='OBJECT', name=obj.name)
        if asignar:
            ad = obj.animation_data_create()
            ad.action = accion
            ad.action_slot = slot
        canal = tira.channelbag(slot, ensure=True)
        for eje in range(3):
            fc = canal.fcurves.new("location", index=eje)
            fc.keyframe_points.add(len(serie))
            for kp, (f, pos) in zip(fc.keyframe_points, serie):
                kp.co = (float(f), pos[eje])
                kp.interpolation = 'LINEAR'
            fc.update()
            total += len(serie)

    Estado.accion_personaje = None
    arm = personaje(escena)
    perfil = detectar_perfil(b.name for b in arm.data.bones) if arm else None
    if perfil is not None:
        Estado.accion_personaje = hornear_clip(datos, arm, PERFILES[perfil], nombre_accion(palabra),
                                               fps, inicio, asignar)

    if asignar:
        ultimo = frame_de_tiempo(datos.get("duration", datos["frames"][-1]["t"]), fps, inicio)
        ultimo = max(ultimo, frame_de_tiempo(datos["frames"][-1]["t"], fps, inicio))
        escena.frame_start = int(inicio)
        escena.frame_end = max(int(inicio) + 1, ultimo)
        escena.frame_set(int(inicio))
    return accion, total


# ---------------------------------------------------------------------------
# Personaje: retargeting de los puntos al rig (RF-23)
# ---------------------------------------------------------------------------
# Cada hueso gira para apuntar en la dirección del segmento de la persona
# (hombro -> codo, codo -> muñeca, cada falange...). Se usan direcciones y no
# posiciones, así que no importa que el personaje mida distinto que la persona.
# El giro sobre el propio eje (roll) sale de una segunda referencia:
#   brazo y antebrazo: hacia dónde dobla el codo;
#   mano: la línea de nudillos índice -> meñique;
#   dedos: la misma línea (el pulgar, la normal de la palma).
# Todo se calcula en el espacio de la armadura como "giro respecto a la pose
# de descanso" (pose T con palmas abajo, mirando a -Y).

CADENAS_DEDO = {             # puntos de la mano de MediaPipe por dedo
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
LADOS = (("L", "left", 11, 13, 15), ("R", "right", 12, 14, 16))   # lado, mano del clip, hombro, codo, muñeca
CABEZA_INCLINACION = 0.35    # rad: la nariz está más abajo que las orejas con la cabeza derecha
REPARTO_PRONACION = 0.5      # parte del giro de la muñeca que toma el antebrazo
VISIBLE = 0.5
# Protecciones contra datos imposibles (MediaPipe a veces inventa el cuerpo cuando no lo ve)
ANCHO_HOMBROS_MIN = 0.15     # m: hombros más juntos que esto = cuerpo mal detectado, no se usa
CADERAS_MAX = math.radians(40)   # caderas -> hombros más inclinado que esto: se usa la vertical
GIRO_MAX = {"pecho": math.radians(35), "cabeza": math.radians(70), "clavicula": math.radians(25)}


def perfil_tripo():
    """Nombres de huesos del rig humanoide de Tripo (L_/R_, 3 falanges por dedo)."""
    dedos = {"thumb": "Thumb", "index": "Index", "middle": "Mid", "ring": "Ring", "pinky": "Pinky"}
    lados = {}
    for s, *_ in LADOS:
        lados[s] = {
            "clavicula": f"{s}_Clavicle", "brazo": f"{s}_Upperarm", "antebrazo": f"{s}_Forearm",
            "mano": f"{s}_Hand",
            "dedos": {d: tuple(f"{s}_{n}{k}" for k in (1, 2, 3)) for d, n in dedos.items()},
        }
    return {"columna": ("Waist", "Spine01", "Spine02"), "cabeza": "Head", "caderas": ("L_Thigh", "R_Thigh"),
            "lados": lados}


PERFILES = {"Tripo": perfil_tripo()}


def huesos_del_perfil(perfil):
    nombres = list(perfil["columna"]) + [perfil["cabeza"]]
    for lado in perfil["lados"].values():
        nombres += [lado["clavicula"], lado["brazo"], lado["antebrazo"], lado["mano"]]
        for cadena in lado["dedos"].values():
            nombres += list(cadena)
    return nombres


def detectar_perfil(nombres_huesos):
    """Nombre del perfil cuyos huesos están todos en el rig, o None."""
    nombres = set(nombres_huesos)
    for nombre, perfil in PERFILES.items():
        if all(h in nombres for h in huesos_del_perfil(perfil) + list(perfil["caderas"])):
            return nombre
    return None


def suavizar_frames(frames, ventana=5):
    """Promedio móvil centrado de cada punto (pose y manos) a lo largo del clip.
    Solo promedia frames donde esa parte existe; no inventa partes ausentes."""
    r = ventana // 2
    out = [dict(fr) for fr in frames]
    for clave in ("pose", "left", "right"):
        for i, fr in enumerate(frames):
            if fr.get(clave) is None:
                continue
            vecinos = [frames[j][clave] for j in range(max(0, i - r), min(len(frames), i + r + 1))
                       if frames[j].get(clave) is not None]
            n = len(vecinos)
            out[i][clave] = [[sum(v[p][e] for v in vecinos) / n for e in range(3)] for p in range(len(fr[clave]))]
    return out


def _limitar(q, maximo):
    """El mismo giro, recortado a `maximo` radianes."""
    angulo = q.angle if q.angle <= math.pi else 2 * math.pi - q.angle
    return q if angulo <= maximo else Quaternion().slerp(q, maximo / angulo)


def _transicion(x, a, b):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class Retarget:
    """Convierte frames de movimiento en rotaciones de los huesos de un rig."""

    def __init__(self, armadura, perfil):
        self.arm = armadura
        self.perfil = perfil
        huesos = armadura.data.bones
        self.reposo = {b.name: b.matrix_local.copy() for b in huesos}
        self.orden = []                       # padres antes que hijos
        pendientes = [b for b in huesos if b.parent is None]
        while pendientes:
            b = pendientes.pop(0)
            self.orden.append(b.name)
            pendientes.extend(b.children)
        self.padre = {b.name: (b.parent.name if b.parent else None) for b in huesos}
        self.ultimo = {}                      # última rotación de cada hueso (para partes perdidas)
        mw = armadura.matrix_world
        self.escala = mw.to_scale().x         # de unidades de la armadura a metros
        a_arm = mw.inverted().to_3x3()          # ejes del mundo vistos desde la armadura
        self.vertical = (a_arm @ Vector((0, 0, 1))).normalized()
        self.frente = (a_arm @ Vector((0, -1, 0))).normalized()   # el personaje mira a -Y
        self.lateral = (a_arm @ Vector((1, 0, 0))).normalized()
        self._marcos_reposo(huesos)

    # -- marcos de referencia --------------------------------------------------
    @staticmethod
    def marco(primario, secundario):
        """Base ortonormal (columnas x, y, z) con y = primario y x hacia secundario."""
        if primario.length < 1e-9:
            return None
        y = primario.normalized()
        x = secundario - y * secundario.dot(y)
        if x.length < 1e-9:
            return None
        x.normalize()
        return Matrix((x, y, x.cross(y))).transposed()

    def _puntos_mano_reposo(self, lado):
        h = self.arm.data.bones
        pts = [None] * N_MANO
        pts[0] = h[lado["mano"]].head_local.copy()
        for dedo, cadena in lado["dedos"].items():
            idx = CADENAS_DEDO[dedo]
            for k, nombre in enumerate(cadena):
                pts[idx[k]] = h[nombre].head_local.copy()
            pts[idx[3]] = h[cadena[2]].tail_local.copy()
        return pts

    def _marcos_reposo(self, h):
        p = self.perfil
        self.r = {}
        hombros = {}
        for s, *_ in LADOS:
            lado = p["lados"][s]
            hombro, codo, muneca = (h[lado[k]].head_local.copy() for k in ("brazo", "antebrazo", "mano"))
            hombros[s] = hombro
            mano = self._puntos_mano_reposo(lado)
            frente = self.frente
            dir_mano, nudillos = mano[9] - mano[0], mano[5] - mano[17]
            # El codo dobla hacia adelante. Si el rig ya trae el codo algo doblado,
            # se usa ese doblez real (así en reposo el brazo no gira nada).
            u, f = codo - hombro, muneca - codo
            doblez = f - u.normalized() * f.dot(u.normalized())
            self.r[s] = {
                "u": u, "f": f,
                "brazo": self.marco(u, doblez if doblez.length > 0.2 * f.length else frente),
                "mano": self.marco(dir_mano, nudillos),
                "dedos": self._marcos_dedos(mano, dir_mano, nudillos),
            }
        centro = (hombros["L"] + hombros["R"]) / 2
        for s, *_ in LADOS:
            self.r[s]["clavicula"] = self.marco(hombros[s] - centro, self.frente)
        # Con caderas visibles, el pecho se inclina según la línea caderas -> hombros;
        # sin ellas solo se sabe la línea de hombros y se compara con la vertical
        caderas = (h[p["caderas"][0]].head_local + h[p["caderas"][1]].head_local) / 2
        self.r["pecho"] = self.marco(hombros["L"] - hombros["R"], centro - caderas)
        self.r["pecho_vertical"] = self.marco(hombros["L"] - hombros["R"], self.vertical)
        self.r["cabeza"] = self.marco(self.lateral, self.frente * math.cos(CABEZA_INCLINACION)
                                      - self.vertical * math.sin(CABEZA_INCLINACION))

    def _marcos_dedos(self, mano, dir_mano, nudillos):
        normal = dir_mano.cross(nudillos)
        marcos = {}
        for dedo, idx in CADENAS_DEDO.items():
            ref = normal if dedo == "thumb" else nudillos
            marcos[dedo] = [self.marco(mano[idx[k + 1]] - mano[idx[k]], ref) for k in range(3)]
        return marcos

    # -- resolver un frame -----------------------------------------------------
    def _delta(self, marco_destino, marco_reposo):
        if marco_destino is None or marco_reposo is None:
            return None
        return (marco_destino @ marco_reposo.transposed()).to_quaternion()

    def resolver(self, frame):
        """Frame de movimiento (coordenadas del clip) -> {hueso: giro respecto al reposo}
        en el espacio de la armadura. Las partes ausentes conservan su último giro."""
        a_local = self.arm.matrix_world.inverted()

        def puntos(clave):
            datos = frame.get(clave)
            return None if datos is None else [a_local @ Vector(convertir_ejes(q)) for q in datos]

        pose, vis = puntos("pose"), frame.get("vis") or [1.0] * N_CUERPO
        manos = {"left": puntos("left"), "right": puntos("right")}
        p, giros = self.perfil, {}

        if pose is not None and (pose[11] - pose[12]).length * self.escala < ANCHO_HOMBROS_MIN:
            pose = None                       # cuerpo imposible: se conserva la pose anterior
        if pose is not None:
            hombro_l, hombro_r = pose[11], pose[12]
            centro = (hombro_l + hombro_r) / 2
            arriba, ref = self.vertical, self.r["pecho_vertical"]
            if vis[23] > VISIBLE and vis[24] > VISIBLE:
                columna = centro - (pose[23] + pose[24]) / 2
                if columna.length > 1e-6 and columna.angle(self.vertical) < CADERAS_MAX:
                    arriba, ref = columna, self.r["pecho"]
            q = self._delta(self.marco(hombro_l - hombro_r, arriba), ref)
            if q is not None:
                q = _limitar(q, GIRO_MAX["pecho"])
                for k, nombre in enumerate(p["columna"]):
                    giros[nombre] = Quaternion().slerp(q, (k + 1) / len(p["columna"]))
            if vis[7] > VISIBLE and vis[8] > VISIBLE:
                orejas = (pose[7] + pose[8]) / 2
                q = self._delta(self.marco(pose[7] - pose[8], pose[0] - orejas), self.r["cabeza"])
                if q is not None:
                    giros[p["cabeza"]] = _limitar(q, GIRO_MAX["cabeza"])
            for s, clave_mano, i_hombro, i_codo, i_muneca in LADOS:
                lado, r = p["lados"][s], self.r[s]
                q = self._delta(self.marco(pose[i_hombro] - centro, self.frente), r["clavicula"])
                if q is not None:
                    giros[lado["clavicula"]] = _limitar(q, GIRO_MAX["clavicula"])
                giros.update(self._brazo(lado, r, pose[i_hombro], pose[i_codo], pose[i_muneca],
                                         manos[clave_mano]))
        for s, clave_mano, *_ in LADOS:
            if manos[clave_mano] is not None:
                giros.update(self._dedos(p["lados"][s], self.r[s], manos[clave_mano]))

        for nombre, q in giros.items():
            previo = self.ultimo.get(nombre)
            if previo is not None and previo.dot(q) < 0:   # mismo hemisferio: sin saltos al interpolar
                q.negate()
            self.ultimo[nombre] = q
        return dict(self.ultimo)

    def _brazo(self, lado, r, hombro, codo, muneca, mano):
        u, f = codo - hombro, muneca - codo
        if u.length < 1e-6 or f.length < 1e-6:
            return {}
        giros = {}
        uh = u.normalized()
        doblez = f - uh * f.dot(uh)
        q_giro = r["u"].rotation_difference(u)                     # solo dirección
        q_marco = self._delta(self.marco(u, doblez), r["brazo"])  # dirección y plano del codo
        peso = _transicion(doblez.length / f.length, 0.2, 0.45)  # brazo casi recto: el plano no es confiable
        if q_marco is None or peso == 0:
            q_brazo = q_giro
        else:
            if q_giro.dot(q_marco) < 0:
                q_marco.negate()
            q_brazo = q_giro.slerp(q_marco, peso)
        q_ante = (q_brazo @ r["f"]).rotation_difference(f) @ q_brazo
        giros[lado["brazo"]] = q_brazo
        if mano is not None:
            q_mano = self._delta(self.marco(mano[9] - mano[0], mano[5] - mano[17]), r["mano"])
            if q_mano is not None:
                # Parte del giro de la muñeca (pronación) pasa al antebrazo
                rel = q_ante.inverted() @ q_mano
                eje = r["f"].normalized()
                proy = eje * Vector(rel[1:]).dot(eje)
                torsion = Quaternion((rel[0], proy.x, proy.y, proy.z))
                if torsion.magnitude > 1e-9:
                    torsion.normalize()
                    q_ante = q_ante @ Quaternion().slerp(torsion, REPARTO_PRONACION)
                giros[lado["mano"]] = q_mano
        giros[lado["antebrazo"]] = q_ante
        return giros

    def _dedos(self, lado, r, mano):
        dir_mano, nudillos = mano[9] - mano[0], mano[5] - mano[17]
        normal = dir_mano.cross(nudillos)
        giros = {}
        for dedo, idx in CADENAS_DEDO.items():
            ref = normal if dedo == "thumb" else nudillos
            for k, nombre in enumerate(lado["dedos"][dedo]):
                q = self._delta(self.marco(mano[idx[k + 1]] - mano[idx[k]], ref), r["dedos"][dedo][k])
                if q is not None:
                    giros[nombre] = q
        return giros

    # -- de giros a la pose de Blender -----------------------------------------
    def bases(self, giros):
        """{hueso: giro absoluto} -> {hueso: rotación local (matrix_basis) en cuaternión}."""
        pb = self.arm.pose.bones
        posada, salida = {}, {}
        for nombre in self.orden:
            reposo, padre = self.reposo[nombre], self.padre[nombre]
            base_padre = posada[padre] @ self.reposo[padre].inverted() if padre else Matrix.Identity(4)
            sin_giro = base_padre @ reposo
            if nombre in giros:
                destino = Matrix.Translation(sin_giro.translation) @ \
                    (giros[nombre].to_matrix() @ reposo.to_3x3()).to_4x4()
                q = (sin_giro.inverted() @ destino).to_quaternion()
                salida[nombre] = q
                posada[nombre] = destino
            else:
                posada[nombre] = sin_giro @ pb[nombre].matrix_basis
        return salida

    def aplicar(self, frame):
        """Pone al personaje en la pose del frame (modo en vivo)."""
        pb = self.arm.pose.bones
        for nombre, q in self.bases(self.resolver(frame)).items():
            pb[nombre].rotation_mode = 'QUATERNION'
            pb[nombre].rotation_quaternion = q


def personaje(escena):
    """La armadura conectada en la escena, si existe y tiene un perfil conocido."""
    obj = getattr(escena, "inc_personaje", None)
    if obj is None or obj.type != 'ARMATURE':
        return None
    return obj


def retarget_para(escena):
    obj = personaje(escena)
    if obj is None:
        return None
    perfil = detectar_perfil(b.name for b in obj.data.bones)
    if perfil is None:
        return None
    if Estado.retarget is None or Estado.retarget.arm != obj:
        Estado.retarget = Retarget(obj, PERFILES[perfil])
    return Estado.retarget


def hornear_clip(datos, armadura, perfil, nombre, fps, inicio, asignar=True):
    """Hornea el clip en una acción del personaje (rotaciones de los huesos)."""
    rt = Retarget(armadura, perfil)
    frames = suavizar_frames(datos["frames"])
    series = {}
    for fr in frames:
        f = frame_de_tiempo(fr["t"], fps, inicio)
        for hueso, q in rt.bases(rt.resolver(fr)).items():
            series.setdefault(hueso, []).append((f, q))
    previa = bpy.data.actions.get(nombre)
    if previa is not None:
        if armadura.animation_data is not None and armadura.animation_data.action == previa:
            armadura.animation_data.action = None
        bpy.data.actions.remove(previa)
    accion = bpy.data.actions.new(nombre)
    accion.use_fake_user = True
    tira = accion.layers.new("Capa").strips.new(type='KEYFRAME')
    slot = accion.slots.new(id_type='OBJECT', name=armadura.name)
    canal = tira.channelbag(slot, ensure=True)
    for hueso, serie in series.items():
        armadura.pose.bones[hueso].rotation_mode = 'QUATERNION'
        ruta = f'pose.bones["{hueso}"].rotation_quaternion'
        for eje in range(4):
            fc = canal.fcurves.new(ruta, index=eje, group_name=hueso)
            fc.keyframe_points.add(len(serie))
            for kp, (f, q) in zip(fc.keyframe_points, serie):
                kp.co = (float(f), q[eje])
                kp.interpolation = 'LINEAR'
            fc.update()
    if asignar:
        ad = armadura.animation_data_create()
        ad.action = accion
        ad.action_slot = slot
    return accion


# ---------------------------------------------------------------------------
# Escucha UDP
# ---------------------------------------------------------------------------
class Estado:
    """Estado global de la escucha (no se guarda en el .blend)."""
    sock = None
    activo = False
    frames = 0
    clips = 0
    ultimo_error = ""
    retarget = None            # Retarget del personaje conectado (se rehace si cambia)
    accion_personaje = None    # última acción horneada en el personaje


def abrir_socket(host, puerto):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind((host, int(puerto)))
        s.setblocking(False)
    except OSError:
        s.close()
        raise
    return s


def cerrar_socket():
    if Estado.sock is not None:
        try:
            Estado.sock.close()
        except OSError:
            pass
    Estado.sock = None
    Estado.activo = False


def procesar_datagramas(escena, sock=None, empties=None):
    """Drena el socket; aplica solo el último frame; importa clips si procede.

    Devuelve la cantidad de datagramas válidos de tipo 'frame' recibidos.
    """
    sock = sock or Estado.sock
    if sock is None:
        return 0
    ultimo = None
    clips = []
    recibidos = 0
    while True:
        try:
            datos, _dir = sock.recvfrom(65535)
        except BlockingIOError:
            break
        except InterruptedError:
            continue
        except OSError:  # p. ej. ECONNRESET en Windows por ICMP: seguir
            break
        msg = parsear_mensaje(datos)
        if msg is None:
            continue
        if msg["type"] == "frame":
            ultimo = msg
            recibidos += 1
        else:
            clips.append(msg)
    if ultimo is not None:
        aplicar_frame(ultimo, empties)
        rt = retarget_para(escena)
        if rt is not None:
            rt.aplicar(ultimo)
        Estado.frames += recibidos
    for msg in clips:
        Estado.clips += 1
        if getattr(escena, "inc_auto_importar", False):
            try:
                # En vivo el clip se guarda sin asignarlo: los puntos siguen a la persona
                importar_clip(msg["path"], escena, asignar=not Estado.activo)
            except ClipInvalido as e:
                Estado.ultimo_error = str(e)
    return recibidos


# ---------------------------------------------------------------------------
# Operadores
# ---------------------------------------------------------------------------
class INCLUSION_OT_crear_puntos(Operator):
    bl_idname = "inclusion.crear_puntos"
    bl_label = "Crear puntos"
    bl_description = "Crea los empties del cuerpo (33) y de las manos (21 + 21) y el esqueleto visual"

    def execute(self, context):
        n = crear_puntos(context.scene)
        self.report({'INFO'}, f"Puntos listos: {n} empties en '{COLECCION}'.")
        return {'FINISHED'}


class INCLUSION_OT_escuchar(Operator):
    bl_idname = "inclusion.escuchar"
    bl_label = "Escuchar en vivo"
    bl_description = "Recibe por UDP los frames de la app y mueve los puntos"

    _timer = None

    def execute(self, context):
        if Estado.activo:
            return {'CANCELLED'}
        esc = context.scene
        crear_puntos(esc)
        soltar_acciones()
        try:
            Estado.sock = abrir_socket(esc.inc_host, esc.inc_puerto)
        except OSError as e:
            Estado.sock = None
            self.report({'ERROR'}, f"No se pudo abrir {esc.inc_host}:{esc.inc_puerto}: {e}")
            return {'CANCELLED'}
        Estado.activo = True
        Estado.frames = 0
        Estado.clips = 0
        Estado.ultimo_error = ""
        wm = context.window_manager
        self._timer = wm.event_timer_add(1.0 / 60.0, window=context.window)
        wm.modal_handler_add(self)
        self.report({'INFO'}, f"Escuchando en {esc.inc_host}:{esc.inc_puerto}")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not Estado.activo:
            return self._terminar(context)
        if event.type == 'TIMER':
            try:
                n = procesar_datagramas(context.scene)
            except Exception as e:  # nunca romper el modal por un mensaje raro
                Estado.ultimo_error = str(e)
                n = 0
            if n:
                for area in context.screen.areas:
                    if area.type in {'VIEW_3D', 'PROPERTIES'}:
                        area.tag_redraw()
        return {'PASS_THROUGH'}

    def cancel(self, context):
        self._terminar(context)

    def _terminar(self, context):
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        cerrar_socket()
        return {'CANCELLED'}


class INCLUSION_OT_detener(Operator):
    bl_idname = "inclusion.detener"
    bl_label = "Detener"
    bl_description = "Deja de escuchar y libera el puerto"

    def execute(self, context):
        Estado.activo = False  # el modal lo nota en el siguiente tick y cierra el socket
        if Estado.sock is not None:
            cerrar_socket()
        return {'FINISHED'}


class INCLUSION_OT_conectar_personaje(Operator):
    bl_idname = "inclusion.conectar_personaje"
    bl_label = "Conectar personaje"
    bl_description = "Busca el rig del personaje (perfil conocido) y lo conecta a los puntos"

    def execute(self, context):
        esc = context.scene
        candidatos = [esc.inc_personaje] if esc.inc_personaje else []
        if context.active_object is not None:
            candidatos.append(context.active_object)
        candidatos += [o for o in esc.objects if o.type == 'ARMATURE']
        for obj in candidatos:
            if obj is None or obj.type != 'ARMATURE':
                continue
            perfil = detectar_perfil(b.name for b in obj.data.bones)
            if perfil is not None:
                esc.inc_personaje = obj
                Estado.retarget = None
                for nombre in huesos_del_perfil(PERFILES[perfil]):
                    obj.pose.bones[nombre].rotation_mode = 'QUATERNION'
                self.report({'INFO'}, f"Personaje conectado: '{obj.name}' (rig {perfil}).")
                return {'FINISHED'}
        self.report({'ERROR'}, "No hay un rig con un perfil conocido (" + ", ".join(PERFILES) + ").")
        return {'CANCELLED'}


class INCLUSION_OT_pose_reposo(Operator):
    bl_idname = "inclusion.pose_reposo"
    bl_label = "Pose de descanso"
    bl_description = "Quita la animación y devuelve el personaje a su pose de descanso"

    def execute(self, context):
        arm = personaje(context.scene)
        if arm is None:
            return {'CANCELLED'}
        if arm.animation_data is not None:
            arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        if Estado.retarget is not None:
            Estado.retarget.ultimo.clear()
        return {'FINISHED'}


class INCLUSION_OT_importar_clip(Operator, ImportHelper):
    bl_idname = "inclusion.importar_clip"
    bl_label = "Importar clip"
    bl_description = "Importa un clip .json como animación de los puntos"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        try:
            accion, n = importar_clip(self.filepath, context.scene)
        except ClipInvalido as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        extra = f"; personaje: '{Estado.accion_personaje.name}'" if Estado.accion_personaje else ""
        self.report({'INFO'}, f"Clip importado: '{accion.name}' ({n} keyframes){extra}.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class INCLUSION_PT_panel(Panel):
    bl_label = "Avatar LSM"
    bl_idname = "INCLUSION_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "INCLUSION"

    def draw(self, context):
        esc = context.scene
        lay = self.layout

        caja = lay.box()
        caja.label(text="Puntos")
        caja.operator("inclusion.crear_puntos", icon='EMPTY_AXIS')

        caja = lay.box()
        caja.label(text="Personaje")
        caja.prop(esc, "inc_personaje", text="Rig")
        fila = caja.row(align=True)
        fila.operator("inclusion.conectar_personaje", icon='ARMATURE_DATA')
        fila.operator("inclusion.pose_reposo", icon='LOOP_BACK')
        arm = personaje(esc)
        if arm is not None:
            perfil = detectar_perfil(b.name for b in arm.data.bones)
            caja.label(text=f"Perfil: {perfil}" if perfil else "Rig sin perfil conocido",
                       icon='CHECKMARK' if perfil else 'ERROR')

        caja = lay.box()
        caja.label(text="En vivo (UDP)")
        col = caja.column(align=True)
        col.enabled = not Estado.activo
        col.prop(esc, "inc_host", text="Host")
        col.prop(esc, "inc_puerto", text="Puerto")
        caja.prop(esc, "inc_auto_importar")
        if Estado.activo:
            caja.operator("inclusion.detener", icon='PAUSE')
            caja.label(text=f"Escuchando · frames: {Estado.frames}", icon='REC')
        else:
            caja.operator("inclusion.escuchar", icon='PLAY')
            caja.label(text="Detenido", icon='PAUSE')
        if Estado.clips:
            caja.label(text=f"Clips avisados: {Estado.clips}")
        if Estado.ultimo_error:
            caja.label(text=Estado.ultimo_error[:60], icon='ERROR')

        caja = lay.box()
        caja.label(text="Clips")
        caja.prop(esc, "inc_inicio", text="Frame de inicio")
        caja.operator("inclusion.importar_clip", icon='IMPORT')


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
_CLASES = (
    INCLUSION_OT_crear_puntos,
    INCLUSION_OT_escuchar,
    INCLUSION_OT_detener,
    INCLUSION_OT_conectar_personaje,
    INCLUSION_OT_pose_reposo,
    INCLUSION_OT_importar_clip,
    INCLUSION_PT_panel,
)

_PROPS = ("inc_host", "inc_puerto", "inc_auto_importar", "inc_inicio", "inc_personaje")


def register():
    unregister()  # idempotente (útil con Run Script repetido)
    for c in _CLASES:
        bpy.utils.register_class(c)
    S = bpy.types.Scene
    S.inc_host = StringProperty(name="Host", default="127.0.0.1")
    S.inc_puerto = IntProperty(name="Puerto", default=5005, min=1, max=65535)
    S.inc_auto_importar = BoolProperty(
        name="Importar clips automáticamente", default=True,
        description="Al recibir el aviso de un clip guardado por la app, importarlo")
    S.inc_inicio = IntProperty(name="Frame de inicio", default=1, min=0)
    S.inc_personaje = PointerProperty(
        name="Personaje", type=bpy.types.Object,
        poll=lambda _self, obj: obj.type == 'ARMATURE',
        description="Rig que se mueve con la persona y recibe los clips")


def unregister():
    cerrar_socket()
    Estado.retarget = None
    for c in reversed(_CLASES):
        try:
            bpy.utils.unregister_class(c)
        except (RuntimeError, ValueError):
            pass
    for p in _PROPS:
        if hasattr(bpy.types.Scene, p):
            delattr(bpy.types.Scene, p)


if __name__ == "__main__" and bpy is not None:
    register()

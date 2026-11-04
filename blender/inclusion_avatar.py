"""INCLUSION · Avatar LSM para Blender (RF-21, RF-22).

Add-on de un solo archivo:
  * Crea un esqueleto de puntos (empties) para cuerpo (33) y manos (21 + 21).
  * Escucha por UDP los frames que envía la app y mueve los puntos en vivo.
  * Importa clips ``.json`` (formato ``inclusion-movimiento``, version 1) como
    animación de esos puntos, con una acción por palabra.

Ejes: el clip usa x = izquierda de la persona, y = arriba, z = hacia adelante.
En Blender (personaje mirando a -Y): (X, Y, Z) = (x, -z, y).

Instalación: Edit > Preferences > Add-ons > Install from Disk, o abrir el
archivo en el Text Editor y pulsar "Run Script".
"""

bl_info = {
    "name": "INCLUSION Avatar LSM",
    "author": "Proyecto INCLUSION",
    "version": (1, 0, 0),
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
    from bpy.props import BoolProperty, IntProperty, StringProperty
    from bpy.types import Operator, Panel
    from bpy_extras.io_utils import ImportHelper
    from mathutils import Matrix, Vector
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


def soltar_acciones(empties=None):
    """Quita la animación asignada a los puntos (las acciones quedan guardadas),
    para que el movimiento en vivo no lo pise un clip al cambiar de frame."""
    empties = empties if empties is not None else obtener_empties()
    for obj in empties.values():
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
    nombre = nombre_accion(palabra)
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

    if asignar:
        ultimo = frame_de_tiempo(datos.get("duration", datos["frames"][-1]["t"]), fps, inicio)
        ultimo = max(ultimo, frame_de_tiempo(datos["frames"][-1]["t"], fps, inicio))
        escena.frame_start = int(inicio)
        escena.frame_end = max(int(inicio) + 1, ultimo)
        escena.frame_set(int(inicio))
    return accion, total


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
        self.report({'INFO'}, f"Clip importado: '{accion.name}' ({n} keyframes).")
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
    INCLUSION_OT_importar_clip,
    INCLUSION_PT_panel,
)

_PROPS = ("inc_host", "inc_puerto", "inc_auto_importar", "inc_inicio")


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


def unregister():
    cerrar_socket()
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

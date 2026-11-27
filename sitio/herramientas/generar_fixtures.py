"""Casos de prueba de paridad Python ↔ JavaScript para «Pruébalo».

    python sitio/herramientas/generar_fixtures.py                      # sitio/probar/tests/fixtures/
    python sitio/herramientas/generar_fixtures.py --datos repo/app/data  # + casos con tus muestras reales

Usa los módulos reales de app/modules/ (sin modificarlos) y guarda en JSON lo que calculan:
frames crudos → segmentador → secuencias preparadas → features (30 × 260) → probabilidades del
traductor, y también world_frame, One Euro, rest_arm, clips y las reglas de progreso.py.
Las pruebas de sitio/probar/tests/*.test.mjs comparan el motor en JavaScript contra estos JSON.

- Los casos que se suben a git usan solo señas sintéticas (app/tests/synthetic.py) y un traductor
  entrenado con ellas, así no llevan datos de ninguna persona.
- Con --datos, también se generan casos con el dataset y el modelo reales en
  sitio/probar/tests/local/ (está en .gitignore: son datos derivados de quien grabó).

Los float32 se escriben con su representación más corta (como str(np.float32)): en JavaScript,
Math.fround() del número recupera exactamente el mismo float32.
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
SITIO = os.path.dirname(AQUI)
APP = os.path.abspath(os.path.join(SITIO, "..", "app"))
sys.path.insert(0, APP)
sys.path.insert(0, AQUI)

import config as C  # noqa: E402
from modules import landmarks as L  # noqa: E402
from modules import motion as M  # noqa: E402
from modules import progreso as P  # noqa: E402
from modules.landmark_detector import anatomical_order, hand_slot_hint  # noqa: E402
from modules.segmenter import SignSegmenter  # noqa: E402
from tests import synthetic as S  # noqa: E402

from exportar_modelo import exportar_pipeline  # noqa: E402

SALIDA = os.path.join(SITIO, "probar", "tests", "fixtures")
SALIDA_LOCAL = os.path.join(SITIO, "probar", "tests", "local")


# ------------------------------------------------------------------ JSON
def f32(a):
    """Arreglo float32 -> lista plana de números con la representación corta de float32."""
    a = np.asarray(a, dtype=np.float32).ravel()
    return [float(str(v)) for v in a]


def f64(a):
    return [float(v) for v in np.asarray(a, dtype=np.float64).ravel()]


def arreglo(a, tipo=f32):
    """{"forma": [...], "datos": [...]} (o None)."""
    if a is None:
        return None
    a = np.asarray(a)
    return {"forma": list(a.shape), "datos": tipo(a)}


def guardar(carpeta, nombre, datos):
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  {os.path.relpath(ruta, SITIO)}  ({os.path.getsize(ruta) / 1024:.0f} KB)")


def nuevo_segmentador():
    return SignSegmenter(C.SEQUENCE_LENGTH, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES, C.SEGMENT_MIN_FRAMES,
                         C.SEGMENT_MAX_FRAMES, C.SEGMENT_CONTEXT_FRAMES, C.RESTING_HAND_MARGIN)


# ------------------------------------------------------------ flujos sintéticos
def flujos():
    """Flujos de frames crudos que cubren los caminos del segmentador y de las features."""
    rng = np.random.RandomState(3)
    out = {}
    out["una_mano_derecha"] = S.stream(S.make_sign("arriba", 32, rng=rng))
    out["una_mano_izquierda"] = S.stream(S.make_sign("circulo", 45, hand_slot=0, center=(0.8, 0.55), scale=0.25, rng=rng))

    a = S.make_sign("derecha", 40, rng=rng)
    b = S.make_sign("arriba", 40, hand_slot=0, mirrored=True, rng=rng)
    dos = a.copy()
    dos[:, :L.HAND_SIZE] = b[:, :L.HAND_SIZE]
    dos[:, L.ARMS_START:L.ARMS_START + 3] = b[:, L.ARMS_START:L.ARMS_START + 3]
    dos[:, L.ARMS_START + 6:L.ARMS_START + 9] = b[:, L.ARMS_START + 6:L.ARMS_START + 9]
    out["dos_manos"] = S.stream(dos)

    huecos = S.make_sign("circulo", 50, rng=rng)
    huecos[12:15, L.HAND_SIZE:L.HANDS_SIZE] = 0          # hueco corto: se rellena
    huecos[30:37, L.HAND_SIZE:L.HANDS_SIZE] = 0          # hueco de 7: no se rellena (y no corta la seña)
    huecos[20:22, L.ARMS_START + 3:L.ARMS_START + 6] = 0  # se pierde un codo
    out["huecos"] = S.stream(huecos)

    sin_cuerpo = S.stream(S.make_sign("derecha", 36, rng=rng))
    sin_cuerpo[:, L.HANDS_SIZE:] = 0
    out["sin_cuerpo"] = sin_cuerpo

    # La mano izquierda se queda apoyada (muy abajo) mientras la derecha seña: no cuenta
    reposo = S.stream(S.make_sign("arriba", 34, rng=rng))
    mano = S.make_sign("arriba", 1, hand_slot=0, rng=rng)[0, :L.HAND_SIZE].reshape(L.HAND_POINTS, 3)
    mano[:, 1] += 1.1 - mano[0, 1]
    reposo[:, :L.HAND_SIZE] = mano.reshape(-1)
    out["mano_en_reposo"] = reposo

    out["muy_corta"] = S.stream(S.make_sign("arriba", 6, rng=rng))
    out["muy_larga"] = S.stream(S.make_sign("circulo", 140, rng=rng))

    # Varias señas seguidas, con distinto ritmo, hombros con algo de ruido y otra escala
    partes = []
    for et, n in (("arriba", 28), ("circulo", 55), ("derecha", 22)):
        partes.append(S.stream(S.make_sign(et, n, center=(0.95, 0.62), scale=0.33, rng=rng), pad=12))
    seguidas = np.concatenate(partes)
    seguidas[:, L.HANDS_SIZE:] += (rng.normal(0, 0.002, seguidas[:, L.HANDS_SIZE:].shape)
                                   * (seguidas[:, L.HANDS_SIZE:] != 0)).astype(np.float32)
    out["seguidas"] = seguidas.astype(np.float32)
    return out


def correr_segmentador(frames):
    seg = nuevo_segmentador()
    pasos, secuencias = [], []
    for i, f in enumerate(frames):
        s = seg.update(f)
        pasos.append([int(seg.active), seg.captured, int(seg.last_discarded), int(seg.body_visible)])
        if s is not None:
            secuencias.append({"frame": i, "secuencia": arreglo(s)})
    return pasos, secuencias


# ------------------------------------------------------------ traductor sintético
def dataset_sintetico(rng, por_sena=10):
    raw, y = [], []
    for et in ("arriba", "derecha", "circulo"):
        for k in range(por_sena):
            n = int(rng.randint(22, 60))
            center = (0.8 + rng.uniform(-0.1, 0.1), 0.6 + rng.uniform(-0.05, 0.05))
            sign = S.make_sign(et, n, center=center, scale=rng.uniform(0.24, 0.36), rng=rng, noise=0.02)
            raw.append(L.prepare_sequence(sign, C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES))
            y.append(et)
    return np.stack(raw), np.array(y)


def casos_umbral(modelo_json, X, cuantos=60):
    """Features justo en el umbral de un nodo (y el float32 vecino de cada lado): ahí se ve si
    JavaScript escala y compara exactamente igual que scikit-learn."""
    rasgos = modelo_json["rasgos"]
    pos = {r: i for i, r in enumerate(rasgos)}
    casos = []
    rng = np.random.RandomState(5)
    for k in range(cuantos):
        arbol = modelo_json["arboles"][rng.randint(len(modelo_json["arboles"]))]
        internos = [n for n, iz in enumerate(arbol["izq"]) if iz != -1]
        if not internos:
            continue
        n = internos[rng.randint(len(internos))]
        f, u = arbol["rasgo"][n], arbol["umbral"][n]
        m, s = modelo_json["media"][pos[f]], modelo_json["escala"][pos[f]]
        x0 = np.float32(m + u * s)
        b = int(rng.randint(len(X)))
        for paso in (-2, -1, 0, 1, 2):
            v = x0
            for _ in range(abs(paso)):
                v = np.nextafter(v, np.float32(np.inf if paso > 0 else -np.inf), dtype=np.float32)
            x = X[b].copy()
            x[f] = v
            casos.append((b, f, v, x))
    return casos


def fixtures_entrenamiento(carpeta, modelo, raw, y, rng):
    """El dataset con el que scikit-learn entrenó el traductor sintético y señas nuevas, más difíciles
    (más ruido, otro lugar y otro tamaño), con la exactitud que logra scikit-learn en ellas: el bosque
    de JavaScript (bosque.js), entrenado con lo mismo, tiene que lograr una exactitud parecida."""
    prueba, yp = [], []
    for et in ("arriba", "derecha", "circulo"):
        for k in range(8):
            n = int(rng.randint(20, 70))
            center = (0.8 + rng.uniform(-0.15, 0.15), 0.6 + rng.uniform(-0.08, 0.08))
            sign = S.make_sign(et, n, center=center, scale=rng.uniform(0.2, 0.4), rng=rng, noise=0.05,
                               mirrored=bool(k == 7), hand_slot=0 if k == 7 else 1)
            prueba.append(L.prepare_sequence(sign, C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES))
            yp.append(et)
    X = np.stack([L.sequence_features(s).reshape(-1) for s in prueba])
    pred = modelo.predict(X)
    guardar(carpeta, "entrenamiento.json", {
        "entrenamiento": [{"label": str(e), "seq": f32(s)} for s, e in zip(raw, y)],
        "prueba": [{"label": e, "seq": f32(s)} for s, e in zip(prueba, yp)],
        "exactitud_sklearn": float(np.mean(pred == np.array(yp))),
    })


def fixtures_traductor(carpeta, secuencias_flujos):
    from train_model import fit
    rng = np.random.RandomState(11)
    raw, y = dataset_sintetico(rng)
    modelo = fit(raw, y, np.random.RandomState(42))
    mj = exportar_pipeline(modelo, {"muestras": int(len(raw)), "personas": 1, "origen": "sintetico (pruebas)"})
    guardar(carpeta, "modelo_sintetico.json", mj)
    fixtures_entrenamiento(carpeta, modelo, raw, y, rng)

    # Señas nuevas (no vistas al entrenar), en espejo, sin cuerpo y las que cortó el segmentador
    prueba = [L.prepare_sequence(S.make_sign(et, n, rng=rng, noise=0.03), C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES)
              for et, n in (("arriba", 30), ("derecha", 41), ("circulo", 27), ("circulo", 58))]
    prueba += [L.prepare_sequence(S.make_sign("derecha", 35, hand_slot=0, mirrored=True, rng=rng),
                                  C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES)]
    sin = prueba[0].copy()
    sin[:, L.HANDS_SIZE:] = 0
    prueba.append(sin)
    prueba += secuencias_flujos
    casos = []
    for seq in prueba:
        feat = L.sequence_features(seq)
        proba = modelo.predict_proba(feat.reshape(1, -1))[0]
        casos.append({"secuencia": arreglo(seq), "features": arreglo(feat), "proba": f64(proba)})
    X = np.stack([c for c in (L.sequence_features(s).reshape(-1) for s in prueba)])
    borde = casos_umbral(mj, X)
    guardar(carpeta, "traductor.json", {
        "min_confianza": C.MIN_CONFIDENCE,
        "casos": casos,
        # Cada caso: las features del caso `base` con un solo valor cambiado
        "umbral": [{"base": b, "rasgo": int(f), "valor": float(str(v)),
                    "proba": f64(modelo.predict_proba(x.reshape(1, -1))[0])} for b, f, v, x in borde],
    })
    return modelo, mj


# ------------------------------------------------------------ funciones sueltas
def fixtures_landmarks(carpeta):
    rng = np.random.RandomState(21)
    out = {}
    out["resample"] = [{"n": n, "largo": m, "indices": L.resample(np.arange(n), m).tolist()}
                       for n in (1, 2, 9, 10, 11, 17, 29, 30, 31, 45, 59, 61, 88, 119, 120, 121) for m in (30, 7, 1)]

    def con_huecos():
        f = S.stream(S.make_sign("circulo", 30, rng=rng), pad=3)
        f[5:7, L.HAND_SIZE:L.HANDS_SIZE] = 0
        f[10:16, L.HAND_SIZE:L.HANDS_SIZE] = 0
        f[18, L.HANDS_SIZE:L.ARMS_START] = 0
        f[20:23, L.ARMS_START:L.ARMS_START + 3] = 0
        return f
    casos = []
    for f in (con_huecos(), S.make_sign("arriba", 12, rng=rng), np.zeros((4, L.RAW_FRAME_SIZE), np.float32)):
        casos.append({"frames": arreglo(f), "fill_gaps": arreglo(L.fill_gaps(f)), "trim": arreglo(L.trim(f)),
                      "body_reference_pose": arreglo(L.body_reference_pose(f)),
                      "hand_coverage": L.hand_coverage(f),
                      "missing_hands": {m: L.missing_hands(f, m, C.MIN_HAND_COVERAGE) for m in C.HANDS_MODES},
                      "prepare": arreglo(L.prepare_sequence(f, C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES)),
                      "prepare_body": arreglo(L.prepare_sequence(f, C.SEQUENCE_LENGTH, C.SEGMENT_MIN_FRAMES,
                                                                 body=S.body_pose((0.88, 0.61), 0.31)))})
    out["secuencias"] = casos

    reposo = []
    body = S.body_pose()
    for dy in (-0.3, 0.0, 0.3, 0.44, 0.45, 0.46, 0.8):
        frame = S.stream(S.make_sign("arriba", 3, rng=rng), pad=0)[1].copy()
        for slot in (0, 1):
            frame[slot * L.HAND_SIZE:(slot + 1) * L.HAND_SIZE] = S.make_sign("arriba", 1, hand_slot=slot, rng=rng)[0, slot * L.HAND_SIZE:(slot + 1) * L.HAND_SIZE]
        frame[1] = 0.6 + dy
        frame[L.HAND_SIZE + 1] = 0.6 + dy / 2
        reposo.append({"frame": f32(frame), "salida": f32(L.drop_resting_hands(frame, body, C.RESTING_HAND_MARGIN))})
    reposo.append({"frame": reposo[0]["frame"], "sin_cuerpo": True,
                   "salida": f32(L.drop_resting_hands(np.array(reposo[0]["frame"], np.float32), None, 1.5))})
    out["drop_resting_hands"] = {"body": f32(body), "casos": reposo}

    f = S.make_sign("arriba", 1, rng=rng)[0]
    f[:L.HAND_SIZE] = S.make_sign("arriba", 1, hand_slot=0, rng=rng)[0, :L.HAND_SIZE]
    out["keep_hands"] = {"frame": f32(f), **{m: f32(L.keep_hands(f, m)) for m in C.HANDS_MODES}}
    out["validez"] = [{"frame": f32(fr), "hands_present": L.hands_present(fr), "pose_valid": L.pose_valid(fr),
                       "elbows_visible": L.elbows_visible(fr)}
                      for fr in (f, np.zeros(L.RAW_FRAME_SIZE, np.float32), S.stream(S.make_sign("arriba", 2), pad=1)[0])]
    feat = L.sequence_features(S.make_sign("circulo", 30, rng=rng))
    out["mirror_features"] = {"features": arreglo(feat), "espejo": arreglo(L.mirror_features(feat))}
    out["upgrade_raw"] = {"viejo": arreglo(np.ones((2, L.OLD_RAW_FRAME_SIZE), np.float32)),
                          "nuevo": arreglo(L.upgrade_raw(np.ones((2, L.OLD_RAW_FRAME_SIZE), np.float32)))}

    slots = []
    for _ in range(300):
        nd = rng.randint(0, 3)
        dets = [(int(rng.randint(2)), float(np.float32(rng.uniform(0.5, 1))),
                 (float(np.float32(rng.uniform(0, 1.8))), float(np.float32(rng.uniform(0, 1))))) for _ in range(nd)]
        prev = [None if rng.rand() < 0.35 else (float(np.float32(rng.uniform(0, 1.8))), float(np.float32(rng.uniform(0, 1))))
                for _ in range(2)]
        if dets and rng.rand() < 0.5:                       # que a veces la mano siga cerca de donde estaba
            s = rng.randint(2)
            if prev[s] is not None:
                dets[0] = (dets[0][0], dets[0][1], (prev[s][0] + 0.05, prev[s][1] - 0.03))
        slots.append({"detecciones": dets, "previas": prev, "salida": L.assign_slots(dets, prev)})
    out["assign_slots"] = slots

    pistas = []
    for _ in range(80):
        wrist = (float(rng.uniform(0, 1.8)), float(rng.uniform(0, 1)))
        pw = [None if rng.rand() < 0.2 else (float(rng.uniform(0, 1.8)), float(rng.uniform(0, 1))) for _ in range(2)]
        if pw[0] is not None and rng.rand() < 0.5:
            pw[0] = (wrist[0] + rng.uniform(-0.12, 0.12), wrist[1] + rng.uniform(-0.05, 0.05))
        label = "Left" if rng.rand() < 0.5 else "Right"
        pistas.append({"label": label, "wrist": wrist, "pose_wrists": pw, "salida": hand_slot_hint(label, wrist, pw)})
    out["hand_slot_hint"] = pistas
    out["anatomical_order"] = [{"izq": a, "der": b, "salida": anatomical_order(a, b)} for a, b in ((0.3, 0.7), (0.7, 0.3), (0.5, 0.5))]
    guardar(carpeta, "landmarks.json", out)


def mundo_json(w):
    return {k: (None if w[k] is None else f32(w[k])) for k in ("pose", "vis", "left", "right")}


def fixtures_movimiento(carpeta):
    rng = np.random.RandomState(31)
    out = {}

    def pose_rand():
        return rng.normal(0, 0.3, (33, 3)).astype(np.float32)

    casos = []
    for k in range(6):
        pose = None if k == 5 else pose_rand()
        vis = None if k == 4 else rng.uniform(0, 1, 33).astype(np.float32)
        hands = [None if (k % 3 == 1) else rng.normal(0, 0.05, (21, 3)).astype(np.float32),
                 None if (k % 3 == 2) else rng.normal(0, 0.05, (21, 3)).astype(np.float32)]
        w = M.world_frame(pose, vis, hands)
        casos.append({"pose": None if pose is None else f32(pose), "vis": None if vis is None else f32(vis),
                      "manos": [None if h is None else f32(h) for h in hands], "salida": mundo_json(w)})
    out["world_frame"] = casos

    w = M.world_frame(pose_rand(), rng.uniform(0, 1, 33).astype(np.float32),
                      [rng.normal(0, 0.05, (21, 3)).astype(np.float32)] * 2)
    out["rest_arm"] = {"mundo": mundo_json(w), "left": mundo_json(M.rest_arm(w, "left")),
                       "right": mundo_json(M.rest_arm(w, "right"))}
    out["resting_side"] = {m: M.resting_side(m) for m in C.HANDS_MODES}

    # One Euro y LiveSmoother: una caminata al azar a ~30 fps, con una mano que desaparece
    filtro, suav = M.OneEuroFilter(), M.LiveSmoother()
    x = rng.normal(0, 0.2, (33, 3)).astype(np.float32)
    t = 10.0
    pasos = []
    for i in range(60):
        x = (x + rng.normal(0, 0.01 if i < 30 else 0.08, x.shape)).astype(np.float32)
        t += float(rng.uniform(0.025, 0.045)) if i != 40 else 0.0     # un t repetido reinicia el filtro
        mundo = {"pose": x, "vis": np.ones(33, np.float32), "left": None if 20 <= i < 25 else x[:21] * 0.5,
                 "right": x[:21] * 0.25}
        pasos.append({"t": t, "x": f32(x), "filtro": f32(filtro(x, t)), "mundo": mundo_json(mundo),
                      "suave": mundo_json(suav(mundo, t))})
    out["one_euro"] = pasos

    # Clip: grabar, rellenar huecos, recortar
    frames = []
    t = 3.0
    for i in range(25):
        t += 1 / 30
        pose = None if i in (7, 8) else pose_rand()
        f = {"pose": pose, "vis": None if pose is None else np.ones(33, np.float32),
             "left": None if i in (3, 4, 5, 15, 16, 17, 18, 19, 20) else rng.normal(0, 0.1, (21, 3)).astype(np.float32),
             "right": rng.normal(0, 0.1, (21, 3)).astype(np.float32)}
        frames.append((t, f))
    clip = M.make_clip(frames, "hola", "demo", "derecha")
    clip.pop("created")
    out["clip"] = {"frames": [{"t": t, "mundo": mundo_json(f)} for t, f in frames], "salida": clip,
                   "recortes": [{"inicio": a, "fin": b, "salida": M.trim_clip(clip, a, b)}
                                for a, b in ((0.1, 0.5), (0.0, clip["duration"]), (0.2333, 0.4))]}
    guardar(carpeta, "movimiento.json", out)


def fixtures_progreso(carpeta):
    categorias = {"saludos": ["hola", "adios", "buenos dias"], "cortesia": ["gracias"], "familia": ["mama"],
                  "emociones": ["feliz"]}
    hoy = [date(2026, 11, 1)]
    p = P.Progreso(os.path.join(carpeta, "_no_existe_.json"), hoy=lambda: hoy[0])
    pasos = []
    guion = [("intento", "Hola", True, 0.95), ("intento", "hola", False, 0.4), ("dia", 1), ("intento", "Adiós", True, 0.8),
             ("evaluar", ["hola", "adios", "c"], 0, False), ("dia", 1), ("intento", "c", True, 0.61),
             ("oracion",), ("evaluar", ["hola", "adios", "c"], 1, True), ("dia", 2), ("intento", "gracias", True, 0.75),
             ("intento", "¡Mamá!", True, 0.9), ("evaluar", ["hola", "adios", "c", "gracias", "mama"], 1, True),
             ("dia", 1), ("intento", "feliz", True, 0.89)]
    for i in range(8):
        guion += [("dia", 1), ("intento", f"palabra {i}", True, 0.5 + i / 20)]
    guion += [("evaluar", ["hola"], 2, True), ("dia", 3)]
    for paso in guion:
        r = None
        if paso[0] == "intento":
            r = p.registrar_intento(paso[1], paso[2], paso[3])
        elif paso[0] == "dia":
            hoy[0] += timedelta(days=paso[1])
        elif paso[0] == "oracion":
            p.registrar_oracion()
        elif paso[0] == "evaluar":
            r = p.evaluar(categorias, paso[1], paso[2], paso[3])
        pasos.append({"paso": list(paso), "hoy": hoy[0].isoformat(), "resultado": r, "resumen": json.loads(json.dumps(p.resumen())),
                      "datos": json.loads(json.dumps(p.datos))})
    guardar(carpeta, "progreso.json", {
        "categorias": categorias, "inicio": "2026-11-01", "pasos": pasos,
        "estrellas": [{"c": c, "e": P.estrellas_por_confianza(c)} for c in (0.0, 0.6, 0.749, 0.75, 0.8999, 0.9, 1.0)],
        "normalizar": {t: P.normalizar(t) for t in ("¡Adiós!", "Buenos  Días", "MAMÁ", "por qué?", "niño_1", "  ")},
        "insignias": P.INSIGNIAS,
    })


# ------------------------------------------------------------ datos reales (solo local)
def fixtures_locales(datos):
    import joblib
    from train_model import load_dataset
    print("Casos con datos reales (no se suben a git):")
    raw, y, _ = load_dataset(os.path.join(datos, "dataset_v2.csv"))
    bundle = joblib.load(os.path.join(datos, "model.pkl"))
    modelo = bundle["pipeline"]
    mj = exportar_pipeline(modelo, {"muestras": int(bundle.get("samples", 0)), "personas": len(bundle.get("persons", [])),
                                    "origen": "local"})
    guardar(SALIDA_LOCAL, "modelo_real.json", mj)
    casos = []
    for seq, etiqueta in zip(raw, y):
        # La muestra guardada como flujo: reposo antes y después, por el segmentador real
        cuerpo = seq[0, L.HANDS_SIZE:]
        reposo = np.zeros((20, L.RAW_FRAME_SIZE), np.float32)
        reposo[:, L.HANDS_SIZE:] = cuerpo
        flujo = np.concatenate([reposo, seq, reposo])
        _, cortes = correr_segmentador(flujo)
        feat = L.sequence_features(seq)
        casos.append({"etiqueta": str(etiqueta), "secuencia": arreglo(seq), "features": arreglo(feat),
                      "proba": f64(modelo.predict_proba(feat.reshape(1, -1))[0]),
                      "flujo": arreglo(flujo), "cortes": cortes})
    guardar(SALIDA_LOCAL, "muestras_reales.json", {"casos": casos})


# ------------------------------------------------------------ la app completa
def fixtures_app(carpeta, modelo):
    """Un guion de la app entera (InclusionApp real, con cámara, voz y micrófono simulados):
    señas por la cámara, acciones de la interfaz (ACCIONES de servidor_web.py) y rutas /api/...
    Después de cada paso se guarda el estado: motor.js tiene que llegar al mismo."""
    import tempfile
    from datetime import date

    import joblib
    import inclusion_app as IA
    from modules.data_collector import DataCollector
    from modules.gesture_logic import GestureLogic
    from modules.motion import ClipStore, frame_to_json, world_frame
    from servidor_web import ACCIONES

    IA.beep_start = IA.beep_stop = IA.beep_error = lambda: None       # sin pitidos
    tmp = tempfile.mkdtemp(prefix="kabtaan_fixture_")
    pkl = os.path.join(tmp, "model.pkl")
    joblib.dump({"pipeline": modelo, "feature_version": C.FEATURE_VERSION, "sequence_length": C.SEQUENCE_LENGTH}, pkl)

    class Detector:
        def __init__(self):
            self.raw, self.world = None, None

        def process(self, frame):
            return frame, self.raw

    class Voz:
        def __init__(self):
            self.enabled, self.speaking, self.last_error, self.dichas = True, False, "", []

        def speak(self, texto):
            if self.enabled and texto:
                self.dichas.append(texto)

        def toggle(self):
            self.enabled = not self.enabled
            return self.enabled

    class Dictado:
        def __init__(self):
            self.is_recording, self.last_error, self.results = False, "", []

        def start_recording(self):
            self.is_recording = True

        def stop_recording(self):
            self.is_recording = False
            self.results.append("¿en qué le puedo ayudar?")

        def get_result(self):
            return self.results.pop(0) if self.results else None

    class Enviador:
        def send_frame(self, *a):
            pass

        def send_clip(self, *a):
            pass

        def close(self):
            pass

    reloj = [100.0]
    det, voz = Detector(), Voz()
    app = IA.InclusionApp(det, voz, Dictado(),
                          collector=DataCollector(os.path.join(tmp, "dataset.csv"), os.path.join(tmp, "respaldos"), 50,
                                                  C.SEQUENCE_LENGTH),
                          logic=GestureLogic(pkl, C.FEATURE_VERSION, C.SEQUENCE_LENGTH, C.MIN_CONFIDENCE),
                          clips=ClipStore(os.path.join(tmp, "avatar")), sender=Enviador(),
                          coherence=lambda palabras, enabled=True: " ".join(palabras),
                          clock=lambda: reloj[0], background=False, review_takes=True)
    app.progreso.hoy = lambda: date(2026, 11, 10)
    frame_vacio = np.zeros((4, 4, 3), np.uint8)
    rng = np.random.RandomState(9)

    def mundo_de(raw, k):
        pose = (rng.normal(0, 0.2, (33, 3)) + 0.001 * k).astype(np.float32)
        manos = [rng.normal(0, 0.05, (21, 3)).astype(np.float32) if np.any(raw[s * 63:(s + 1) * 63] != 0) else None
                 for s in (0, 1)]
        return world_frame(pose, np.ones(33, np.float32), manos)

    def sena(et, n, **kw):
        return S.stream(S.make_sign(et, n, rng=rng, **kw), pad=15)

    def reposo(n):
        return S.stream(S.make_sign("arriba", 1, rng=rng), pad=n)[:n]

    dos = S.make_sign("derecha", 34, rng=rng)
    dos[:, :63] = S.make_sign("arriba", 34, hand_slot=0, mirrored=True, rng=rng)[:, :63]
    solo_izq = S.make_sign("circulo", 34, hand_slot=0, rng=rng)

    guion = [
        ("frames", sena("arriba", 32)), ("frames", sena("circulo", 40)), ("frames", reposo(90)),
        ("accion", "texto_interlocutor", {"texto": "Hola, ¿cómo estás?"}), ("accion", "escuchar", {}),
        ("accion", "escuchar", {}), ("frames", reposo(2)), ("accion", "voz", {}), ("accion", "voz", {}),
        ("accion", "modo_deteccion", {"practica": True}), ("frames", sena("circulo", 38)), ("frames", reposo(90)),
        ("accion", "practica", {"palabra": "circulo", "acierto": True, "confianza": 0.95}),
        ("accion", "practica", {"palabra": "Arriba", "acierto": False, "confianza": 0.3}),
        ("accion", "practica", {"palabra": "arriba", "acierto": True, "confianza": 0.8}),
        ("obtener", "/api/progreso"), ("obtener", "/api/diccionario"),
        ("accion", "entrenar_palabra", {"palabra": "  Hola ", "persona": "Ana"}), ("accion", "grabar", {}),
        ("frames", sena("arriba", 30)), ("frames", S.stream(dos, pad=15)),
        ("frames", S.stream(S.make_sign("arriba", 6, rng=rng), pad=15)),
        ("accion", "manos", {"modo": "derecha"}), ("frames", S.stream(dos, pad=15)),
        ("accion", "manos", {"modo": "izquierda"}), ("frames", S.stream(solo_izq, pad=15)),
        ("accion", "deshacer", {}), ("obtener", "/api/dataset"),
        ("accion", "entrenar_palabra", {"palabra": "", "persona": ""}), ("accion", "manos", {"modo": "tres"}),
        ("accion", "avatar_palabra", {"palabra": "Hola"}), ("frames", reposo(20)), ("accion", "grabar", {}),
        ("frames", sena("arriba", 30)), ("accion", "manos", {"modo": "dos"}), ("accion", "grabar", {}),
        ("frames", sena("arriba", 36)), ("obtener", "/api/toma"), ("accion", "grabar", {}),
        ("accion", "guardar_toma", {"inicio": 0.2, "fin": 1.4}), ("obtener", "/api/clips"),
        ("obtener", "/api/clip/hola"),
        ("accion", "grabar", {}), ("frames", sena("derecha", 30)), ("accion", "descartar_toma", {}),
        ("accion", "grabar", {}), ("frames", sena("circulo", 30)), ("obtener", "/api/toma"),
        ("accion", "guardar_toma", {"inicio": 0.3, "fin": 1.5}), ("obtener", "/api/clip/hola"),
        ("accion", "deshacer", {}), ("obtener", "/api/clip/hola"), ("accion", "avatar_palabra", {"palabra": ""}),
        ("frames", sena("arriba", 20)), ("accion", "borrar_clip", {"palabra": "hola"}), ("obtener", "/api/clips"),
        ("accion", "borrar_sena", {"palabra": "hola"}), ("accion", "modo_deteccion", {}),
        ("obtener", "/api/diccionario"), ("obtener", "/api/progreso"),
    ]

    def obtener(ruta):
        if ruta == "/api/clips":
            return {"clips": app.clips.words()}
        if ruta.startswith("/api/clip/"):
            palabra = ruta[len("/api/clip/"):]
            return app.clips.load(palabra) if palabra in app.clips.words() else {"error": 404}
        if ruta == "/api/toma":
            return app.pending_take if app.pending_take is not None else {"error": 404}
        if ruta == "/api/diccionario":
            return {"palabras": app.vocabulary()}
        if ruta == "/api/progreso":
            return app.progress_summary()
        if ruta == "/api/dataset":
            senas, personas = app.collector.stats()
            return {"senas": senas, "personas": personas}
        return None

    def sin_fecha(x):
        if isinstance(x, dict):
            return {k: sin_fecha(v) for k, v in x.items() if k != "created"}
        return x

    pasos, k = [], 0
    for paso in guion:
        tipo, rec = paso[0], {"tipo": paso[0]}
        if tipo == "frames":
            frames = paso[1].astype(np.float32)
            mundos = []
            for raw in frames:
                k += 1
                reloj[0] += 1 / 30
                det.raw = raw
                det.world = mundo_de(raw, k)
                mundos.append({p: (None if det.world[p] is None else f32(det.world[p]))
                               for p in ("pose", "vis", "left", "right")})
                app.process_frame(frame_vacio, render=False)
            rec.update({"frames": arreglo(frames), "mundos": mundos})
        elif tipo == "accion":
            rec.update({"nombre": paso[1], "datos": paso[2]})
            try:
                r = ACCIONES[paso[1]](app, paso[2])
                rec["resultado"] = json.loads(json.dumps(sin_fecha(r), ensure_ascii=False, default=str))
                rec["ok"] = True
            except ValueError as e:
                rec["ok"], rec["error"] = False, str(e)
        else:
            r = obtener(paso[1])
            rec.update({"ruta": paso[1], "resultado": json.loads(json.dumps(sin_fecha(r), ensure_ascii=False))})
            if paso[1] == "/api/dataset":         # lo que guardó el CSV (5 decimales), muestra por muestra
                rec["muestras"] = [{"label": f[0], "person": f[1], "valores": [float(v) for v in f[2:]]}
                                   for f in app.collector._read_rows()[1]]
        estado = app.state()
        estado.pop("aviso")
        estado.pop("accion")       # textos: la web los adapta (sin teclas ni envío por UDP)
        rec["estado"] = estado
        rec["mundo"] = None if app.live_world is None else frame_to_json(app.live_world, 0.0)
        rec["voz"] = list(voz.dichas)
        pasos.append(rec)
    guardar(carpeta, "app.json", {"reloj_inicio": 100.0, "hoy": "2026-11-10", "pasos": pasos})


def main():
    p = argparse.ArgumentParser(description="Genera los casos de paridad Python ↔ JavaScript.")
    p.add_argument("--datos", help="carpeta con dataset_v2.csv y model.pkl reales (casos locales, fuera de git)")
    a = p.parse_args()
    print("Casos sintéticos:")
    secs, segs = [], {}
    for nombre, frames in flujos().items():
        pasos, cortes = correr_segmentador(frames)
        segs[nombre] = {"frames": arreglo(frames), "pasos": pasos, "cortes": cortes}
        secs += [np.array(c["secuencia"]["datos"], np.float32).reshape(c["secuencia"]["forma"]) for c in cortes]
    guardar(SALIDA, "segmentador.json", {"config": {
        "length": C.SEQUENCE_LENGTH, "start": C.SEGMENT_START_FRAMES, "end": C.SEGMENT_END_FRAMES,
        "min": C.SEGMENT_MIN_FRAMES, "max": C.SEGMENT_MAX_FRAMES, "contexto": C.SEGMENT_CONTEXT_FRAMES,
        "margen": C.RESTING_HAND_MARGIN}, "flujos": segs})
    modelo, _ = fixtures_traductor(SALIDA, secs)
    fixtures_app(SALIDA, modelo)
    fixtures_landmarks(SALIDA)
    fixtures_movimiento(SALIDA)
    fixtures_progreso(SALIDA)
    if a.datos:
        fixtures_locales(os.path.abspath(a.datos))


if __name__ == "__main__":
    main()

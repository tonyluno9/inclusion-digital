"""Prueba de punta a punta: el mismo video por la app de Python y por «Pruébalo», y se comparan.

    python sitio/herramientas/prueba_video.py VIDEO.mp4 [--modelo app/data/model.pkl] [--max 300]
                                             [--delegado cpu|gpu] [--camara-falsa]

1. Extrae los cuadros del video a PNG (sin pérdida), para que Python y el navegador vean
   exactamente los mismos píxeles.
2. Python: cada cuadro pasa por lo mismo que en la app (cv2.flip, LandmarkDetector.process,
   SignSegmenter y GestureLogic con el modelo dado).
3. Navegador (Chromium con Playwright): cada cuadro pasa por camara.js (espejo, MediaPipe para
   web, detector.js) y por el mismo segmentador y traductor en JavaScript.
4. Compara cuadro por cuadro los puntos (manos, lado de cada mano y cuerpo), dónde se corta cada
   seña y qué seña reconoce cada uno.
5. Con --camara-falsa, además abre la página con una cámara falsa que reproduce el video
   (--use-fake-device-for-media-stream) y revisa que el camino real de la cámara funcione.

Los cuadros y resultados quedan en sitio/probar/tests/local/video/ (fuera de git: puede ser tu video).
Ningún dato sale de tu computadora.
"""
import argparse
import contextlib
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
SITIO = AQUI.parent
APP = SITIO.parent / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(AQUI))

import config as C  # noqa: E402

SALIDA = SITIO / "probar" / "tests" / "local" / "video"
HAND = 63
HANDS = 126


def extraer_cuadros(video, maximo):
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    SALIDA.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-frames:v", str(maximo),
                    str(SALIDA / "cuadro_%04d.png")], check=True)
    return sorted(SALIDA.glob("cuadro_*.png"))


def ts_de(i, fps=30):
    return int(round(i * 1000 / fps)) + 1


# ------------------------------------------------------------------ Python
def correr_python(cuadros, modelo_pkl):
    import cv2
    from modules.gesture_logic import GestureLogic
    from modules.landmark_detector import LandmarkDetector
    from modules.segmenter import SignSegmenter
    detector = LandmarkDetector(C.MODELS_DIR, pose_every=C.POSE_EVERY_N_FRAMES, pose_model=C.POSE_MODEL)
    contador = {"i": 0}
    detector._timestamp = lambda: ts_de(contador["i"])          # mismos tiempos que en el navegador
    raws, mundos = [], []
    t0 = time.perf_counter()
    for i, ruta in enumerate(cuadros):
        contador["i"] = i
        frame = cv2.flip(cv2.imread(str(ruta)), 1)               # inclusion_app.process_frame
        _, raw = detector.process(frame)
        raws.append(raw)
        mundos.append({k: (None if detector.world[k] is None else np.asarray(detector.world[k], np.float32).tolist())
                       for k in ("pose", "left", "right")})
    ms = 1000 * (time.perf_counter() - t0) / max(1, len(cuadros))
    detector.close()
    logic = GestureLogic(str(modelo_pkl), C.FEATURE_VERSION, C.SEQUENCE_LENGTH, C.MIN_CONFIDENCE) if modelo_pkl else None
    return np.stack(raws), mundos, segmentar_python(raws, logic), ms


def segmentar_python(raws, logic):
    from modules.segmenter import SignSegmenter
    seg = SignSegmenter(C.SEQUENCE_LENGTH, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES, C.SEGMENT_MIN_FRAMES,
                        C.SEGMENT_MAX_FRAMES, C.SEGMENT_CONTEXT_FRAMES, C.RESTING_HAND_MARGIN)
    cortes = []
    for i, raw in enumerate(raws):
        s = seg.update(raw)
        if s is not None:
            pred, conf = logic.predict(s) if logic and logic.model is not None else ("", 0.0)
            cortes.append({"frame": i, "sena": pred, "confianza": round(float(conf), 4)})
    return cortes


# --------------------------------------------------------------- navegador
@contextlib.contextmanager
def servidor():
    from servidor_local import Manejador
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Manejador, directory=str(SITIO)))
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


SCRIPT_WEB = """
async ({ urls, modelo, fps }) => {
  const { camara } = window.inclusion;
  const L = await import('./js/motor/landmarks.js');
  const { SignSegmenter } = await import('./js/motor/segmentador.js');
  const { Traductor } = await import('./js/motor/traductor.js');
  await camara.cargar();
  const cargar = (u) => new Promise((ok, mal) => { const i = new Image(); i.onload = () => ok(i); i.onerror = mal; i.src = u; });
  const raws = [];
  const mundos = [];
  let ms = 0;
  for (let i = 0; i < urls.length; i += 1) {
    const img = await cargar(urls[i]);
    const t0 = performance.now();
    const r = camara.procesarFuente(img, img.naturalWidth, img.naturalHeight, Math.round(i * 1000 / fps) + 1);
    ms += performance.now() - t0;
    raws.push(Array.from(r.raw));
    mundos.push({ pose: r.world.pose, left: r.world.left, right: r.world.right });
  }
  const t = modelo ? new Traductor(modelo) : null;
  const seg = new SignSegmenter(30, 3, 8, 10, 120, 15, 1.5);
  const cortes = [];
  raws.forEach((raw, i) => {
    const s = seg.update(Float32Array.from(raw));
    if (s) {
      const [sena, conf] = t ? t.predict(s) : ['', 0];
      cortes.push({ frame: i, sena, confianza: Math.round(conf * 1e4) / 1e4 });
    }
  });
  return { raws, mundos, cortes, ms: ms / urls.length, delegado: camara.delegado };
}
"""


def correr_web(pw, base, cuadros, modelo_json, delegado):
    navegador = pw.chromium.launch(args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pagina = navegador.new_page(viewport={"width": 1366, "height": 800})
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(f"{base}/probar/?delegado={delegado}")
    pagina.wait_for_function("window.inclusion && window.inclusion.camara", timeout=60000)
    urls = [f"tests/local/video/{c.name}" for c in cuadros]
    r = pagina.evaluate(SCRIPT_WEB, {"urls": urls, "modelo": modelo_json, "fps": 30})
    navegador.close()
    if errores:
        print("Errores en la página:", *errores, sep="\n  ")
    return np.array(r["raws"], dtype=np.float32), r["mundos"], r["cortes"], r["ms"], r["delegado"]


def camara_falsa(pw, base, video, segundos=12):
    """El camino real: getUserMedia con una cámara falsa que reproduce el video (en bucle)."""
    y4m = Path(tempfile.gettempdir()) / "kabtaan_prueba.y4m"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-t", "10", "-pix_fmt", "yuv420p", str(y4m)], check=True)
    navegador = pw.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
                                         f"--use-file-for-fake-video-capture={y4m}", "--enable-unsafe-swiftshader"])
    contexto = navegador.new_context(viewport={"width": 1366, "height": 800}, permissions=["camera"])
    contexto.add_init_script("try { localStorage.setItem('kabtaan.tutorialVisto', '1'); } catch (e) {}")
    pagina = contexto.new_page()
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(f"{base}/probar/")
    pagina.wait_for_function("window.inclusion && window.inclusion.pruebalo", timeout=60000)
    pagina.evaluate("""() => {
      const i = window.inclusion; i.escenas.encima = () => false;
      document.querySelector('#tutorial').classList.add('oculto');
      document.querySelector('[data-pagina=traducir]').click();
      i.cuadros = { total: 0, manos: 0, cuerpo: 0, palabras: [] };
      const antes = i.camara.alFrame;
      i.camara.alFrame = (r) => {
        const c = i.cuadros; c.total += 1;
        if (r.raw.slice(0, 126).some((v) => v !== 0)) c.manos += 1;
        if (r.raw[129] !== 0 && r.raw[132] !== 0) c.cuerpo += 1;
        antes(r);
      };
      i.motor.escuchar(({ estado }) => { if (estado.seq_palabra && i.cuadros.ultima !== estado.seq_palabra) { i.cuadros.ultima = estado.seq_palabra; i.cuadros.palabras.push(estado.prediccion); } });
    }""")
    pagina.click("#pagina-traducir [data-encender-camara]")
    pagina.wait_for_function("window.inclusion.camara.activa", timeout=90000)
    time.sleep(segundos)
    datos = pagina.evaluate("() => ({ ...window.inclusion.cuadros, fps: window.inclusion.ui.estado.fps, chip: document.querySelector('#chip-camara').textContent, delegado: window.inclusion.camara.delegado })")
    captura = SALIDA / "camara_falsa.png"
    pagina.screenshot(path=str(captura))
    navegador.close()
    y4m.unlink(missing_ok=True)
    return datos, errores, captura


# -------------------------------------------------------------- comparar
def comparar(py, web):
    n = min(len(py), len(web))
    py, web = py[:n], web[:n]
    rep = {"cuadros": n}
    for nombre, ini, fin in (("mano izquierda", 0, HAND), ("mano derecha", HAND, HANDS), ("cuerpo", HANDS, 147)):
        a = np.any(py[:, ini:fin] != 0, axis=1)
        b = np.any(web[:, ini:fin] != 0, axis=1)
        ambos = a & b
        d = np.abs(py[ambos, ini:fin] - web[ambos, ini:fin]) if ambos.any() else np.zeros((0, 1))
        rep[nombre] = {"python": int(a.sum()), "web": int(b.sum()), "coinciden": int((a == b).sum()),
                       "dif_media": float(d.mean()) if d.size else 0.0, "dif_max": float(d.max()) if d.size else 0.0}
    return rep


def comparar_mundos(py, web):
    """Movimiento 3D del avatar (metros): en cuántos cuadros hay cada parte y cuánto difieren."""
    rep = {}
    for parte in ("pose", "left", "right"):
        a = [m[parte] is not None for m in py]
        b = [m[parte] is not None for m in web]
        dif = [np.abs(np.array(p[parte]) - np.array(w[parte])) for p, w in zip(py, web)
               if p[parte] is not None and w[parte] is not None]
        d = np.concatenate([x.ravel() for x in dif]) if dif else np.zeros(1)
        rep[parte] = {"python": sum(a), "web": sum(b), "coinciden": sum(x == y for x, y in zip(a, b)),
                      "dif_media_m": float(d.mean()), "dif_max_m": float(d.max())}
    # Lo que mueve al avatar: hombros, codos, muñecas y dedos del cuerpo (puntos 11 a 22)
    brazos = [np.abs(np.array(p["pose"])[11:23] - np.array(w["pose"])[11:23]) for p, w in zip(py, web)
              if p["pose"] is not None and w["pose"] is not None]
    if brazos:
        b = np.stack(brazos)
        rep["brazos"] = {"dif_media_m": float(b.mean()), "dif_max_m": float(b.max()),
                         "dif_max_por_eje_m": [float(v) for v in b.max(axis=(0, 1))]}
    return rep


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("video")
    p.add_argument("--modelo", help="model.pkl de la app (por defecto, ninguno: solo se comparan puntos y cortes)")
    p.add_argument("--max", type=int, default=300, help="cuadros a comparar (300 = 10 s a 30 fps)")
    p.add_argument("--delegado", default="cpu", choices=["cpu", "gpu"])
    p.add_argument("--camara-falsa", action="store_true")
    a = p.parse_args()
    from playwright.sync_api import sync_playwright
    from exportar_modelo import exportar_pipeline
    import joblib

    cuadros = extraer_cuadros(Path(a.video), a.max)
    print(f"{len(cuadros)} cuadros extraídos de {a.video}")
    modelo_json = None
    if a.modelo:
        b = joblib.load(a.modelo)
        modelo_json = exportar_pipeline(b["pipeline"], {"origen": "prueba"})
    py_raw, py_mundos, py_cortes, py_ms = correr_python(cuadros, a.modelo)
    print(f"Python: {py_ms:.0f} ms por cuadro; señas: {[(c['frame'], c['sena'], c['confianza']) for c in py_cortes]}")
    with servidor() as base, sync_playwright() as pw:
        web_raw, web_mundos, web_cortes, web_ms, deleg = correr_web(pw, base, cuadros, modelo_json, a.delegado)
        print(f"Web ({deleg}): {web_ms:.0f} ms por cuadro; señas: {[(c['frame'], c['sena'], c['confianza']) for c in web_cortes]}")
        rep = comparar(py_raw, web_raw)
        rep["avatar_3d"] = comparar_mundos(py_mundos, web_mundos)
        rep.update({"python": {"cortes": py_cortes, "ms_cuadro": py_ms}, "web": {"cortes": web_cortes, "ms_cuadro": web_ms, "delegado": deleg}})
        print(json.dumps({k: v for k, v in rep.items() if k not in ("python", "web")}, ensure_ascii=False, indent=1))
        mismas = [c["sena"] for c in py_cortes] == [c["sena"] for c in web_cortes]
        print("Señas reconocidas:", "IGUALES" if mismas else "DISTINTAS")
        if a.camara_falsa:
            datos, errores, captura = camara_falsa(pw, base, Path(a.video))
            rep["camara_falsa"] = datos
            print(f"Cámara falsa: {json.dumps(datos, ensure_ascii=False)}  (captura: {captura})")
            if errores:
                print("Errores en la página:", *errores, sep="\n  ")
    with open(SALIDA / "reporte.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    np.save(SALIDA / "raw_python.npy", py_raw)
    np.save(SALIDA / "raw_web.npy", web_raw)
    return 0 if mismas else 1


if __name__ == "__main__":
    sys.exit(main())

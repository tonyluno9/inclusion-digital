"""Genera las imagenes de diseno/prompts/imagenes.json con WaveSpeedAI (Nano Banana 2.1, 1K).

Uso (desde la raiz del repo):
    $env:WAVESPEED_API_KEY = "..."     # nunca se guarda en ningun archivo
    python diseno/herramientas/generar_imagenes.py                                   # imagenes.json
    python diseno/herramientas/generar_imagenes.py diseno/prompts/logo_kab_taan.json # otro lote

Cada lote guarda sus imagenes y su manifest.json en la carpeta "salida" de su JSON.
Si el JSON trae "modo": "edicion" y "referencia" (una imagen del repo), se usa el modelo de
edicion con esa imagen como referencia (MODELO_EDICION; revisar en la documentacion de
WaveSpeedAI el identificador y el campo de imagenes antes de correrlo).

Reglas:
- Una sola generacion por imagen. Si diseno/generadas/<archivo> ya existe, se salta.
- Si una tarea ya fue enviada (su id esta en el manifiesto) pero no hay archivo, se vuelve a
  consultar ese mismo id en lugar de enviar una tarea nueva.
- Si el envio falla, se anota el error y NO se reenvia.
- La clave nunca se escribe en el manifiesto ni en la salida.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
JSON_PROMPTS = RAIZ / "diseno" / "prompts" / "imagenes.json"
SALIDA = RAIZ / "diseno" / "generadas"
MANIFIESTO = SALIDA / "manifest.json"

MODELO = "google/nano-banana-2.1/text-to-image"
MODELO_EDICION = "google/nano-banana-2.1/edit"   # imagen(es) de referencia + instrucciones
URL_BASE = "https://api.wavespeed.ai/api/v3/"
URL_ENVIO = f"{URL_BASE}{MODELO}"
URL_RESULTADO = "https://api.wavespeed.ai/api/v3/predictions/{id}/result"
RESOLUCION = "1k"  # maximo permitido por la persona; nunca 2k ni 4k
COSTO_DOCUMENTADO_USD = 0.04  # precio publicado por imagen a 1k
COSTO_POR_REFERENCIA_USD = 0.002  # edicion: se suma por cada imagen de referencia
ACEPTA_NEGATIVO = False  # el modelo no documenta prompt negativo

INTERVALO_S = 3
LIMITE_S = 300


def cargar_manifiesto() -> dict:
    if MANIFIESTO.exists():
        return json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    return {"modelo": MODELO, "resolucion": RESOLUCION, "imagenes": {}}


def guardar_manifiesto(m: dict) -> None:
    MANIFIESTO.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def encabezados(clave: str) -> dict:
    return {"Authorization": f"Bearer {clave}", "Content-Type": "application/json"}


def subir_referencia(clave: str, ruta: Path) -> str:
    """Sube la imagen con la carga directa de WaveSpeedAI y devuelve su download_url.

    El modo de edicion pide URLs en "images" (no base64). Documentacion:
    https://wavespeed.ai/docs/docs-common-api/media-upload  (los archivos duran 7 dias).
    La clave solo va a la API de WaveSpeedAI, nunca a la URL firmada de subida.
    """
    r = requests.post(URL_BASE + "media/uploads", headers=encabezados(clave),
                      json={"filename": ruta.name, "size": ruta.stat().st_size,
                            "content_type": "image/png"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"subida (ticket) HTTP {r.status_code}: {r.text[:300]}")
    ticket = r.json().get("data") or {}
    subida = ticket.get("upload") or {}
    if not subida.get("url") or not ticket.get("download_url"):
        raise RuntimeError(f"subida sin url: {r.text[:300]}")
    with ruta.open("rb") as f:
        p = requests.put(subida["url"], headers=subida.get("headers") or {}, data=f, timeout=300)
    if p.status_code not in (200, 201):
        raise RuntimeError(f"subida (PUT) HTTP {p.status_code}: {p.text[:300]}")
    return ticket["download_url"]


def enviar(clave: str, prompt: str, aspecto: str, referencia_url: str | None = None) -> str:
    cuerpo = {
        "prompt": prompt,
        "aspect_ratio": aspecto,
        "resolution": RESOLUCION,
        "output_format": "png",
        "enable_web_search": False,
        "enable_image_search": False,
    }
    url = URL_ENVIO
    if referencia_url is not None:
        url = URL_BASE + MODELO_EDICION
        cuerpo["images"] = [referencia_url]
    r = requests.post(url, headers=encabezados(clave), json=cuerpo, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"envio HTTP {r.status_code}: {r.text[:500]}")
    datos = r.json().get("data") or {}
    if not datos.get("id"):
        raise RuntimeError(f"envio sin id: {r.text[:500]}")
    return datos["id"]


def esperar(clave: str, tarea_id: str) -> dict:
    """Consulta el resultado; reintenta solo la consulta ante 429/5xx o errores de red."""
    inicio = time.time()
    while time.time() - inicio < LIMITE_S:
        try:
            r = requests.get(URL_RESULTADO.format(id=tarea_id), headers=encabezados(clave), timeout=30)
        except requests.RequestException as e:
            print(f"    consulta con error de red ({type(e).__name__}), reintento...")
            time.sleep(INTERVALO_S)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            espera = int(r.headers.get("Retry-After", INTERVALO_S))
            time.sleep(max(espera, INTERVALO_S))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"consulta HTTP {r.status_code}: {r.text[:500]}")
        datos = r.json().get("data") or {}
        estado = datos.get("status")
        if estado == "completed":
            return datos
        if estado in ("failed", "cancelled", "timeout", "deleted"):
            raise RuntimeError(f"tarea {estado}: {datos.get('error')}")
        time.sleep(INTERVALO_S)
    raise TimeoutError(f"sin resultado tras {LIMITE_S} s (la tarea sigue registrada en el manifiesto)")


def descargar_png(url: str, destino: Path) -> tuple[int, int, str]:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    formato = img.format or "?"
    if formato == "PNG":
        destino.write_bytes(r.content)
    else:  # solo cambia el contenedor, sin escalar ni recortar
        img.save(destino, "PNG")
    return img.width, img.height, formato


def main() -> int:
    clave = os.environ.get("WAVESPEED_API_KEY")
    if not clave:
        print("Falta WAVESPEED_API_KEY. Definela en la terminal: $env:WAVESPEED_API_KEY = \"...\"")
        return 1

    global SALIDA, MANIFIESTO
    ruta_prompts = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else JSON_PROMPTS
    spec = json.loads(ruta_prompts.read_text(encoding="utf-8"))
    SALIDA = RAIZ / spec.get("salida", "diseno/generadas")
    MANIFIESTO = SALIDA / "manifest.json"
    SALIDA.mkdir(parents=True, exist_ok=True)
    m = cargar_manifiesto()
    referencia = None
    if spec.get("modo") == "edicion":
        referencia = (RAIZ / spec["referencia"]).resolve()
        if not referencia.is_file():
            print(f"No existe la imagen de referencia {referencia}")
            return 1
    modelo = MODELO_EDICION if referencia else MODELO
    m["modelo"], m["resolucion"] = modelo, RESOLUCION
    if referencia:
        m["referencia"] = spec["referencia"]
    m["acepta_prompt_negativo"] = ACEPTA_NEGATIVO

    errores = 0
    for item in spec["imagenes"]:
        archivo = item["archivo"]
        destino = SALIDA / archivo
        entrada = m["imagenes"].get(item["id"], {})
        if destino.exists():
            print(f"[{item['id']}] ya existe {archivo}, se salta.")
            continue
        if entrada.get("error_envio"):
            print(f"[{item['id']}] el envio fallo antes ({entrada['error_envio'][:80]}); no se reenvia.")
            errores += 1
            continue

        prompt = f"{spec['estilo_comun']} {item['prompt']}"
        if ACEPTA_NEGATIVO:
            pass  # el modelo no lo admite; nunca se agrega al texto
        entrada.update({
            "archivo": archivo,
            "modelo": modelo,
            "prompt_final": prompt,
            "tamano_pedido": {"aspecto": item["aspecto"], "resolucion": RESOLUCION,
                              "referencia": f"{item['ancho']}x{item['alto']}"},
        })
        m["imagenes"][item["id"]] = entrada

        tarea_id = entrada.get("id_tarea")
        if tarea_id:
            print(f"[{item['id']}] retomando la tarea ya enviada {tarea_id}")
        else:
            print(f"[{item['id']}] enviando...")
            try:
                referencia_url = None
                if referencia:
                    if not m.get("referencia_url"):  # se sube una sola vez por lote
                        print("    subiendo la imagen de referencia...")
                        m["referencia_url"] = subir_referencia(clave, referencia)
                        guardar_manifiesto(m)
                    referencia_url = m["referencia_url"]
                tarea_id = enviar(clave, prompt, item["aspecto"], referencia_url)
            except Exception as e:  # noqa: BLE001
                entrada["error_envio"] = str(e)
                guardar_manifiesto(m)
                print(f"[{item['id']}] ERROR al enviar: {e}")
                errores += 1
                continue
            entrada["id_tarea"] = tarea_id
            entrada["fecha"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            guardar_manifiesto(m)

        try:
            datos = esperar(clave, tarea_id)
            salidas = datos.get("outputs") or []
            url = salidas[0] if salidas and isinstance(salidas[0], str) else (salidas[0] or {}).get("url")
            if not url:
                raise RuntimeError(f"tarea completada sin url: {salidas!r}")
            ancho, alto, formato = descargar_png(url, destino)
        except Exception as e:  # noqa: BLE001
            entrada["error_resultado"] = str(e)
            guardar_manifiesto(m)
            print(f"[{item['id']}] ERROR en el resultado: {e}")
            errores += 1
            continue

        entrada.pop("error_resultado", None)
        aspecto_real = ancho / alto
        a, b = (int(x) for x in item["aspecto"].split(":"))
        entrada.update({
            "tamano_real": f"{ancho}x{alto}",
            "formato_entregado": formato,
            "coincide_aspecto": abs(aspecto_real - a / b) < 0.02,
            "tiempo_inferencia_ms": (datos.get("timings") or {}).get("inference"),
            "costo_usd": datos.get("cost") or datos.get("price"),
            "costo_documentado_usd": round(COSTO_DOCUMENTADO_USD + (COSTO_POR_REFERENCIA_USD if referencia else 0), 3),
        })
        if not entrada["coincide_aspecto"]:
            entrada["nota_tamano"] = f"Pedido {item['aspecto']}, entregado {ancho}x{alto}."
        guardar_manifiesto(m)
        print(f"[{item['id']}] listo: {archivo} ({ancho}x{alto})")

    guardar_manifiesto(m)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())

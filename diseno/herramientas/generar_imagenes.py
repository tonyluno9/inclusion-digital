"""Genera las imagenes de diseno/prompts/imagenes.json con WaveSpeedAI (Nano Banana 2.1, 1K).

Uso (desde la raiz del repo):
    $env:WAVESPEED_API_KEY = "..."     # nunca se guarda en ningun archivo
    python diseno/herramientas/generar_imagenes.py

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
URL_ENVIO = f"https://api.wavespeed.ai/api/v3/{MODELO}"
URL_RESULTADO = "https://api.wavespeed.ai/api/v3/predictions/{id}/result"
RESOLUCION = "1k"  # maximo permitido por la persona; nunca 2k ni 4k
COSTO_DOCUMENTADO_USD = 0.04  # precio publicado por imagen a 1k
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


def enviar(clave: str, prompt: str, aspecto: str) -> str:
    cuerpo = {
        "prompt": prompt,
        "aspect_ratio": aspecto,
        "resolution": RESOLUCION,
        "output_format": "png",
        "enable_web_search": False,
        "enable_image_search": False,
    }
    r = requests.post(URL_ENVIO, headers=encabezados(clave), json=cuerpo, timeout=60)
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

    spec = json.loads(JSON_PROMPTS.read_text(encoding="utf-8"))
    SALIDA.mkdir(parents=True, exist_ok=True)
    m = cargar_manifiesto()
    m["modelo"], m["resolucion"] = MODELO, RESOLUCION
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
            "modelo": MODELO,
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
                tarea_id = enviar(clave, prompt, item["aspecto"])
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
            "costo_documentado_usd": COSTO_DOCUMENTADO_USD,
        })
        if not entrada["coincide_aspecto"]:
            entrada["nota_tamano"] = f"Pedido {item['aspecto']}, entregado {ancho}x{alto}."
        guardar_manifiesto(m)
        print(f"[{item['id']}] listo: {archivo} ({ancho}x{alto})")

    guardar_manifiesto(m)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())

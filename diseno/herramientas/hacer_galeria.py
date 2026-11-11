"""Anota la revision visual en el manifiesto y genera diseno/generadas/galeria.html."""
import html
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SPEC = json.loads((RAIZ / "diseno/prompts/imagenes.json").read_text(encoding="utf-8"))
MAN_PATH = RAIZ / "diseno/generadas/manifest.json"
MAN = json.loads(MAN_PATH.read_text(encoding="utf-8"))

# Revision visual hecha a mano, sin regenerar ninguna imagen.
REVISION = {
    "logo": ("ok", [
        "Una sola figura centrada sobre fondo blanco liso, sin texto: cumple.",
        "Mano con 5 dedos (4 dedos y el pulgar): cumple, aunque los dedos se marcan con líneas finas del degradado y se ven algo irregulares.",
        "El símbolo ocupa cerca del 50 % del lienzo, no el 70 % pedido: se puede recortar el margen al integrarlo.",
    ]),
    "iconos": ("ok", [
        "20 íconos en 5 columnas × 4 filas, en el orden pedido, negros de línea sobre blanco y sin texto: cumple.",
        "Tamaño real 1152×928 (el modelo entrega 1K más grande en 5:4); la proporción coincide.",
        "Las celdas no son milimétricas: comprobar el corte en celdas iguales al integrarla.",
    ]),
    "fondo_avatar": ("ok", [
        "Fondo vacío con centro más claro y foco de luz en el piso, sin objetos, personas ni texto: cumple.",
        "En los bordes izquierdo y derecho hay brillos naranja/ámbar que no se pidieron (solo violeta).",
        "Tamaño real 1376×768 (16:9, 1K del modelo).",
    ]),
    "fondo_inicio": ("ok", [
        "Tercio izquierdo oscuro y limpio, formas fluidas a la derecha con puntos conectados, sin personas ni texto: cumple.",
        "Tamaño real 1376×768 (16:9, 1K del modelo).",
    ]),
    "ilustraciones": ("problemas", [
        "4 ilustraciones en 2 × 2, mismo estilo, fondo blanco, sin texto: cumple.",
        "Arriba a la derecha: la guía punteada no enmarca bien cabeza, hombros y codos; queda como un rectángulo partido con un recuadro aparte en un codo, y la persona saluda en lugar de estar frente a la cámara con los codos visibles.",
        "Arriba a la izquierda: el avatar es una criatura tipo mascota, no un personaje 3D, y está abajo, no entre los dos.",
        "Manos: en general tienen 5 dedos; la mano de puntos (abajo a la derecha) también.",
    ]),
}

for k, (estado, notas) in REVISION.items():
    MAN["imagenes"][k]["revision_estado"] = estado
    MAN["imagenes"][k]["revision_notas"] = notas
MAN["costo_total_nota"] = "La API no informó el costo. Precio publicado: 0.04 USD por imagen a 1K, unos 0.20 USD en total."
MAN_PATH.write_text(json.dumps(MAN, ensure_ascii=False, indent=2), encoding="utf-8")

tarjetas = []
for it in SPEC["imagenes"]:
    m = MAN["imagenes"][it["id"]]
    estado, notas = REVISION[it["id"]]
    e = html.escape
    tarjetas.append(f"""
<section class="card">
  <h2>{e(it['archivo'])} <span class="tag {estado}">{'OK' if estado == 'ok' else 'Con problemas'}</span></h2>
  <img src="{e(it['archivo'])}" alt="{e(it['id'])}">
  <p><b>Para qué es:</b> {e(it['para_que'])}</p>
  <p><b>Lista de revisión:</b> {e(it['revision'])}</p>
  <p><b>Tamaño:</b> pedido {e(it['aspecto'])} a 1K, real {e(m['tamano_real'])} · tarea {e(m['id_tarea'])}</p>
  <ul>{''.join(f'<li>{e(n)}</li>' for n in notas)}</ul>
</section>""")

pagina = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>INCLUSION - galería de imágenes generadas</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#0F1724; color:#e8ecf3; margin:0; padding:24px; }}
h1 {{ margin-top:0 }}
.card {{ background:#18223a; border-radius:12px; padding:20px; margin:0 auto 28px; max-width:1200px; }}
.card img {{ width:100%; height:auto; border-radius:8px; background:repeating-conic-gradient(#ccc 0 25%,#eee 0 50%) 0/20px 20px; }}
.tag {{ font-size:14px; padding:3px 10px; border-radius:20px; vertical-align:middle; }}
.ok {{ background:#2EC4B6; color:#0F1724; }} .problemas {{ background:#FF6B6B; color:#0F1724; }}
li {{ margin:4px 0 }}
</style></head><body>
<h1>Imágenes generadas · {html.escape(MAN['modelo'])} · {html.escape(MAN['resolucion'])}</h1>
<p>Una generación por imagen, sin reintentos. {html.escape(MAN['costo_total_nota'])}</p>
{''.join(tarjetas)}
</body></html>"""
(RAIZ / "diseno/generadas/galeria.html").write_text(pagina, encoding="utf-8")
print("galeria lista")

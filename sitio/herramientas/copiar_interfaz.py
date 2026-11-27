"""Copia la interfaz de la app (app/web) a «Pruébalo» (sitio/probar), cambiando solo las rutas.

    python sitio/herramientas/copiar_interfaz.py           # copia
    python sitio/herramientas/copiar_interfaz.py --revisar # solo dice si la copia está al día (sale con 1 si no)

Los módulos de la interfaz son los mismos que usa la app de escritorio; aquí solo cambia de
dónde salen los recursos:
- las imágenes son las del sitio (sitio/assets/img, en WebP) en vez de las PNG/JPG de la app;
- la fuente es Lexend recortada a latín (WOFF) y three.js está en sitio/vendor;
- la hoja de estilos va en sitio/probar/app.css (no en css/): así sus url(../assets/...) y las de
  los estilos en línea del HTML apuntan a la misma carpeta sitio/assets;
- la cámara es un <canvas data-video> en vez de <img data-video> (CSS).

app.js e index.html NO se copian: en «Pruébalo» hablan con el motor del navegador
(sitio/probar/js/motor/) en vez de con servidor_web.py. Si cambian en la app, hay que
pasar los cambios a mano.
"""
import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
WEB = RAIZ / "app" / "web"
SITIO = RAIZ / "sitio"
PROBAR = SITIO / "probar"

MODULOS = ["avatar.js", "retarget.js", "texto.js", "diccionario.js", "aprender.js", "escenas.js",
           "vista_aprender.js", "vista_diccionario.js"]


def rutas(texto, nombre):
    # Imágenes: las WebP del sitio (sitio/assets/img), relativas a la página sitio/probar/index.html
    texto = re.sub(r"""(?<![\w.])(?:\.\./|/)?assets/img/([\w/${}.+ -]+?)\.(?:png|jpg)""",
                   r"../assets/img/\1.webp", texto)
    if nombre == "app.css":
        texto = texto.replace('url("../assets/fuentes/Lexend.ttf") format("truetype")',
                              'url("../assets/fuentes/Lexend-latin.woff") format("woff")')
        texto = texto.replace("img[data-video]", "[data-video]")
    if nombre == "retarget.js":
        texto = texto.replace("'../vendor/three/three.module.js'", "'../../vendor/three/three.module.js'")
    if nombre == "avatar.js":
        texto = texto.replace("async cargar(base = 'assets/modelos/')", "async cargar(base = '../assets/modelos/')")
    return texto


def cabecera(nombre, origen):
    aviso = f"Copiado de app/web/{origen} por sitio/herramientas/copiar_interfaz.py (solo cambian las rutas). No lo edites aquí."
    return f"/* {aviso} */\n" if nombre.endswith(".css") else f"// {aviso}\n"


def copias():
    for m in MODULOS:
        yield WEB / "js" / m, PROBAR / "js" / m, f"js/{m}"
    yield WEB / "css" / "app.css", PROBAR / "app.css", "css/app.css"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--revisar", action="store_true")
    a = p.parse_args()
    viejas, faltan = [], []
    for origen, destino, rel in copias():
        texto = cabecera(destino.name, rel) + rutas(origen.read_text(encoding="utf-8"), destino.name)
        # Toda imagen a la que apunte la copia tiene que existir en el sitio
        for img in re.findall(r"\.\./assets/img/([\w/.-]+\.webp)", texto):
            if "$" not in img and not (SITIO / "assets" / "img" / img).exists():
                faltan.append(f"{rel}: assets/img/{img}")
        actual = destino.read_text(encoding="utf-8") if destino.exists() else None
        if actual != texto:
            viejas.append(rel)
            if not a.revisar:
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(texto, encoding="utf-8", newline="\n")
    if faltan:
        print("Faltan imágenes en sitio/assets/img:\n  " + "\n  ".join(faltan))
        return 1
    if a.revisar:
        print("La copia está al día." if not viejas else "Hay que volver a copiar: " + ", ".join(viejas))
        return 1 if viejas else 0
    print(f"Copiados {len(viejas)} archivos" + (f": {', '.join(viejas)}" if viejas else " (ya estaban al día)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

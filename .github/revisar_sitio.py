"""Revisa que todos los archivos locales que usa sitio/ existan (HTML, CSS y JS).

Uso:  python .github/revisar_sitio.py
Sale con error (código 1) si falta alguno, para que el despliegue no publique un sitio roto.
"""
import re
import sys
from pathlib import Path

SITIO = Path(__file__).resolve().parents[1] / "sitio"
EXTERNO = re.compile(r"^(https?:|data:|mailto:|#|//)")
PATRONES = {
    ".html": [r'(?:src|href)="([^"]+)"', r"url\(([^)]+)\)", r'"(\./vendor/[^"]+)"'],
    ".css": [r"url\(([^)]+)\)"],
    ".js": [r"""(?:import|from)\s*\(?\s*['"](\.{1,2}/[^'"]+)['"]""", r"""['"`](assets/[^'"`$]+\.\w+)['"`]"""],
}


def limpiar(ref):
    return ref.strip().strip("'\"").split("#")[0].split("?")[0]


faltan = []
revisados = 0
for archivo in SITIO.rglob("*"):
    if archivo.suffix not in PATRONES or "vendor" in archivo.parts:
        continue
    texto = archivo.read_text(encoding="utf-8")
    for patron in PATRONES[archivo.suffix]:
        for ref in re.findall(patron, texto):
            ref = limpiar(ref)
            if not ref or EXTERNO.match(ref) or ref.endswith("/"):
                continue
            # En CSS y en estilos en línea, url() es relativo a la hoja (css/); en JS, los
            # import son relativos al módulo y las rutas «assets/...» a la página.
            if archivo.suffix == ".js" and ref.startswith("assets/"):
                base = SITIO
            elif archivo.suffix == ".html" and ref.startswith("../"):
                base = SITIO / "css"
            else:
                base = archivo.parent
            destino = (base / ref).resolve()
            revisados += 1
            if not destino.exists():
                faltan.append(f"{archivo.relative_to(SITIO)} → {ref}")

if faltan:
    print("Faltan archivos:")
    print("\n".join(f"  {f}" for f in sorted(set(faltan))))
    sys.exit(1)
print(f"Todo bien: {revisados} referencias revisadas en sitio/.")

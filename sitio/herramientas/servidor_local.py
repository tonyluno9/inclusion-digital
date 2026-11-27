"""Sirve sitio/ en tu computadora para probarlo (como GitHub Pages, pero sin caché).

    python sitio/herramientas/servidor_local.py            # http://127.0.0.1:8790/probar/
    python sitio/herramientas/servidor_local.py 8791

Solo escucha en 127.0.0.1 (nadie más en la red lo ve). «localhost» cuenta como sitio seguro,
así que el navegador deja usar la cámara sin https.
"""
import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITIO = Path(__file__).resolve().parents[1]


class Manejador(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm", ".json": "application/json",
        ".task": "application/octet-stream", ".glb": "model/gltf-binary", ".webp": "image/webp", ".woff": "font/woff",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if not str(args[1] if len(args) > 1 else "").startswith(("2", "3")):
            super().log_message(fmt, *args)


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), functools.partial(Manejador, directory=str(SITIO)))
    print(f"Sitio en http://127.0.0.1:{puerto}/  ·  Pruébalo en http://127.0.0.1:{puerto}/probar/", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

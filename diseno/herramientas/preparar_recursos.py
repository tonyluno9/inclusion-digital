"""Convierte las imágenes de diseno/generadas en recursos de la app (app/web/assets).

    python diseno/herramientas/preparar_recursos.py

- logo e ilustraciones: el fondo blanco (solo el que toca el borde) se vuelve transparente;
- íconos: la hoja 5 × 4 se corta en celdas y cada ícono queda como máscara (blanco con
  transparencia), para pintarlo del color que toque con CSS;
- fondos: a JPEG, para que pesen menos.
"""
import os

import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ORIGEN = os.path.join(RAIZ, "diseno", "generadas")
DESTINO = os.path.join(RAIZ, "app", "web", "assets")

ICONOS = [
    "senas", "camara", "avatar", "subtitulos", "microfono",
    "voz", "silencio", "grabar", "detener", "reproducir",
    "deshacer", "borrar", "entrenar", "datos", "estadisticas",
    "ajustes", "ayuda", "pantalla_completa", "persona_nueva", "inicio",
]
ILUSTRACIONES = ["bienvenida", "encuadre", "sin_camara", "entrenando"]


def leer(nombre):
    img = cv2.imread(os.path.join(ORIGEN, nombre), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Falta {nombre} en {ORIGEN}")
    return img


def quitar_fondo_blanco(img, tolerancia=18):
    """Transparente solo el blanco conectado con el borde (lo blanco de adentro se queda)."""
    h, w = img.shape[:2]
    casi_blanco = (img.min(axis=2) >= 255 - tolerancia).astype(np.uint8)
    relleno = np.zeros((h + 2, w + 2), np.uint8)
    fondo = np.zeros((h, w), np.uint8)
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if casi_blanco[y, x]:
            m = casi_blanco.copy()
            cv2.floodFill(m, relleno, (x, y), 2)
            fondo |= (m == 2).astype(np.uint8)
    # Borde suave: el antialias del contorno queda semitransparente según lo blanco que sea
    alfa = np.where(fondo > 0, 0, 255).astype(np.float32)
    borde = cv2.dilate(fondo, np.ones((3, 3), np.uint8)) & (1 - fondo)
    blancura = img.min(axis=2).astype(np.float32)
    alfa[borde > 0] = np.clip((255 - blancura[borde > 0]) * 4, 0, 255)
    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    rgba[..., 3] = alfa.astype(np.uint8)
    return rgba


def recortar(rgba, margen=0.04):
    ys, xs = np.nonzero(rgba[..., 3] > 8)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    lado = max(y1 - y0, x1 - x0)
    m = int(lado * margen)
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    mitad = lado // 2 + m
    lienzo = np.zeros((2 * mitad, 2 * mitad, 4), np.uint8)
    sy0, sx0 = max(0, cy - mitad), max(0, cx - mitad)
    sy1, sx1 = min(rgba.shape[0], cy + mitad), min(rgba.shape[1], cx + mitad)
    lienzo[sy0 - (cy - mitad): sy1 - (cy - mitad), sx0 - (cx - mitad): sx1 - (cx - mitad)] = rgba[sy0:sy1, sx0:sx1]
    return lienzo


def logo():
    rgba = recortar(quitar_fondo_blanco(leer("logo.png")))
    cv2.imwrite(os.path.join(DESTINO, "img", "logo.png"), cv2.resize(rgba, (512, 512), interpolation=cv2.INTER_AREA))
    # Ícono de la ventana: varios tamaños dentro de un .ico
    from PIL import Image
    pil = Image.fromarray(cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA))
    pil.save(os.path.join(DESTINO, "img", "logo.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return "logo.png, logo.ico"


def celdas(img, columnas, filas):
    h, w = img.shape[:2]
    for f in range(filas):
        for c in range(columnas):
            yield img[f * h // filas:(f + 1) * h // filas, c * w // columnas:(c + 1) * w // columnas]


def iconos(lado=128):
    hoja = cv2.cvtColor(leer("iconos.png"), cv2.COLOR_BGR2GRAY)
    for nombre, celda in zip(ICONOS, celdas(hoja, 5, 4)):
        tinta = 255 - celda.astype(np.float32)                 # negro = tinta
        tinta[tinta < 30] = 0                                  # papel
        ys, xs = np.nonzero(tinta > 60)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        cuadro = max(y1 - y0, x1 - x0) + 1
        pad = int(cuadro * 0.08)
        lienzo = np.zeros((cuadro + 2 * pad, cuadro + 2 * pad), np.float32)
        oy = pad + (cuadro - (y1 - y0 + 1)) // 2
        ox = pad + (cuadro - (x1 - x0 + 1)) // 2
        lienzo[oy:oy + y1 - y0 + 1, ox:ox + x1 - x0 + 1] = tinta[y0:y1 + 1, x0:x1 + 1]
        alfa = cv2.resize(np.clip(lienzo * 1.15, 0, 255), (lado, lado), interpolation=cv2.INTER_AREA).astype(np.uint8)
        rgba = np.dstack([np.full_like(alfa, 255)] * 3 + [alfa])
        cv2.imwrite(os.path.join(DESTINO, "iconos", f"{nombre}.png"), rgba)
    return f"{len(ICONOS)} íconos"


def ilustraciones(lado=480):
    hoja = leer("ilustraciones.png")
    for nombre, celda in zip(ILUSTRACIONES, celdas(hoja, 2, 2)):
        rgba = recortar(quitar_fondo_blanco(celda), margen=0.02)
        cv2.imwrite(os.path.join(DESTINO, "img", f"{nombre}.png"),
                    cv2.resize(rgba, (lado, lado), interpolation=cv2.INTER_AREA))
    return f"{len(ILUSTRACIONES)} ilustraciones"


def fondos():
    for nombre in ("fondo_avatar", "fondo_inicio"):
        cv2.imwrite(os.path.join(DESTINO, "img", f"{nombre}.jpg"), leer(f"{nombre}.png"),
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
    return "2 fondos"


if __name__ == "__main__":
    for carpeta in ("img", "iconos"):
        os.makedirs(os.path.join(DESTINO, carpeta), exist_ok=True)
    for paso in (logo, iconos, ilustraciones, fondos):
        print("ok:", paso())

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


# Logo de K'ab T'aan: el concepto C «Diálogo» (mano de la persona y mano de puntos del sistema)
LOGO = os.path.join("logo_kab_taan", "concepto_dialogo.png")


def rellenar_circulo(rgba, margen):
    """El logo es un emblema redondo: todo lo de adentro del aro es opaco sobre blanco (el relleno
    del fondo se puede colar por el aro, que es una línea fina, y dejar el interior transparente)."""
    lado = rgba.shape[0]
    radio = lado / 2 / (1 + 2 * margen) - 1
    yy, xx = np.mgrid[:lado, :lado]
    dentro = (xx - lado / 2 + .5) ** 2 + (yy - lado / 2 + .5) ** 2 <= radio ** 2
    a = rgba[..., 3:4].astype(np.float32) / 255
    blanco = rgba[..., :3].astype(np.float32) * a + 255 * (1 - a)
    rgba[dentro, :3] = blanco[dentro].astype(np.uint8)
    rgba[dentro, 3] = 255
    return rgba


def logo():
    rgba = rellenar_circulo(recortar(quitar_fondo_blanco(leer(LOGO)), margen=0.02), margen=0.02)
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


def iconos(lado=128, archivo="iconos.png", nombres=ICONOS):
    hoja = cv2.cvtColor(leer(archivo), cv2.COLOR_BGR2GRAY)
    for nombre, celda in zip(nombres, celdas(hoja, 5, 4)):
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
    return f"{len(nombres)} íconos"


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


# ---------------------------------------------------------------- app completa
# Imágenes de diseno/generadas/app_completa (prompts en diseno/prompts/app_completa.json)
COMPLETA = "app_completa"
ICONOS_2 = [
    "diccionario", "aprender", "trofeo", "estrella", "racha",
    "conversacion", "buscar", "recortar", "cronometro", "lento",
    "una_mano", "dos_manos", "correcto", "incorrecto", "consejo",
    "tema", "escenario", "exportar", "info", "repetir",
]
# (hoja, columnas, filas, carpeta de destino, nombres, lado en px)
HOJAS = [
    ("insignias.png", 3, 3, "insignias", ["primera_sena", "diez_senas", "racha_3", "racha_7", "saludos",
                                          "primer_movimiento", "traductor", "conversacion", "explorador"], 256),
    ("bienvenida.png", 2, 2, "tutorial", ["paso_1", "paso_2", "paso_3", "paso_4"], 420),
    ("categorias.png", 3, 2, "categorias", ["saludos", "cortesia", "preguntas", "familia", "emociones",
                                            "numeros"], 200),
    ("estados.png", 2, 2, "estados", ["bien_hecho", "otra_vez", "sin_conexion", "entrenado"], 360),
]
ESCENARIOS = ["escenario_maya", "escenario_aula", "escenario_plaza"]


def iconos_2():
    return iconos(archivo=os.path.join(COMPLETA, "iconos_2.png"), nombres=ICONOS_2)


def hojas():
    hechas = 0
    for archivo, columnas, filas, carpeta, nombres, lado in HOJAS:
        os.makedirs(os.path.join(DESTINO, "img", carpeta), exist_ok=True)
        hoja = leer(os.path.join(COMPLETA, archivo))
        for nombre, celda in zip(nombres, celdas(hoja, columnas, filas)):
            # Cada dibujo se recorta por su contenido (las celdas generadas no son exactas)
            rgba = recortar(quitar_fondo_blanco(celda), margen=0.03)
            cv2.imwrite(os.path.join(DESTINO, "img", carpeta, f"{nombre}.png"),
                        cv2.resize(rgba, (lado, lado), interpolation=cv2.INTER_AREA))
            hechas += 1
    return f"{hechas} imágenes de {len(HOJAS)} hojas"


def escenarios():
    os.makedirs(os.path.join(DESTINO, "img", "escenarios"), exist_ok=True)
    for nombre in ESCENARIOS:
        cv2.imwrite(os.path.join(DESTINO, "img", "escenarios", nombre.replace("escenario_", "") + ".jpg"),
                    leer(os.path.join(COMPLETA, f"{nombre}.png")), [cv2.IMWRITE_JPEG_QUALITY, 88])
    cv2.imwrite(os.path.join(DESTINO, "img", "portada.jpg"), leer(os.path.join(COMPLETA, "portada.png")),
                [cv2.IMWRITE_JPEG_QUALITY, 88])
    return f"{len(ESCENARIOS)} escenarios y la portada"


if __name__ == "__main__":
    for carpeta in ("img", "iconos"):
        os.makedirs(os.path.join(DESTINO, carpeta), exist_ok=True)
    for paso in (logo, iconos, ilustraciones, fondos, iconos_2, hojas, escenarios):
        print("ok:", paso())

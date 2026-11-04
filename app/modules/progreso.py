"""Progreso del modo Aprender: aciertos por palabra, estrellas, racha de días e insignias.

Se guarda en `progreso.json`, junto al dataset (dato personal: fuera de git). Las reglas de
las insignias están aquí para que la interfaz solo las muestre.
"""
import json
import os
import re
import unicodedata
from datetime import date, timedelta

# (id, nombre, cómo se gana). La imagen es web/assets/img/insignias/<id>.png
INSIGNIAS = [
    ("primera_sena", "Primera seña", "Haz bien una seña en Aprender."),
    ("diez_senas", "Diez señas", "Haz bien 10 señas distintas."),
    ("racha_3", "Racha de 3 días", "Practica 3 días seguidos."),
    ("racha_7", "Racha de 7 días", "Practica 7 días seguidos."),
    ("saludos", "Maestro de los saludos", "Haz bien los saludos que conoce el traductor (al menos 2)."),
    ("primer_movimiento", "Primer movimiento", "Graba el movimiento de una seña para el avatar."),
    ("traductor", "Traductor entrenado", "Entrena el traductor con tus señas."),
    ("conversacion", "Primera conversación", "Traduce una oración completa."),
    ("explorador", "Explorador", "Haz bien señas de 3 categorías distintas."),
]
NOMBRES = {i: n for i, n, _ in INSIGNIAS}
DIEZ = 10
SALUDOS_MIN = 2
CATEGORIAS_MIN = 3


def normalizar(texto):
    """Igual que `norm` de web/js/texto.js: minúsculas, sin acentos ni signos («¡Adiós!» -> «adios»),
    para que la app web y el progreso usen las mismas claves."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", str(texto).lower())
                          if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", sin_acentos).split())


def estrellas_por_confianza(confianza):
    """3 estrellas con 90 % de confianza o más, 2 con 75 %, 1 si solo acertó."""
    return 3 if confianza >= 0.9 else 2 if confianza >= 0.75 else 1


class Progreso:
    def __init__(self, ruta, hoy=date.today):
        self.ruta = ruta
        self.hoy = hoy
        self.datos = self._cargar()

    # ------------------------------------------------------------ archivo
    @staticmethod
    def _vacio():
        return {"estrellas": 0, "aciertos": 0, "intentos": 0, "oraciones": 0,
                "palabras": {}, "dias": [], "insignias": {}}

    def _cargar(self):
        datos = self._vacio()
        try:
            with open(self.ruta, encoding="utf-8") as f:
                leido = json.load(f)
            if isinstance(leido, dict):
                datos.update({k: v for k, v in leido.items() if k in datos})
        except (OSError, ValueError):
            pass
        return datos

    def guardar(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.ruta)), exist_ok=True)
        tmp = self.ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.datos, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, self.ruta)

    # ----------------------------------------------------------- registrar
    def registrar_intento(self, palabra, acierto, confianza=0.0):
        """Un intento en Aprender. Devuelve las estrellas ganadas (0 si falló)."""
        clave = normalizar(palabra)
        d = self.datos
        p = d["palabras"].setdefault(clave, {"aciertos": 0, "intentos": 0, "mejor": 0})
        p["intentos"] += 1
        d["intentos"] += 1
        estrellas = 0
        if acierto:
            estrellas = estrellas_por_confianza(confianza)
            p["aciertos"] += 1
            p["mejor"] = max(p["mejor"], estrellas)
            d["aciertos"] += 1
            d["estrellas"] += estrellas
            hoy = self.hoy().isoformat()
            if hoy not in d["dias"]:
                d["dias"] = sorted(d["dias"] + [hoy])
        return estrellas

    def registrar_oracion(self):
        self.datos["oraciones"] += 1

    # ------------------------------------------------------------- cálculos
    def racha(self):
        """Días seguidos con al menos un acierto, contando hasta hoy (o hasta ayer: la racha
        sigue viva mientras hoy no termine)."""
        dias = {date.fromisoformat(d) for d in self.datos["dias"]}
        dia = self.hoy()
        if dia not in dias:
            dia -= timedelta(days=1)
        n = 0
        while dia in dias:
            n += 1
            dia -= timedelta(days=1)
        return n

    def aprendidas(self):
        return sorted(p for p, v in self.datos["palabras"].items() if v["aciertos"] > 0)

    def evaluar(self, categorias=None, conocidas=(), clips=0, modelo=False):
        """Otorga las insignias que ya se cumplen. `categorias`: {categoría: [palabras]};
        `conocidas`: señas del traductor. Devuelve las ids nuevas."""
        aprendidas = set(self.aprendidas())
        categorias = {c: {normalizar(p) for p in ps} for c, ps in (categorias or {}).items()}
        conocidas = {normalizar(p) for p in conocidas}
        racha = self.racha()
        saludos = categorias.get("saludos", set()) & conocidas
        cumple = {
            "primera_sena": len(aprendidas) >= 1,
            "diez_senas": len(aprendidas) >= DIEZ,
            "racha_3": racha >= 3,
            "racha_7": racha >= 7,
            "saludos": len(saludos) >= SALUDOS_MIN and saludos <= aprendidas,
            "primer_movimiento": clips >= 1,
            "traductor": bool(modelo),
            "conversacion": self.datos["oraciones"] >= 1,
            "explorador": sum(1 for ps in categorias.values() if ps & aprendidas) >= CATEGORIAS_MIN,
        }
        nuevas = [i for i, _, _ in INSIGNIAS if cumple[i] and i not in self.datos["insignias"]]
        for i in nuevas:
            self.datos["insignias"][i] = self.hoy().isoformat()
        return nuevas

    def resumen(self):
        d = self.datos
        hoy = self.hoy().isoformat()
        return {
            "estrellas": d["estrellas"],
            "aciertos": d["aciertos"],
            "intentos": d["intentos"],
            "racha": self.racha(),
            "practico_hoy": hoy in d["dias"],
            "aprendidas": self.aprendidas(),
            "palabras": d["palabras"],
            "insignias": [{"id": i, "nombre": n, "como": c, "ganada": d["insignias"].get(i)}
                          for i, n, c in INSIGNIAS],
        }

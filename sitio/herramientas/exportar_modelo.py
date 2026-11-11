"""Convierte el traductor de la app (model.pkl de scikit-learn) en modelo.json para «Pruébalo».

    python sitio/herramientas/exportar_modelo.py RUTA/model.pkl sitio/probar/datos/modelo.json

El JSON trae lo mínimo para que sitio/probar/js/motor/traductor.js calcule lo mismo que
`pipeline.predict_proba` (ver app/modules/gesture_logic.py):

- `rasgos`: los índices de las features (0..7799) que usa algún árbol, con su `media` y su
  `escala` del StandardScaler. Las demás no cambian el resultado, así que no se exportan.
- `arboles`: cada árbol en arreglos planos. Nodo interno: `izq`/`der` (hijos), `rasgo` (índice
  original de la feature) y `umbral`. Hoja: `izq` = -1 y `rasgo` = número de hoja; su
  distribución de clases (ya normalizada por scikit-learn) está en `hojas[n]`.

No se exporta quién grabó las muestras (`persons` del modelo): solo cuántas hay.
Los números van completos (repr de Python): un umbral redondeado podría mandar una
seña por la otra rama del árbol.
"""
import argparse
import json
import os
import sys

import joblib
import numpy as np

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app")
sys.path.insert(0, os.path.abspath(APP))

import config as C  # noqa: E402

FORMATO = "kabtaan-modelo"
VERSION = 1


def exportar_pipeline(pipeline, extra=None):
    """dict listo para json.dump a partir de un Pipeline(StandardScaler, RandomForestClassifier)."""
    scaler = pipeline.named_steps["scaler"]
    rf = pipeline.named_steps["rf"]
    usados = sorted({int(f) for e in rf.estimators_ for f in e.tree_.feature if f >= 0})
    arboles = []
    for e in rf.estimators_:
        t = e.tree_
        izq, der, rasgo, umbral, hojas = [], [], [], [], []
        for n in range(t.node_count):
            if t.children_left[n] == -1:                     # hoja
                valor = t.value[n, 0, :].astype(np.float64)
                total = valor.sum()
                if not np.isclose(total, 1.0):               # versiones viejas guardan conteos
                    valor = valor / total
                izq.append(-1)
                der.append(-1)
                rasgo.append(len(hojas))
                umbral.append(0)
                hojas.append([float(v) for v in valor])
            else:
                izq.append(int(t.children_left[n]))
                der.append(int(t.children_right[n]))
                rasgo.append(int(t.feature[n]))
                umbral.append(float(t.threshold[n]))
        arboles.append({"izq": izq, "der": der, "rasgo": rasgo, "umbral": umbral, "hojas": hojas})
    media = scaler.mean_ if scaler.with_mean else np.zeros(scaler.n_features_in_)
    escala = scaler.scale_ if scaler.with_std else np.ones(scaler.n_features_in_)
    return {
        "formato": FORMATO,
        "version": VERSION,
        "feature_version": C.FEATURE_VERSION,
        "sequence_length": C.SEQUENCE_LENGTH,
        "n_rasgos": int(scaler.n_features_in_),
        "clases": [str(c) for c in rf.classes_],
        "rasgos": usados,
        "media": [float(media[i]) for i in usados],
        "escala": [float(escala[i]) for i in usados],
        "arboles": arboles,
        **(extra or {}),
    }


def exportar(ruta_pkl, ruta_json, origen="demo"):
    bundle = joblib.load(ruta_pkl)
    if bundle.get("feature_version") != C.FEATURE_VERSION or bundle.get("sequence_length") != C.SEQUENCE_LENGTH:
        raise SystemExit("El modelo es de otra versión de las features: reentrénalo en la app.")
    datos = exportar_pipeline(bundle["pipeline"], {
        "muestras": int(bundle.get("samples", 0)),
        "personas": len(bundle.get("persons", [])),
        "origen": origen,
    })
    os.makedirs(os.path.dirname(os.path.abspath(ruta_json)), exist_ok=True)
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    nodos = sum(len(a["izq"]) for a in datos["arboles"])
    print(f"{ruta_json}: {len(datos['clases'])} señas {datos['clases']}, {len(datos['arboles'])} árboles, "
          f"{nodos} nodos, {len(datos['rasgos'])} de {datos['n_rasgos']} rasgos, "
          f"{os.path.getsize(ruta_json) / 1024:.0f} KB")
    return datos


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("pkl")
    p.add_argument("json")
    p.add_argument("--origen", default="demo", help="texto que se guarda en el JSON (no pongas nombres)")
    a = p.parse_args()
    exportar(a.pkl, a.json, a.origen)

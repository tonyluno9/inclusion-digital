"""Verifica que cada seña grabada se reconozca como si llegara por la cámara.

    python verificar_senas.py                 # dataset de la app
    python verificar_senas.py --dataset otro.csv

Para cada muestra del dataset:
1. la reproduce a varias velocidades (0.6x a 2x), rodeada de frames sin manos, y la pasa por
   el segmentador real (el mismo camino que la cámara en vivo);
2. la clasifica con un modelo entrenado SIN esa muestra (validación cruzada: por persona si hay
   varias, si no por muestras);
3. reporta el acierto por seña, la confianza y qué muestras fallan, para regrabarlas.
"""
import argparse
import os
import sys

import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config as C
from modules.landmarks import HANDS_SIZE, resample
from modules.segmenter import SignSegmenter
from train_model import features, fit, load_dataset

VELOCIDADES = (0.6, 1.0, 1.5, 2.0)


def simular_camara(muestra, velocidad, relleno=20):
    """La muestra como la vería la cámara: a otra velocidad y con frames sin manos antes y después."""
    n = max(C.SEGMENT_MIN_FRAMES + 2, int(round(C.SEQUENCE_LENGTH / velocidad)))
    sena = resample(muestra, n)
    quieto = np.zeros((relleno, muestra.shape[1]), np.float32)
    quieto[:, HANDS_SIZE:] = muestra[0, HANDS_SIZE:]          # el cuerpo sigue a la vista
    seg = SignSegmenter(C.SEQUENCE_LENGTH, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES, C.SEGMENT_MIN_FRAMES,
                        C.SEGMENT_MAX_FRAMES, C.SEGMENT_CONTEXT_FRAMES, C.RESTING_HAND_MARGIN)
    salidas = [s for f in np.concatenate([quieto, sena, quieto]) if (s := seg.update(f)) is not None]
    return salidas


def pliegues(y, grupos, k=5):
    personas = sorted(set(grupos))
    if len(personas) >= 2:                      # deja fuera a una persona cada vez
        return [(np.array([g != p for g in grupos]), p) for p in personas]
    rng = np.random.RandomState(0)
    orden = rng.permutation(len(y))
    return [(np.isin(np.arange(len(y)), np.delete(orden, np.arange(i, len(y), k))), f"pliegue {i + 1}")
            for i in range(k)]


def verificar(ruta):
    raw, y, grupos = load_dataset(ruta)
    print(f"{len(y)} muestras, {len(set(y))} señas, personas: {sorted(set(grupos))}")
    if len(set(grupos)) < 2:
        print("Solo hay una persona: el resultado es optimista (mide si el traductor te entiende a ti).")
    resultados = []          # (seña real, predicha, confianza, índice, velocidad)
    rng = np.random.RandomState(0)
    for entrena, nombre in pliegues(y, grupos):
        if len(set(y[entrena])) < 2:
            continue
        modelo = fit(raw[entrena], y[entrena], rng)
        for i in np.flatnonzero(~entrena):
            for v in VELOCIDADES:
                salidas = simular_camara(raw[i], v)
                if len(salidas) != 1:
                    resultados.append((y[i], f"<{len(salidas)} señas detectadas>", 0.0, i, v))
                    continue
                p = modelo.predict_proba(features(np.array(salidas)).reshape(1, -1))[0]
                mejor = int(np.argmax(p))
                pred = modelo.classes_[mejor] if p[mejor] >= C.MIN_CONFIDENCE else "<no reconocida>"
                resultados.append((y[i], pred, float(p[mejor]), i, v))
    print()
    print(f"{'Seña':<18}{'Acierto':>9}{'Confianza':>11}   Intentos")
    total_ok = 0
    for sena in sorted(set(y)):
        r = [x for x in resultados if x[0] == sena]
        ok = sum(x[1] == sena for x in r)
        total_ok += ok
        conf = np.mean([x[2] for x in r if x[1] == sena]) if ok else 0
        print(f"{sena:<18}{100 * ok / len(r):>8.1f}%{100 * conf:>10.0f}%   {len(r)}")
    print(f"\nTotal: {100 * total_ok / len(resultados):.1f}% de {len(resultados)} intentos "
          f"({len(y)} muestras × {len(VELOCIDADES)} velocidades)")
    fallas = [x for x in resultados if x[1] != x[0]]
    if fallas:
        print("\nFallas (muestra n.º en el dataset, velocidad -> lo que entendió):")
        for real, pred, conf, i, v in fallas:
            print(f"  #{i:<4} {real:<16} {v:>3}x -> {pred} ({100 * conf:.0f}%)")
    return total_ok / len(resultados), fallas


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dataset", default=C.DATASET_PATH)
    args = p.parse_args(argv)
    if not os.path.exists(args.dataset):
        print(f"No existe {args.dataset}: graba señas primero.")
        return 1
    verificar(args.dataset)
    return 0


if __name__ == "__main__":
    sys.exit(main())

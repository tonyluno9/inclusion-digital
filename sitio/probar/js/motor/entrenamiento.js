// Entrenar el traductor en el navegador: port de app/train_model.py (check_dataset, augment, fit).
// Lo usa el Web Worker (entrenador.worker.js) y las pruebas de Node.
import { entrenarBosque, azar } from './bosque.js';
import * as C from './config.js';
import { FEATURE_FRAME_SIZE, HANDS_SIZE, RAW_FRAME_SIZE, aplanar, mirrorFeatures, resample, sequenceFeatures } from './landmarks.js';
import { FORMATO } from './traductor.js';

export const MIN_SAMPLES_PER_SIGN = 5;

/** "" si alcanza para entrenar; si no, el mensaje (como check_dataset). */
export function revisarDataset(etiquetas) {
  const cuentas = {};
  for (const e of etiquetas) cuentas[e] = (cuentas[e] || 0) + 1;
  const pocas = Object.keys(cuentas).sort().filter((e) => cuentas[e] < MIN_SAMPLES_PER_SIGN).map((e) => `${e} (${cuentas[e]})`);
  if (Object.keys(cuentas).length < 2 || pocas.length) {
    let msg = `Se necesitan al menos 2 señas con ${MIN_SAMPLES_PER_SIGN} muestras cada una.`;
    if (pocas.length) msg += ` Faltan muestras de: ${pocas.join(', ')}`;
    return msg;
  }
  return '';
}

/** Muestra guardada (Float32Array de 30 × 147) -> 30 frames. */
export function aFrames(seq) {
  return Array.from({ length: seq.length / RAW_FRAME_SIZE }, (_, i) => seq.subarray(i * RAW_FRAME_SIZE, (i + 1) * RAW_FRAME_SIZE));
}

/** Aumento de datos como augment() de train_model.py: sin cuerpo, espejo, recortes y ruido. */
export function aumentar(secuencias, y, r, { espejo = true, copias = 1 } = {}) {
  const sinCuerpo = secuencias.map((seq) => seq.map((fr) => { const c = Float32Array.from(fr); c.fill(0, HANDS_SIZE); return c; }));
  let X = [...secuencias, ...sinCuerpo].map(sequenceFeatures);
  let Y = [...y, ...y];
  if (espejo) { X = [...X, ...X.map(mirrorFeatures)]; Y = [...Y, ...Y]; }
  const todas = [...X];
  const etiquetas = [...Y];
  const T = X[0].length;
  for (let c = 0; c < copias; c += 1) {
    for (const feat of X) {
      const a = r.entero(4);
      const b = T - r.entero(4);
      const out = resample(feat.slice(a, b), T).map((fr) => {
        const o = Float32Array.from(fr);
        for (let j = 0; j < o.length; j += 1) if (o[j] !== 0) o[j] = Math.fround(o[j] + Math.fround(r.normal() * 0.01));
        return o;
      });
      todas.push(out);
    }
    etiquetas.push(...Y);
  }
  return [todas, etiquetas];
}

/**
 * muestras: [{ label, person, seq: Float32Array(30·147) }] -> modelo.json (formato de exportar_modelo.py).
 * alProgreso(hecho, total) mientras se construyen los árboles.
 */
export function entrenarModelo(muestras, { semilla = 42, arboles = 200, alProgreso = null } = {}) {
  const y = muestras.map((m) => m.label);
  const problema = revisarDataset(y);
  if (problema) throw new Error(problema);
  const clases = [...new Set(y)].sort();
  const r = azar(semilla);
  const [X, Y] = aumentar(muestras.map((m) => aFrames(m.seq)), y, r);
  const filas = X.map(aplanar);
  const yi = Int32Array.from(Y, (e) => clases.indexOf(e));
  const t0 = Date.now();
  const bosque = entrenarBosque(filas, yi, clases.length, { arboles, minHoja: 2, semilla: semilla + 1, alProgreso });
  const usados = [...new Set(bosque.arboles.flatMap((a) => a.izq.flatMap((iz, n) => (iz === -1 ? [] : [a.rasgo[n]]))))].sort((a, b) => a - b);
  return {
    formato: FORMATO,
    version: 1,
    feature_version: C.FEATURE_VERSION,
    sequence_length: C.SEQUENCE_LENGTH,
    n_rasgos: C.SEQUENCE_LENGTH * FEATURE_FRAME_SIZE,
    clases,
    rasgos: usados,
    media: usados.map((j) => bosque.media[j]),
    escala: usados.map((j) => bosque.escala[j]),
    arboles: bosque.arboles,
    muestras: muestras.length,
    personas: new Set(muestras.map((m) => m.person)).size,
    origen: 'navegador',
    entrenado: new Date().toISOString(),
    segundos: Math.round((Date.now() - t0) / 100) / 10,
  };
}

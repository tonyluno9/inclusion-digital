// El traductor en el navegador: StandardScaler + RandomForestClassifier de scikit-learn, leídos de
// modelo.json (lo escribe sitio/herramientas/exportar_modelo.py). Igual que gesture_logic.py:
// las features se escalan en float64 y se guardan en float32, y cada árbol compara el float32
// con su umbral; predict_proba es el promedio de las hojas de los 200 árboles.
import { aplanar, sequenceFeatures } from './landmarks.js';

const f = Math.fround;
export const FORMATO = 'kabtaan-modelo';

export class Traductor {
  constructor(modelo, { minConfianza = 0.6, featureVersion = 4, sequenceLength = 30 } = {}) {
    if (!modelo || modelo.formato !== FORMATO) throw new Error('No es un modelo de K\'ab T\'aan');
    if (modelo.feature_version !== featureVersion || modelo.sequence_length !== sequenceLength) {
      throw new Error('El modelo es de otra versión de las features: hay que reentrenarlo');
    }
    this.modelo = modelo;
    this.clases = modelo.clases;
    this.minConfianza = minConfianza;
    this.sequenceLength = sequenceLength;
    this.rasgos = Int32Array.from(modelo.rasgos);
    this.media = Float64Array.from(modelo.media);
    this.escala = Float64Array.from(modelo.escala);
    this.arboles = modelo.arboles.map((a) => ({
      izq: Int32Array.from(a.izq), der: Int32Array.from(a.der), rasgo: Int32Array.from(a.rasgo),
      umbral: Float64Array.from(a.umbral), hojas: a.hojas.map((h) => Float64Array.from(h)),
    }));
    this._x = new Float32Array(modelo.n_rasgos);
  }

  /** Probabilidad de cada clase para las features ya aplanadas (Float32Array de 7800). */
  probaFeatures(x) {
    const esc = this._x;
    for (let k = 0; k < this.rasgos.length; k += 1) {
      const i = this.rasgos[k];
      esc[i] = f(f(x[i] - this.media[k]) / this.escala[k]);
    }
    const suma = new Float64Array(this.clases.length);
    for (const a of this.arboles) {
      let n = 0;
      while (a.izq[n] !== -1) n = esc[a.rasgo[n]] <= a.umbral[n] ? a.izq[n] : a.der[n];
      const hoja = a.hojas[a.rasgo[n]];
      for (let c = 0; c < suma.length; c += 1) suma[c] += hoja[c];
    }
    for (let c = 0; c < suma.length; c += 1) suma[c] /= this.arboles.length;
    return suma;
  }

  /** secuencia cruda (30 frames de 147) -> [seña o "", confianza, probabilidades]. */
  predict(secuencia) {
    if (!secuencia || secuencia.length !== this.sequenceLength) return ['', 0, null];
    const proba = this.probaFeatures(aplanar(sequenceFeatures(secuencia)));
    let mejor = 0;
    for (let c = 1; c < proba.length; c += 1) if (proba[c] > proba[mejor]) mejor = c;
    const confianza = proba[mejor];
    return [confianza < this.minConfianza ? '' : this.clases[mejor], confianza, proba];
  }
}

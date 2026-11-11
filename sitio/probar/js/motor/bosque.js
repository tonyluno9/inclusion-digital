// Bosque aleatorio en JavaScript, para entrenar el traductor dentro del navegador.
// Sigue la receta de scikit-learn que usa app/train_model.py:
//   StandardScaler + RandomForestClassifier(n_estimators=200, min_samples_leaf=2), es decir:
//   bootstrap, criterio de Gini, √(rasgos) candidatos por nodo (saltando los constantes, como
//   scikit-learn), umbral en el punto medio y hojas con la proporción de cada clase.
// No da el mismo bosque que scikit-learn (otro generador de azar), pero sí uno equivalente.
// El resultado tiene el formato de modelo.json (exportar_modelo.py), así traductor.js lo usa igual.
const f = Math.fround;

/** Generador de azar con semilla (mulberry32): mismo bosque con la misma semilla. */
export function azar(semilla) {
  let a = semilla >>> 0;
  const r = () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  r.entero = (n) => Math.floor(r() * n);
  r.normal = () => {             // Box-Muller
    let u = 0;
    while (u === 0) u = r();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
  };
  return r;
}

/** Media y escala de StandardScaler (escala 1 donde la varianza es 0). filas: Float32Array[]. */
export function ajustarEscala(filas, d) {
  const n = filas.length;
  const media = new Float64Array(d);
  const escala = new Float64Array(d);
  for (const x of filas) for (let j = 0; j < d; j += 1) media[j] += x[j];
  for (let j = 0; j < d; j += 1) media[j] /= n;
  for (const x of filas) for (let j = 0; j < d; j += 1) { const v = x[j] - media[j]; escala[j] += v * v; }
  for (let j = 0; j < d; j += 1) {
    const s = Math.sqrt(escala[j] / n);
    escala[j] = s < 10 * Number.EPSILON * Math.max(1, Math.abs(media[j])) ? 1 : s;
  }
  return { media, escala };
}

const gini = (cuentas, n) => {
  let s = 0;
  for (let c = 0; c < cuentas.length; c += 1) { const p = cuentas[c] / n; s += p * p; }
  return 1 - s;
};

/**
 * Entrena el bosque. filas: Float32Array[] (features sin escalar), y: índices de clase.
 * Devuelve { media, escala, arboles } con los árboles en arreglos planos.
 */
export function entrenarBosque(filas, y, nClases, { arboles = 200, minHoja = 2, semilla = 42, alProgreso = null } = {}) {
  const n = filas.length;
  const d = filas[0].length;
  const { media, escala } = ajustarEscala(filas, d);
  // Columnas ya escaladas (float32, igual que al predecir): col[j][i]
  const X = new Float32Array(d * n);
  for (let i = 0; i < n; i += 1) {
    const x = filas[i];
    for (let j = 0; j < d; j += 1) X[j * n + i] = f(f(x[j] - media[j]) / escala[j]);
  }
  const maxRasgos = Math.max(1, Math.floor(Math.sqrt(d)));
  const r = azar(semilla);
  const orden = new Int32Array(d);
  const valores = new Float64Array(n);
  const resultado = [];

  for (let t = 0; t < arboles; t += 1) {
    const muestra = new Int32Array(n);
    for (let i = 0; i < n; i += 1) muestra[i] = r.entero(n);             // bootstrap
    const izq = []; const der = []; const rasgo = []; const umbral = []; const hojas = [];
    const nuevoNodo = () => { izq.push(-1); der.push(-1); rasgo.push(0); umbral.push(0); return izq.length - 1; };
    const pila = [[nuevoNodo(), muestra]];
    while (pila.length) {
      const [nodo, idx] = pila.pop();
      const m = idx.length;
      const cuentas = new Float64Array(nClases);
      for (let k = 0; k < m; k += 1) cuentas[y[idx[k]]] += 1;
      let mejor = null;
      const puro = cuentas.some((c) => c === m);
      if (!puro && m >= 2 * minHoja) {
        const base = gini(cuentas, m) * m;
        for (let j = 0; j < d; j += 1) orden[j] = j;
        let vistos = 0; let validos = 0;
        while (validos < maxRasgos && vistos < d) {
          const k = vistos + r.entero(d - vistos);                         // sin repetir, como scikit-learn
          const j = orden[k]; orden[k] = orden[vistos]; orden[vistos] = j; vistos += 1;
          const col = j * n;
          let lo = Infinity; let hi = -Infinity;
          for (let q = 0; q < m; q += 1) { const v = X[col + idx[q]]; if (v < lo) lo = v; if (v > hi) hi = v; }
          if (hi <= lo) continue;                                          // constante en este nodo
          validos += 1;
          const ord = Array.from(idx).sort((a, b) => X[col + a] - X[col + b]);
          for (let q = 0; q < m; q += 1) valores[q] = X[col + ord[q]];
          const ci = new Float64Array(nClases);
          for (let p = 0; p < m - 1; p += 1) {
            ci[y[ord[p]]] += 1;
            const ni = p + 1;
            if (valores[p] === valores[p + 1] || ni < minHoja || m - ni < minHoja) continue;
            let si = 0; let sd = 0;
            for (let c = 0; c < nClases; c += 1) { const a = ci[c]; const b = cuentas[c] - a; si += a * a; sd += b * b; }
            const costo = ni - si / ni + (m - ni) - sd / (m - ni);             // ni·gini_izq + nd·gini_der
            if (costo < base - 1e-12 && (!mejor || costo < mejor.costo)) {
              let u = valores[p] / 2 + valores[p + 1] / 2;
              if (u === valores[p + 1] || !Number.isFinite(u)) u = valores[p];
              mejor = { costo, j, u };
            }
          }
        }
      }
      if (!mejor) {
        rasgo[nodo] = hojas.length;
        hojas.push(Array.from(cuentas, (c) => c / m));
        continue;
      }
      const a = []; const b = [];
      const col = mejor.j * n;
      for (let q = 0; q < m; q += 1) (X[col + idx[q]] <= mejor.u ? a : b).push(idx[q]);
      rasgo[nodo] = mejor.j;
      umbral[nodo] = mejor.u;
      izq[nodo] = nuevoNodo();
      der[nodo] = nuevoNodo();
      pila.push([der[nodo], Int32Array.from(b)], [izq[nodo], Int32Array.from(a)]);
    }
    resultado.push({ izq, der, rasgo, umbral, hojas });
    if (alProgreso) alProgreso(t + 1, arboles);
  }
  return { media, escala, arboles: resultado };
}

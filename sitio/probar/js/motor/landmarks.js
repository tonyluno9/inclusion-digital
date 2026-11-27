// Port de app/modules/landmarks.py: formato crudo (147 valores) y features (260 por frame).
//
// numpy hace estas cuentas en float32: aquí cada operación se redondea con Math.fround en el
// mismo orden que numpy, para que las features salgan iguales (y caigan del mismo lado de cada
// umbral del traductor). Un frame es un Float32Array(147); una secuencia, un arreglo de frames.
const f = Math.fround;

export const HAND_POINTS = 21;
export const HAND_SIZE = HAND_POINTS * 3;            // 63
export const HANDS_SIZE = HAND_SIZE * 2;             // 126
export const POSE_POINTS = [0, 11, 12, 13, 14, 15, 16];
export const POSE_SIZE = POSE_POINTS.length * 3;     // 21
export const BODY_SIZE = 9;
export const ARMS_START = HANDS_SIZE + BODY_SIZE;    // 135
export const RAW_FRAME_SIZE = HANDS_SIZE + POSE_SIZE;
export const OLD_RAW_FRAME_SIZE = HANDS_SIZE + BODY_SIZE;
export const ARM_FEATURES = 8;
export const FEATURE_FRAME_SIZE = HANDS_SIZE * 2 + ARM_FEATURES;   // 260
export const DEFAULT_SCALE = 0.3;
export const MAX_GAP_FRAMES = 5;
export const HAND_SLOTS = { izquierda: 0, derecha: 1 };

const F_1E3 = f(1e-3);

// ------------------------------------------------------------- utilidades numpy
/** np.rint: redondeo a entero con empates al par (np.round). */
export function rint(x) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 ? 2 * Math.round(x / 2) : r;
}

/** np.linspace(0, n - 1, largo) (float64), igual que numpy 2. */
export function linspace(n, largo) {
  const delta = n - 1;
  const div = largo - 1;
  const y = new Array(largo);
  if (div > 0) {
    const step = delta / div;
    for (let i = 0; i < largo; i += 1) y[i] = step === 0 ? (i / div) * delta : i * step;
    y[largo - 1] = delta;
  } else {
    for (let i = 0; i < largo; i += 1) y[i] = i * delta;
  }
  return y;
}

/** np.median de valores float32 (el promedio de los dos del centro, en float32). */
export function median32(valores) {
  const v = Float32Array.from(valores).sort();
  const n = v.length;
  const m = n >> 1;
  return n % 2 ? v[m] : f(f(v[m - 1] + v[m]) / 2);
}

/** np.linalg.norm de un vector float32 de 2 valores. */
function norm2(x, y) {
  return f(Math.sqrt(f(f(x * x) + f(y * y))));
}

const algo = (a, ini, fin) => {
  for (let i = ini; i < fin; i += 1) if (a[i] !== 0) return true;
  return false;
};

// ------------------------------------------------------------------- manos
/**
 * Lugar (0 = izquierda, 1 = derecha) de cada mano detectada; ver assign_slots en Python.
 * detecciones: [[slot según MediaPipe, confianza, [x, y] de la muñeca]]; previas: [[x, y] | null, ...].
 */
export function assignSlots(detecciones, previas, maxJump = 0.25) {
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const porEtiqueta = () => {
    const orden = detecciones.map((_, i) => i).sort((i, j) => -detecciones[i][1] + detecciones[j][1]);
    const slots = new Array(detecciones.length).fill(null);
    const usados = new Set();
    for (const i of orden) {
      let s = detecciones[i][0];
      if (usados.has(s)) s = 1 - s;
      usados.add(s);
      slots[i] = s;
    }
    return slots;
  };
  detecciones = detecciones.slice(0, 2);
  const conocidas = [0, 1].filter((s) => previas[s] !== null && previas[s] !== undefined);
  if (!detecciones.length || !conocidas.length) return porEtiqueta();

  if (detecciones.length === 1) {
    const w = detecciones[0][2];
    let mejor = conocidas[0];
    for (const s of conocidas) if (dist(w, previas[s]) < dist(w, previas[mejor])) mejor = s;
    return dist(w, previas[mejor]) < maxJump ? [mejor] : porEtiqueta();
  }
  const a = detecciones[0][2];
  const b = detecciones[1][2];
  if (conocidas.length === 2) {
    const quedar = dist(a, previas[0]) + dist(b, previas[1]);
    const cambiar = dist(a, previas[1]) + dist(b, previas[0]);
    if (Math.min(quedar, cambiar) < 2 * maxJump) return quedar <= cambiar ? [0, 1] : [1, 0];
    return porEtiqueta();
  }
  const s = conocidas[0];
  const cerca = dist(a, previas[s]) <= dist(b, previas[s]) ? 0 : 1;
  if (dist(detecciones[cerca][2], previas[s]) >= maxJump) return porEtiqueta();
  const slots = [1 - s, 1 - s];
  slots[cerca] = s;
  return slots;
}

export const handsPresent = (frame) => algo(frame, 0, HANDS_SIZE);

/** Con una sola mano ("derecha" o "izquierda") borra la otra; con "dos" deja el frame igual. */
export function keepHands(frame, modo) {
  if (!(modo in HAND_SLOTS)) return frame;
  const out = Float32Array.from(frame);
  const otra = 1 - HAND_SLOTS[modo];
  out.fill(0, otra * HAND_SIZE, (otra + 1) * HAND_SIZE);
  return out;
}

/** Fracción de los frames en que se ve cada mano. */
export function handCoverage(frames) {
  const out = {};
  for (const [lado, s] of Object.entries(HAND_SLOTS)) {
    if (!frames.length) { out[lado] = 0; continue; }
    let n = 0;
    for (const fr of frames) if (algo(fr, s * HAND_SIZE, (s + 1) * HAND_SIZE)) n += 1;
    out[lado] = n / frames.length;
  }
  return out;
}

/** Manos que la seña necesita y que se vieron en menos de `minCoverage` de los frames. */
export function missingHands(frames, modo, minCoverage) {
  const necesarias = modo === 'dos' ? Object.keys(HAND_SLOTS) : [modo];
  const cob = handCoverage(frames);
  return necesarias.filter((lado) => cob[lado] < minCoverage);
}

/** Frames de 135 valores (formato anterior) -> 147, con ceros en codos y muñecas. */
export function upgradeRaw(frames) {
  return frames.map((fr) => {
    if (fr.length === RAW_FRAME_SIZE) return Float32Array.from(fr);
    if (fr.length !== OLD_RAW_FRAME_SIZE) throw new Error(`frame de ${fr.length} valores: se esperaban ${RAW_FRAME_SIZE} u ${OLD_RAW_FRAME_SIZE}`);
    const out = new Float32Array(RAW_FRAME_SIZE);
    out.set(fr);
    return out;
  });
}

function slotsDe(ancho) {
  const s = [[0, HAND_SIZE], [HAND_SIZE, HANDS_SIZE]];
  if (ancho >= RAW_FRAME_SIZE) {
    s.push([HANDS_SIZE, ARMS_START]);
    for (let i = ARMS_START; i < RAW_FRAME_SIZE; i += 3) s.push([i, i + 3]);
  }
  return s;
}

/** Rellena por interpolación huecos cortos (hasta `maxGap` frames) de cada parte. */
export function fillGaps(frames, maxGap = MAX_GAP_FRAMES) {
  const out = frames.map((fr) => Float32Array.from(fr));
  if (!out.length) return out;
  for (const [ini, fin] of slotsDe(out[0].length)) {
    const idx = [];
    out.forEach((fr, i) => { if (algo(fr, ini, fin)) idx.push(i); });
    for (let p = 0; p + 1 < idx.length; p += 1) {
      const a = idx[p];
      const b = idx[p + 1];
      const hueco = b - a - 1;
      if (hueco > 0 && hueco <= maxGap) {
        for (let k = 1; k <= hueco; k += 1) {
          // En Python los índices salen de np.flatnonzero (np.int64), así que t es np.float64:
          // numpy hace la cuenta en float64 y redondea a float32 una sola vez, al guardar
          const t = k / (hueco + 1);
          for (let j = ini; j < fin; j += 1) out[a + k][j] = (1 - t) * out[a][j] + t * out[b][j];
        }
      }
    }
  }
  return out;
}

/** Quita los frames sin manos al principio y al final. */
export function trim(frames) {
  let ini = -1;
  let fin = -1;
  frames.forEach((fr, i) => {
    if (handsPresent(fr)) { if (ini < 0) ini = i; fin = i; }
  });
  return ini < 0 ? [] : frames.slice(ini, fin + 1);
}

/** Índices que usa resample (vecino más cercano). */
export function resampleIndices(n, largo) {
  return linspace(n, largo).map(rint);
}

export function resample(frames, largo) {
  return resampleIndices(frames.length, largo).map((i) => frames[i]);
}

/** True si el frame trae ambos hombros. */
export function poseValid(frame) {
  if (frame.length < RAW_FRAME_SIZE) return false;
  return algo(frame, HANDS_SIZE + 3, HANDS_SIZE + 6) && algo(frame, HANDS_SIZE + 6, HANDS_SIZE + 9);
}

/** True si el frame trae al menos un codo. */
export function elbowsVisible(frame) {
  if (frame.length < RAW_FRAME_SIZE) return false;
  return algo(frame, ARMS_START, ARMS_START + 6);
}

/** Quita las manos cuya muñeca está más de `margen` anchos de hombro por debajo de los hombros. */
export function dropRestingHands(frame, body, margen) {
  if (!body) return frame;
  const s0x = f(body[3]); const s0y = f(body[4]);
  const s1x = f(body[6]); const s1y = f(body[7]);
  const ancho = norm2(f(s0x - s1x), f(s0y - s1y));
  if (ancho < 1e-3) return frame;
  const limite = f(f(f(s0y + s1y) / 2) + f(margen * ancho));
  let out = null;
  for (const ini of [0, HAND_SIZE]) {
    if (algo(frame, ini, ini + HAND_SIZE) && frame[ini + 1] > limite) {
      if (!out) out = Float32Array.from(frame);
      out.fill(0, ini, ini + HAND_SIZE);
    }
  }
  return out || frame;
}

const hombrosVisibles = (fr, base) => (fr[base + 3] !== 0 || fr[base + 4] !== 0) && (fr[base + 6] !== 0 || fr[base + 7] !== 0);

/** Mediana de la pose (21 valores) en los frames con ambos hombros; null si hay menos de `minValid`. */
export function bodyReferencePose(frames, minValid = 3) {
  if (!frames.length || frames[0].length < RAW_FRAME_SIZE) return null;
  const validos = frames.filter((fr) => hombrosVisibles(fr, HANDS_SIZE));
  if (validos.length < minValid) return null;
  const out = new Float32Array(POSE_SIZE);
  for (let j = 0; j < POSE_SIZE; j += 1) out[j] = median32(validos.map((fr) => fr[HANDS_SIZE + j]));
  return out;
}

/** Recortar, rellenar huecos y remuestrear (lo mismo al grabar y al detectar). */
export function prepareSequence(frames, largo, minFrames, body = null) {
  if (!frames.length) return null;
  const recortada = trim(frames);
  if (recortada.length < minFrames) return null;
  let out = resample(fillGaps(recortada), largo);
  if (body && out[0].length >= RAW_FRAME_SIZE) {
    out = out.map((fr) => {
      const c = Float32Array.from(fr);
      for (let j = 0; j < BODY_SIZE; j += 1) c[HANDS_SIZE + j] = f(body[j]);
      return c;
    });
  } else {
    out = out.map((fr) => Float32Array.from(fr));
  }
  return out;
}

function referenciaCuerpo(seq) {
  const validos = seq.filter((fr) => hombrosVisibles(fr, HANDS_SIZE));
  if (validos.length) {
    const lx = median32(validos.map((fr) => fr[HANDS_SIZE + 3]));
    const ly = median32(validos.map((fr) => fr[HANDS_SIZE + 4]));
    const rx = median32(validos.map((fr) => fr[HANDS_SIZE + 6]));
    const ry = median32(validos.map((fr) => fr[HANDS_SIZE + 7]));
    const escala = norm2(f(lx - rx), f(ly - ry));
    if (escala > 1e-3) return [f(f(lx + rx) / 2), f(f(ly + ry) / 2), escala];
  }
  // Sin cuerpo visible: centrar en las manos con una escala típica
  let sx = 0; let sy = 0; let n = 0;
  for (const fr of seq) {
    for (let p = 0; p < HANDS_SIZE; p += 3) {
      if (fr[p] !== 0 || fr[p + 1] !== 0 || fr[p + 2] !== 0) { sx = f(sx + fr[p]); sy = f(sy + fr[p + 1]); n += 1; }
    }
  }
  return n ? [f(sx / n), f(sy / n), f(DEFAULT_SCALE)] : [0, 0, f(DEFAULT_SCALE)];
}

/** (T, 147) crudo -> T Float32Array(260): posición, forma de la mano y brazos. */
export function sequenceFeatures(seq) {
  const [cx, cy, escala] = referenciaCuerpo(seq);
  return seq.map((fr) => {
    const out = new Float32Array(FEATURE_FRAME_SIZE);
    for (let m = 0; m < 2; m += 1) {
      const base = m * HAND_SIZE;
      if (!algo(fr, base, base + HAND_SIZE)) continue;
      const wx = fr[base]; const wy = fr[base + 1]; const wz = fr[base + 2];
      const tx = f(fr[base + 27] - wx); const ty = f(fr[base + 28] - wy);   // muñeca -> nudillo del medio
      const tam = Math.max(norm2(tx, ty), F_1E3);
      for (let p = 0; p < HAND_POINTS; p += 1) {
        const i = base + p * 3;
        out[i] = f(f(fr[i] - cx) / escala);
        out[i + 1] = f(f(fr[i + 1] - cy) / escala);
        out[i + 2] = f(fr[i + 2] / escala);
        const o = HANDS_SIZE + i;
        out[o] = f(f(fr[i] - wx) / tam);
        out[o + 1] = f(f(fr[i + 1] - wy) / tam);
        out[o + 2] = f(f(fr[i + 2] - wz) / tam);
      }
    }
    for (let k = 0; k < 4; k += 1) {           // codo izq., codo der., muñeca izq., muñeca der.
      const x = fr[ARMS_START + k * 3]; const y = fr[ARMS_START + k * 3 + 1];
      if (x === 0 && y === 0) continue;
      out[HANDS_SIZE * 2 + k * 2] = f(f(x - cx) / escala);
      out[HANDS_SIZE * 2 + k * 2 + 1] = f(f(y - cy) / escala);
    }
    return out;
  });
}

/** Espejo de una secuencia de features: intercambia izquierda y derecha e invierte x (zurdos). */
export function mirrorFeatures(feat) {
  return feat.map((fr) => {
    const out = new Float32Array(FEATURE_FRAME_SIZE);
    for (let bloque = 0; bloque < 2; bloque += 1) {
      for (let m = 0; m < 2; m += 1) {
        const de = bloque * HANDS_SIZE + (1 - m) * HAND_SIZE;
        const a = bloque * HANDS_SIZE + m * HAND_SIZE;
        for (let j = 0; j < HAND_SIZE; j += 1) out[a + j] = j % 3 === 0 ? -fr[de + j] : fr[de + j];
      }
    }
    const A = HANDS_SIZE * 2;
    for (let parte = 0; parte < 2; parte += 1) {
      for (let lado = 0; lado < 2; lado += 1) {
        const de = A + parte * 4 + (1 - lado) * 2;
        const a = A + parte * 4 + lado * 2;
        out[a] = -fr[de];
        out[a + 1] = fr[de + 1];
      }
    }
    return out;
  });
}

/** Features de una secuencia aplanadas en un solo Float32Array (como reshape(1, -1)). */
export function aplanar(feat) {
  const out = new Float32Array(feat.length * FEATURE_FRAME_SIZE);
  feat.forEach((fr, i) => out.set(fr, i * FEATURE_FRAME_SIZE));
  return out;
}

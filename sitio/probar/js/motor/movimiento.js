// Port de app/modules/motion.py: movimiento 3D para el avatar (frames «world», suavizado, clips).
//
// Un frame de movimiento es { pose: 33×[x,y,z] | null, vis: 33 | null, left: 21×[x,y,z] | null, right: ... }
// en metros, con origen en el centro de las caderas: x hacia la izquierda de la persona, y hacia
// arriba, z hacia la cámara. Es el mismo formato del evento {mundo} de servidor_web.py y de los
// clips «inclusion-movimiento» v1, así avatar.js lo usa sin cambios. Los valores van en float32.
const f = Math.fround;

export const CLIP_FORMAT = 'inclusion-movimiento';
export const CLIP_VERSION = 1;
export const COORDS = 'metros; origen en el centro de las caderas; x hacia la izquierda de la persona, '
  + 'y hacia arriba, z hacia adelante (hacia la cámara)';
export const POSE_NAMES = [
  'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer', 'right_eye_inner', 'right_eye',
  'right_eye_outer', 'left_ear', 'right_ear', 'mouth_left', 'mouth_right', 'left_shoulder',
  'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist', 'left_pinky',
  'right_pinky', 'left_index', 'right_index', 'left_thumb', 'right_thumb', 'left_hip', 'right_hip',
  'left_knee', 'right_knee', 'left_ankle', 'right_ankle', 'left_heel', 'right_heel',
  'left_foot_index', 'right_foot_index',
];
export const HAND_NAMES = [
  'wrist', 'thumb_cmc', 'thumb_mcp', 'thumb_ip', 'thumb_tip', 'index_finger_mcp', 'index_finger_pip',
  'index_finger_dip', 'index_finger_tip', 'middle_finger_mcp', 'middle_finger_pip', 'middle_finger_dip',
  'middle_finger_tip', 'ring_finger_mcp', 'ring_finger_pip', 'ring_finger_dip', 'ring_finger_tip',
  'pinky_mcp', 'pinky_pip', 'pinky_dip', 'pinky_tip',
];
export const POSE_LR_PAIRS = [[1, 4], [2, 5], [3, 6], [7, 8], [9, 10], [11, 12], [13, 14], [15, 16], [17, 18],
  [19, 20], [21, 22], [23, 24], [25, 26], [27, 28], [29, 30], [31, 32]];
export const LEFT_WRIST = 15;
export const RIGHT_WRIST = 16;
export const PARTS = ['pose', 'left', 'right'];
const ARM_POINTS = { left: [11, 13, 15, 17, 19, 21], right: [12, 14, 16, 18, 20, 22] };
export const HANDS_TO_SIDE = { derecha: 'right', izquierda: 'left' };

const puntos32 = (pts) => pts.map((p) => [f(p[0]), f(p[1]), f(p[2])]);
const copiar = (pts) => (pts ? pts.map((p) => (Array.isArray(p) ? p.slice() : p)) : pts);

export const emptyWorld = () => ({ pose: null, vis: null, left: null, right: null });

/** Frame de movimiento a partir de los world landmarks de MediaPipe sobre la imagen en espejo
 *  (pose ya en orden anatómico): invertir los tres ejes deja x a la izquierda, y arriba, z adelante. */
export function worldFrame(pose, vis, hands) {
  const out = emptyWorld();
  if (pose) {
    out.pose = pose.map((p) => [-f(p[0]), -f(p[1]), -f(p[2])]);
    out.vis = vis ? vis.map((v) => f(v)) : pose.map(() => 1);
  }
  if (!out.pose) return out;
  for (const [lado, muneca, i] of [['left', LEFT_WRIST, 0], ['right', RIGHT_WRIST, 1]]) {
    const mano = hands[i];
    if (!mano) continue;
    const h = mano.map((p) => [-f(p[0]), -f(p[1]), -f(p[2])]);
    const w = out.pose[muneca];
    out[lado] = h.map((p) => [0, 1, 2].map((j) => f(f(p[j] - h[0][j]) + w[j])));
  }
  return out;
}

/** Lado ("left"/"right") que no participa en una seña de una mano; null si es de dos. */
export function restingSide(manos) {
  const lado = HANDS_TO_SIDE[manos];
  return lado === undefined ? null : (lado === 'right' ? 'left' : 'right');
}

/** Deja el brazo `lado` colgando junto al cuerpo y sin mano (seña de una mano). */
export function restArm(world, lado) {
  const out = { ...world, [lado]: null };
  if (!world.pose) return out;
  const pose = puntos32(world.pose);
  const vis = world.vis ? world.vis.map((v) => f(v)) : pose.map(() => 1);
  const [hombro, codo, muneca, menique, indice, pulgar] = ARM_POINTS[lado];
  const fuera = lado === 'left' ? 1 : -1;
  const sumar = (p, d) => [f(p[0] + d[0]), f(p[1] + d[1]), f(p[2] + d[2])];
  pose[codo] = sumar(pose[hombro], [0.06 * fuera, -0.28, -0.01]);
  pose[muneca] = sumar(pose[codo], [0.015 * fuera, -0.245, 0.07]);
  for (const [i, dx] of [[menique, 0.02], [indice, -0.01], [pulgar, -0.02]]) pose[i] = sumar(pose[muneca], [dx * fuera, -0.07, 0.02]);
  for (const i of [codo, muneca, menique, indice, pulgar]) vis[i] = 1;
  out.pose = pose;
  out.vis = vis;
  return out;
}

// ----------------------------------------------------------------- suavizado
const alfa = (cutoff, dt) => 1 / (1 + (1 / (2 * Math.PI * cutoff)) / dt);
const DOS_PI32 = f(2 * Math.PI);

/** Filtro One Euro (Casiez et al., 2012), con las cuentas en float32 como numpy. */
export class OneEuroFilter {
  constructor({ minCutoff = 1.5, beta = 0.5, dCutoff = 1.0 } = {}) {
    Object.assign(this, { minCutoff, beta, dCutoff });
    this.reset();
  }

  reset() { this._x = null; this._dx = null; this._t = null; }

  /** x: Float32Array (cualquier tamaño fijo). */
  filtrar(x, t) {
    x = Float32Array.from(x);
    if (this._x === null || this._x.length !== x.length || t <= this._t) {
      this._x = x; this._dx = new Float32Array(x.length); this._t = t;
      return x;
    }
    const dt = t - this._t;
    const dt32 = f(dt);
    const aD = alfa(this.dCutoff, dt);
    const aD32 = f(aD); const unoMenosAD = f(1 - aD);
    const minC = f(this.minCutoff); const beta = f(this.beta);
    const out = new Float32Array(x.length);
    for (let i = 0; i < x.length; i += 1) {
      const dx = f(f(x[i] - this._x[i]) / dt32);
      const ddx = f(f(aD32 * dx) + f(unoMenosAD * this._dx[i]));
      this._dx[i] = ddx;
      const cutoff = f(minC + f(beta * Math.abs(ddx)));
      const tau = f(1 / f(DOS_PI32 * cutoff));
      const a = f(1 / f(1 + f(tau / dt32)));
      out[i] = f(f(a * x[i]) + f(f(1 - a) * this._x[i]));
    }
    this._x = out;
    this._t = t;
    return Float32Array.from(out);
  }
}

const plano = (pts) => Float32Array.from(pts.flat());
const puntos = (a) => Array.from({ length: a.length / 3 }, (_, i) => [a[i * 3], a[i * 3 + 1], a[i * 3 + 2]]);

/** Un filtro por parte; si una parte desaparece, su filtro empieza de nuevo. */
export class LiveSmoother {
  constructor(opciones) { this.filtros = Object.fromEntries(PARTS.map((p) => [p, new OneEuroFilter(opciones)])); }

  suavizar(world, t) {
    const out = { ...world };
    for (const p of PARTS) {
      if (!world[p]) this.filtros[p].reset();
      else out[p] = puntos(this.filtros[p].filtrar(plano(world[p]), t));
    }
    return out;
  }
}

// --------------------------------------------------------------------- clips
const mezclar = (A, B, w) => {
  const c1 = f(1 - w); const c2 = f(w);
  const m = (a, b) => f(f(c1 * a) + f(c2 * b));
  return A.map((p, i) => (Array.isArray(p) ? p.map((v, j) => m(v, B[i][j])) : m(p, B[i])));
};

/** Rellena por interpolación huecos cortos de cada parte (pose y manos). */
export function fillShortGaps(frames, maxGap = 5) {
  frames = frames.map((fr) => ({ ...fr }));
  for (const parte of PARTS) {
    const idx = [];
    frames.forEach((fr, i) => { if (fr[parte]) idx.push(i); });
    for (let p = 0; p + 1 < idx.length; p += 1) {
      const a = idx[p]; const b = idx[p + 1];
      const hueco = b - a - 1;
      if (hueco > 0 && hueco <= maxGap) {
        for (let k = 1; k <= hueco; k += 1) {
          const w = k / (hueco + 1);
          frames[a + k][parte] = mezclar(frames[a][parte], frames[b][parte], w);
          if (parte === 'pose') frames[a + k].vis = mezclar(frames[a].vis, frames[b].vis, w);
        }
      }
    }
  }
  return frames;
}

/** Junta los frames de una seña, con unos frames de antes (para que empiece en reposo). */
export class MotionRecorder {
  constructor(prerollFrames = 15, maxFrames = 600) {
    this.preroll = Math.max(1, prerollFrames);
    this._recent = [];
    this.maxFrames = maxFrames;
    this.frames = null;
  }

  get recording() { return this.frames !== null; }

  push(world, t) {
    if (this.frames === null) {
      this._recent.push([t, world]);
      if (this._recent.length > this.preroll) this._recent.shift();
    } else if (this.frames.length < this.maxFrames) {
      this.frames.push([t, world]);
    }
  }

  begin() { this.frames = this._recent; this._recent = []; }

  cancel() { this.frames = null; }

  finish() { const fr = this.frames || []; this.frames = null; return fr; }
}

const r4 = (x) => { const y = x * 10000; const r = Math.round(y); return (Math.abs(y % 1) === 0.5 ? 2 * Math.round(y / 2) : r) / 10000; };
const redondear = (a) => (a ? a.map((p) => (Array.isArray(p) ? p.map(r4) : r4(p))) : null);
/** round() de Python (sin empates posibles con 2-4 decimales en binario). */
export const redondeo = (x, d) => Number(x.toFixed(d));

export function frameToJson(world, t) {
  return { t: redondeo(t, 4), pose: redondear(world.pose), vis: redondear(world.vis), left: redondear(world.left), right: redondear(world.right) };
}

function ahora() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** Clip listo para guardar a partir de [[t, frame]]. Rellena huecos cortos. */
export function makeClip(timedFrames, word, person = 'anonimo', hands = 'dos', created = ahora()) {
  if (!timedFrames.length) throw new Error('el clip no tiene frames');
  const t0 = timedFrames[0][0];
  const tiempos = timedFrames.map(([t]) => t - t0);
  const frames = fillShortGaps(timedFrames.map(([, fr]) => fr));
  const duracion = tiempos[tiempos.length - 1];
  const fps = duracion > 0 ? (tiempos.length - 1) / duracion : 30.0;
  return {
    format: CLIP_FORMAT, version: CLIP_VERSION, word, person, hands, created,
    fps: redondeo(fps, 2), duration: redondeo(duracion, 3), coords: COORDS,
    pose_names: POSE_NAMES, hand_names: HAND_NAMES,
    frames: frames.map((fr, i) => frameToJson(fr, tiempos[i])),
  };
}

/** Copia del clip con solo los frames entre `inicio` y `fin` (s); el tiempo vuelve a empezar en 0. */
export function trimClip(clip, inicio, fin) {
  inicio = Number(inicio); fin = Number(fin);
  const frames = clip.frames.filter((fr) => inicio - 1e-6 <= fr.t && fr.t <= fin + 1e-6);
  if (frames.length < 2) throw new Error('el recorte es demasiado corto');
  const t0 = frames[0].t;
  const out = { ...clip, frames: frames.map((fr) => ({ ...fr, t: redondeo(fr.t - t0, 4) })) };
  const duracion = out.frames[out.frames.length - 1].t;
  out.duration = redondeo(duracion, 3);
  out.fps = duracion > 0 ? redondeo((frames.length - 1) / duracion, 2) : (clip.fps ?? 30.0);
  out.trimmed_from = [redondeo(inicio, 3), redondeo(fin, 3)];
  return out;
}

export function validateClip(clip) {
  if (!clip || typeof clip !== 'object' || clip.format !== CLIP_FORMAT) throw new Error('no es un clip de movimiento de INCLUSION');
  if (clip.version !== CLIP_VERSION) throw new Error(`versión de clip ${clip.version} no soportada (se espera ${CLIP_VERSION})`);
  if (!clip.frames || !clip.frames.length) throw new Error('el clip no tiene frames');
  return clip;
}

export { copiar };

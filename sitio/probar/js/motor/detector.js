// Port de app/modules/landmark_detector.py (sin MediaPipe: eso está en camara.js).
//
// Recibe los resultados de HandLandmarker y PoseLandmarker calculados sobre la imagen YA
// INVERTIDA EN ESPEJO (como hace inclusion_app.py con cv2.flip antes de detectar) y arma:
// - el frame crudo de 147 valores para el traductor (x multiplicada por ancho/alto);
// - el frame «world» en 3D para el avatar;
// - lo que hay que dibujar encima del video (manos y brazos).
// Izquierda y derecha son siempre las de la persona.
import { HAND_SIZE, HANDS_SIZE, POSE_POINTS, RAW_FRAME_SIZE, assignSlots } from './landmarks.js';
import { POSE_LR_PAIRS, emptyWorld, worldFrame } from './movimiento.js';

export const MIN_VISIBILITY = 0.5;
export const WORLD_HOLD_FRAMES = 5;
export const WRIST_MATCH = 0.15;
export const ARM_CHAINS = [[11, 13, 15], [12, 14, 16]];
export const HAND_CONNECTIONS = [[0, 1], [1, 5], [9, 13], [13, 17], [5, 9], [0, 17], [1, 2], [2, 3], [3, 4], [5, 6], [6, 7],
  [7, 8], [9, 10], [10, 11], [11, 12], [13, 14], [14, 15], [15, 16], [17, 18], [18, 19], [19, 20]];
const f = Math.fround;

/** Lado (0 = izquierda, 1 = derecha de la persona) de una mano: la muñeca del cuerpo más cercana,
 *  o si no se ve el cuerpo, la etiqueta de MediaPipe invertida. */
export function handSlotHint(label, wrist, poseWrists) {
  if (poseWrists.every((p) => p !== null && p !== undefined)) {
    const d = poseWrists.map((p) => Math.hypot(wrist[0] - p[0], wrist[1] - p[1]));
    const lado = d[1] < d[0] ? 1 : 0;
    if (d[lado] < WRIST_MATCH) return lado;
  }
  return label === 'Left' ? 1 : 0;
}

/** Índices de la pose reordenados para que left_* sea el lado izquierdo de la persona. */
export function anatomicalOrder(hombroIzqX, hombroDerX) {
  const orden = Array.from({ length: 33 }, (_, i) => i);
  if (hombroIzqX > hombroDerX) for (const [a, b] of POSE_LR_PAIRS) { orden[a] = b; orden[b] = a; }
  return orden;
}

const xyz = (p) => [p.x, p.y, p.z];

export class Detector {
  constructor() {
    this._prevWrists = [null, null];
    this._wristAge = [0, 0];
    this._lastPose = new Float32Array(RAW_FRAME_SIZE - HANDS_SIZE);
    this._lastArms = [[], []];          // puntos (0..1 de la imagen) de cada brazo, para dibujarlos
    this._poseWrists = [null, null];
    this._lastWorldPose = null;
    this._lastVis = null;
    this._worldAge = 0;
    this.world = emptyWorld();
  }

  /**
   * manos: HandLandmarkerResult; cuerpo: PoseLandmarkerResult o null si no se calculó en este frame.
   * Devuelve { raw: Float32Array(147), world, dibujo: { manos: [{ lado, puntos }], brazos: [[...], [...]] } }.
   */
  procesar(manos, cuerpo, ancho, alto) {
    const aspecto = ancho / alto;
    const raw = new Float32Array(RAW_FRAME_SIZE);
    if (cuerpo) this._actualizarCuerpo(cuerpo, aspecto);

    const lista = (manos.landmarks || []).slice(0, 2);
    const lados = manos.handedness || manos.handednesses || [];
    const detecciones = lista.map((lm, i) => {
      const muneca = [lm[0].x * aspecto, lm[0].y];
      const cat = lados[i] && lados[i][0] ? lados[i][0] : { categoryName: '', score: 0 };
      return [handSlotHint(cat.categoryName, muneca, this._poseWrists), cat.score, muneca];
    });
    const slots = assignSlots(detecciones, this._prevWrists);
    this._wristAge = this._wristAge.map((e) => e + 1);
    slots.forEach((s, i) => { this._prevWrists[s] = detecciones[i][2]; this._wristAge[s] = 0; });
    this._prevWrists = this._prevWrists.map((w, s) => (this._wristAge[s] <= 5 ? w : null));

    const worldManos = [null, null];
    const mundoLista = manos.worldLandmarks || [];
    const dibujo = { manos: [], brazos: this._lastArms };
    lista.forEach((lm, i) => {
      const s = slots[i];
      const off = s * HAND_SIZE;
      const wz = lm[0].z;
      lm.forEach((p, k) => {
        raw[off + k * 3] = p.x * aspecto;
        raw[off + k * 3 + 1] = p.y;
        raw[off + k * 3 + 2] = p.z - wz;
      });
      if (mundoLista[i]) worldManos[s] = mundoLista[i].map(xyz);
      dibujo.manos.push({ lado: s, puntos: lm.map((p) => [p.x, p.y]) });
    });
    raw.set(this._lastPose, HANDS_SIZE);
    this.world = worldFrame(this._lastWorldPose, this._lastVis, worldManos);
    return { raw, world: this.world, dibujo };
  }

  _actualizarCuerpo(resultado, aspecto) {
    this._lastPose.fill(0);
    this._lastArms = [[], []];
    this._poseWrists = [null, null];
    // MediaPipe a veces pierde el cuerpo un frame: para el avatar se conserva unos frames
    this._worldAge += 1;
    if (this._worldAge > WORLD_HOLD_FRAMES) { this._lastWorldPose = null; this._lastVis = null; }
    if (!resultado.landmarks || !resultado.landmarks.length) return;
    const original = resultado.landmarks[0];
    const orden = anatomicalOrder(original[11].x, original[12].x);
    const pose = orden.map((i) => original[i]);
    const visible = (i) => (pose[i].visibility || 0) > MIN_VISIBILITY;
    const hombros = visible(11) && visible(12);
    POSE_POINTS.forEach((i, k) => {
      if ((k < 3 && hombros) || (k >= 3 && visible(i))) {
        this._lastPose[k * 3] = pose[i].x * aspecto;
        this._lastPose[k * 3 + 1] = pose[i].y;
        this._lastPose[k * 3 + 2] = pose[i].z;
      }
    });
    ARM_CHAINS.forEach((cadena, lado) => {
      const pts = [];
      for (const i of cadena) {
        if (!visible(i)) break;
        pts.push([pose[i].x, pose[i].y]);
      }
      this._lastArms[lado] = pts;
      if (visible(cadena[2])) this._poseWrists[lado] = [pose[cadena[2]].x * aspecto, pose[cadena[2]].y];
    });
    if (resultado.worldLandmarks && resultado.worldLandmarks.length) {
      const mundo = resultado.worldLandmarks[0];
      this._lastWorldPose = orden.map((i) => xyz(mundo[i]));
      this._lastVis = pose.map((p) => f(p.visibility || 0));
      this._worldAge = 0;
    }
  }
}

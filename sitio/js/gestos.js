// Movimientos de muestra para el avatar del sitio. No son señas de LSM: sirven para ver el
// personaje y sus dedos en acción. Generan frames en el mismo formato que los clips de la app
// (puntos de la persona: x a su izquierda, y arriba, z hacia la cámara), así que pasan por el
// mismo retargeting (retarget.js) que los movimientos grabados.
import * as THREE from 'three';
import { CADENAS_DEDO } from './retarget.js';

const v3 = (x, y, z) => new THREE.Vector3(x, y, z);
const dir = (x, y, z) => v3(x, y, z).normalize();
const suave = (x) => { const t = Math.min(1, Math.max(0, x)); return t * t * (3 - 2 * t); };
const NOMBRE_DEDO = { thumb: 'Thumb', index: 'Index', middle: 'Mid', ring: 'Ring', pinky: 'Pinky' };
const DEDOS = ['thumb', 'index', 'middle', 'ring', 'pinky'];

// Base ortonormal (como `marco` en retarget.js) en forma de cuaternión
function base(primario, secundario) {
  const e1 = primario.clone().normalize();
  const e2 = secundario.clone().sub(e1.clone().multiplyScalar(secundario.dot(e1))).normalize();
  const e3 = new THREE.Vector3().crossVectors(e1, e2);
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(e1, e2, e3));
}

export class Gestos {
  constructor(reposo, frameReposo) {
    this.reposo = frameReposo;
    const cab = (n) => v3(...reposo[n].cabeza);
    const cola = (n) => v3(...reposo[n].cola);
    this.lado = {};
    for (const s of ['L', 'R']) {
      const hombro = cab(`${s}_Upperarm`); const codo = cab(`${s}_Forearm`); const muneca = cab(`${s}_Hand`);
      const mano = new Array(21);
      mano[0] = muneca;
      for (const [dedo, idx] of Object.entries(CADENAS_DEDO)) {
        [1, 2, 3].forEach((k, i) => { mano[idx[i]] = cab(`${s}_${NOMBRE_DEDO[dedo]}${k}`); });
        mano[idx[3]] = cola(`${s}_${NOMBRE_DEDO[dedo]}3`);
      }
      const local = mano.map((p) => p.clone().sub(muneca));
      const dMano = local[9].clone(); const nud = local[5].clone().sub(local[17]);
      let palmar = new THREE.Vector3().crossVectors(dMano, nud).normalize();
      if (palmar.y > 0) palmar.negate();                 // en el reposo (pose T) las palmas miran abajo
      this.lado[s] = {
        hombro, largoBrazo: hombro.distanceTo(codo), largoAnte: codo.distanceTo(muneca),
        local, palmar, qBase: base(dMano, nud).invert(),
      };
    }
  }

  // Puntos de una mano: orientación (dirección de los dedos y línea de nudillos índice → meñique)
  // y cuánto se cierra cada dedo (0 abierto, 1 cerrado).
  mano(s, muneca, qMano, cierre) {
    const L = this.lado[s];
    const pts = L.local.map((p) => p.clone());
    DEDOS.forEach((dedo, d) => {
      const k = cierre[d]; if (!k) return;
      const idx = CADENAS_DEDO[dedo];
      const seg = pts[idx[1]].clone().sub(pts[idx[0]]).normalize();
      const eje = new THREE.Vector3().crossVectors(seg, L.palmar).normalize();
      const angulos = dedo === 'thumb' ? [0.35, 0.6, 0.6] : [1.35, 1.6, 1.1];
      for (let j = 0; j < 3; j++) {
        const q = new THREE.Quaternion().setFromAxisAngle(eje, angulos[j] * k);
        const centro = pts[idx[j]].clone();
        for (let m = j + 1; m < 4; m++) pts[idx[m]].sub(centro).applyQuaternion(q).add(centro);
      }
    });
    const q = qMano.clone().multiply(L.qBase);
    return pts.map((p) => p.applyQuaternion(q).add(muneca).toArray());
  }

  // Frame completo a partir de las direcciones del brazo y la mano de cada lado
  frame(brazos) {
    const pose = this.reposo.pose.map((p) => p.slice());
    const vis = this.reposo.vis.slice();
    const out = { pose, vis, left: null, right: null };
    for (const [s, iC, iM, clave] of [['L', 13, 15, 'left'], ['R', 14, 16, 'right']]) {
      const L = this.lado[s]; const b = brazos[s];
      const codo = L.hombro.clone().add(b.brazo.clone().normalize().multiplyScalar(L.largoBrazo));
      const muneca = codo.clone().add(b.ante.clone().normalize().multiplyScalar(L.largoAnte));
      pose[iC] = codo.toArray(); pose[iM] = muneca.toArray(); vis[iC] = 1; vis[iM] = 1;
      out[clave] = this.mano(s, muneca, b.qMano, b.cierre);
    }
    return out;
  }

  // Brazo colgando, palma hacia el muslo, dedos relajados
  colgando(s) {
    const hacia = s === 'L' ? 1 : -1;
    return {
      brazo: dir(0.2 * hacia, -1, -0.04), ante: dir(0.05 * hacia, -1, 0.27),
      qMano: base(v3(0.02 * hacia, -1, 0.12), v3(0, 0, 1)), cierre: [0.15, 0.22, 0.26, 0.3, 0.34],
    };
  }

  // Mezcla dos poses de brazo (posición con lerp, orientación de la mano con slerp)
  mezclar(a, b, k) {
    return {
      brazo: a.brazo.clone().lerp(b.brazo, k), ante: a.ante.clone().lerp(b.ante, k),
      qMano: a.qMano.clone().slerp(b.qMano, k), cierre: a.cierre.map((x, i) => x + (b.cierre[i] - x) * k),
    };
  }

  reposoNatural(t = 0) {
    const r = { L: this.colgando('L'), R: this.colgando('R') };
    const s = Math.sin(t * 1.4) * 0.012;
    r.L.ante.x += s; r.R.ante.x -= s;
    return this.frame(r);
  }

  // ------------------------------------------------------------------ movimientos
  // Cada uno: { duracion, en(t) → frame }
  saludo() {
    const D = 3.6;
    return {
      duracion: D,
      en: (t) => {
        const u = suave(t / 0.6) * (1 - suave((t - (D - 0.7)) / 0.7));
        const ola = Math.sin((t - 0.5) * 7.2) * suave((t - 0.45) / 0.3) * (1 - suave((t - (D - 0.9)) / 0.3));
        const arriba = {
          brazo: dir(-0.55, -0.55, 0.38), ante: dir(-0.12 + ola * 0.38, 1, 0.12),
          qMano: base(dir(-0.05 + ola * 0.55, 1, 0.08), v3(1, 0, -0.1 * ola)), cierre: [0, 0, 0, 0, 0],
        };
        const izq = this.colgando('L');
        return this.frame({ L: izq, R: this.mezclar(this.colgando('R'), arriba, u) });
      },
    };
  }

  contar() {
    const D = 5.4;
    return {
      duracion: D,
      en: (t) => {
        const u = suave(t / 0.6) * (1 - suave((t - (D - 0.7)) / 0.7));
        const k = Math.max(0, (t - 0.8) / 0.62);               // dedos que ya se abrieron
        const orden = [1, 2, 3, 4, 0];                          // índice, medio, anular, meñique, pulgar
        const cierre = [1, 1, 1, 1, 1];
        orden.forEach((d, i) => { cierre[d] = 1 - suave((k - i) * 2.2); });
        cierre[0] = Math.min(cierre[0], 0.85);
        const frente = {
          brazo: dir(-0.3, -0.8, 0.55), ante: dir(0.28, 0.85, 0.55),
          qMano: base(dir(0.05, 1, 0.12), v3(1, 0, 0)), cierre,
        };
        return this.frame({ L: this.colgando('L'), R: this.mezclar(this.colgando('R'), frente, u) });
      },
    };
  }

  pulgar() {
    const D = 3.2;
    return {
      duracion: D,
      en: (t) => {
        const u = suave(t / 0.6) * (1 - suave((t - (D - 0.7)) / 0.7));
        const golpe = Math.sin(Math.max(0, t - 0.7) * 5) * 0.06 * (1 - suave((t - 2) / 0.5));
        const frente = {
          brazo: dir(-0.25, -0.85, 0.5), ante: dir(0.35, 0.3 + golpe, 0.9),
          qMano: base(dir(0.4, 0.05, 0.9), v3(0, 1, 0)), cierre: [0, 1, 1, 1, 1],
        };
        return this.frame({ L: this.colgando('L'), R: this.mezclar(this.colgando('R'), frente, u) });
      },
    };
  }
}

// Retargeting de los puntos de la persona al rig del personaje (RF-23), dentro de la app.
//
// Es el mismo algoritmo que blender/inclusion_avatar.py (clase Retarget), escrito para three.js:
// cada hueso gira para apuntar como el segmento de la persona (dirección, no posición), con el
// giro sobre su eje tomado del doblez del codo, la línea de nudillos o la palma. Ver
// requerimientos/06_avatar.md.
//
// Ejes: los frames del clip (x a la izquierda de la persona, y arriba, z hacia la cámara) coinciden
// con los del mundo de three.js para un personaje exportado desde Blender mirando a -Y (en glTF,
// mirando a +Z). Por eso los puntos se usan tal cual.
import * as THREE from '../vendor/three/three.module.js';

export const CADENAS_DEDO = {
  thumb: [1, 2, 3, 4], index: [5, 6, 7, 8], middle: [9, 10, 11, 12], ring: [13, 14, 15, 16], pinky: [17, 18, 19, 20],
};
const LADOS = [['L', 'left', 11, 13, 15], ['R', 'right', 12, 14, 16]];
const CABEZA_INCLINACION = 0.35;
const REPARTO_PRONACION = 0.5;
const VISIBLE = 0.5;
const ANCHO_HOMBROS_MIN = 0.15;
const CADERAS_MAX = THREE.MathUtils.degToRad(40);
const GIRO_MAX = { pecho: THREE.MathUtils.degToRad(35), cabeza: THREE.MathUtils.degToRad(70), clavicula: THREE.MathUtils.degToRad(25) };

export function perfilTripo() {
  const dedos = { thumb: 'Thumb', index: 'Index', middle: 'Mid', ring: 'Ring', pinky: 'Pinky' };
  const lados = {};
  for (const [s] of LADOS) {
    const d = {};
    for (const [k, n] of Object.entries(dedos)) d[k] = [1, 2, 3].map((i) => `${s}_${n}${i}`);
    lados[s] = { clavicula: `${s}_Clavicle`, brazo: `${s}_Upperarm`, antebrazo: `${s}_Forearm`, mano: `${s}_Hand`, dedos: d };
  }
  return { columna: ['Waist', 'Spine01', 'Spine02'], cabeza: 'Head', caderas: ['L_Thigh', 'R_Thigh'], lados };
}

export function huesosDelPerfil(p) {
  const n = [...p.columna, p.cabeza];
  for (const l of Object.values(p.lados)) {
    n.push(l.clavicula, l.brazo, l.antebrazo, l.mano);
    for (const c of Object.values(l.dedos)) n.push(...c);
  }
  return n;
}

const v = (a) => new THREE.Vector3(a[0], a[1], a[2]);
const angulo = (q) => 2 * Math.acos(Math.min(1, Math.abs(q.w)));

function marco(primario, secundario) {
  if (primario.lengthSq() < 1e-18) return null;
  const y = primario.clone().normalize();
  const x = secundario.clone().sub(y.clone().multiplyScalar(secundario.dot(y)));
  if (x.lengthSq() < 1e-18) return null;
  x.normalize();
  const z = new THREE.Vector3().crossVectors(x, y);
  return new THREE.Matrix4().makeBasis(x, y, z);
}

function delta(destino, reposo) {
  if (!destino || !reposo) return null;
  const m = destino.clone().multiply(reposo.clone().transpose());
  return new THREE.Quaternion().setFromRotationMatrix(m);
}

function limitar(q, maximo) {
  const a = angulo(q);
  return a <= maximo ? q : new THREE.Quaternion().slerp(q, maximo / a);
}

function transicion(x, a, b) {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

export class Retarget {
  // huesos: { nombre: THREE.Bone } del personaje cargado (en reposo)
  // reposo: { nombre: { cabeza: [x,y,z], cola: [x,y,z] } } en ejes del mundo (personaje_reposo.json)
  constructor(huesos, reposo, perfil = perfilTripo()) {
    this.huesos = huesos;
    this.perfil = perfil;
    this.ultimo = {};
    let raiz = Object.values(huesos)[0];
    while (raiz.parent) raiz = raiz.parent;
    raiz.updateMatrixWorld(true);              // todo el árbol, no solo una rama
    this.reposoMundo = {};
    this.reposoLocal = {};
    for (const [n, b] of Object.entries(huesos)) {
      this.reposoMundo[n] = b.getWorldQuaternion(new THREE.Quaternion());
      this.reposoLocal[n] = b.quaternion.clone();
    }
    // Orden padres -> hijos, solo de los huesos del rig
    this.orden = [];
    const visitar = (o) => {
      if (o.isBone && huesos[o.name] === o) this.orden.push(o.name);
      for (const h of o.children) visitar(h);
    };
    visitar(raiz);
    this.vertical = new THREE.Vector3(0, 1, 0);
    this.frente = new THREE.Vector3(0, 0, 1);      // el personaje mira a +Z
    this.lateral = new THREE.Vector3(1, 0, 0);     // su izquierda
    this._marcosReposo(reposo);
  }

  _marcosReposo(reposo) {
    const p = this.perfil;
    const cab = (n) => v(reposo[n].cabeza);
    const cola = (n) => v(reposo[n].cola);
    this.r = {};
    const hombros = {};
    for (const [s] of LADOS) {
      const lado = p.lados[s];
      const hombro = cab(lado.brazo); const codo = cab(lado.antebrazo); const muneca = cab(lado.mano);
      hombros[s] = hombro;
      const mano = new Array(21);
      mano[0] = muneca;
      for (const [dedo, cadena] of Object.entries(lado.dedos)) {
        const idx = CADENAS_DEDO[dedo];
        cadena.forEach((n, k) => { mano[idx[k]] = cab(n); });
        mano[idx[3]] = cola(cadena[2]);
      }
      const u = codo.clone().sub(hombro); const f = muneca.clone().sub(codo);
      const uh = u.clone().normalize();
      const doblez = f.clone().sub(uh.multiplyScalar(f.dot(uh)));
      const dirMano = mano[9].clone().sub(mano[0]); const nudillos = mano[5].clone().sub(mano[17]);
      this.r[s] = {
        u, f,
        brazo: marco(u, doblez.length() > 0.2 * f.length() ? doblez : this.frente),
        mano: marco(dirMano, nudillos),
        dedos: this._marcosDedos(mano, dirMano, nudillos),
      };
    }
    const centro = hombros.L.clone().add(hombros.R).multiplyScalar(0.5);
    for (const [s] of LADOS) this.r[s].clavicula = marco(hombros[s].clone().sub(centro), this.frente);
    const caderas = cab(p.caderas[0]).add(cab(p.caderas[1])).multiplyScalar(0.5);
    const linea = hombros.L.clone().sub(hombros.R);
    this.r.pecho = marco(linea, centro.clone().sub(caderas));
    this.r.pechoVertical = marco(linea, this.vertical);
    const adelante = this.frente.clone().multiplyScalar(Math.cos(CABEZA_INCLINACION))
      .sub(this.vertical.clone().multiplyScalar(Math.sin(CABEZA_INCLINACION)));
    this.r.cabeza = marco(this.lateral, adelante);
  }

  _marcosDedos(mano, dirMano, nudillos) {
    const normal = new THREE.Vector3().crossVectors(dirMano, nudillos);
    const marcos = {};
    for (const [dedo, idx] of Object.entries(CADENAS_DEDO)) {
      const ref = dedo === 'thumb' ? normal : nudillos;
      marcos[dedo] = [0, 1, 2].map((k) => marco(mano[idx[k + 1]].clone().sub(mano[idx[k]]), ref));
    }
    return marcos;
  }

  // Frame de movimiento -> { hueso: giro respecto al reposo } (espacio del mundo).
  // Las partes ausentes conservan su último giro.
  resolver(frame) {
    const puntos = (k) => (frame[k] ? frame[k].map(v) : null);
    let pose = puntos('pose');
    const vis = frame.vis || new Array(33).fill(1);
    const manos = { left: puntos('left'), right: puntos('right') };
    const p = this.perfil; const giros = {};
    if (pose && pose[11].distanceTo(pose[12]) < ANCHO_HOMBROS_MIN) pose = null;   // cuerpo imposible
    if (pose) {
      const centro = pose[11].clone().add(pose[12]).multiplyScalar(0.5);
      let arriba = this.vertical; let ref = this.r.pechoVertical;
      if (vis[23] > VISIBLE && vis[24] > VISIBLE) {
        const col = centro.clone().sub(pose[23].clone().add(pose[24]).multiplyScalar(0.5));
        if (col.lengthSq() > 1e-12 && col.angleTo(this.vertical) < CADERAS_MAX) { arriba = col; ref = this.r.pecho; }
      }
      let q = delta(marco(pose[11].clone().sub(pose[12]), arriba), ref);
      if (q) {
        q = limitar(q, GIRO_MAX.pecho);
        p.columna.forEach((n, k) => { giros[n] = new THREE.Quaternion().slerp(q, (k + 1) / p.columna.length); });
      }
      if (vis[7] > VISIBLE && vis[8] > VISIBLE) {
        const orejas = pose[7].clone().add(pose[8]).multiplyScalar(0.5);
        const qc = delta(marco(pose[7].clone().sub(pose[8]), pose[0].clone().sub(orejas)), this.r.cabeza);
        if (qc) giros[p.cabeza] = limitar(qc, GIRO_MAX.cabeza);
      }
      for (const [s, claveMano, iH, iC, iM] of LADOS) {
        const lado = p.lados[s]; const r = this.r[s];
        const qcl = delta(marco(pose[iH].clone().sub(centro), this.frente), r.clavicula);
        if (qcl) giros[lado.clavicula] = limitar(qcl, GIRO_MAX.clavicula);
        Object.assign(giros, this._brazo(lado, r, pose[iH], pose[iC], pose[iM], manos[claveMano]));
      }
    }
    for (const [s, claveMano] of LADOS) {
      if (manos[claveMano]) Object.assign(giros, this._dedos(p.lados[s], this.r[s], manos[claveMano]));
    }
    for (const [n, q] of Object.entries(giros)) {
      const previo = this.ultimo[n];
      if (previo && previo.dot(q) < 0) q.set(-q.x, -q.y, -q.z, -q.w);   // mismo hemisferio
      this.ultimo[n] = q;
    }
    return { ...this.ultimo };
  }

  _brazo(lado, r, hombro, codo, muneca, mano) {
    const u = codo.clone().sub(hombro); const f = muneca.clone().sub(codo);
    if (u.length() < 1e-6 || f.length() < 1e-6) return {};
    const giros = {};
    const uh = u.clone().normalize();
    const doblez = f.clone().sub(uh.clone().multiplyScalar(f.dot(uh)));
    const qGiro = new THREE.Quaternion().setFromUnitVectors(r.u.clone().normalize(), uh);
    let qMarco = delta(marco(u, doblez), r.brazo);
    const peso = transicion(doblez.length() / f.length(), 0.2, 0.45);
    let qBrazo = qGiro;
    if (qMarco && peso > 0) {
      if (qGiro.dot(qMarco) < 0) qMarco.set(-qMarco.x, -qMarco.y, -qMarco.z, -qMarco.w);
      qBrazo = qGiro.clone().slerp(qMarco, peso);
    }
    const fRot = r.f.clone().applyQuaternion(qBrazo).normalize();
    let qAnte = new THREE.Quaternion().setFromUnitVectors(fRot, f.clone().normalize()).multiply(qBrazo);
    giros[lado.brazo] = qBrazo;
    if (mano) {
      const qMano = delta(marco(mano[9].clone().sub(mano[0]), mano[5].clone().sub(mano[17])), r.mano);
      if (qMano) {
        // Parte del giro de la muñeca (pronación) pasa al antebrazo
        const rel = qAnte.clone().invert().multiply(qMano);
        const eje = r.f.clone().normalize();
        const proy = eje.clone().multiplyScalar(new THREE.Vector3(rel.x, rel.y, rel.z).dot(eje));
        const torsion = new THREE.Quaternion(proy.x, proy.y, proy.z, rel.w);
        if (torsion.length() > 1e-9) {
          torsion.normalize();
          qAnte = qAnte.clone().multiply(new THREE.Quaternion().slerp(torsion, REPARTO_PRONACION));
        }
        giros[lado.mano] = qMano;
      }
    }
    giros[lado.antebrazo] = qAnte;
    return giros;
  }

  _dedos(lado, r, mano) {
    const dirMano = mano[9].clone().sub(mano[0]); const nudillos = mano[5].clone().sub(mano[17]);
    const normal = new THREE.Vector3().crossVectors(dirMano, nudillos);
    const giros = {};
    for (const [dedo, idx] of Object.entries(CADENAS_DEDO)) {
      const ref = dedo === 'thumb' ? normal : nudillos;
      lado.dedos[dedo].forEach((n, k) => {
        const q = delta(marco(mano[idx[k + 1]].clone().sub(mano[idx[k]]), ref), r.dedos[dedo][k]);
        if (q) giros[n] = q;
      });
    }
    return giros;
  }

  // { hueso: giro absoluto } -> rotación local de cada hueso de three.js
  aplicar(giros) {
    const mundo = {};
    for (const n of this.orden) {
      const b = this.huesos[n];
      const padre = b.parent;
      const mPadre = (padre && padre.isBone && mundo[padre.name])
        ? mundo[padre.name] : padre.getWorldQuaternion(new THREE.Quaternion());
      const w = giros[n]
        ? giros[n].clone().multiply(this.reposoMundo[n])
        : mPadre.clone().multiply(this.reposoLocal[n]);
      mundo[n] = w;
      b.quaternion.copy(mPadre.clone().invert().multiply(w)).normalize();
    }
  }

  // Frame -> pose del personaje
  mover(frame) {
    this.aplicar(this.resolver(frame));
  }

  reposo() {
    this.ultimo = {};
    for (const [n, b] of Object.entries(this.huesos)) b.quaternion.copy(this.reposoLocal[n]);
  }
}

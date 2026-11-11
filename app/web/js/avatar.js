// El avatar dentro de la app (RF-27): personaje 3D con three.js, movido por el retargeting.
// Estados: reposo (brazos abajo, respira), en vivo (imita a la persona) y reproduciendo clips
// de palabras grabadas, uno tras otro, con transiciones suaves.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Retarget, perfilTripo } from './retarget.js';

const TRANSICION = 0.3;          // s para pasar de una pose a otra
const SIN_DATOS_VIVO = 0.6;      // s sin frames en vivo para volver al reposo
const DISTANCIA = 1.25;          // cámara: de la cintura para arriba (el personaje mide 1 m)
const PAUSA_BUCLE = 0.5;         // s quieto al final del recorte antes de repetirlo
// Señas de una mano: el lado del rig que se queda quieto ('L' = izquierda de la persona)
const LADO_QUIETO = { derecha: 'L', izquierda: 'R' };

export class Avatar {
  constructor() {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.escena = new THREE.Scene();
    this.camara = new THREE.PerspectiveCamera(30, 1, 0.05, 20);
    this.camara.position.set(0, 0.8, DISTANCIA);
    this.camara.lookAt(0, 0.74, 0);
    this.escena.add(new THREE.HemisphereLight(0xdde6ff, 0x1a1f33, 1.1));
    const clave = new THREE.DirectionalLight(0xffffff, 2.2);
    clave.position.set(-1.2, 2.2, 2.5);
    this.escena.add(clave);
    const contra = new THREE.DirectionalLight(0x9d86ff, 1.6);
    contra.position.set(1.5, 1.6, -2.0);
    this.escena.add(contra);
    this.reloj = new THREE.Clock();
    this.modo = 'cargando';
    this.cola = [];               // clips por reproducir
    this.alPalabra = null;        // (palabra | null) al empezar cada clip y al terminar
    this.alTiempo = null;         // (t) en cada cuadro mientras se revisa una toma
    this.rev = null;              // toma en revisión: { frames, inicio, fin, t, reproduciendo, velocidad }
    this.ultimoVivo = 0;
    this._transicion = null;
    this.contenedor = null;
    this._medir = new ResizeObserver(() => this._ajustar());
    this.renderer.setAnimationLoop(() => this._cuadro());
  }

  async cargar(base = 'assets/modelos/') {
    const [gltf, reposo] = await Promise.all([
      new GLTFLoader().loadAsync(`${base}personaje.glb`),
      fetch(`${base}personaje_reposo.json`).then((r) => r.json()),
    ]);
    this.modelo = gltf.scene;
    this.escena.add(this.modelo);
    const huesos = {};
    this.modelo.traverse((o) => {
      if (o.isBone) huesos[o.name] = o;
      if (o.isMesh) o.frustumCulled = false;      // la malla se mueve fuera de su caja original
    });
    this.huesos = huesos;
    this.rt = new Retarget(huesos, reposo, perfilTripo());
    this.frameReposo = frameReposoNatural(reposo);
    this.modo = 'reposo';
    this.rt.mover(this.frameReposo);
    return this;
  }

  // Pone el lienzo dentro de `contenedor` (la app tiene un solo avatar para todas las pantallas)
  montar(contenedor) {
    if (this.contenedor === contenedor) return;
    if (this.contenedor) this._medir.unobserve(this.contenedor);
    this.contenedor = contenedor;
    contenedor.appendChild(this.renderer.domElement);
    this._medir.observe(contenedor);
    this._ajustar();
  }

  _ajustar() {
    if (!this.contenedor) return;
    const w = this.contenedor.clientWidth || 1; const h = this.contenedor.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camara.aspect = w / h;
    // Que entren los brazos extendidos aunque el escenario sea angosto
    this.camara.position.z = w / h < 1.3 ? DISTANCIA * (1.3 / Math.max(0.6, w / h)) : DISTANCIA;
    this.camara.updateProjectionMatrix();
  }

  // ------------------------------------------------------------------ estados
  // manos: 'dos', 'derecha' o 'izquierda' (con una, la otra mano vuelve a su reposo)
  vivo(frame, manos = 'dos') {
    if (!this.rt || this.modo === 'revision') return;
    if (this.modo !== 'vivo') { this.cola = []; this._empezarTransicion(); this.modo = 'vivo'; }
    this.ultimoVivo = performance.now();
    this._soltarMano(manos);
    this.rt.mover(frame);
  }

  _soltarMano(manos) {
    if (LADO_QUIETO[manos]) this.rt.olvidarMano(LADO_QUIETO[manos]);
  }

  // ------------------------------------------------- revisar y recortar una toma
  revisar(clip) {
    if (!this.rt) return;
    const frames = clip.frames;
    this.cola = [];
    this.rev = { frames, inicio: 0, fin: frames[frames.length - 1].t, t: 0, reproduciendo: true, velocidad: 1,
      previo: performance.now(), pausaHasta: null };
    this._soltarMano(clip.hands);
    this._empezarTransicion();
    this.modo = 'revision';
  }

  tramo(inicio, fin) {
    if (!this.rev) return;
    Object.assign(this.rev, { inicio, fin, pausaHasta: null });
  }

  // Muestra el instante `t` y deja la reproducción en pausa (al arrastrar la línea de tiempo)
  irA(t) {
    if (!this.rev) return;
    Object.assign(this.rev, { t, reproduciendo: false, pausaHasta: null });
  }

  reproducirTramo(si = true) {
    const r = this.rev;
    if (!r) return;
    if (si && (r.t >= r.fin - 1e-3 || r.t < r.inicio)) r.t = r.inicio;
    r.reproduciendo = si;
    r.pausaHasta = null;
    r.previo = performance.now();
  }

  velocidad(v) { if (this.rev) this.rev.velocidad = v; }

  terminarRevision() {
    this.rev = null;
    if (this.modo === 'revision') this._aReposo();
  }

  // clips: [{ palabra, clip }] (clip = JSON del formato inclusion-movimiento, o null si no hay).
  // velocidad: 1 normal, 0.5 en cámara lenta (Diccionario y Aprender).
  reproducir(clips, { velocidad = 1 } = {}) {
    if (!this.rt) return;
    this.velocidadClip = velocidad;
    this.cola = clips.filter((c) => c.clip && c.clip.frames && c.clip.frames.length);
    this._siguiente();
  }

  detener() {
    this.cola = [];
    this._aReposo();
  }

  _siguiente() {
    const c = this.cola.shift();
    if (!c) { this._aReposo(); return; }
    this.actual = { palabra: c.palabra, frames: c.clip.frames, inicio: performance.now(), i: 0 };
    this._soltarMano(c.clip.hands);
    this._empezarTransicion();
    this.modo = 'clip';
    if (this.alPalabra) this.alPalabra(c.palabra);
  }

  _aReposo() {
    if (this.modo === 'reposo') return;
    this._empezarTransicion();
    this.modo = 'reposo';
    this.rt.ultimo = {};
    this.rt.mover(this.frameReposo);
    if (this.alPalabra) this.alPalabra(null);
  }

  // --------------------------------------------------------------- animación
  _empezarTransicion() {
    if (!this.huesos) return;
    const desde = {};
    for (const [n, b] of Object.entries(this.huesos)) desde[n] = b.quaternion.clone();
    this._transicion = { desde, inicio: performance.now() };
  }

  _cuadro() {
    if (this.rt) {
      const ahora = performance.now();
      if (this.modo === 'vivo' && ahora - this.ultimoVivo > SIN_DATOS_VIVO * 1000) this._aReposo();
      if (this.modo === 'clip') this._avanzarClip(ahora);
      if (this.modo === 'revision') this._avanzarRevision(ahora);
      if (this.modo === 'reposo') this._respirar(ahora);
      this._mezclar(ahora);
    }
    this.renderer.render(this.escena, this.camara);
  }

  _avanzarClip(ahora) {
    const a = this.actual; const fr = a.frames;
    const t = ((ahora - a.inicio) / 1000) * (this.velocidadClip || 1);
    if (t > fr[fr.length - 1].t) { this._siguiente(); return; }
    while (a.i < fr.length - 2 && fr[a.i + 1].t <= t) a.i += 1;
    const f0 = fr[a.i]; const f1 = fr[Math.min(a.i + 1, fr.length - 1)];
    const k = f1.t > f0.t ? Math.min(1, Math.max(0, (t - f0.t) / (f1.t - f0.t))) : 0;
    this.rt.mover(interpolar(f0, f1, k));
  }

  _avanzarRevision(ahora) {
    const r = this.rev;
    const dt = Math.min(0.1, (ahora - r.previo) / 1000);
    r.previo = ahora;
    if (r.reproduciendo) {
      if (r.pausaHasta !== null) {
        if (ahora >= r.pausaHasta) { r.pausaHasta = null; r.t = r.inicio; }
      } else {
        r.t += dt * r.velocidad;
        if (r.t >= r.fin) { r.t = r.fin; r.pausaHasta = ahora + PAUSA_BUCLE * 1000; }
      }
    }
    this.rt.mover(poseEn(r.frames, r.t));
    if (this.alTiempo) this.alTiempo(r.t);
  }

  _respirar(ahora) {
    this.rt.mover(this.frameReposo);
    const s = Math.sin(ahora / 1000 * 1.4);
    const pecho = this.huesos.Spine02;
    if (pecho) pecho.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.012 * s));
  }

  _mezclar(ahora) {
    const tr = this._transicion;
    if (!tr) return;
    const k = (ahora - tr.inicio) / (TRANSICION * 1000);
    if (k >= 1) { this._transicion = null; return; }
    const e = k * k * (3 - 2 * k);
    for (const [n, b] of Object.entries(this.huesos)) b.quaternion.copy(tr.desde[n].clone().slerp(b.quaternion, e));
  }
}

// Pose del clip en el instante t (s), interpolando entre los dos frames vecinos
export function poseEn(frames, t) {
  let a = 0; let b = frames.length - 1;
  if (t <= frames[0].t) return interpolar(frames[0], frames[0], 0);
  if (t >= frames[b].t) return interpolar(frames[b], frames[b], 0);
  while (b - a > 1) { const m = (a + b) >> 1; if (frames[m].t <= t) a = m; else b = m; }
  const f0 = frames[a]; const f1 = frames[b];
  return interpolar(f0, f1, f1.t > f0.t ? (t - f0.t) / (f1.t - f0.t) : 0);
}

// Interpolación lineal entre dos frames del clip (solo las partes que tienen ambos)
function interpolar(a, b, k) {
  const mezcla = (p, q) => (p && q ? p.map((pt, i) => pt.map((x, j) => x + (q[i][j] - x) * k)) : (k < 0.5 ? p : q));
  return { pose: mezcla(a.pose, b.pose), vis: a.vis || b.vis, left: mezcla(a.left, b.left), right: mezcla(a.right, b.right) };
}

// Pose de descanso natural: brazos abajo, codos apenas doblados (en vez de la pose T del rig)
export function frameReposoNatural(reposo) {
  const p = Array.from({ length: 33 }, () => [0, 0, 0]);
  const vis = new Array(33).fill(0);
  const cab = (n) => new THREE.Vector3(...reposo[n].cabeza);
  for (const [s, iH, iC, iM] of [['L', 11, 13, 15], ['R', 12, 14, 16]]) {
    const hombro = cab(`${s}_Upperarm`);
    const largoBrazo = hombro.distanceTo(cab(`${s}_Forearm`));
    const largoAnte = cab(`${s}_Forearm`).distanceTo(cab(`${s}_Hand`));
    const hacia = s === 'L' ? 1 : -1;           // un poco separados del cuerpo
    const codo = hombro.clone().add(new THREE.Vector3(0.06 * hacia, -largoBrazo, -0.01));
    const muneca = codo.clone().add(new THREE.Vector3(0.015 * hacia, -largoAnte * 0.97, 0.07));
    [[iH, hombro], [iC, codo], [iM, muneca]].forEach(([i, v]) => { p[i] = v.toArray(); vis[i] = 1; });
  }
  const cabeza = cab('Head');
  const b = 0.35;
  p[7] = cabeza.clone().add(new THREE.Vector3(0.05, 0, 0)).toArray();
  p[8] = cabeza.clone().add(new THREE.Vector3(-0.05, 0, 0)).toArray();
  p[0] = cabeza.clone().add(new THREE.Vector3(0, -Math.sin(b), Math.cos(b)).multiplyScalar(0.06)).toArray();
  p[23] = cab('L_Thigh').toArray(); p[24] = cab('R_Thigh').toArray();
  [0, 7, 8, 23, 24].forEach((i) => { vis[i] = 1; });
  return { pose: p, vis, left: null, right: null };
}

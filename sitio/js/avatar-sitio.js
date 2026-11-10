// El avatar 3D en el sitio: el mismo personaje (GLB) y el mismo retargeting que la app
// (app/web/js/avatar.js y retarget.js), con movimientos de muestra y el modo «Imítame».
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Retarget, perfilTripo } from './retarget.js';
import { Gestos } from './gestos.js';

const TRANSICION = 0.3;          // s para pasar de una pose a otra (igual que la app)
const DISTANCIA = 1.25;          // cámara: de la cintura para arriba (el personaje mide 1 m)
const SIN_DATOS_VIVO = 0.6;      // s sin cuadros de la cámara para volver al reposo

const $ = (s) => document.querySelector(s);

class AvatarSitio {
  constructor(contenedor) {
    this.contenedor = contenedor;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    contenedor.appendChild(this.renderer.domElement);
    this.escena = new THREE.Scene();
    this.camara = new THREE.PerspectiveCamera(30, 1, 0.05, 20);
    this.escena.add(new THREE.HemisphereLight(0xdde6ff, 0x1a1f33, 1.1));
    const clave = new THREE.DirectionalLight(0xffffff, 2.2); clave.position.set(-1.2, 2.2, 2.5); this.escena.add(clave);
    const contra = new THREE.DirectionalLight(0x9d86ff, 1.6); contra.position.set(1.5, 1.6, -2.0); this.escena.add(contra);
    const relleno = new THREE.DirectionalLight(0x2ec4b6, 0.5); relleno.position.set(1.8, 0.6, 1.5); this.escena.add(relleno);
    this.pivote = new THREE.Group(); this.escena.add(this.pivote);
    this.giro = 0; this.giroVel = 0; this.giroMeta = null;
    this.modo = 'cargando'; this.gesto = null; this.ultimoVivo = 0; this._transicion = null;
    this.visible = true;
    new ResizeObserver(() => this._ajustar()).observe(contenedor);
    new IntersectionObserver((e) => { this.visible = e[0].isIntersecting; this._bucle(); }).observe(contenedor);
    document.addEventListener('visibilitychange', () => this._bucle());
    this._arrastrar();
    this._ajustar();
  }

  async cargar(base = 'assets/modelos/') {
    const [gltf, reposo] = await Promise.all([
      new GLTFLoader().loadAsync(`${base}personaje.glb`),
      fetch(`${base}personaje_reposo.json`).then((r) => r.json()),
    ]);
    this.modelo = gltf.scene;
    this.pivote.add(this.modelo);
    const huesos = {};
    this.modelo.traverse((o) => {
      if (o.isBone) huesos[o.name] = o;
      if (o.isMesh) o.frustumCulled = false;
    });
    this.huesos = huesos;
    this.rt = new Retarget(huesos, reposo, perfilTripo());
    this.gestos = new Gestos(reposo, frameReposoNatural(reposo));
    this.modo = 'reposo';
    this.rt.mover(this.gestos.reposoNatural(0));
    this._bucle();
  }

  _ajustar() {
    const w = this.contenedor.clientWidth || 1; const h = this.contenedor.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camara.aspect = w / h;
    const z = w / h < 1.3 ? DISTANCIA * (1.3 / Math.max(0.6, w / h)) : DISTANCIA;
    this.camara.position.set(0, 0.8, z);
    this.camara.lookAt(0, 0.72, 0);
    this.camara.updateProjectionMatrix();
    if (this.modo !== 'cargando') this.renderer.render(this.escena, this.camara);
  }

  // Girar arrastrando (con inercia); doble clic lo regresa al frente
  _arrastrar() {
    const el = this.contenedor.closest('.escenario');
    let x0 = null; let ultimoX = 0; let ultimoT = 0;
    el.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || e.target.closest('button')) return;
      x0 = e.clientX; ultimoX = e.clientX; ultimoT = performance.now(); this.giroVel = 0; this.giroMeta = null;
      el.setPointerCapture(e.pointerId);
    });
    el.addEventListener('pointermove', (e) => {
      if (x0 === null) return;
      const dx = e.clientX - ultimoX; const ahora = performance.now();
      this.giro += dx * 0.009;
      this.giroVel = (dx * 0.009) / Math.max(1, ahora - ultimoT) * 16;
      ultimoX = e.clientX; ultimoT = ahora;
      this._bucle();
    });
    const soltar = () => { x0 = null; };
    el.addEventListener('pointerup', soltar); el.addEventListener('pointercancel', soltar);
    el.addEventListener('dblclick', () => { this.giroMeta = 0; this._bucle(); });
  }

  // ------------------------------------------------------------------ estados
  hacer(nombre) {
    if (!this.gestos) return;
    if (nombre === 'reposo') { this._aReposo(); return; }
    this.gesto = { ...this.gestos[nombre](), nombre, inicio: performance.now() };
    this._empezarTransicion();
    this.modo = 'gesto';
    this.giroMeta = 0;
    this._bucle();
  }

  vivo(frame) {
    if (!this.rt) return;
    if (this.modo !== 'vivo') { this.gesto = null; this._empezarTransicion(); this.modo = 'vivo'; }
    this.ultimoVivo = performance.now();
    this.rt.mover(frame);
    this._bucle();
  }

  _aReposo() {
    if (this.modo === 'reposo') return;
    this._empezarTransicion();
    this.modo = 'reposo'; this.gesto = null;
    if (this.alTerminar) this.alTerminar();
  }

  _empezarTransicion() {
    if (!this.huesos) return;
    const desde = {};
    for (const [n, b] of Object.entries(this.huesos)) desde[n] = b.quaternion.clone();
    this._transicion = { desde, inicio: performance.now() };
  }

  _mezclar(ahora) {
    const tr = this._transicion;
    if (!tr) return;
    const k = (ahora - tr.inicio) / (TRANSICION * 1000);
    if (k >= 1) { this._transicion = null; return; }
    const e = k * k * (3 - 2 * k);
    for (const [n, b] of Object.entries(this.huesos)) b.quaternion.copy(tr.desde[n].clone().slerp(b.quaternion, e));
  }

  _bucle() {
    const debe = this.visible && !document.hidden;
    this.renderer.setAnimationLoop(debe ? () => this._cuadro() : null);
  }

  _cuadro() {
    const ahora = performance.now();
    if (this.rt) {
      if (this.modo === 'vivo' && ahora - this.ultimoVivo > SIN_DATOS_VIVO * 1000) this._aReposo();
      if (this.modo === 'gesto') {
        const t = (ahora - this.gesto.inicio) / 1000;
        if (t > this.gesto.duracion) this._aReposo();
        else this.rt.mover(this.gesto.en(t));
      }
      if (this.modo === 'reposo') this.rt.mover(this.gestos.reposoNatural(ahora / 1000));
      this._mezclar(ahora);
    }
    // Giro con inercia, o de regreso al frente
    if (this.giroMeta !== null) {
      this.giro += (this.giroMeta - this.giro) * 0.08;
      if (Math.abs(this.giroMeta - this.giro) < 0.002) { this.giro = this.giroMeta; this.giroMeta = null; }
    } else {
      this.giro += this.giroVel; this.giroVel *= 0.93;
      if (Math.abs(this.giroVel) < 1e-4) this.giroVel = 0;
    }
    this.pivote.rotation.y = this.giro;
    this.renderer.render(this.escena, this.camara);
  }
}

// Pose de descanso natural (brazos abajo), como en la app (app/web/js/avatar.js)
function frameReposoNatural(reposo) {
  const p = Array.from({ length: 33 }, () => [0, 0, 0]);
  const vis = new Array(33).fill(0);
  const cab = (n) => new THREE.Vector3(...reposo[n].cabeza);
  for (const [s, iH, iC, iM] of [['L', 11, 13, 15], ['R', 12, 14, 16]]) {
    const hombro = cab(`${s}_Upperarm`);
    const largoBrazo = hombro.distanceTo(cab(`${s}_Forearm`));
    const largoAnte = cab(`${s}_Forearm`).distanceTo(cab(`${s}_Hand`));
    const hacia = s === 'L' ? 1 : -1;
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

// ------------------------------------------------------------------ interfaz de la sección
export async function iniciarAvatar() {
  const lienzo = $('#avatar-lienzo'); const carga = $('#avatar-carga'); const estado = $('#avatar-estado');
  const escenario = $('#escenario');
  const av = new AvatarSitio(lienzo);
  await av.cargar();
  carga.classList.add('oculto');

  const botones = [...document.querySelectorAll('[data-gesto]')];
  const NOMBRES = { saludo: 'Saludando', contar: 'Contando con los dedos', pulgar: 'Pulgar arriba' };
  const marcar = (nombre) => botones.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.gesto === nombre)));
  av.alTerminar = () => { if (!imitando) { marcar(null); estado.textContent = ''; } };
  botones.forEach((b) => b.addEventListener('click', () => {
    if (imitando) return;
    av.hacer(b.dataset.gesto);
    marcar(b.dataset.gesto === 'reposo' ? null : b.dataset.gesto);
    estado.textContent = NOMBRES[b.dataset.gesto] || '';
  }));

  // Escenarios
  const radios = [...document.querySelectorAll('.escenarios-fila [data-escenario]')];
  radios.forEach((r) => r.addEventListener('click', () => {
    escenario.dataset.escenario = r.dataset.escenario;
    radios.forEach((o) => o.setAttribute('aria-checked', String(o === r)));
  }));
  // Flechas dentro del grupo de escenarios
  document.querySelector('.escenarios-fila').addEventListener('keydown', (e) => {
    const i = radios.indexOf(document.activeElement);
    if (i < 0 || !['ArrowRight', 'ArrowLeft'].includes(e.key)) return;
    e.preventDefault();
    const j = (i + (e.key === 'ArrowRight' ? 1 : radios.length - 1)) % radios.length;
    radios[j].focus(); radios[j].click();
  });

  // Saluda una vez al aparecer
  const io = new IntersectionObserver((e) => {
    if (e[0].isIntersecting && e[0].intersectionRatio > 0.5) {
      io.disconnect();
      if (!matchMedia('(prefers-reduced-motion: reduce)').matches) { av.hacer('saludo'); marcar('saludo'); estado.textContent = NOMBRES.saludo; }
    }
  }, { threshold: [0.5] });
  io.observe(escenario);

  // Imítame (cámara del visitante, MediaPipe para web)
  let imitando = false; let imitador = null;
  const botonImitar = $('#imitame-boton'); const textoImitar = $('#imitame-texto');
  botonImitar.addEventListener('click', async () => {
    if (imitando) {
      imitador?.detener(); imitando = false; textoImitar.textContent = 'Imítame';
      botones.forEach((b) => { b.disabled = false; });
      estado.textContent = ''; av._aReposo();
      return;
    }
    botonImitar.disabled = true; textoImitar.textContent = 'Preparando la cámara…';
    estado.textContent = 'Descargando los modelos de detección…';
    try {
      const { Imitador } = await import('./imitame.js');
      imitador = imitador || new Imitador($('#imitame-video'));
      await imitador.iniciar((frame) => av.vivo(frame), (msg) => { estado.textContent = msg; });
      imitando = true; textoImitar.textContent = 'Detener la cámara';
      botones.forEach((b) => { b.disabled = true; }); marcar(null);
      av.giroMeta = 0;
    } catch (err) {
      console.error(err);
      textoImitar.textContent = 'Imítame';
      estado.textContent = err && err.name === 'NotAllowedError'
        ? 'Sin permiso para usar la cámara.'
        : 'No se pudo iniciar la cámara en este navegador.';
    } finally {
      botonImitar.disabled = false;
    }
  });
}

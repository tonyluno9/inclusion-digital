// Cámara + MediaPipe para web (@mediapipe/tasks-vision 0.10.35, la misma versión que usa la app
// en Python, con los mismos modelos .task), alojados en sitio/vendor/mediapipe/.
// Se cargan solo cuando el visitante enciende la cámara. El video nunca sale del navegador.
//
// Igual que la app: cada cuadro se invierte en espejo ANTES de detectar (cv2.flip en
// inclusion_app.py), con 2 manos, confianzas de 0.5, modo VIDEO y la pose «full».
// Un mismo <canvas> muestra el cuadro en espejo con las manos y los brazos dibujados encima.
import * as C from './config.js';
import { ARM_CHAINS, Detector, HAND_CONNECTIONS } from './detector.js';

const VENDOR = new URL('../../../vendor/mediapipe/', import.meta.url).href;
// Colores de la app (BGR en OpenCV): izquierda azul, derecha ámbar
const COLORES = ['rgb(60, 160, 255)', 'rgb(255, 200, 60)'];
const parametro = (n) => { try { return new URLSearchParams(location.search).get(n); } catch { return null; } };
const CLAVE_POSE = 'kabtaan.pose';
const leer = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const escribir = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };
const OPCIONES_POSE = { numPoses: 1, minPoseDetectionConfidence: 0.5, minPosePresenceConfidence: 0.5, minTrackingConfidence: 0.5 };

export class Camara {
  constructor() {
    this.video = document.createElement('video');
    this.video.muted = true;
    this.video.playsInline = true;
    this.video.setAttribute('playsinline', '');
    this.canvas = document.createElement('canvas');
    this.canvas.setAttribute('data-video', '');
    this.canvas.setAttribute('role', 'img');
    this.canvas.setAttribute('aria-label', 'Tu cámara, en espejo, con los puntos de las manos y los brazos');
    this.canvas.width = 640;
    this.canvas.height = 360;
    this.ctx = this.canvas.getContext('2d', { willReadFrequently: false });
    this.detector = new Detector();
    this.activa = false;
    this.cargada = false;
    this.delegado = null;
    // «full» como la app; «lite» (modo rápido) si se pide en la dirección o el visitante lo eligió
    const pedido = parametro('pose') || leer(CLAVE_POSE);
    this.poseModelo = pedido === 'lite' || pedido === 'full' ? pedido : C.POSE_MODEL;
    this._ultimoTs = 0;
    this.alFrame = null;
  }

  /** Descarga MediaPipe y los modelos (unos 30 MB la primera vez; después, del caché). */
  async cargar(alProgreso = () => {}) {
    if (this.cargada) return;
    alProgreso('Cargando MediaPipe…');
    const vision = await import(`${VENDOR}vision_bundle.mjs`);
    const archivos = await vision.FilesetResolver.forVisionTasks(`${VENDOR}wasm`);
    const pedido = parametro('delegado');
    const delegados = pedido === 'cpu' ? ['CPU'] : ['GPU', 'CPU'];
    const crear = async (Clase, modelo, extra) => {
      let error;
      for (const delegate of delegados) {
        try {
          const t = await Clase.createFromOptions(archivos, {
            baseOptions: { modelAssetPath: `${VENDOR}modelos/${modelo}`, delegate }, runningMode: 'VIDEO', ...extra,
          });
          return [t, delegate];
        } catch (e) { error = e; }
      }
      throw error;
    };
    alProgreso('Cargando los modelos de manos y cuerpo…');
    const [[manos, d1], [cuerpo, d2]] = await Promise.all([
      crear(vision.HandLandmarker, 'hand_landmarker.task', {
        numHands: 2, minHandDetectionConfidence: 0.5, minHandPresenceConfidence: 0.5, minTrackingConfidence: 0.5,
      }),
      crear(vision.PoseLandmarker, `pose_landmarker_${this.poseModelo}.task`, OPCIONES_POSE),
    ]);
    this._crear = crear;
    this._vision = vision;
    this.manos = manos;
    this.cuerpo = cuerpo;
    this.delegado = d1 === d2 ? d1 : `${d1}/${d2}`;
    this.cargada = true;
  }

  /** Cambia el modelo del cuerpo («full» o «lite») sin apagar la cámara, y lo recuerda. */
  async cambiarPose(modelo) {
    escribir(CLAVE_POSE, modelo);
    if (modelo === this.poseModelo) return;
    this.poseModelo = modelo;
    if (!this.cargada) return;
    const [nuevo] = await this._crear(this._vision.PoseLandmarker, `pose_landmarker_${modelo}.task`, OPCIONES_POSE);
    const viejo = this.cuerpo;
    this.cuerpo = nuevo;
    try { viejo.close(); } catch { /* ya cerrado */ }
  }

  /** Pide la cámara y empieza. Lanza un error con `.motivo` si no se puede. */
  async encender(alProgreso = () => {}) {
    if (this.activa) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw Object.assign(new Error('Este navegador no da acceso a la cámara'), { motivo: 'sin-api' });
    }
    await this.cargar(alProgreso);
    alProgreso('Pidiendo permiso para la cámara…');
    try {
      this.flujo = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { width: { ideal: C.CAMERA_WIDTH }, height: { ideal: C.CAMERA_HEIGHT }, facingMode: 'user' },
      });
    } catch (e) {
      const motivo = e.name === 'NotAllowedError' || e.name === 'SecurityError' ? 'negada'
        : e.name === 'NotFoundError' || e.name === 'OverconstrainedError' ? 'no-hay' : e.name === 'NotReadableError' ? 'ocupada'
          : e.name === 'NotSupportedError' ? 'sin-api' : 'otro';
      throw Object.assign(new Error(e.message), { motivo });
    }
    this.video.srcObject = this.flujo;
    await this.video.play();
    this.activa = true;
    const pista = this.flujo.getVideoTracks()[0];
    if (pista) pista.addEventListener('ended', () => this.apagar());
    this._siguiente();
  }

  apagar() {
    this.activa = false;
    if (this._idCuadro && this.video.cancelVideoFrameCallback) this.video.cancelVideoFrameCallback(this._idCuadro);
    if (this.flujo) this.flujo.getTracks().forEach((t) => t.stop());
    this.flujo = null;
    this.video.srcObject = null;
  }

  // Un cálculo por cada cuadro nuevo de la cámara (como la app, que procesa cada cuadro que
  // lee): el segmentador cuenta frames, así que el ritmo importa.
  _siguiente() {
    if (!this.activa) return;
    if (this.video.requestVideoFrameCallback) {
      this._idCuadro = this.video.requestVideoFrameCallback(() => { this._procesar(); this._siguiente(); });
    } else {
      requestAnimationFrame(() => {
        if (this.video.currentTime !== this._tiempoVideo) { this._tiempoVideo = this.video.currentTime; this._procesar(); }
        this._siguiente();
      });
    }
  }

  _procesar() {
    const ts = Math.max(Math.round(performance.now()), this._ultimoTs + 1);   // VIDEO exige tiempos crecientes
    const resultado = this.procesarFuente(this.video, this.video.videoWidth, this.video.videoHeight, ts);
    if (resultado && this.alFrame) this.alFrame(resultado);
  }

  /** Espejo + detección + dibujo de una imagen (cuadro de video, <img> o ImageBitmap).
   *  También lo usa la prueba con video (sitio/herramientas/prueba_video.py), cuadro por cuadro. */
  procesarFuente(fuente, w, h, ts) {
    if (!w || !h) return null;
    if (this.canvas.width !== w || this.canvas.height !== h) { this.canvas.width = w; this.canvas.height = h; }
    const ctx = this.ctx;
    ctx.save();
    ctx.imageSmoothingEnabled = false;   // voltear sin mezclar píxeles: igual que cv2.flip
    ctx.translate(w, 0);
    ctx.scale(-1, 1);              // espejo, antes de detectar
    ctx.drawImage(fuente, 0, 0, w, h);
    ctx.restore();
    this._ultimoTs = Math.max(ts, this._ultimoTs + 1);
    let resultado;
    try {
      const manos = this.manos.detectForVideo(this.canvas, this._ultimoTs);
      const cuerpo = this.cuerpo.detectForVideo(this.canvas, this._ultimoTs);
      resultado = this.detector.procesar(manos, cuerpo, w, h);
    } catch (e) {
      console.error('[Cámara] Error al detectar:', e);
      return null;
    }
    this._dibujar(resultado.dibujo, w, h);
    return resultado;
  }

  _dibujar(dibujo, w, h) {
    const ctx = this.ctx;
    const k = w / 1280;            // grosores como en la app (cuadro de 1280 px)
    ctx.lineCap = 'round';
    dibujo.brazos.forEach((pts, lado) => {
      ctx.strokeStyle = COLORES[lado];
      ctx.lineWidth = 4 * k;
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x * w, y * h) : ctx.moveTo(x * w, y * h)));
      ctx.stroke();
      ctx.fillStyle = '#fff';
      for (const [x, y] of pts) { ctx.beginPath(); ctx.arc(x * w, y * h, 6 * k, 0, 2 * Math.PI); ctx.fill(); }
    });
    for (const { lado, puntos } of dibujo.manos) {
      ctx.strokeStyle = COLORES[lado];
      ctx.lineWidth = 2.5 * k;
      ctx.beginPath();
      for (const [a, b] of HAND_CONNECTIONS) {
        ctx.moveTo(puntos[a][0] * w, puntos[a][1] * h);
        ctx.lineTo(puntos[b][0] * w, puntos[b][1] * h);
      }
      ctx.stroke();
      ctx.fillStyle = '#fff';
      for (const [x, y] of puntos) { ctx.beginPath(); ctx.arc(x * w, y * h, 3.5 * k, 0, 2 * Math.PI); ctx.fill(); }
    }
  }
}

/** ¿El navegador puede con «Pruébalo»? (WebGL para el avatar, WebAssembly y cámara para MediaPipe) */
export function revisarNavegador() {
  const faltan = [];
  try {
    const c = document.createElement('canvas');
    if (!(c.getContext('webgl2') || c.getContext('webgl'))) faltan.push('webgl');
  } catch { faltan.push('webgl'); }
  if (typeof WebAssembly !== 'object') faltan.push('wasm');
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) faltan.push('camara');
  if (!window.isSecureContext) faltan.push('https');
  return faltan;
}

export { ARM_CHAINS };

// «Imítame»: la cámara del visitante mueve al avatar, todo dentro del navegador.
// Usa MediaPipe para web (manos y cuerpo) y arma los mismos frames que la app
// (app/modules/motion.py, world_frame): puntos en metros con x a la izquierda de la persona,
// y hacia arriba y z hacia la cámara, y cada mano colocada en la muñeca de su lado del cuerpo.
// El video nunca sale del navegador; solo se descargan los modelos.
const VERSION = '0.10.14';
const CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VERSION}`;
const MODELO_MANOS = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
const MODELO_CUERPO = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
const MUNECA = { left: 15, right: 16 };
const SUAVIZADO = 0.55;          // 0 = sin suavizar, 1 = inmóvil

export class Imitador {
  constructor(video) {
    this.video = video;
    this.activo = false;
    this.previo = null;
  }

  async iniciar(alFrame, alEstado) {
    this.alFrame = alFrame; this.alEstado = alEstado;
    if (!this.manos) {
      const vision = await import(/* webpackIgnore: true */ `${CDN}/vision_bundle.mjs`);
      const archivos = await vision.FilesetResolver.forVisionTasks(`${CDN}/wasm`);
      const crear = (Clase, modelo, extra) => Clase.createFromOptions(archivos, {
        baseOptions: { modelAssetPath: modelo, delegate: 'GPU' }, runningMode: 'VIDEO', ...extra,
      }).catch(() => Clase.createFromOptions(archivos, {
        baseOptions: { modelAssetPath: modelo, delegate: 'CPU' }, runningMode: 'VIDEO', ...extra,
      }));
      [this.manos, this.cuerpo] = await Promise.all([
        crear(vision.HandLandmarker, MODELO_MANOS, { numHands: 2 }),
        crear(vision.PoseLandmarker, MODELO_CUERPO, { numPoses: 1 }),
      ]);
    }
    alEstado('Pidiendo permiso para la cámara…');
    this.flujo = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' }, audio: false });
    this.video.srcObject = this.flujo;
    await this.video.play();
    this.video.classList.add('visible');
    this.activo = true; this.previo = null; this.ultimoT = -1;
    alEstado('Muévete frente a la cámara: el avatar te imita');
    const paso = () => {
      if (!this.activo) return;
      this._procesar();
      this.idCuadro = requestAnimationFrame(paso);
    };
    paso();
  }

  detener() {
    this.activo = false;
    cancelAnimationFrame(this.idCuadro);
    this.flujo?.getTracks().forEach((t) => t.stop());
    this.video.srcObject = null;
    this.video.classList.remove('visible');
  }

  _procesar() {
    const v = this.video;
    if (v.readyState < 2) return;
    const t = performance.now();
    if (t <= this.ultimoT) return;
    this.ultimoT = t;
    const rc = this.cuerpo.detectForVideo(v, t);
    const rm = this.manos.detectForVideo(v, t);
    if (!rc.worldLandmarks || !rc.worldLandmarks.length) return;

    // Imagen sin espejo: la izquierda de la persona queda a la derecha de la imagen, que es +x
    // en MediaPipe. Solo hay que invertir y (abajo → arriba) y z (lejos → hacia la cámara).
    const aPersona = (p) => [p.x, -p.y, -p.z];
    const pose = rc.worldLandmarks[0].map(aPersona);
    const vis = rc.landmarks[0].map((p) => (p.visibility ?? 1));
    const frame = { pose, vis, left: null, right: null };

    // Cada mano va al lado de la muñeca del cuerpo más cercana (en la imagen)
    const img = rc.landmarks[0];
    (rm.worldLandmarks || []).forEach((mano, i) => {
      const w = rm.landmarks[i][0];
      const dist = (k) => Math.hypot(img[MUNECA[k]].x - w.x, img[MUNECA[k]].y - w.y);
      const lado = dist('left') <= dist('right') ? 'left' : 'right';
      if (frame[lado]) return;
      const pts = mano.map(aPersona);
      const base = pts[0]; const mun = pose[MUNECA[lado]];
      frame[lado] = pts.map((p) => [p[0] - base[0] + mun[0], p[1] - base[1] + mun[1], p[2] - base[2] + mun[2]]);
    });

    this.alFrame(this._suavizar(frame));
  }

  _suavizar(f) {
    const p = this.previo;
    const mezcla = (a, b) => (a && b ? b.map((q, i) => q.map((x, j) => a[i][j] + (x - a[i][j]) * (1 - SUAVIZADO))) : b);
    const out = p ? { pose: mezcla(p.pose, f.pose), vis: f.vis, left: mezcla(p.left, f.left), right: mezcla(p.right, f.right) } : f;
    this.previo = out;
    return out;
  }
}

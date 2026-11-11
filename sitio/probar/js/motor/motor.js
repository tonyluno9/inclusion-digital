// El motor de K'ab T'aan en el navegador: port de app/inclusion_app.py (la lógica de la app) y de
// app/servidor_web.py (el contrato con la interfaz). La interfaz habla con él igual que con el
// servidor de Python:
//   accion(nombre, datos)  ≈ POST /api/accion        -> { ok, resultado, aviso } | { ok: false, error }
//   obtener(ruta)          ≈ GET /api/... y /datos/...
//   escuchar(alEvento)     ≈ /eventos (SSE)           -> alEvento({ estado, mundo }) en cada frame
// La cámara (camara.js) entrega cada frame ya detectado: el frame crudo de 147 valores y el
// frame 3D del avatar. Todo pasa dentro del navegador; nada se envía a ningún servidor.
import { Almacen } from './almacen.js';
import * as C from './config.js';
import { elbowsVisible, handsPresent, keepHands, missingHands, poseValid } from './landmarks.js';
import { LiveSmoother, MotionRecorder, frameToJson, makeClip, restArm, restingSide, trimClip, validateClip } from './movimiento.js';
import { Progreso, normalizar } from './progreso.js';
import { SignSegmenter } from './segmentador.js';
import { Traductor } from './traductor.js';
import { Dictado, Voz, beepError, beepStart, beepStop } from './voz.js';

const GREEN = 'ok';
const RED = 'error';
const GRAY = 'neutro';
const reloj = () => performance.now() / 1000;
const r5 = (v) => Math.fround(Number(v.toFixed(5)));    // el CSV de la app guarda 5 decimales

// ----------------------------------------------------------------- dataset
/** Port de DataCollector: las muestras (secuencias de 30 × 147) van en el navegador. */
export class Colector {
  constructor(almacen) {
    this.almacen = almacen;
    this.muestras = almacen.leer('muestras', []);
  }

  _guardar() { this.almacen.escribir('muestras', this.muestras); }

  saveSequence(label, secuencia, person = 'anonimo') {
    label = label.toLowerCase().trim();
    person = person.toLowerCase().trim() || 'anonimo';
    const seq = new Float32Array(secuencia.length * secuencia[0].length);
    secuencia.forEach((fr, i) => { for (let j = 0; j < fr.length; j += 1) seq[i * fr.length + j] = r5(fr[j]); });
    this.muestras.push({ label, person, seq });
    this._guardar();
  }

  count(label = null) {
    if (label === null) return this.muestras.length;
    const l = label.toLowerCase().trim();
    return this.muestras.filter((m) => m.label === l).length;
  }

  removeLast() {
    const m = this.muestras.pop();
    if (m) this._guardar();
    return m ? m.label : null;
  }

  deleteLabel(label) {
    const l = label.toLowerCase().trim();
    const antes = this.muestras.length;
    this.muestras = this.muestras.filter((m) => m.label !== l);
    if (this.muestras.length !== antes) this._guardar();
    return antes - this.muestras.length;
  }

  stats() {
    const senas = {};
    const personas = {};
    for (const m of this.muestras) {
      senas[m.label] = (senas[m.label] || 0) + 1;
      personas[m.person] = (personas[m.person] || 0) + 1;
    }
    return [senas, personas];
  }
}

// ------------------------------------------------------------------- clips
/** Port de ClipStore: los clips del visitante (con su toma anterior para deshacer) y los de
 *  fábrica, que vienen con la página y no se pueden borrar (uno propio los reemplaza). */
export class Clips {
  constructor(almacen, fabrica = {}) {
    this.almacen = almacen;
    this.propios = new Map(Object.entries(almacen.leer('clips', {})));
    this.previos = new Map(Object.entries(almacen.leer('clipsPrevios', {})));
    this.fabrica = new Map(Object.entries(fabrica));
  }

  static filename(word) {
    return word.trim().toLowerCase().replace(/[<>:"/\\|?*\x00-\x1f]/g, '_') || '_';
  }

  _guardar() {
    this.almacen.escribir('clips', Object.fromEntries(this.propios));
    this.almacen.escribir('clipsPrevios', Object.fromEntries(this.previos));
  }

  save(clip) {
    const k = Clips.filename(clip.word);
    if (this.propios.has(k)) this.previos.set(k, this.propios.get(k)); else this.previos.delete(k);
    this.propios.set(k, clip);
    this._guardar();
    return k;
  }

  undo(word) {
    const k = Clips.filename(word);
    if (!this.propios.has(k)) return null;
    let r;
    if (this.previos.has(k)) { this.propios.set(k, this.previos.get(k)); this.previos.delete(k); r = 'restaurado'; } else { this.propios.delete(k); r = 'borrado'; }
    this._guardar();
    return r;
  }

  load(word) {
    const k = Clips.filename(word);
    const clip = this.propios.get(k) || this.fabrica.get(k);
    if (!clip) throw new Error('no existe');
    return validateClip(clip);
  }

  esDeFabrica(word) { const k = Clips.filename(word); return this.fabrica.has(k) && !this.propios.has(k); }

  words() { return [...new Set([...this.propios.keys(), ...this.fabrica.keys()])].sort(); }
}

// --------------------------------------------------------------- traductor
/** Port de GestureLogic: el traductor del visitante (si entrenó uno) o el de fábrica. */
export class Logica {
  constructor(almacen, fabrica = null) {
    this.almacen = almacen;
    this.fabrica = fabrica;
    this.model = null;
    this.classes = [];
    this.origen = null;
    this.loadModel();
  }

  loadModel() {
    this.model = null;
    this.classes = [];
    this.origen = null;
    for (const [m, origen] of [[this.almacen.leer('modelo'), 'propio'], [this.fabrica, 'fabrica']]) {
      if (!m) continue;
      try {
        this.model = new Traductor(m, { minConfianza: C.MIN_CONFIDENCE, featureVersion: C.FEATURE_VERSION, sequenceLength: C.SEQUENCE_LENGTH });
        this.classes = [...this.model.clases];
        this.origen = origen;
        return;
      } catch (e) { console.warn(`[Traductor] ${origen}: ${e.message}`); }
    }
  }

  predict(secuencia) {
    if (!this.model) return ['', 0];
    const [sena, conf] = this.model.predict(secuencia);
    return [sena, conf];
  }
}

async function oracion(palabras) {
  const unidas = palabras.join(' ');
  if (!C.URL_ORACION) return unidas;
  try {
    const r = await fetch(C.URL_ORACION, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ palabras }) });
    const j = await r.json();
    return (j && j.oracion) || unidas;
  } catch { return unidas; }
}

// --------------------------------------------------------------------- app
/** Port de InclusionApp (sin la ventana de OpenCV ni el envío por UDP). */
export class App {
  constructor({ almacen, categorias = [], modelo = null, clips = {}, manos = {}, clock = reloj, tts = new Voz(), stt = new Dictado(), entrenador = null }) {
    this.almacen = almacen;
    this.categorias = categorias;
    this.collector = new Colector(almacen);
    this.logic = new Logica(almacen, modelo);
    this.clips = new Clips(almacen, clips);
    this.tts = tts;
    this.stt = stt;
    this.entrenador = entrenador;
    this.clock = clock;
    this.recorder = new MotionRecorder(C.AVATAR_PREROLL_FRAMES + C.SEGMENT_START_FRAMES);
    this.smoother = new LiveSmoother();
    this.lastClip = null;
    this.pendingTake = null;
    this.takeSeq = 0;
    this.hands = 'dos';
    this.handsByWord = { ...manos, ...almacen.leer('manos', {}) };
    this.progreso = new Progreso(almacen.leer('progreso'));
    this.practice = false;
    this.liveWorld = null;
    this.wordSeq = 0;
    this.textSeq = 0;
    this.clipSeq = 0;
    this.actionStatus = '';
    this.segmenter = new SignSegmenter(C.SEQUENCE_LENGTH, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES, C.SEGMENT_MIN_FRAMES,
      C.SEGMENT_MAX_FRAMES, C.SEGMENT_CONTEXT_FRAMES, C.RESTING_HAND_MARGIN);
    this.mode = 'DETECTION';
    this.label = '';
    this.person = 'anonimo';
    this.armed = false;
    this.prediction = '';
    this.confidence = 0;
    this.history = [];
    this.pendingWords = [];
    this.lastHandsTime = this.clock();
    this.sentence = '';
    this.sentenceLoading = false;
    this.sttText = '';
    this.status = '';
    this.statusUntil = 0;
    this.flash = null;
    this.flashUntil = 0;
    this.training = false;
    this.bodyVisible = true;
    this.framingHint = '';
    this._elbowsSeen = [];
    this.lastSaved = null;
    this.modelSeq = 0;
  }

  // ----------------------------------------------------------- utilidades
  notify(texto, segundos = 3) {
    this.status = texto;
    this.statusUntil = this.clock() + segundos;
  }

  _flash(color, segundos = 0.5) { this.flash = color; this.flashUntil = this.clock() + segundos; }

  _setMode(mode) {
    this.mode = mode;
    this.pendingTake = null;
    this.practice = false;
    this._elbowsSeen = [];
    this.armed = false;
    this.prediction = '';
    this.segmenter.reset();
    this.recorder.cancel();
  }

  _guardarProgreso() { this.almacen.escribir('progreso', this.progreso.datos); }

  // -------------------------------------------------------------- acciones
  _rememberHands() {
    if (!this.label) return;
    this.handsByWord[this.label] = this.hands;
    this.almacen.escribir('manos', this.handsByWord);
  }

  setHands(mode) {
    if (!C.HANDS_MODES.includes(mode)) throw new Error(`modo de manos desconocido: ${mode}`);
    this.hands = mode;
    this.segmenter.reset();
    this.recorder.cancel();
    this._rememberHands();
    this.notify({
      dos: 'Seña de dos manos',
      derecha: 'Seña de una mano: la derecha (la izquierda no se graba)',
      izquierda: 'Seña de una mano: la izquierda (la derecha no se graba)',
    }[mode]);
    return mode;
  }

  _wordHands() { this.hands = this.handsByWord[this.label] ?? this.hands; }

  _handsLabel() { return { dos: 'dos manos', derecha: 'mano derecha', izquierda: 'mano izquierda' }[this.hands]; }

  trainWord(word, person = '') {
    this.label = word.trim().toLowerCase();
    if (person && person.trim()) this.person = person.trim().toLowerCase();
    this._setMode('TRAINING');
    this._wordHands();
    const n = this.collector.count(this.label);
    this.notify(`'${this.label}' por ${this.person} (${n} muestras, ${this._handsLabel()}). Espacio para empezar.`);
  }

  avatarWord(word) {
    this.label = word.trim().toLowerCase();
    this._setMode('AVATAR');
    if (!this.label) { this.notify('Avatar en vivo. Escribe una palabra para grabar su movimiento.'); return; }
    this._wordHands();
    const existe = this.clips.words().includes(Clips.filename(this.label));
    this.notify(`Avatar: '${this.label}' (${this._handsLabel()})${existe ? ' (ya tiene clip: se reemplaza)' : ''}. Espacio para grabar.`);
  }

  detectionMode(practice = false) {
    this._setMode('DETECTION');
    this.practice = Boolean(practice);
    if (practice) { this.pendingWords = []; this.history = []; }
    this.logic.loadModel();
    this.notify(practice ? 'Modo práctica' : 'Modo detección');
  }

  toggleRecording() {
    if (this.mode !== 'TRAINING' && this.mode !== 'AVATAR') return false;
    if (!this.label) { this.notify('Primero escribe la palabra que vas a grabar.'); return false; }
    if (this.pendingTake !== null) { this.notify('Primero guarda o descarta la toma que estás revisando.'); return false; }
    this.armed = !this.armed;
    this.segmenter.reset();
    this.recorder.cancel();
    this.notify(this.armed ? 'Grabación activada' : 'Grabación en pausa');
    return this.armed;
  }

  undo() {
    if (this.mode === 'TRAINING') {
      const quitada = this.collector.removeLast();
      this._flash(quitada ? RED : GRAY);
      this.notify(quitada ? `Se deshizo la última muestra ('${quitada}')` : 'No hay muestras.');
    } else if (this.mode === 'AVATAR') {
      if (this.pendingTake !== null) { this.discardTake(); return; }
      const r = this.clips.undo(this.label);
      this._flash(r ? RED : GRAY);
      this.notify({
        restaurado: `Se deshizo la toma: '${this.label}' vuelve a la anterior`,
        borrado: `Se borró el clip de '${this.label}'`,
      }[r] || `'${this.label}' no tiene clip propio.`);
    }
  }

  reloadModel() {
    this.logic.loadModel();
    this.prediction = '';
    this.notify(this.logic.model ? 'Modelo recargado' : 'No hay modelo para cargar');
  }

  toggleVoice() {
    const on = this.tts.toggle();
    this.notify(`Voz ${on ? 'activada' : 'desactivada'}`);
    return on;
  }

  toggleListening() {
    if (!this.stt.isRecording) { this.sttText = ''; this.stt.start_recording(); } else this.stt.stop_recording();
    return this.stt.isRecording;
  }

  deleteSign(word) {
    const n = this.collector.deleteLabel(word);
    this.notify(n ? `Borradas ${n} muestras de '${word}'. Vuelve a entrenar el traductor.` : `No se encontró '${word}'.`);
    return n;
  }

  deleteClip(word) {
    let n = 0;
    while (this.clips.undo(word)) n += 1;
    const fabrica = this.clips.esDeFabrica(word);
    this.notify(n ? `Se borró tu movimiento de '${word}'.${fabrica ? ' Queda el de demostración.' : ''}`
      : fabrica ? `El movimiento de '${word}' es de demostración: no se puede borrar, pero puedes grabar el tuyo.` : `'${word}' no tiene movimiento.`);
    return Boolean(n);
  }

  saveTake(inicio = null, fin = null) {
    if (this.pendingTake === null) throw new Error('no hay ninguna toma por guardar');
    let clip = this.pendingTake;
    if (inicio !== null || fin !== null) clip = trimClip(clip, inicio ?? 0, fin ?? clip.duration);
    this.pendingTake = null;
    this._storeClip(clip);
    return this.lastClip;
  }

  discardTake() {
    if (this.pendingTake === null) return false;
    this.pendingTake = null;
    this._flash(GRAY);
    this.notify('Toma descartada. Espacio para grabar otra.');
    return true;
  }

  _storeClip(clip) {
    this.lastClip = this.clips.save(clip);
    this.clipSeq += 1;
    this._flash(GREEN);
    this.notify(`Movimiento guardado: '${clip.word}' (${clip.duration.toFixed(1)} s)`);
  }

  // ----------------------------------------------- aprender y diccionario
  _categoriasDict() { return Object.fromEntries(this.categorias.map((c) => [c.id, c.palabras])); }

  _evaluarInsignias() {
    // «Traductor entrenado» se gana con un traductor propio, no con el de demostración
    const propio = this.logic.origen === 'propio';
    return this.progreso.evaluar(this._categoriasDict(), this.logic.model ? this.logic.classes : [],
      this.clips.propios.size, propio);
  }

  practiceResult(word, correct, confidence = 0) {
    const estrellas = this.progreso.registrarIntento(word, correct, confidence);
    const nuevas = this._evaluarInsignias();
    this._guardarProgreso();
    return { estrellas, nuevas, resumen: this.progreso.resumen() };
  }

  progressSummary() {
    const nuevas = this._evaluarInsignias();
    if (nuevas.length) this._guardarProgreso();
    return { ...this.progreso.resumen(), nuevas };
  }

  vocabulary() {
    const [labels] = this.collector.stats();
    const model = this.logic.model ? this.logic.classes : [];
    const out = new Map();
    const entry = (label) => {
      const clave = normalizar(label);
      if (!out.has(clave)) {
        out.set(clave, { palabra: label, clave, nombre: C.displayName(label), muestras: 0, traductor: false, movimiento: null,
          manos: this.handsByWord[label] ?? null });
      }
      return out.get(clave);
    };
    for (const [label, n] of Object.entries(labels)) entry(label).muestras += n;
    for (const label of model) entry(label).traductor = true;
    for (const w of this.clips.words()) entry(w).movimiento = w;
    return [...out.values()].sort((a, b) => (a.clave < b.clave ? -1 : a.clave > b.clave ? 1 : 0));
  }

  interlocutorText(texto) {
    this.sttText = texto.trim();
    this.textSeq += 1;
  }

  startTraining() {
    if (this.training) { this.notify('Ya se está entrenando...'); return; }
    if (!this.entrenador) { this.notify('Este navegador no puede entrenar el traductor.', 5); return; }
    this.training = true;
    this.notify('Entrenando el traductor... la cámara sigue funcionando.', 600);
    this.entrenador(this.collector.muestras).then((modelo) => {
      this.almacen.escribir('modelo', modelo);
      this.logic.loadModel();
      this.modelSeq += 1;            // la interfaz celebra solo cuando de verdad hay un traductor nuevo
      this.notify('Traductor entrenado y cargado.', 5);
    }).catch((e) => {
      this.notify(`No se pudo entrenar: ${e.message}`, 6);
    }).finally(() => { this.training = false; });
  }

  startSentence(palabras) {
    this.sentenceLoading = true;
    this.sentence = '';
    oracion(palabras).then((texto) => {
      this.sentence = texto;
      this.tts.speak(texto);
      this.sentenceLoading = false;
      this.progreso.registrarOracion();
      this._guardarProgreso();
    });
  }

  // -------------------------------------------------------------- por frame
  /** raw: Float32Array(147) del detector (imagen en espejo); world: frame 3D o null. */
  processFrame(raw, world) {
    const now = this.clock();
    if ((this.mode === 'TRAINING' || this.mode === 'AVATAR') && this.hands !== 'dos') {
      // Seña de una mano: la otra no cuenta (ni para cortar la seña ni en el avatar)
      raw = keepHands(raw, this.hands);
      if (world) world = restArm(world, restingSide(this.hands));
    }
    this.liveWorld = null;
    if (this.mode === 'AVATAR' && world) this.liveWorld = this.smoother.suavizar(world, now);

    if (handsPresent(raw)) this.lastHandsTime = now;
    this.bodyVisible = poseValid(raw) || this.segmenter.bodyVisible;
    this.framingHint = this._framing(raw);
    this.actionStatus = this.mode === 'AVATAR' ? this._avatar(raw, world, now) : this._segment(raw);
    this.tick(now);
  }

  /** Lo que la app revisa en cada frame aunque no haya cámara (dictado, avisos, destellos). */
  tick(now = this.clock()) {
    const texto = this.stt.get_result();
    if (texto) { this.sttText = texto; this.textSeq += 1; }
    if (this.stt.lastError) { this.notify(this.stt.lastError, 5); this.stt.lastError = ''; }
    if (this.tts.lastError) { this.notify(this.tts.lastError, 5); this.tts.lastError = ''; }
    if (this.status && now > this.statusUntil) this.status = '';
    if (this.flash !== null && now > this.flashUntil) this.flash = null;
  }

  _framing(raw) {
    if (!poseValid(raw)) return '';
    if (this.mode === 'AVATAR' || handsPresent(raw)) {
      this._elbowsSeen.push(elbowsVisible(raw));
      if (this._elbowsSeen.length > C.FRAMING_WINDOW) this._elbowsSeen.shift();
    }
    const vistos = this._elbowsSeen;
    if (vistos.length === C.FRAMING_WINDOW && vistos.filter(Boolean).length < C.FRAMING_MIN_SEEN * vistos.length) return 'Aléjate: no veo tus codos';
    return '';
  }

  _avatar(raw, world, now) {
    const estabaActivo = this.segmenter.active;
    const secuencia = this.armed ? this.segmenter.update(raw) : null;
    if (world) this.recorder.push(world, now);
    if (this.armed && !estabaActivo && this.segmenter.active) { this.recorder.begin(); beepStart(); }
    if (estabaActivo && !this.segmenter.active) {
      const frames = this.recorder.finish();
      if (secuencia && frames.length > 1) {
        const clip = makeClip(frames, this.label, this.person, this.hands);
        beepStop();
        // Se revisa y recorta antes de guardarla; mientras, no se graba otra
        this.pendingTake = clip;
        this.takeSeq += 1;
        this.armed = false;
        this.notify('Revisa la toma: recórtala si hace falta y guárdala.');
      } else {
        beepError();
        this._flash(RED);
        this.notify('Seña muy corta o sin cuerpo detectado, no se guardó.');
      }
    }
    if (this.segmenter.active) return `GRABANDO movimiento de '${this.label}'... baja las manos al terminar`;
    if (this.pendingTake !== null) return `Revisando la toma de '${this.label}'`;
    if (this.armed) return `Avatar '${this.label}': levanta las manos y haz la seña`;
    return this.label ? `Avatar '${this.label}': Espacio para grabar` : '';
  }

  _segment(raw) {
    const estabaActivo = this.segmenter.active;
    let secuencia = null;
    if (this.mode === 'DETECTION' || this.armed) secuencia = this.segmenter.update(raw);
    const termino = estabaActivo && !this.segmenter.active;

    if (this.mode === 'TRAINING') {
      if (!estabaActivo && this.segmenter.active) beepStart();
      const faltan = termino && secuencia ? missingHands(secuencia, this.hands, C.MIN_HAND_COVERAGE) : [];
      if (faltan.length) {
        beepError();
        this._flash(RED);
        if (this.hands === 'dos' && faltan.length === 1) {
          this.notify(`No vi tu mano ${faltan[0]} en casi toda la seña: no se guardó. Si la seña es de una mano, elige «una mano».`, 5);
        } else {
          this.notify(`No vi tu mano ${faltan.join(' ni la ')} en casi toda la seña: no se guardó. Repítela.`, 5);
        }
      } else if (termino) {
        if (secuencia) {
          this.collector.saveSequence(this.label, secuencia, this.person);
          this.lastSaved = [this.label, this.person];
          beepStop();
          this._flash(GREEN);
          this.notify(`Muestra guardada: '${this.label}' (${this.collector.count(this.label)} en total)`);
        } else {
          beepError();
          this._flash(RED);
          this.notify('Seña muy corta, no se guardó.');
        }
      }
      const n = this.collector.count(this.label);
      if (this.segmenter.active) return `GRABANDO '${this.label}'... baja las manos al terminar`;
      if (this.armed) return `'${this.label}' (${n} muestras): levanta las manos y haz la seña`;
      return `'${this.label}' (${n} muestras): Espacio para empezar a grabar`;
    }

    if (termino && secuencia) {
      const [pred, conf] = this.logic.predict(secuencia);
      this.confidence = conf;
      if (pred) {
        this.prediction = pred;
        this.wordSeq += 1;            // la interfaz reproduce la seña con el avatar
        const mostrada = C.displayName(pred);
        this.tts.speak(mostrada);
        if (!this.practice) {          // en Aprender no se arman oraciones
          this.pendingWords.push(mostrada);
          this.history = [...this.history, mostrada].slice(-C.SUBTITLE_HISTORY);
        }
      } else if (this.logic.model) {
        this.prediction = '';
        this.notify(`Seña no reconocida (${Math.round(conf * 100)}%)`, 1.5);
      }
    }
    // Oración tras un silencio sin manos
    if (this.pendingWords.length && !this.sentenceLoading && this.clock() - this.lastHandsTime > C.SILENCE_SECONDS) {
      const palabras = this.pendingWords;
      this.pendingWords = [];
      this.history = [];
      this.startSentence(palabras);
    }
    return this.logic.model ? '' : 'Sin traductor: graba señas en Entrenar y entrénalo';
  }

  state() {
    return {
      modo: this.mode,
      palabra: this.label,
      persona: this.person,
      muestras_palabra: this.label ? this.collector.count(this.label) : 0,
      armado: this.armed,
      grabando: this.segmenter.active,
      progreso: Math.min(1, this.segmenter.captured / C.SEGMENT_MAX_FRAMES),
      prediccion: this.prediction ? C.displayName(this.prediction) : '',
      confianza: Math.round(this.confidence * 1000) / 1000,
      historial: [...this.history],
      oracion: this.sentence,
      oracion_cargando: this.sentenceLoading,
      interlocutor: this.sttText,
      escuchando: Boolean(this.stt.isRecording),
      aviso: this.status,
      accion: this.actionStatus,
      destello: this.flash,
      voz: Boolean(this.tts.enabled),
      hablando: Boolean(this.tts.speaking),
      cuerpo_visible: this.bodyVisible,
      aviso_encuadre: this.framingHint,
      entrenando: this.training,
      modelo_senas: this.logic.model ? [...this.logic.classes].sort() : [],
      modelo_origen: this.logic.origen,
      modelo_seq: this.modelSeq,
      seq_palabra: this.wordSeq,
      seq_texto: this.textSeq,
      seq_clip: this.clipSeq,
      manos: this.hands,
      practica: this.practice,
      toma_seq: this.takeSeq,
      toma_pendiente: this.pendingTake !== null,
    };
  }
}

// ----------------------------------------------- acciones (como servidor_web.py)
function texto(d, clave) {
  const v = String(d[clave] ?? '').trim();
  if (!v) throw new RangeError(`falta '${clave}'`);
  return v.slice(0, 60);
}
const segundos = (d, clave) => (d[clave] === undefined || d[clave] === null ? null : Math.max(0, Number(d[clave])));

export const ACCIONES = {
  modo_deteccion: (app, d) => app.detectionMode(Boolean(d.practica)),
  entrenar_palabra: (app, d) => app.trainWord(texto(d, 'palabra'), String(d.persona ?? '')),
  avatar_palabra: (app, d) => app.avatarWord(String(d.palabra ?? '').slice(0, 60)),
  grabar: (app) => app.toggleRecording(),
  deshacer: (app) => app.undo(),
  entrenar_modelo: (app) => app.startTraining(),
  recargar_modelo: (app) => app.reloadModel(),
  voz: (app) => app.toggleVoice(),
  escuchar: (app) => app.toggleListening(),
  borrar_sena: (app, d) => app.deleteSign(texto(d, 'palabra')),
  borrar_clip: (app, d) => app.deleteClip(texto(d, 'palabra')),
  texto_interlocutor: (app, d) => app.interlocutorText(String(d.texto ?? '').slice(0, 300)),
  manos: (app, d) => app.setHands(String(d.modo ?? '')),
  guardar_toma: (app, d) => Boolean(app.saveTake(segundos(d, 'inicio'), segundos(d, 'fin'))),
  descartar_toma: (app) => app.discardTake(),
  practica: (app, d) => app.practiceResult(texto(d, 'palabra'), Boolean(d.acierto), Number(d.confianza || 0)),
};

/** Las rutas GET de servidor_web.py. Lanza Error('404') si no existe (como la respuesta 404). */
export function responderApi(app, ruta) {
  if (ruta === '/api/clips') return { clips: app.clips.words() };
  if (ruta.startsWith('/api/clip/')) return app.clips.load(ruta.slice('/api/clip/'.length));
  if (ruta === '/api/toma') { if (!app.pendingTake) throw new Error('404'); return app.pendingTake; }
  if (ruta === '/api/diccionario') return { palabras: app.vocabulary() };
  if (ruta === '/api/progreso') return app.progressSummary();
  if (ruta === '/api/dataset') { const [senas, personas] = app.collector.stats(); return { senas, personas }; }
  throw new Error('404');
}

/** Entrena en un Web Worker (entrenador.worker.js): la página y la cámara siguen fluidas. */
function entrenadorEnWorker(app) {
  return (muestras) => new Promise((resolver, rechazar) => {
    const w = new Worker(new URL('./entrenador.worker.js', import.meta.url), { type: 'module' });
    const terminar = () => w.terminate();
    w.onmessage = (ev) => {
      const m = ev.data;
      if (m.tipo === 'progreso') app.notify(`Entrenando el traductor… ${Math.round((100 * m.hecho) / m.total)} %`, 600);
      else if (m.tipo === 'listo') { terminar(); resolver(m.modelo); } else { terminar(); rechazar(new Error(m.mensaje)); }
    };
    w.onerror = (e) => { terminar(); rechazar(new Error(e.message || 'el entrenamiento falló')); };
    w.postMessage({ muestras: muestras.map((m) => ({ label: m.label, person: m.person, seq: m.seq })) });
  });
}

const obtenerJSON = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);

/**
 * Crea el motor. `base`: carpeta de datos de la página (categorías y lo de demostración).
 * Devuelve { app, almacen, accion, obtener, escuchar, alFrame, publicar }.
 */
export async function crearMotor({ base = 'datos/', camara = null } = {}) {
  const almacen = await new Almacen().abrir();
  const [cats, demo] = await Promise.all([obtenerJSON(`${base}categorias.json`), obtenerJSON(`${base}demo/indice.json`)]);
  let modelo = null;
  const clips = {};
  if (demo) {
    if (demo.modelo) modelo = await obtenerJSON(`${base}demo/${demo.modelo}`);
    for (const nombre of demo.clips || []) {
      const c = await obtenerJSON(`${base}demo/clips/${encodeURIComponent(nombre)}.json`);
      if (c) clips[Clips.filename(c.word)] = c;
    }
  }
  const app = new App({ almacen, categorias: (cats && cats.categorias) || [], modelo, clips, manos: (demo && demo.manos) || {} });
  if (typeof Worker !== 'undefined') app.entrenador = entrenadorEnWorker(app);
  if (almacen.error) app.notify(almacen.error, 8);

  const oyentes = new Set();
  let ultimo = { estado: {}, mundo: null };
  const tiempos = [];
  let fps = 0;

  function publicar() {
    const estado = app.state();
    estado.camara = Boolean(camara && camara.activa);
    estado.fps = Math.round(fps * 10) / 10;
    const mundo = app.liveWorld ? frameToJson(app.liveWorld, 0) : null;
    ultimo = { estado, mundo };
    for (const fn of oyentes) {
      try { fn(ultimo); } catch (e) { console.error(e); }
    }
  }

  /** Un frame nuevo de la cámara, ya detectado. */
  function alFrame({ raw, world }) {
    try { app.processFrame(raw, world); } catch (e) { console.error('[MOTOR] Error procesando un frame:', e); }
    const t = performance.now();
    tiempos.push(t);
    if (tiempos.length > 30) tiempos.shift();
    if (tiempos.length > 1) fps = ((tiempos.length - 1) * 1000) / (tiempos[tiempos.length - 1] - tiempos[0] + 1e-9);
    publicar();
  }

  // Sin cámara, el estado se publica unas veces por segundo (avisos, dictado, acciones)
  setInterval(() => {
    if (camara && camara.activa) return;
    fps = 0;
    tiempos.length = 0;
    app.tick();
    publicar();
  }, 200);

  async function accion(nombre, datos = {}) {
    if (!(nombre in ACCIONES)) return { ok: false, error: `acción desconocida: ${nombre}` };
    try {
      const resultado = ACCIONES[nombre](app, datos);
      publicar();
      return { ok: true, resultado: resultado === undefined ? null : resultado, aviso: app.status };
    } catch (e) {
      console.warn(e);
      return { ok: false, error: e.message || String(e) };   // como el ValueError de Python: el texto va a la interfaz
    }
  }

  async function obtener(ruta) {
    ruta = decodeURIComponent(ruta);
    if (ruta === '/api/estado') return ultimo.estado;
    if (ruta.startsWith('/api/')) return responderApi(app, ruta);
    if (ruta.startsWith('/datos/')) {
      const r = await fetch(`${base}${ruta.slice('/datos/'.length)}`);
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    }
    throw new Error('404');
  }

  function escuchar(fn) {
    oyentes.add(fn);
    if (ultimo.estado.modo) fn(ultimo); else publicar();
    return () => oyentes.delete(fn);
  }

  publicar();
  return { app, almacen, accion, obtener, escuchar, alFrame, publicar };
}

// Voz (texto a voz) y dictado (voz a texto) con los servicios del navegador, con la misma
// interfaz que app/modules/tts.py y stt.py para que el motor los use igual.

/** Mejor voz en español: México primero, luego EE. UU. y España (como pick_spanish_voice). */
export function elegirVoz(voces) {
  const puntos = (v) => {
    const l = (v.lang || '').toLowerCase().replace('_', '-');
    if (!l.startsWith('es')) return -1;
    return (l === 'es-mx' ? 30 : l === 'es-us' || l === 'es-419' ? 20 : l === 'es-es' ? 10 : 5) + (v.localService ? 1 : 0);
  };
  return [...voces].filter((v) => puntos(v) >= 0).sort((a, b) => puntos(b) - puntos(a))[0] || null;
}

export class Voz {
  constructor() {
    this.enabled = true;
    this.speaking = false;
    this.lastError = '';
    this.disponible = typeof speechSynthesis !== 'undefined';
    this.voz = null;
    if (this.disponible) {
      const cargar = () => { this.voz = elegirVoz(speechSynthesis.getVoices()); };
      cargar();
      speechSynthesis.addEventListener?.('voiceschanged', cargar);
    }
  }

  speak(texto) {
    if (!this.enabled || !texto) return;
    if (!this.disponible) { this.lastError = 'Este navegador no tiene voz'; return; }
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = this.voz ? this.voz.lang : 'es-MX';
    if (this.voz) u.voice = this.voz;
    u.onstart = () => { this.speaking = true; };
    u.onend = () => { this.speaking = speechSynthesis.speaking; };
    u.onerror = (e) => {
      this.speaking = false;
      if (e.error !== 'interrupted' && e.error !== 'canceled') this.lastError = 'No se pudo hablar';
    };
    speechSynthesis.speak(u);
  }

  toggle() {
    this.enabled = !this.enabled;
    if (!this.enabled && this.disponible) speechSynthesis.cancel();
    return this.enabled;
  }
}

/** Dictado con SpeechRecognition (Chrome, Edge, Safari). El audio lo procesa el servicio de voz
 *  del navegador (en Chrome y Edge, en línea): por eso se avisa antes de usarlo. */
export class Dictado {
  constructor() {
    const R = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
    this.disponible = Boolean(R);
    this.Clase = R;
    this.isRecording = false;
    this.lastError = '';
    this._resultado = '';
    this._partes = [];
  }

  start_recording() {
    if (!this.disponible) { this.lastError = 'Tu navegador no tiene dictado: escribe el texto (funciona en Chrome y Edge).'; return; }
    const r = new this.Clase();
    r.lang = 'es-MX';
    r.continuous = true;
    r.interimResults = false;
    this._partes = [];
    r.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i += 1) if (e.results[i].isFinal) this._partes.push(e.results[i][0].transcript.trim());
    };
    r.onerror = (e) => {
      this.lastError = e.error === 'not-allowed' || e.error === 'service-not-allowed'
        ? 'No hay permiso para el micrófono. Actívalo en el candado de la barra de direcciones.'
        : e.error === 'network' ? 'El dictado necesita internet.' : e.error === 'no-speech' ? 'No te escuché. Inténtalo otra vez.' : `Error del dictado (${e.error})`;
    };
    r.onend = () => {
      this.isRecording = false;
      const texto = this._partes.join(' ').trim();
      if (texto) this._resultado = texto;
    };
    try {
      r.start();
      this.rec = r;
      this.isRecording = true;
    } catch (e) {
      this.lastError = 'No se pudo empezar a dictar';
    }
  }

  stop_recording() {
    if (this.rec) this.rec.stop();
  }

  get_result() {
    const t = this._resultado;
    this._resultado = '';
    return t;
  }
}

/** Pitidos al empezar y terminar de grabar (modules/beep.py), con WebAudio. */
let audio = null;
function tono(frecuencias, duracion = 0.09) {
  try {
    audio = audio || new AudioContext();
    let t = audio.currentTime;
    for (const fr of frecuencias) {
      const o = audio.createOscillator();
      const g = audio.createGain();
      o.frequency.value = fr;
      g.gain.setValueAtTime(0.12, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + duracion);
      o.connect(g).connect(audio.destination);
      o.start(t);
      o.stop(t + duracion);
      t += duracion;
    }
  } catch { /* sin audio */ }
}
export const beepStart = () => tono([880]);
export const beepStop = () => tono([660, 990]);
export const beepError = () => tono([300, 220], 0.14);

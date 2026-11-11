// La app completa: el mismo guion por InclusionApp (Python) y por App (motor.js).
//   node sitio/probar/tests/app.test.mjs
// Señas por la cámara (Traducir, Aprender), acciones de la interfaz (como POST /api/accion),
// muestras de Entrenar (una y dos manos, rechazos), tomas del avatar (grabar, revisar, recortar,
// deshacer) y las rutas GET /api/... del Diccionario y del progreso. Después de cada paso, el
// estado de la app (lo que recibe la interfaz) tiene que ser el mismo. Solo se omiten los textos
// de aviso, que en la web no mencionan teclas ni el envío por UDP.
import { readFileSync } from 'node:fs';
import { Almacen } from '../js/motor/almacen.js';
import { ACCIONES, App, responderApi } from '../js/motor/motor.js';
import { fin, fixture, matriz, ok, profundo } from './comun.mjs';

const fx = fixture('app.json');
const modelo = fixture('modelo_sintetico.json');
const categorias = JSON.parse(readFileSync(new URL('../datos/categorias.json', import.meta.url), 'utf-8')).categorias;

let reloj = fx.reloj_inicio;
const tts = {
  enabled: true, speaking: false, lastError: '', dichas: [],
  speak(t) { if (this.enabled && t) this.dichas.push(t); },
  toggle() { this.enabled = !this.enabled; return this.enabled; },
};
const stt = {
  isRecording: false, lastError: '', disponible: true, resultados: [],
  start_recording() { this.isRecording = true; },
  stop_recording() { this.isRecording = false; this.resultados.push('¿en qué le puedo ayudar?'); },
  get_result() { return this.resultados.shift() || ''; },
};
const almacen = new Almacen();               // sin IndexedDB: en memoria
almacen.memoria.set('modelo', modelo);      // el traductor «entrenado» por quien usa la app
const app = new App({ almacen, categorias, clock: () => reloj, tts, stt });
app.progreso.hoy = () => fx.hoy;

const pts = (plano) => (plano ? Array.from({ length: plano.length / 3 }, (_, i) => plano.slice(i * 3, i * 3 + 3).map(Math.fround)) : null);
const sinFecha = (x) => {
  if (x && typeof x === 'object' && !Array.isArray(x)) {
    const o = {};
    for (const [k, v] of Object.entries(x)) if (k !== 'created') o[k] = sinFecha(v);
    return o;
  }
  return x;
};
const normal = (x) => (x === undefined ? null : JSON.parse(JSON.stringify(sinFecha(x))));
const vaciar = async () => { for (let i = 0; i < 4; i += 1) await null; };   // la oración se arma en una promesa

let pasoMal = null;
for (const [n, paso] of fx.pasos.entries()) {
  const nombre = `paso ${n + 1}: ${paso.tipo} ${paso.nombre || paso.ruta || `${paso.mundos.length} cuadros`}`;
  const errores = [];
  if (paso.tipo === 'frames') {
    const frames = matriz(paso.frames);
    for (const [k, raw] of frames.entries()) {
      reloj += 1 / 30;
      const m = paso.mundos[k];
      app.processFrame(raw, { pose: pts(m.pose), vis: m.vis && m.vis.map(Math.fround), left: pts(m.left), right: pts(m.right) });
      await vaciar();
    }
  } else if (paso.tipo === 'accion') {
    let r; let okJs = true; let error;
    try { r = ACCIONES[paso.nombre](app, paso.datos); } catch (e) { okJs = false; error = e.message; }
    await vaciar();
    if (okJs !== paso.ok) errores.push(`ok: ${okJs} vs ${paso.ok} (${error || ''})`);
    else if (!okJs && error !== paso.error) errores.push(`error: «${error}» vs «${paso.error}»`);
    else if (okJs) { const d = profundo(normal(r), paso.resultado, 1e-9, 'resultado'); if (d) errores.push(d); }
  } else {
    let r;
    try { r = responderApi(app, paso.ruta); } catch (e) { r = e.message === '404' || e.message === 'no existe' ? { error: 404 } : { error: e.message }; }
    const d = profundo(normal(r), paso.resultado, 1.1e-4, 'resultado');
    if (d) errores.push(d);
    if (paso.muestras) {
      const js = app.collector.muestras;
      const igual = js.length === paso.muestras.length && js.every((m, i) => m.label === paso.muestras[i].label
        && m.person === paso.muestras[i].person && m.seq.every((v, j) => v === Math.fround(paso.muestras[i].valores[j])));
      if (!igual) errores.push('las muestras guardadas no son iguales a las del CSV de Python');
    }
  }
  const estado = app.state();
  delete estado.aviso;
  delete estado.accion;
  delete estado.modelo_origen;   // solo existen en la web (de quién es el traductor)
  delete estado.modelo_seq;
  const d = profundo(normal(estado), paso.estado, 1e-9, 'estado');
  if (d) errores.push(d);
  const dm = profundo(app.liveWorld ? normal({ ...frameJson(app.liveWorld) }) : null, paso.mundo, 1.1e-4, 'mundo');
  if (dm) errores.push(dm);
  if (JSON.stringify(tts.dichas) !== JSON.stringify(paso.voz)) errores.push(`voz: ${JSON.stringify(tts.dichas)} vs ${JSON.stringify(paso.voz)}`);
  if (errores.length && !pasoMal) pasoMal = `${nombre}: ${errores.join(' · ')}`;
}

function frameJson(w) {
  // frameToJson con t = 0, como _publicar de servidor_web.py
  const r4 = (x) => { const y = x * 10000; const r = Math.round(y); return (Math.abs(y % 1) === 0.5 ? 2 * Math.round(y / 2) : r) / 10000; };
  const red = (a) => (a ? a.map((p) => (Array.isArray(p) ? p.map(r4) : r4(p))) : null);
  return { t: 0, pose: red(w.pose), vis: red(w.vis), left: red(w.left), right: red(w.right) };
}

ok(pasoMal === null, `la app completa: ${fx.pasos.length} pasos con el mismo estado, resultados, voz y movimiento que InclusionApp`, pasoMal || '');
const tiposDe = (t) => fx.pasos.filter((p) => p.tipo === t).length;
console.log(`      (${tiposDe('frames')} tandas de cuadros, ${tiposDe('accion')} acciones, ${tiposDe('obtener')} consultas a /api/...)`);
fin();

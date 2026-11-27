// Paridad de movimiento.js (avatar) y progreso.js (Aprender) con motion.py y progreso.py.
//   node sitio/probar/tests/movimiento_progreso.test.mjs
import * as M from '../js/motor/movimiento.js';
import { INSIGNIAS, Progreso, estrellasPorConfianza, normalizar } from '../js/motor/progreso.js';
import { fin, fixture, igual, ok, profundo } from './comun.mjs';

const TOL = 1e-6;           // metros: el avatar no necesita más (y casi todo sale exacto)
const fx = fixture('movimiento.json');
const pts = (plano) => (plano ? Array.from({ length: plano.length / 3 }, (_, i) => plano.slice(i * 3, i * 3 + 3)) : null);
const mundo = (m) => ({ pose: pts(m.pose), vis: m.vis, left: pts(m.left), right: pts(m.right) });
const plano = (w) => Object.fromEntries(['pose', 'vis', 'left', 'right'].map((k) => [k, w[k] ? w[k].flat() : null]));

function comparar(obtenido, esperado, texto, tol = TOL) {
  const r = profundo(obtenido, esperado, tol);
  return ok(r === null, texto, r || '');
}

fx.world_frame.forEach((c, i) => {
  const w = M.worldFrame(pts(c.pose), c.vis, c.manos.map(pts));
  comparar(plano(w), c.salida, `world_frame ${i}`);
});
for (const lado of ['left', 'right']) comparar(plano(M.restArm(mundo(fx.rest_arm.mundo), lado)), fx.rest_arm[lado], `rest_arm(${lado})`);
igual(Object.fromEntries(['dos', 'derecha', 'izquierda'].map((m) => [m, M.restingSide(m)])), fx.resting_side, 'resting_side');

const filtro = new M.OneEuroFilter();
const suav = new M.LiveSmoother();
let peorF = 0; let peorS = null;
for (const p of fx.one_euro) {
  const y = filtro.filtrar(Float32Array.from(p.x), p.t);
  peorF = Math.max(peorF, ...Array.from(y, (v, i) => Math.abs(v - Math.fround(p.filtro[i]))));
  const s = plano(suav.suavizar(mundo(p.mundo), p.t));
  peorS = peorS || profundo(s, p.suave, TOL);
}
ok(peorF <= TOL, `One Euro: 60 pasos (dif. máx. ${peorF.toExponential(1)})`);
ok(peorS === null, 'LiveSmoother: una parte que desaparece reinicia su filtro', peorS || '');

const clip = M.makeClip(fx.clip.frames.map((f) => [f.t, mundo(f.mundo)]), 'hola', 'demo', 'derecha', 'x');
delete clip.created;
comparar(clip, fx.clip.salida, 'make_clip: mismo JSON (huecos rellenados y redondeo a 4 decimales)', 1e-9);
for (const r of fx.clip.recortes) {
  const c = M.trimClip(fx.clip.salida, r.inicio, r.fin);
  comparar(c, r.salida, `trim_clip(${r.inicio}, ${r.fin})`, 1e-9);
}
let error = '';
try { M.trimClip(fx.clip.salida, 0.1, 0.1); } catch (e) { error = e.message; }
ok(error === 'el recorte es demasiado corto', 'trim_clip: un recorte de un solo frame da error');

// ---------------------------------------------------------------- progreso
const pr = fixture('progreso.json');
let hoy = pr.inicio;
const sumar = (iso, n) => { const d = new Date(`${iso}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const p = new Progreso(null, () => hoy);
pr.pasos.forEach((paso, i) => {
  const [op, ...args] = paso.paso;
  let r = null;
  if (op === 'intento') r = p.registrarIntento(args[0], args[1], args[2]);
  else if (op === 'dia') hoy = sumar(hoy, args[0]);
  else if (op === 'oracion') p.registrarOracion();
  else if (op === 'evaluar') r = p.evaluar(pr.categorias, args[0], args[1], args[2]);
  const dif = profundo({ r, resumen: p.resumen(), datos: p.datos }, { r: paso.resultado, resumen: paso.resumen, datos: paso.datos });
  ok(dif === null, `progreso paso ${i + 1} (${op}${args.length ? ` ${JSON.stringify(args[0])}` : ''})`, dif || '');
});
igual(pr.estrellas.map((e) => estrellasPorConfianza(e.c)), pr.estrellas.map((e) => e.e), 'estrellas por confianza');
igual(Object.fromEntries(Object.keys(pr.normalizar).map((t) => [t, normalizar(t)])), pr.normalizar, 'normalizar');
igual(INSIGNIAS, pr.insignias, 'las mismas 9 insignias');

fin();

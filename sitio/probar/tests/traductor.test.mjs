// Paridad del segmentador, las features y el traductor con Python:
//   frames crudos -> SignSegmenter -> secuencia preparada -> features (30 × 260) -> predict_proba.
//   node sitio/probar/tests/traductor.test.mjs
// Si existen los casos locales (generar_fixtures.py --datos), también prueba el modelo y las
// muestras reales (no se suben a git).
import { aplanar, sequenceFeatures } from '../js/motor/landmarks.js';
import { SignSegmenter } from '../js/motor/segmentador.js';
import { Traductor } from '../js/motor/traductor.js';
import { LOCAL, cerca, difMax, existe, fin, fixture, igual, matriz, ok } from './comun.mjs';

const TOL_FEATURES = 1e-5;
const TOL_PROBA = 1e-6;

// ------------------------------------------------------------- segmentador
const seg = fixture('segmentador.json');
const nuevo = () => new SignSegmenter(seg.config.length, seg.config.start, seg.config.end, seg.config.min, seg.config.max,
  seg.config.contexto, seg.config.margen);

function correr(frames) {
  const s = nuevo();
  const pasos = [];
  const cortes = [];
  frames.forEach((fr, i) => {
    const out = s.update(fr);
    pasos.push([Number(s.active), s.captured, Number(s.lastDiscarded), Number(s.bodyVisible)]);
    if (out) cortes.push({ frame: i, secuencia: out });
  });
  return { pasos, cortes };
}

for (const [nombre, caso] of Object.entries(seg.flujos)) {
  const { pasos, cortes } = correr(matriz(caso.frames));
  igual(pasos, caso.pasos, `segmentador «${nombre}»: mismo estado en los ${pasos.length} frames`);
  igual(cortes.map((c) => c.frame), caso.cortes.map((c) => c.frame), `segmentador «${nombre}»: corta en los mismos frames`);
  cortes.forEach((c, i) => {
    if (caso.cortes[i]) cerca(c.secuencia, matriz(caso.cortes[i].secuencia), 0, `segmentador «${nombre}»: seña ${i + 1} preparada igual`);
  });
}

// --------------------------------------------------------------- traductor
function probarModelo(modelo, casos, etiqueta) {
  const t = new Traductor(modelo);
  let peorF = 0; let peorP = 0; let clases = 0;
  for (const c of casos) {
    const seq = matriz(c.secuencia);
    const feat = sequenceFeatures(seq);
    peorF = Math.max(peorF, difMax(feat, matriz(c.features)));
    const proba = t.probaFeatures(aplanar(feat));
    peorP = Math.max(peorP, difMax(Array.from(proba), c.proba));
    const mejor = (p) => p.indexOf(Math.max(...p));
    if (mejor(Array.from(proba)) === mejor(c.proba)) clases += 1;
  }
  ok(peorF < TOL_FEATURES, `${etiqueta}: features de ${casos.length} señas (dif. máx. ${peorF.toExponential(1)} < ${TOL_FEATURES})`);
  ok(peorP < TOL_PROBA, `${etiqueta}: probabilidades (dif. máx. ${peorP.toExponential(1)} < ${TOL_PROBA})`);
  ok(clases === casos.length, `${etiqueta}: la misma seña ganadora en ${clases} de ${casos.length}`);
  return t;
}

const tr = fixture('traductor.json');
const t = probarModelo(fixture('modelo_sintetico.json'), tr.casos, 'traductor sintético');

// Justo en los umbrales: el valor exacto del umbral y sus float32 vecinos
const bases = tr.casos.map((c) => aplanar(matriz(c.features)));
let peor = 0;
for (const c of tr.umbral) {
  const x = Float32Array.from(bases[c.base]);
  x[c.rasgo] = c.valor;
  peor = Math.max(peor, difMax(Array.from(t.probaFeatures(x)), c.proba));
}
ok(peor < TOL_PROBA, `traductor en ${tr.umbral.length} casos en el borde de un umbral (dif. máx. ${peor.toExponential(1)})`);

const [sena, conf] = t.predict(matriz(tr.casos[0].secuencia));
const p0 = tr.casos[0].proba;
const iMax = p0.indexOf(Math.max(...p0));
igual([sena, Number(conf.toFixed(9))], [p0[iMax] >= tr.min_confianza ? t.clases[iMax] : '', Number(p0[iMax].toFixed(9))],
  'predict(): seña y confianza como GestureLogic.predict');
ok(t.predict(matriz(tr.casos[0].secuencia).slice(0, 29))[0] === '', 'predict(): una secuencia de otro largo no se clasifica');

// ------------------------------------------------------ datos reales (local)
if (existe('muestras_reales.json') && existe('modelo_real.json')) {
  const reales = fixture('muestras_reales.json', LOCAL);
  probarModelo(fixture('modelo_real.json', LOCAL), reales.casos, 'traductor real (local)');
  let iguales = 0;
  for (const c of reales.casos) {
    const { cortes } = correr(matriz(c.flujo));
    if (cortes.length === c.cortes.length && cortes.every((x, i) => x.frame === c.cortes[i].frame
      && difMax(x.secuencia, matriz(c.cortes[i].secuencia)) === 0)) iguales += 1;
  }
  ok(iguales === reales.casos.length, `segmentador con muestras reales: ${iguales} de ${reales.casos.length} iguales`);
} else {
  console.log('(sin casos locales: corre generar_fixtures.py --datos para probar con el modelo real)');
}

fin();

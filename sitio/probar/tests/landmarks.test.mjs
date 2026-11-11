// Paridad de landmarks.js con app/modules/landmarks.py (y la parte lógica del detector).
//   node sitio/probar/tests/landmarks.test.mjs
import * as L from '../js/motor/landmarks.js';
import { anatomicalOrder, handSlotHint } from '../js/motor/detector.js';
import { cerca, fin, fixture, igual, matriz, ok } from './comun.mjs';

const fx = fixture('landmarks.json');
const TOL = 0;   // las funciones de frames crudos son exactas: el mismo float32

let malos = fx.resample.filter((c) => JSON.stringify(L.resampleIndices(c.n, c.largo)) !== JSON.stringify(c.indices));
ok(!malos.length, `resample: índices iguales en ${fx.resample.length} casos (empates al par, como np.round)`,
  malos.length ? JSON.stringify(malos[0]) : '');

fx.secuencias.forEach((c, i) => {
  const frames = matriz(c.frames);
  cerca(L.fillGaps(frames), matriz(c.fill_gaps), TOL, `caso ${i}: fill_gaps`);
  cerca(L.trim(frames), c.trim.forma[0] ? matriz(c.trim) : [], TOL, `caso ${i}: trim`);
  const ref = L.bodyReferencePose(frames);
  cerca(ref, matriz(c.body_reference_pose), TOL, `caso ${i}: body_reference_pose`);
  const cob = L.handCoverage(frames);
  ok(Math.abs(cob.izquierda - c.hand_coverage.izquierda) < 1e-12 && Math.abs(cob.derecha - c.hand_coverage.derecha) < 1e-12,
    `caso ${i}: hand_coverage`);
  for (const m of ['dos', 'derecha', 'izquierda']) igual(L.missingHands(frames, m, 0.5), c.missing_hands[m], `caso ${i}: missing_hands(${m})`);
  cerca(L.prepareSequence(frames, 30, 10), matriz(c.prepare), TOL, `caso ${i}: prepare_sequence`);
});

const { body, casos } = fx.drop_resting_hands;
casos.forEach((c, i) => {
  const out = L.dropRestingHands(Float32Array.from(c.frame), c.sin_cuerpo ? null : Float32Array.from(body), 1.5);
  cerca(out, c.salida, TOL, `drop_resting_hands ${i}${c.sin_cuerpo ? ' (sin cuerpo)' : ''}`);
});

// prepare_sequence con cuerpo de referencia: el cuerpo es body_pose((0.88, 0.61), 0.31) de synthetic.py
fx.secuencias.forEach((c, i) => {
  if (!c.prepare_body) return;
  const ref = matriz(c.prepare_body)[0].slice(L.HANDS_SIZE, L.HANDS_SIZE + L.POSE_SIZE);
  cerca(L.prepareSequence(matriz(c.frames), 30, 10, ref), matriz(c.prepare_body), TOL, `caso ${i}: prepare_sequence con cuerpo`);
});

const kh = fx.keep_hands;
for (const m of ['dos', 'derecha', 'izquierda']) cerca(L.keepHands(Float32Array.from(kh.frame), m), kh[m], TOL, `keep_hands(${m})`);
fx.validez.forEach((c, i) => {
  const fr = Float32Array.from(c.frame);
  igual([L.handsPresent(fr), L.poseValid(fr), L.elbowsVisible(fr)], [c.hands_present, c.pose_valid, c.elbows_visible], `validez ${i}`);
});
cerca(L.mirrorFeatures(matriz(fx.mirror_features.features)), matriz(fx.mirror_features.espejo), TOL, 'mirror_features');
cerca(L.upgradeRaw(matriz(fx.upgrade_raw.viejo)), matriz(fx.upgrade_raw.nuevo), TOL, 'upgrade_raw (135 -> 147)');

malos = fx.assign_slots.filter((c) => JSON.stringify(L.assignSlots(c.detecciones, c.previas)) !== JSON.stringify(c.salida));
ok(!malos.length, `assign_slots: ${fx.assign_slots.length} casos al azar`, malos.length ? JSON.stringify(malos[0]) : '');
malos = fx.hand_slot_hint.filter((c) => handSlotHint(c.label, c.wrist, c.pose_wrists) !== c.salida);
ok(!malos.length, `hand_slot_hint: ${fx.hand_slot_hint.length} casos`, malos.length ? JSON.stringify(malos[0]) : '');
fx.anatomical_order.forEach((c) => igual(anatomicalOrder(c.izq, c.der), c.salida, `anatomical_order(${c.izq}, ${c.der})`));

fin();

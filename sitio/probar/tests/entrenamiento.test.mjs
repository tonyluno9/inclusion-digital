// Entrenar el traductor en el navegador (bosque.js + entrenamiento.js) contra scikit-learn.
//   node sitio/probar/tests/entrenamiento.test.mjs
// El bosque de JavaScript no es idéntico al de scikit-learn (otro generador de azar), así que no
// se comparan números: se entrena con el mismo dataset y se mide la exactitud en señas nuevas.
// Con los casos locales (generar_fixtures.py --datos), también con las muestras reales.
import { entrenarModelo, revisarDataset } from '../js/motor/entrenamiento.js';
import { aFrames } from '../js/motor/entrenamiento.js';
import { Traductor } from '../js/motor/traductor.js';
import { LOCAL, existe, fin, fixture, igual, matriz, ok } from './comun.mjs';

const fx = fixture('entrenamiento.json');
const muestras = (lista) => lista.map((m) => ({ label: m.label, person: 'demo', seq: Float32Array.from(m.seq) }));
const exactitud = (modelo, lista) => {
  const t = new Traductor(modelo);
  let bien = 0;
  for (const m of lista) {
    const [, , proba] = t.predict(aFrames(Float32Array.from(m.seq)));
    const mejor = proba.indexOf(Math.max(...proba));
    if (t.clases[mejor] === m.label) bien += 1;
  }
  return bien / lista.length;
};

// ----------------------------------------------------- reglas del dataset
igual(revisarDataset(['a', 'a', 'a', 'a', 'a']), 'Se necesitan al menos 2 señas con 5 muestras cada una.', 'una sola seña no alcanza');
igual(revisarDataset([...'aaaaa', 'b', 'b', 'b']), 'Se necesitan al menos 2 señas con 5 muestras cada una. Faltan muestras de: b (3)',
  'avisa qué seña tiene pocas muestras (como check_dataset)');
igual(revisarDataset([...'aaaaa', ...'bbbbb']), '', '2 señas con 5 muestras sí alcanzan');
let error = '';
try { entrenarModelo(muestras(fx.entrenamiento.slice(0, 3))); } catch (e) { error = e.message; }
ok(error.startsWith('Se necesitan al menos 2 señas'), 'entrenar con pocas muestras da el mensaje, no un modelo roto');

// --------------------------------------------- entrenar y medir exactitud
const t0 = Date.now();
const modelo = entrenarModelo(muestras(fx.entrenamiento));
const seg = (Date.now() - t0) / 1000;
ok(modelo.arboles.length === 200 && modelo.clases.join() === 'arriba,circulo,derecha',
  `entrena 200 árboles con ${fx.entrenamiento.length} muestras (×8 con el aumento) en ${seg.toFixed(1)} s`);
let carga = true;
try { new Traductor(modelo); } catch { carga = false; }
ok(carga, 'el modelo entrenado tiene el formato de modelo.json (traductor.js lo carga)');
const acc = exactitud(modelo, fx.prueba);
ok(acc >= fx.exactitud_sklearn - 0.05, `exactitud en ${fx.prueba.length} señas nuevas: JavaScript ${(acc * 100).toFixed(0)} % · scikit-learn ${(fx.exactitud_sklearn * 100).toFixed(0)} %`);
igual(exactitud(modelo, fx.entrenamiento), 1, 'reconoce las mismas muestras con que se entrenó');

const a = entrenarModelo(muestras(fx.entrenamiento), { arboles: 10, semilla: 7 });
const b = entrenarModelo(muestras(fx.entrenamiento), { arboles: 10, semilla: 7 });
igual(JSON.stringify(a.arboles), JSON.stringify(b.arboles), 'con la misma semilla sale el mismo bosque');

// ------------------------------------------------ muestras reales (local)
if (existe('muestras_reales.json')) {
  // Validación cruzada de 5 partes, como evaluate_model() de train_model.py con una sola persona
  const reales = fixture('muestras_reales.json', LOCAL).casos.map((c) => ({ label: c.etiqueta, person: 'demo', seq: Float32Array.from(c.secuencia.datos) }));
  let bien = 0;
  const partes = 5;
  const t1 = Date.now();
  for (let p = 0; p < partes; p += 1) {
    const entrena = reales.filter((_, i) => i % partes !== p);
    const prueba = reales.filter((_, i) => i % partes === p);
    const m = entrenarModelo(entrena, { arboles: 100 });
    bien += exactitud(m, prueba.map((x) => ({ label: x.label, seq: Array.from(x.seq) }))) * prueba.length;
  }
  ok(bien / reales.length >= 0.9, `muestras reales (local), validación cruzada de 5 partes: ${(100 * bien / reales.length).toFixed(0)} % en ${((Date.now() - t1) / 1000).toFixed(0)} s`);
}
void matriz;
fin();

// retarget.js contra el retargeting de Blender (RF-23). Correr con:  node app/web/tests/retarget.test.mjs
// La referencia la genera blender/tests/generar_fixture_js.py (fixture_retarget.json).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from '../vendor/three/three.module.js';
import { Retarget, huesosDelPerfil, perfilTripo } from '../js/retarget.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const MODELOS = join(AQUI, '..', 'assets', 'modelos');
let fallas = 0;
const comprobar = (ok, texto) => { console.log(`${ok ? 'ok   ' : 'FALLA'} ${texto}`); if (!ok) fallas += 1; };

// Esqueleto armado directo del JSON del GLB (sin GLTFLoader, que necesita navegador)
function cargarEsqueleto() {
  const glb = readFileSync(join(MODELOS, 'personaje.glb'));
  const largo = glb.readUInt32LE(12);
  const gltf = JSON.parse(glb.subarray(20, 20 + largo).toString('utf8'));
  const juntas = new Set(gltf.skins[0].joints);
  const objetos = gltf.nodes.map((n, i) => {
    const o = juntas.has(i) ? new THREE.Bone() : new THREE.Object3D();
    o.name = n.name;
    if (n.translation) o.position.fromArray(n.translation);
    if (n.rotation) o.quaternion.fromArray(n.rotation);
    if (n.scale) o.scale.fromArray(n.scale);
    return o;
  });
  gltf.nodes.forEach((n, i) => (n.children || []).forEach((c) => objetos[i].add(objetos[c])));
  const escena = new THREE.Object3D();
  gltf.scenes[0].nodes.forEach((i) => escena.add(objetos[i]));
  escena.updateMatrixWorld(true);
  const huesos = {};
  objetos.forEach((o) => { if (o.isBone) huesos[o.name] = o; });
  return { escena, huesos };
}

const reposo = JSON.parse(readFileSync(join(MODELOS, 'personaje_reposo.json'), 'utf8'));
const fixture = JSON.parse(readFileSync(join(AQUI, 'fixture_retarget.json'), 'utf8'));
const { escena, huesos } = cargarEsqueleto();
const perfil = perfilTripo();
const nombres = huesosDelPerfil(perfil);

// El esqueleto del GLB en reposo coincide con la geometría de reposo exportada de Blender
let peor = 0;
for (const n of nombres) peor = Math.max(peor, huesos[n].getWorldPosition(new THREE.Vector3()).distanceTo(new THREE.Vector3(...reposo[n].cabeza)));
comprobar(peor < 1e-4, `el GLB en reposo coincide con Blender (máx. ${(peor * 1000).toFixed(3)} mm)`);

const rt = new Retarget(huesos, reposo, perfil);

function direcciones() {
  escena.updateMatrixWorld(true);
  const out = {};
  for (const n of nombres) {
    const b = huesos[n];
    const giro = b.getWorldQuaternion(new THREE.Quaternion()).multiply(rt.reposoMundo[n].clone().invert());
    const resto = new THREE.Vector3(...reposo[n].cola).sub(new THREE.Vector3(...reposo[n].cabeza));
    out[n] = { cabeza: b.getWorldPosition(new THREE.Vector3()), dir: resto.applyQuaternion(giro) };
  }
  return out;
}

for (const [caso, datos] of Object.entries(fixture)) {
  rt.reposo();
  rt.mover(datos.frame);
  const obtenido = direcciones();
  let peorAng = 0; let peorHueso = ''; let peorPos = 0;
  for (const n of nombres) {
    const e = datos.huesos[n];
    const dirE = new THREE.Vector3(...e.cola).sub(new THREE.Vector3(...e.cabeza));
    const ang = THREE.MathUtils.radToDeg(dirE.angleTo(obtenido[n].dir));
    if (ang > peorAng) { peorAng = ang; peorHueso = n; }
    peorPos = Math.max(peorPos, obtenido[n].cabeza.distanceTo(new THREE.Vector3(...e.cabeza)));
  }
  comprobar(peorAng < 0.5, `${caso}: cada hueso apunta igual que en Blender (peor ${peorHueso}: ${peorAng.toFixed(3)}°)`);
  comprobar(peorPos < 0.002, `${caso}: las articulaciones quedan en el mismo lugar (máx. ${(peorPos * 1000).toFixed(2)} mm)`);
}

// Partes ausentes y frame vacío: no rompen ni borran la pose
rt.reposo();
rt.mover(fixture.pose.frame);
const antes = huesos.L_Index1.quaternion.clone();
rt.mover({ pose: null, vis: null, left: null, right: null });
// (se comparan los valores: angleTo exagera el redondeo cuando los giros son casi iguales)
const cambio = Math.max(...huesos.L_Index1.quaternion.toArray().map((x, i) => Math.abs(x - antes.toArray()[i])));
comprobar(cambio < 1e-6, `un frame vacío conserva la pose (cambio máx. ${cambio.toExponential(1)})`);
comprobar(Object.values(huesos).every((b) => Number.isFinite(b.quaternion.w)), 'sin NaN');

// Seña de una mano (RF-31): olvidarMano('L') devuelve la mano izquierda y sus dedos al reposo,
// sin tocar la derecha
rt.reposo();
rt.mover(fixture.pose.frame);
const derechaAntes = huesos.R_Index1.quaternion.clone();
rt.olvidarMano('L');
rt.mover({ ...fixture.pose.frame, left: null });
const relativo = (b) => Math.max(...b.quaternion.toArray().map((x, i) => Math.abs(x - rt.reposoLocal[b.name].toArray()[i])));
comprobar(relativo(huesos.L_Index1) < 1e-6 && relativo(huesos.L_Hand) < 1e-6,
  'olvidarMano: la mano izquierda y sus dedos vuelven a su reposo');
const cambioDer = Math.max(...huesos.R_Index1.quaternion.toArray().map((x, i) => Math.abs(x - derechaAntes.toArray()[i])));
comprobar(cambioDer < 1e-6, 'olvidarMano: la mano derecha no cambia');

console.log(fallas ? `${fallas} FALLAS` : 'TODO OK');
process.exit(fallas ? 1 : 0);

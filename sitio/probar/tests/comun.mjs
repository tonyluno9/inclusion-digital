// Ayudas para las pruebas de paridad Python ↔ JavaScript (sin dependencias: solo Node).
// Los JSON de fixtures/ los escribe sitio/herramientas/generar_fixtures.py.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = dirname(fileURLToPath(import.meta.url));
export const FIXTURES = join(AQUI, 'fixtures');
export const LOCAL = join(AQUI, 'local');

export const fixture = (nombre, carpeta = FIXTURES) => JSON.parse(readFileSync(join(carpeta, nombre), 'utf-8'));
export const existe = (nombre, carpeta = LOCAL) => existsSync(join(carpeta, nombre));

/** {forma: [T, n], datos} -> arreglo de T Float32Array (o un Float32Array si es 1D). */
export function matriz(a) {
  if (a === null || a === undefined) return null;
  const datos = Float32Array.from(a.datos);
  if (a.forma.length === 1) return datos;
  const n = a.forma.slice(1).reduce((x, y) => x * y, 1);
  return Array.from({ length: a.forma[0] }, (_, i) => datos.slice(i * n, (i + 1) * n));
}

let fallas = 0;
let pruebas = 0;

export function ok(condicion, texto, detalle = '') {
  pruebas += 1;
  if (!condicion) fallas += 1;
  console.log(`${condicion ? 'ok   ' : 'FALLA'} ${texto}${condicion || !detalle ? '' : `\n      ${detalle}`}`);
  return condicion;
}

/** Mayor diferencia absoluta entre dos listas de números (Infinity si no miden lo mismo). */
export function difMax(a, b) {
  if (a === null || b === null) return a === b ? 0 : Infinity;
  const x = a.length !== undefined && a[0] && a[0].length !== undefined ? a.flatMap((r) => Array.from(r)) : Array.from(a);
  let y = b.length !== undefined && b[0] && b[0].length !== undefined ? b.flatMap((r) => Array.from(r)) : Array.from(b);
  // Lo que en Python es float32 llega como su representación corta: se lleva a float32 otra vez
  const es32 = a instanceof Float32Array || (a[0] instanceof Float32Array);
  if (es32) y = y.map(Math.fround);
  if (x.length !== y.length) return Infinity;
  let m = 0;
  for (let i = 0; i < x.length; i += 1) {
    const d = Math.abs(x[i] - y[i]);
    if (Number.isNaN(d)) return Infinity;
    if (d > m) m = d;
  }
  return m;
}

export function cerca(a, b, tol, texto) {
  const d = difMax(a, b);
  return ok(d <= tol, `${texto} (dif. máx. ${d === 0 ? '0' : d.toExponential(1)})`,
    d === Infinity ? `tamaños distintos: ${a && a.length} vs ${b && b.length}` : `tolerancia ${tol}`);
}

export function igual(obtenido, esperado, texto) {
  const a = JSON.stringify(obtenido);
  const b = JSON.stringify(esperado);
  return ok(a === b, texto, `obtenido: ${a.slice(0, 300)}\n      esperado: ${b.slice(0, 300)}`);
}

/** Compara objetos sin importar el orden de las claves; números con tolerancia. */
export function profundo(a, b, tol = 0, ruta = '') {
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) <= tol ? null : `${ruta}: ${a} vs ${b}`;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
    return a === b ? null : `${ruta}: ${JSON.stringify(a)} vs ${JSON.stringify(b)}`;
  }
  if (Array.isArray(a) !== Array.isArray(b)) return `${ruta}: arreglo vs objeto`;
  const ka = Object.keys(a).filter((k) => a[k] !== undefined);
  const kb = Object.keys(b).filter((k) => b[k] !== undefined);
  if (Array.isArray(a) ? a.length !== b.length : ka.sort().join() !== kb.sort().join()) {
    return `${ruta}: claves o tamaño distintos (${ka.slice(0, 12)} vs ${kb.slice(0, 12)})`;
  }
  for (const k of ka) {
    const r = profundo(a[k], b[k], tol, `${ruta}.${k}`);
    if (r) return r;
  }
  return null;
}

export function fin() {
  console.log(fallas ? `\n${fallas} de ${pruebas} pruebas FALLARON` : `\nTODO OK (${pruebas} pruebas)`);
  process.exitCode = fallas ? 1 : 0;
}

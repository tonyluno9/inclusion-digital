// Diccionario (RF-34) y Aprender (RF-35): la lógica pura de web/js/diccionario.js y web/js/aprender.js.
import { agrupar, estadoPalabra } from '../js/diccionario.js';
import { candidatas, coincide, elegirPalabra, estrellas } from '../js/aprender.js';

let fallas = 0;
const comprobar = (ok, texto) => { console.log(`${ok ? 'ok   ' : 'FALLA'} ${texto}`); if (!ok) fallas += 1; };
const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const categorias = [
  { id: 'saludos', nombre: 'Saludos', palabras: ['hola', 'adios', 'buenas tardes', 'buenos dias'] },
  { id: 'cortesia', nombre: 'Cortesía', palabras: ['gracias', 'hola'] },
];
const palabras = [
  { clave: 'hola', nombre: 'hola', traductor: true, movimiento: 'hola' },
  { clave: 'adios', nombre: 'adiós', traductor: true, movimiento: null },
  { clave: 'gracias', nombre: 'gracias', traductor: false, movimiento: 'gracias' },
  { clave: 'perro', nombre: 'perro', traductor: true, movimiento: 'perro' },
];

// ---------------------------------------------------------------- agrupar
let g = agrupar(palabras, categorias);
comprobar(igual(g.map((x) => x.categoria.id), ['saludos', 'cortesia', 'otras']), 'secciones: saludos, cortesía y otras');
comprobar(igual(g[0].palabras.map((p) => p.clave), ['adios', 'hola']), 'ordenadas por nombre; «hola» solo en su primera categoría');
comprobar(igual(g[0].porAprender, ['buenas tardes', 'buenos dias']), 'por aprender: las de la categoría que faltan');
comprobar(igual(g[2].palabras.map((p) => p.clave), ['perro']), 'sin categoría -> Otras');

g = agrupar(palabras, categorias, { texto: 'ADIÓS' });
comprobar(igual(g.map((x) => [x.categoria.id, x.palabras.map((p) => p.clave)]), [['saludos', ['adios']]]),
  'buscar sin acentos ni mayúsculas');
g = agrupar(palabras, categorias, { texto: 'buenas' });
comprobar(igual(g.map((x) => [x.categoria.id, x.palabras.length, x.porAprender]), [['saludos', 0, ['buenas tardes']]]),
  'buscar también muestra lo que falta por aprender');
g = agrupar(palabras, categorias, { categoria: 'cortesia' });
comprobar(igual(g.map((x) => x.categoria.id), ['cortesia']), 'filtrar por categoría');
comprobar(igual(agrupar([], categorias), []), 'sin palabras no hay secciones');
comprobar(igual(estadoPalabra(palabras[0]), { traductor: true, avatar: true, completa: true }), 'estado de una palabra');

// ---------------------------------------------------------------- aprender
comprobar(igual(candidatas(palabras).map((p) => p.clave), ['hola', 'perro']), 'candidatas: traductor + movimiento');
comprobar(igual(candidatas(palabras.map((p) => ({ ...p, movimiento: null }))).map((p) => p.clave), ['hola', 'adios', 'perro']),
  'sin movimientos: todas las del traductor');
const lista = candidatas(palabras);
comprobar(elegirPalabra(lista, {}, 'hola', () => 0).clave === 'perro', 'no repite la anterior');
comprobar(elegirPalabra([lista[0]], {}, 'hola', () => 0).clave === 'hola', 'con una sola palabra, la repite');
comprobar(elegirPalabra([], {}) === null, 'sin palabras: null');
// hola con 9 aciertos pesa 0.1; perro 1.0 -> con azar 0.5 sale perro
comprobar(elegirPalabra(lista, { hola: { aciertos: 9 } }, null, () => 0.5).clave === 'perro',
  'las menos acertadas salen más');
let cuentas = { hola: 0, perro: 0 };
let semilla = 1;
const azar = () => { semilla = (semilla * 16807) % 2147483647; return semilla / 2147483647; };
for (let i = 0; i < 2000; i += 1) cuentas[elegirPalabra(lista, { hola: { aciertos: 3 } }, null, azar).clave] += 1;
comprobar(cuentas.perro > cuentas.hola * 2.5, `reparto por aciertos (hola ${cuentas.hola}, perro ${cuentas.perro})`);

comprobar(coincide('Adiós', palabras[1]) && !coincide('hola', palabras[1]) && !coincide('', palabras[1]), 'coincide sin acentos');
comprobar(igual([0.95, 0.8, 0.5].map(estrellas), [3, 2, 1]), 'estrellas como en Python');

console.log(fallas ? `${fallas} FALLAS` : 'TODO OK');
process.exit(fallas ? 1 : 0);

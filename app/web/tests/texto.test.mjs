// Texto -> señas del avatar (RF-24). Correr con:  node app/web/tests/texto.test.mjs
import { buscarSenas, norm } from '../js/texto.js';

let fallas = 0;
const igual = (obtenido, esperado, texto) => {
  const ok = JSON.stringify(obtenido) === JSON.stringify(esperado);
  console.log(`${ok ? 'ok   ' : 'FALLA'} ${texto}${ok ? '' : `\n      obtenido: ${JSON.stringify(obtenido)}\n      esperado: ${JSON.stringify(esperado)}`}`);
  if (!ok) fallas += 1;
};

igual(norm('¡Buenos Días, Niño!'), 'buenos dias nino', 'sin acentos, signos ni mayúsculas');
igual(norm('  hola   adiós '), 'hola adios', 'espacios de más');

const conocidas = new Map([['hola', 'hola'], ['buenos dias', 'buenos días'], ['gracias', 'gracias'], ['buenos', 'buenos']]);
igual(buscarSenas('Hola, buenos días', conocidas),
  [{ palabra: 'hola', clip: 'hola' }, { palabra: 'buenos dias', clip: 'buenos días' }],
  'la frase más larga primero («buenos días» y no «buenos»)');
igual(buscarSenas('gracias amigo', conocidas),
  [{ palabra: 'gracias', clip: 'gracias' }, { palabra: 'amigo', clip: null }],
  'una palabra sin seña queda marcada');
igual(buscarSenas('', conocidas), [], 'texto vacío');
igual(buscarSenas('buenos', conocidas), [{ palabra: 'buenos', clip: 'buenos' }], 'palabra sola');

console.log(fallas ? `${fallas} FALLAS` : 'TODO OK');
process.exit(fallas ? 1 : 0);

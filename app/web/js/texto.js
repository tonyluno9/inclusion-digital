// Texto -> señas que el avatar sabe hacer (RF-24). Sin dependencias, para probarlo con Node.

// Minúsculas, sin acentos ni signos: «¡Buenos Días!» -> «buenos dias»
export function norm(s) {
  return String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
}

// Divide el texto en las palabras y frases que el avatar conoce, la más larga primero
// (así «buenos días» usa su propia seña y no «buenos» + «días»).
// conocidas: Map(texto normalizado -> nombre del clip). Devuelve [{ palabra, clip | null }].
export function buscarSenas(texto, conocidas, maxPalabras = 3) {
  const w = norm(texto).split(' ').filter(Boolean);
  const out = [];
  for (let i = 0; i < w.length;) {
    let n = Math.min(maxPalabras, w.length - i);
    for (; n >= 1; n -= 1) {
      const frase = w.slice(i, i + n).join(' ');
      if (conocidas.has(frase)) { out.push({ palabra: frase, clip: conocidas.get(frase) }); break; }
    }
    if (n === 0) { out.push({ palabra: w[i], clip: null }); n = 1; }
    i += n;
  }
  return out;
}

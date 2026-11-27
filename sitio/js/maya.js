// Numerales mayas en SVG: un punto vale 1, una barra vale 5, la concha es el cero.
// Base 20: el nivel de arriba vale veinte veces el de abajo.
const ANCHO = 60;
const R = 5.2;          // radio del punto
const BARRA = 8.5;      // grosor de la barra
const HUECO = 5;        // separación vertical dentro de un nivel
const ENTRE_NIVELES = 16;

function digitos(n) {
  const d = [];
  do { d.unshift(n % 20); n = Math.floor(n / 20); } while (n > 0);
  return d;
}

function nivel(d, y) {
  // Devuelve [svg, alto] de un dígito de 0 a 19 dibujado desde y hacia abajo
  if (d === 0) {
    const h = 20;
    const cy = y + h / 2;
    return [`<g fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round">
      <ellipse cx="${ANCHO / 2}" cy="${cy}" rx="${ANCHO / 2 - 6}" ry="${h / 2 - 1}"/>
      <path d="M${ANCHO / 2 - 14} ${cy - 2} q7 6 14 0 q7 -6 14 0"/>
      <path d="M${ANCHO / 2 - 10} ${cy + 4.5} q5 3 10 0 q5 -3 10 0"/></g>`, h];
  }
  const puntos = d % 5; const barras = Math.floor(d / 5);
  let svg = ''; let h = 0;
  if (puntos) {
    const paso = 12.5; const x0 = ANCHO / 2 - ((puntos - 1) * paso) / 2;
    for (let i = 0; i < puntos; i++) svg += `<circle cx="${x0 + i * paso}" cy="${y + R}" r="${R}"/>`;
    h += R * 2;
  }
  for (let i = 0; i < barras; i++) {
    if (h) h += HUECO;
    svg += `<rect x="3" y="${y + h}" width="${ANCHO - 6}" height="${BARRA}" rx="${BARRA / 2}"/>`;
    h += BARRA;
  }
  return [svg, h];
}

export function numeralMaya(n, { titulo = '', grande = false } = {}) {
  const ds = digitos(Math.max(0, Math.floor(n)));
  let y = 2; let cuerpo = '';
  ds.forEach((d, i) => {
    if (i) y += ENTRE_NIVELES;
    const [svg, h] = nivel(d, y);
    cuerpo += svg; y += h;
  });
  const alto = y + 2;
  const etiqueta = titulo ? `role="img" aria-label="${titulo}"` : 'aria-hidden="true"';
  const estilo = grande ? ` style="height:${Math.min(118, 22 + alto * 1.1)}px"` : '';
  return `<svg viewBox="0 0 ${ANCHO} ${alto}" ${etiqueta} fill="currentColor"${estilo}>${titulo ? `<title>${titulo}</title>` : ''}${cuerpo}</svg>`;
}

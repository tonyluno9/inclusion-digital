// Una persona de puntos que hace una seña en bucle: reposo, sube la mano, seña, baja la mano.
// Coordenadas 2D de la imagen en espejo (como la ve la app), con y hacia abajo y el pecho en (0, 0).
// Es la fuente de datos de casi todos los pasos del diagrama «Cómo funciona».

export const PERIODO = 5.6;              // s de un ciclo completo
export const UMBRAL = 0.16;              // altura de la muñeca (y) por encima de la cual «hay manos»

// Mano abierta, muñeca en el origen y dedos hacia arriba (-y); pulgar hacia -x. Unidades: largo de la palma.
const MANO = [
  [0, 0], [-0.24, -0.1], [-0.42, -0.26], [-0.55, -0.42], [-0.66, -0.56],
  [-0.2, -0.58], [-0.24, -0.84], [-0.26, -1.0], [-0.27, -1.14],
  [0, -0.62], [0, -0.9], [0, -1.08], [0, -1.24],
  [0.18, -0.57], [0.21, -0.82], [0.23, -0.98], [0.24, -1.11],
  [0.34, -0.49], [0.4, -0.67], [0.44, -0.79], [0.47, -0.9],
];
export const CONEXIONES_MANO = [
  [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20],
];
export const PUNTAS = [4, 8, 12, 16, 20];

const suave = (x) => { const t = Math.min(1, Math.max(0, x)); return t * t * (3 - 2 * t); };
const mezcla = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k];

// Dobla un dedo hacia la palma (vista de frente: se acorta y baja hacia el centro)
function cerrar(mano, dedo, k) {
  const cadenas = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]];
  const c = cadenas[dedo];
  const base = mano[c[0]];
  for (let i = 1; i < 4; i++) {
    const p = mano[c[i]];
    const objetivo = [base[0] * 0.75 + (dedo === 0 ? 0.25 : 0), base[1] + 0.12 * i * (dedo === 0 ? 0.4 : 1)];
    mano[c[i]] = mezcla(p, objetivo, k);
  }
}

function colocarMano(muneca, angulo, escala, espejo, abierta = 1, dedos = null) {
  const m = MANO.map(([x, y]) => [espejo ? -x : x, y]);
  if (dedos) dedos.forEach((k, i) => { if (k > 0) cerrar(m, i, k); });
  else if (abierta < 1) for (let i = 0; i < 5; i++) cerrar(m, i, 1 - abierta);
  const s = Math.sin(angulo); const co = Math.cos(angulo);
  return m.map(([x, y]) => [muneca[0] + (x * co - y * s) * escala, muneca[1] + (x * s + y * co) * escala]);
}

// Estado en el instante t (s). Devuelve puntos del cuerpo, las dos manos y cuánto está levantada.
export function figura(t) {
  const f = ((t % PERIODO) + PERIODO) % PERIODO;
  const sube = suave((f - 0.7) / 0.7);
  const baja = suave((f - 3.7) / 0.7);
  const u = sube * (1 - baja);                 // 0 = reposo, 1 = mano arriba
  const respira = Math.sin(t * 1.3) * 0.006;

  const oi = [-0.22, -0.1 + respira]; const od = [0.22, -0.1 + respira];
  const nariz = [0.01 * Math.sin(t * 0.7), -0.38 + respira];

  // Mano derecha de la persona (a la derecha en la imagen en espejo): hace la seña
  const ola = u > 0.6 ? Math.sin((f - 1.4) * 9) * 0.32 * suave((u - 0.6) / 0.4) : 0;
  const cdR = mezcla([0.27, 0.17], [0.4, 0.03], u);
  const mdR = mezcla([0.25, 0.43], [0.33 + ola * 0.05, -0.27], u);
  const anguloR = Math.PI * (1 - u) + ola;
  const manoD = colocarMano(mdR, anguloR, 0.115, false, 0.55 + 0.45 * u);

  // Mano izquierda: acompaña apenas
  const ui = u * 0.35;
  const ciL = mezcla([-0.27, 0.17], [-0.33, 0.12], ui);
  const miL = mezcla([-0.25, 0.43], [-0.2, 0.22], ui);
  const manoI = colocarMano(miL, Math.PI * (1 - ui * 0.6), 0.115, true, 0.55);

  return { f, u, nariz, oi, od, ci: ciL, cd: cdR, mi: miL, md: mdR, manoI, manoD, arriba: mdR[1] < UMBRAL };
}

// Contar con los dedos: k de 0 a 5 dedos abiertos (para la vista del rig)
export function manoContando(muneca, escala, k) {
  const orden = [1, 2, 3, 4, 0];
  const dedos = [1, 1, 1, 1, 1];
  orden.forEach((d, i) => { dedos[d] = 1 - suave(k - i); });
  return colocarMano(muneca, 0, escala, false, 1, dedos);
}

// Diagrama «Cómo funciona»: un lienzo fijo que cambia de escena según el paso que se lee.
// Todas las escenas salen de la misma figura animada (figura.js), así los datos son coherentes:
// la gráfica del corte es la altura real de la muñeca que se ve en la escena de los puntos.
import { figura, CONEXIONES_MANO, PUNTAS, PERIODO, UMBRAL, manoContando } from './figura.js';

const C = {
  fondo: '#0A111C', sup: '#1A2333', sup2: '#222C3F', texto: '#F4F6FA', texto2: '#9AA4B5', texto3: '#6F7A8E',
  linea: 'rgba(154,164,181,0.18)', jade: '#2EC4B6', maya: '#3A86C8', violeta: '#7C5CFF', coral: '#FF6B6B',
  ambar: '#FFC857', naranja: '#FFA53C',
};
const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
const suave = (x) => { const t = Math.min(1, Math.max(0, x)); return t * t * (3 - 2 * t); };
const FUENTE = 'Lexend, system-ui, sans-serif';
const MONO = 'ui-monospace, "Cascadia Code", Consolas, monospace';

const PASOS = {
  camara: ['01', 'Cámara', 'ida'], puntos: ['02', 'Puntos', 'ida'], corte: ['03', 'Corte de la seña', 'ida'],
  rasgos: ['04', 'Rasgos', 'ida'], bosque: ['05', 'Traductor', 'ida'], subtitulo: ['06', 'Subtítulo y voz', 'ida'],
  texto: ['07', 'Texto', 'vuelta'], clips: ['08', 'Clips', 'vuelta'], retarget: ['09', 'Retargeting', 'vuelta'],
  avatar: ['10', 'Avatar', 'vuelta'],
};

export function iniciarProceso() {
  const canvas = document.getElementById('proceso-canvas');
  if (!canvas) return;
  const c = canvas.getContext('2d');
  const quieto = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let w = 0; let h = 0; let dpr = 1;
  let escena = 'camara'; let previa = null; let cambio = 0;
  let visible = false; let corriendo = false;
  const t0 = performance.now();

  function medir() {
    const r = canvas.getBoundingClientRect();
    dpr = Math.min(devicePixelRatio || 1, 2);
    w = r.width; h = r.height;
    canvas.width = Math.max(1, Math.round(w * dpr)); canvas.height = Math.max(1, Math.round(h * dpr));
    if (quieto) cuadro(performance.now());
  }

  // ------------------------------------------------------------ pasos que se activan al leer
  const pasos = [...document.querySelectorAll('.paso')];
  const etiquetaNum = document.getElementById('lienzo-paso');
  const etiquetaNombre = document.getElementById('lienzo-nombre');
  const pista = document.getElementById('lienzo-pista');
  function activar(nombre) {
    if (nombre === escena) return;
    previa = escena; escena = nombre; cambio = performance.now();
    const [num, titulo, lado] = PASOS[nombre];
    etiquetaNum.textContent = num; etiquetaNombre.textContent = titulo; pista.dataset.pista = lado;
    if (quieto) cuadro(performance.now());
  }
  pista.dataset.pista = 'ida';
  pasos[0].classList.add('activo');
  const io = new IntersectionObserver((entradas) => {
    for (const e of entradas) {
      if (!e.isIntersecting) continue;
      pasos.forEach((p) => p.classList.toggle('activo', p === e.target));
      activar(e.target.dataset.paso);
    }
  }, { rootMargin: '-42% 0px -42% 0px' });
  pasos.forEach((p) => io.observe(p));

  // ------------------------------------------------------------ bucle
  function cuadro(ahora) {
    const t = (ahora - t0) / 1000;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const k = quieto ? 1 : suave((ahora - cambio) / 450);
    if (previa && k < 1) {
      c.save(); c.globalAlpha = 1 - k; ESCENAS[previa](c, w, h, t); c.restore();
    }
    c.save(); c.globalAlpha = k; c.translate(0, (1 - k) * 10); ESCENAS[escena](c, w, h, t); c.restore();
  }
  function bucle(ahora) {
    if (!visible || document.hidden) { corriendo = false; return; }
    cuadro(ahora);
    requestAnimationFrame(bucle);
  }
  function arrancar() { if (!corriendo && !quieto && visible) { corriendo = true; requestAnimationFrame(bucle); } }
  new IntersectionObserver((e) => { visible = e[0].isIntersecting; arrancar(); }).observe(canvas);
  document.addEventListener('visibilitychange', arrancar);
  new ResizeObserver(medir).observe(canvas);
  document.fonts?.ready.then(medir);
  medir();
}

// =============================================================== utilidades de dibujo
function caja(c, x, y, w, h, r) {
  c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
function texto(c, s, x, y, { tam = 13, peso = 400, color = C.texto2, alin = 'left', fuente = FUENTE, base = 'alphabetic' } = {}) {
  c.font = `${peso} ${tam}px ${fuente}`; c.fillStyle = color; c.textAlign = alin; c.textBaseline = base; c.fillText(s, x, y);
}
// Texto que se parte en varias líneas si no cabe en `ancho`
function parrafo(c, s, x, y, ancho, opciones = {}) {
  const tam = opciones.tam || 13;
  c.font = `${opciones.peso || 400} ${tam}px ${opciones.fuente || FUENTE}`;
  const lineas = []; let linea = '';
  for (const p of s.split(' ')) {
    const prueba = linea ? `${linea} ${p}` : p;
    if (c.measureText(prueba).width > ancho && linea) { lineas.push(linea); linea = p; } else linea = prueba;
  }
  lineas.push(linea);
  lineas.forEach((l, i) => texto(c, l, x, y + i * tam * 1.45, opciones));
  return lineas.length;
}
// Marco de la «cámara»: rectángulo 4:3 centrado en el área disponible
function visor(w, h, margen = 0.12, arriba = 64, abajo = 70) {
  const aw = w * (1 - margen * 2); const ah = h - arriba - abajo;
  let vw = aw; let vh = vw * 0.75;
  if (vh > ah) { vh = ah; vw = vh / 0.75; }
  return { x: (w - vw) / 2, y: arriba + (ah - vh) / 2, w: vw, h: vh };
}
function esquinas(c, v, color, largo = 18) {
  c.strokeStyle = color; c.lineWidth = 2; c.lineCap = 'round';
  const L = largo;
  for (const [x, y, dx, dy] of [[v.x, v.y, 1, 1], [v.x + v.w, v.y, -1, 1], [v.x, v.y + v.h, 1, -1], [v.x + v.w, v.y + v.h, -1, -1]]) {
    c.beginPath(); c.moveTo(x, y + dy * L); c.lineTo(x, y); c.lineTo(x + dx * L, y); c.stroke();
  }
}
// Convierte coordenadas de la figura a pixeles dentro del visor
function aVisor(v) {
  const s = Math.min(v.h * 1.02, v.w * 1.15); const cx = v.x + v.w / 2; const cy = v.y + v.h * 0.58;
  return (p) => [cx + p[0] * s, cy + p[1] * s];
}

// Silueta desenfocada de la persona: se lee como «video», sin mostrar a nadie
function silueta(c, F, P, alfa = 1) {
  const s = Math.hypot(P(F.od)[0] - P(F.oi)[0], 0) / 0.44;
  c.save();
  c.filter = `blur(${Math.max(3, s * 0.018)}px)`;
  const g = c.createLinearGradient(0, P([0, -0.5])[1], 0, P([0, 0.6])[1]);
  g.addColorStop(0, rgba('#4A5D80', 0.95 * alfa)); g.addColorStop(1, rgba('#1E2A40', 0.9 * alfa));
  c.fillStyle = g; c.strokeStyle = g; c.lineCap = 'round'; c.lineJoin = 'round';
  // torso con hombros redondeados
  c.beginPath();
  c.moveTo(...P([-0.36, 0.75]));
  c.lineTo(...P([-0.33, 0.02]));
  c.quadraticCurveTo(...P([-0.32, -0.1]), ...P([-0.2, -0.12]));
  c.quadraticCurveTo(...P([0, -0.17]), ...P([0.2, -0.12]));
  c.quadraticCurveTo(...P([0.32, -0.1]), ...P([0.33, 0.02]));
  c.lineTo(...P([0.36, 0.75]));
  c.closePath(); c.fill();
  // cuello y cabeza
  c.lineWidth = s * 0.09; c.beginPath(); c.moveTo(...P([0, -0.12])); c.lineTo(...P([0, -0.26])); c.stroke();
  const cab = P([F.nariz[0], F.nariz[1] - 0.04]);
  c.beginPath(); c.ellipse(cab[0], cab[1], s * 0.1, s * 0.125, 0, 0, 6.283); c.fill();
  // brazos
  c.lineWidth = s * 0.085;
  for (const [o, co, m] of [[F.oi, F.ci, F.mi], [F.od, F.cd, F.md]]) {
    c.beginPath(); c.moveTo(...P(o)); c.lineTo(...P(co)); c.lineTo(...P(m)); c.stroke();
  }
  // manos (relleno)
  c.lineWidth = s * 0.035;
  for (const mano of [F.manoI, F.manoD]) {
    for (const [i, j] of CONEXIONES_MANO) { c.beginPath(); c.moveTo(...P(mano[i])); c.lineTo(...P(mano[j])); c.stroke(); }
  }
  c.restore();
}

function esqueleto(c, F, P, { alfa = 1, radio = 3, cuerpo = true, numerar = false } = {}) {
  c.lineCap = 'round';
  if (cuerpo) {
    c.strokeStyle = rgba(C.texto, 0.55 * alfa); c.lineWidth = 2;
    c.beginPath(); c.moveTo(...P(F.oi)); c.lineTo(...P(F.od)); c.stroke();
    for (const [o, co, m] of [[F.oi, F.ci, F.mi], [F.od, F.cd, F.md]]) {
      c.beginPath(); c.moveTo(...P(o)); c.lineTo(...P(co)); c.lineTo(...P(m)); c.stroke();
    }
    c.fillStyle = rgba(C.texto, alfa);
    for (const p of [F.nariz, F.oi, F.od, F.ci, F.cd, F.mi, F.md]) { c.beginPath(); c.arc(...P(p), radio + 1, 0, 6.283); c.fill(); }
  }
  for (const [mano, color] of [[F.manoI, C.jade], [F.manoD, C.maya]]) {
    c.strokeStyle = rgba(color, 0.75 * alfa); c.lineWidth = 1.6;
    for (const [i, j] of CONEXIONES_MANO) { c.beginPath(); c.moveTo(...P(mano[i])); c.lineTo(...P(mano[j])); c.stroke(); }
    c.fillStyle = rgba(color, alfa);
    mano.forEach((p, i) => { c.beginPath(); c.arc(...P(p), PUNTAS.includes(i) ? radio : radio - 0.6, 0, 6.283); c.fill(); });
  }
  if (numerar) {
    const n = P(F.nariz);
    texto(c, 'nariz', n[0] + 10, n[1] + 4, { tam: 11, color: C.texto3 });
  }
}

// =============================================================== escenas
const ESCENAS = {
  camara(c, w, h, t) {
    const v = visor(w, h);
    const F = figura(t); const P = aVisor(v);
    c.save(); caja(c, v.x, v.y, v.w, v.h, 16); c.clip();
    const g = c.createLinearGradient(v.x, v.y, v.x, v.y + v.h);
    g.addColorStop(0, '#162033'); g.addColorStop(1, '#0E1624');
    c.fillStyle = g; c.fillRect(v.x, v.y, v.w, v.h);
    silueta(c, F, P);
    // línea de escaneo
    const y = v.y + ((t * 0.35) % 1) * v.h;
    const gl = c.createLinearGradient(0, y - 40, 0, y);
    gl.addColorStop(0, rgba(C.jade, 0)); gl.addColorStop(1, rgba(C.jade, 0.16));
    c.fillStyle = gl; c.fillRect(v.x, y - 40, v.w, 40);
    c.fillStyle = rgba(C.jade, 0.5); c.fillRect(v.x, y, v.w, 1);
    c.restore();
    esquinas(c, v, C.texto2);
    const fps = 28 + ((Math.sin(t * 3.1) + Math.sin(t * 7.7)) > 0.6 ? 1 : 0);
    c.fillStyle = C.coral; c.beginPath(); c.arc(v.x + 18, v.y + 20, 4, 0, 6.283); c.fill();
    texto(c, `${fps} cps`, v.x + 30, v.y + 24, { tam: 12, color: C.texto, peso: 500 });
    texto(c, 'espejo · 640 × 480', v.x + v.w - 14, v.y + 24, { tam: 11, color: C.texto3, alin: 'right' });
    parrafo(c, 'El video se procesa aquí y se descarta: nunca se guarda.', w / 2, v.y + v.h + 34, w - 40, { tam: w < 420 ? 12 : 13, alin: 'center' });
  },

  puntos(c, w, h, t) {
    const v = visor(w, h);
    const F = figura(t); const P = aVisor(v);
    c.save(); caja(c, v.x, v.y, v.w, v.h, 16); c.clip();
    c.fillStyle = '#0E1624'; c.fillRect(v.x, v.y, v.w, v.h);
    c.globalAlpha *= 0.22; silueta(c, F, P); c.globalAlpha /= 0.22;
    esqueleto(c, F, P, { radio: Math.max(2.4, v.h / 150) });
    c.restore();
    esquinas(c, v, C.texto3);
    // Contador de valores (se encoge si el lienzo es angosto)
    const esc = Math.min(1, (w - 24) / 400);
    c.save(); c.translate(w / 2, v.y + v.h + 34); c.scale(esc, esc); c.translate(-w / 2, 0);
    const y = 0;
    const partes = [['21', C.jade, 'mano izq.'], ['21', C.maya, 'mano der.'], ['7', C.texto, 'cuerpo']];
    let x = w / 2 - 190;
    partes.forEach(([n, col, nom], i) => {
      texto(c, n, x, y, { tam: 22, peso: 600, color: col });
      texto(c, nom, x, y + 18, { tam: 11, color: C.texto3 });
      x += 74;
      if (i < 2) texto(c, '+', x - 20, y, { tam: 18, color: C.texto3 });
    });
    texto(c, '× (x, y, z)  =', x - 4, y, { tam: 14, color: C.texto2 });
    texto(c, '147', x + 98, y, { tam: 26, peso: 700, color: C.ambar });
    texto(c, 'valores', x + 98, y + 18, { tam: 11, color: C.texto3 });
    c.restore();
  },

  corte(c, w, h, t) {
    // Figura pequeña arriba a la izquierda y gráfica de la altura de la muñeca abajo
    const v = { x: 24, y: 64, w: Math.min(220, w * 0.38), h: Math.min(165, w * 0.38 * 0.75) };
    const F = figura(t); const P = aVisor(v);
    c.save(); caja(c, v.x, v.y, v.w, v.h, 12); c.clip(); c.fillStyle = '#0E1624'; c.fillRect(v.x, v.y, v.w, v.h);
    esqueleto(c, F, P, { radio: 1.8 }); c.restore();
    esquinas(c, v, C.texto3, 12);
    // Estado
    const ex = v.x + v.w + 22;
    const anchoTxt = w - ex - 16;
    const n1 = parrafo(c, F.arriba ? 'Manos arriba: grabando la seña' : 'Manos abajo: en espera', ex, v.y + 22, anchoTxt, { tam: 14, peso: 500, color: F.arriba ? C.jade : C.texto2 });
    parrafo(c, 'La seña empieza al levantar las manos y termina al bajarlas.', ex, v.y + 26 + n1 * 20, anchoTxt, { tam: 12, color: C.texto3 });

    // Gráfica: últimos 7 s
    const g = { x: 24, y: v.y + v.h + 40, w: w - 48, h: h - (v.y + v.h + 40) - 66 };
    const ventana = 7; const n = 220;
    const yDe = (alt) => g.y + g.h - ((0.55 - alt) / 0.95) * g.h;     // alt: y de la muñeca (abajo = mayor)
    c.strokeStyle = C.linea; c.lineWidth = 1;
    c.beginPath(); c.moveTo(g.x, g.y + g.h); c.lineTo(g.x + g.w, g.y + g.h); c.stroke();
    // Tramos de seña sombreados
    let dentro = false; let ini = 0;
    const tramos = [];
    for (let i = 0; i <= n; i++) {
      const ti = t - ventana + (i / n) * ventana; const a = figura(ti).md[1] < UMBRAL;
      if (a && !dentro) { dentro = true; ini = i; }
      if ((!a || i === n) && dentro) { dentro = false; tramos.push([ini, i, i === n && a]); }
    }
    for (const [a, b, abierto] of tramos) {
      const x0 = g.x + (a / n) * g.w; const x1 = g.x + (b / n) * g.w;
      c.fillStyle = rgba(C.jade, 0.1); c.fillRect(x0, g.y, x1 - x0, g.h);
      c.fillStyle = C.jade; c.fillRect(x0, g.y, 1.5, g.h); if (!abierto) c.fillRect(x1 - 1.5, g.y, 1.5, g.h);
      if (x1 - x0 > 70) texto(c, abierto ? 'seña…' : 'seña → 30 cuadros', x0 + 8, g.y + 16, { tam: 11, color: C.jade, peso: 500 });
      if (!abierto && x1 - x0 > 60) {
        c.fillStyle = rgba(C.ambar, 0.8);
        for (let k = 0; k < 30; k++) c.fillRect(x0 + ((x1 - x0) * (k + 0.5)) / 30 - 0.75, g.y + g.h - 8, 1.5, 8);
      }
    }
    // Umbral
    c.setLineDash([5, 6]); c.strokeStyle = rgba(C.ambar, 0.8);
    c.beginPath(); c.moveTo(g.x, yDe(UMBRAL)); c.lineTo(g.x + g.w, yDe(UMBRAL)); c.stroke(); c.setLineDash([]);
    texto(c, 'umbral: manos arriba', g.x + g.w, yDe(UMBRAL) - 8, { tam: 11, color: C.ambar, alin: 'right' });
    // Curva
    c.strokeStyle = C.maya; c.lineWidth = 2.2; c.beginPath();
    for (let i = 0; i <= n; i++) {
      const ti = t - ventana + (i / n) * ventana; const x = g.x + (i / n) * g.w; const y = yDe(figura(ti).md[1]);
      if (i) c.lineTo(x, y); else c.moveTo(x, y);
    }
    c.stroke();
    const yAhora = yDe(F.md[1]);
    c.fillStyle = C.maya; c.beginPath(); c.arc(g.x + g.w, yAhora, 4.5, 0, 6.283); c.fill();
    texto(c, 'altura de la muñeca derecha · últimos 7 s', g.x, g.y + g.h + 22, { tam: 11, color: C.texto3 });
  },

  rasgos(c, w, h, t) {
    const cols = 30; const filas = 26;
    const g = { x: 70, y: 76, w: w - 100, h: h - 76 - 92 };
    const cw = g.w / cols; const ch = g.h / filas;
    // Rasgos de la seña: 30 cuadros remuestreados del tramo con las manos arriba
    const t0 = 1.35; const t1 = 4.15;
    const barrido = Math.min(1.2, (t % 7) / 2.6);             // se llena en 2.6 s y se queda
    for (let i = 0; i < cols; i++) {
      const F = figura(t0 + ((t1 - t0) * i) / (cols - 1));
      const ref = F.od; const ancho = F.od[0] - F.oi[0];
      const vals = [];
      for (const p of [F.md, F.mi, F.cd, F.ci]) vals.push((p[0] - ref[0]) / ancho, (p[1] - ref[1]) / ancho);
      for (const k of PUNTAS) { const p = F.manoD[k]; vals.push((p[0] - F.md[0]) * 8, (p[1] - F.md[1]) * 8); }
      for (const k of [4, 8, 12]) { const p = F.manoI[k]; vals.push((p[0] - F.mi[0]) * 8, (p[1] - F.mi[1]) * 8); }
      while (vals.length < filas) vals.push(Math.sin(i * 0.4 + vals.length));
      const aparece = suave((barrido * cols - i) / 2);
      for (let j = 0; j < filas; j++) {
        const v = Math.tanh(vals[j]);
        const col = v >= 0 ? C.ambar : C.maya;
        c.fillStyle = rgba(col, (0.12 + Math.abs(v) * 0.85) * aparece);
        c.fillRect(g.x + i * cw + 1, g.y + j * ch + 1, cw - 2, ch - 2);
      }
    }
    c.strokeStyle = C.linea; c.strokeRect(g.x - 0.5, g.y - 0.5, g.w + 1, g.h + 1);
    texto(c, '30 cuadros  →', g.x, g.y + g.h + 24, { tam: 12, color: C.texto2 });
    c.save(); c.translate(g.x - 18, g.y + g.h); c.rotate(-Math.PI / 2);
    texto(c, '260 rasgos (muestra de 26)  →', 0, 0, { tam: 12, color: C.texto2 }); c.restore();
    const ly = g.y + g.h + 52;
    texto(c, 'respecto a los hombros', g.x, ly, { tam: 11, color: C.texto3 });
    c.fillStyle = C.maya; c.fillRect(g.x + 150, ly - 9, 14, 10);
    texto(c, '−', g.x + 170, ly, { tam: 12, color: C.texto3 });
    c.fillStyle = C.ambar; c.fillRect(g.x + 186, ly - 9, 14, 10);
    texto(c, '+', g.x + 206, ly, { tam: 12, color: C.texto3 });
  },

  bosque(c, w, h, t) {
    const cols = 20; const filas = 10;
    const clases = [['Hola', C.jade, 0.82], ['Adiós', C.maya, 0.09], ['Mucho gusto', C.violeta, 0.06], ['Bienvenido', C.coral, 0.03]];
    const area = { x: 28, y: 72, w: w - 56, h: Math.min(h * 0.5, (w - 56) * 0.5) };
    const cw = area.w / cols; const ch = area.h / filas;
    const ciclo = 6.5; const f = (t % ciclo) / ciclo;
    const votados = Math.floor(suave(f / 0.62) * 200);
    // Votos fijos: la mayoría «Hola»
    const voto = (i) => { const r = ((Math.sin(i * 91.7) * 43758.5) % 1 + 1) % 1; return r < 0.82 ? 0 : r < 0.91 ? 1 : r < 0.97 ? 2 : 3; };
    const conteo = [0, 0, 0, 0];
    for (let i = 0; i < 200; i++) {
      const x = area.x + (i % cols) * cw + cw / 2; const y = area.y + Math.floor(i / cols) * ch + ch / 2;
      const s = Math.min(cw, ch) * 0.34;
      const v = i < votados ? voto(i) : -1;
      if (v >= 0) conteo[v]++;
      const col = v >= 0 ? clases[v][1] : C.sup2;
      c.fillStyle = col;
      c.beginPath(); c.moveTo(x, y - s); c.lineTo(x + s * 0.8, y + s * 0.5); c.lineTo(x - s * 0.8, y + s * 0.5); c.closePath(); c.fill();
      c.fillRect(x - 0.8, y + s * 0.5, 1.6, s * 0.45);
    }
    texto(c, `${votados} de 200 árboles han votado`, area.x, area.y + area.h + 26, { tam: 12, color: C.texto2 });
    // Barras de resultado
    let y = area.y + area.h + 58;
    const bw = w - 56 - 190;
    clases.forEach(([nombre, col], i) => {
      const k = votados ? conteo[i] / votados : 0;
      texto(c, nombre, area.x, y + 4, { tam: 13, color: i === 0 ? C.texto : C.texto2, peso: i === 0 ? 600 : 400 });
      c.fillStyle = rgba(C.texto, 0.06); c.fillRect(area.x + 110, y - 6, bw, 10);
      c.fillStyle = col; c.fillRect(area.x + 110, y - 6, bw * k, 10);
      texto(c, `${Math.round(k * 100)} %`, area.x + 120 + bw, y + 4, { tam: 12, color: C.texto2 });
      y += 26;
    });
    texto(c, 'Ejemplo ilustrativo de cómo vota el bosque', w - 28, h - 18, { tam: 11, color: C.texto3, alin: 'right' });
  },

  subtitulo(c, w, h, t) {
    const palabras = ['Hola', 'Buenos días', 'Gracias'];
    const ciclo = 3.2; const i = Math.floor(t / ciclo) % palabras.length; const f = (t % ciclo) / ciclo;
    // Onda de voz
    const cx = w / 2; const cy = h * 0.32;
    const barras = 38;
    for (let b = 0; b < barras; b++) {
      const x = cx + (b - barras / 2) * 9;
      const env = Math.sin(Math.min(1, f / 0.55) * Math.PI);
      const a = (0.15 + Math.abs(Math.sin(t * 9 + b * 0.7) * Math.cos(t * 3 + b * 0.31))) * env * Math.exp(-(((b - barras / 2) / (barras / 2.4)) ** 2));
      const alto = 4 + a * h * 0.18;
      c.fillStyle = rgba(C.maya, 0.35 + a); caja(c, x - 2.5, cy - alto / 2, 5, alto, 2.5); c.fill();
    }
    // Subtítulo
    const sw = Math.min(w - 48, 460); const sx = (w - sw) / 2; const sy = h * 0.52;
    caja(c, sx, sy, sw, 104, 18); c.fillStyle = rgba('#000000', 0.45); c.fill();
    c.strokeStyle = C.linea; c.stroke();
    const entra = suave(f / 0.15);
    c.save(); c.globalAlpha *= entra;
    texto(c, palabras[i], w / 2, sy + 66, { tam: Math.min(48, w / 9), peso: 700, color: C.texto, alin: 'center' });
    c.restore();
    c.fillStyle = rgba(C.texto, 0.08); c.fillRect(sx + 24, sy + 84, sw - 48, 4);
    c.fillStyle = C.jade; c.fillRect(sx + 24, sy + 84, (sw - 48) * 0.93, 4);
    // Historial y oración
    const hist = palabras.slice(0, i + 1).join('  ·  ');
    texto(c, hist, w / 2, sy + 140, { tam: 13, color: C.texto2, alin: 'center' });
    if (i === palabras.length - 1 && f > 0.45) {
      c.save(); c.globalAlpha *= suave((f - 0.45) / 0.2);
      const ow = Math.min(w - 48, 360); caja(c, (w - ow) / 2, sy + 160, ow, 42, 12); c.fillStyle = rgba(C.violeta, 0.16); c.fill();
      texto(c, '«Hola, buenos días. Gracias.»', w / 2, sy + 186, { tam: 14, color: '#CFC7FF', alin: 'center' });
      c.restore();
    }
  },

  texto(c, w, h, t) {
    const limpia = 'Hola, buenos días, gracias';
    const ciclo = 6; const f = (t % ciclo) / ciclo;
    const n = Math.floor(suave(f / 0.4) * limpia.length);
    const bx = 32; const bw = w - 64; const by = h * 0.22;
    caja(c, bx, by, bw, 58, 14); c.fillStyle = C.sup; c.fill(); c.strokeStyle = rgba(C.violeta, 0.55); c.lineWidth = 1.5; c.stroke();
    texto(c, 'La persona oyente escribe o dicta', bx + 4, by - 14, { tam: 12, color: C.texto3 });
    const escrito = limpia.slice(0, n);
    texto(c, escrito, bx + 20, by + 36, { tam: 18, color: C.texto });
    if ((t * 2) % 1 < 0.6 && f < 0.45) {
      c.font = `400 18px ${FUENTE}`; const tw = c.measureText(escrito).width;
      c.fillStyle = C.violeta; c.fillRect(bx + 22 + tw, by + 20, 2, 22);
    }
    // Fichas: frase más larga primero
    const fichas = [['hola', C.jade, 'clip ✓'], ['buenos días', C.maya, 'frase de 2 palabras ✓'], ['gracias', C.violeta, 'clip ✓']];
    let y = by + 112;
    fichas.forEach(([s, col, nota], i) => {
      const k = suave((f - 0.45 - i * 0.08) / 0.1);
      if (k <= 0) return;
      c.save(); c.globalAlpha *= k; c.translate((1 - k) * 16, 0);
      c.font = `500 15px ${FUENTE}`; const tw = c.measureText(s).width;
      caja(c, bx, y, tw + 32, 40, 20); c.fillStyle = rgba(col, 0.14); c.fill(); c.strokeStyle = rgba(col, 0.6); c.stroke();
      texto(c, s, bx + 16, y + 26, { tam: 15, peso: 500, color: C.texto });
      texto(c, nota, bx + tw + 48, y + 26, { tam: 12, color: C.texto3 });
      if (i < fichas.length - 1) texto(c, '↓', bx + 16, y + 58, { tam: 13, color: C.texto3 });
      c.restore();
      y += 66;
    });
    texto(c, '«buenos días» antes que «buenos»: la frase más larga primero', w / 2, h - 22, { tam: 12, color: C.texto3, alin: 'center' });
  },

  clips(c, w, h, t) {
    // JSON del clip a la izquierda (o arriba si es angosto)
    const lineas = [
      ['{', C.texto2], ['  "format": "inclusion-movimiento",', C.texto2], ['  "word": "hola",', C.ambar], ['  "fps": 29.7,', C.texto2],
      ['  "duration": 2.4,', C.texto2], ['  "frames": [', C.texto2], ['    { "t": 0.0, "pose": [[x, y, z] …],', C.jade],
      ['      "left": [ … 21 ], "right": null },', C.jade], ['    …', C.texto3], ['  ]', C.texto2], ['}', C.texto2],
    ];
    const tam = Math.max(10, Math.min(13, w / 40));
    lineas.forEach(([s, col], i) => texto(c, s, 28, 82 + i * (tam + 7), { tam, color: col, fuente: MONO }));
    // Señal cruda vs suavizada (One Euro)
    const g = { x: 28, y: 82 + lineas.length * (tam + 7) + 26, w: w - 56, h: h - (82 + lineas.length * (tam + 7) + 26) - 60 };
    const n = 160;
    const valor = (k) => Math.sin(k * 5.2 + t * 0.6) * 0.32 + Math.sin(k * 13 + t) * 0.1;
    const ruido = (k) => (Math.sin(k * 311 + t * 37) * Math.cos(k * 97 + t * 11)) * 0.09;
    c.strokeStyle = rgba(C.texto2, 0.45); c.lineWidth = 1.2; c.beginPath();
    for (let i = 0; i <= n; i++) { const k = i / n; const x = g.x + k * g.w; const y = g.y + g.h / 2 - (valor(k) + ruido(k)) * g.h; if (i) c.lineTo(x, y); else c.moveTo(x, y); }
    c.stroke();
    c.strokeStyle = C.jade; c.lineWidth = 2.4; c.beginPath();
    for (let i = 0; i <= n; i++) { const k = i / n; const x = g.x + k * g.w; const y = g.y + g.h / 2 - valor(k) * g.h; if (i) c.lineTo(x, y); else c.moveTo(x, y); }
    c.stroke();
    // Recorte
    const a = 0.12 + Math.sin(t * 0.8) * 0.03; const b = 0.86 + Math.cos(t * 0.7) * 0.03;
    c.fillStyle = rgba('#000000', 0.45);
    c.fillRect(g.x, g.y - 8, g.w * a, g.h + 16); c.fillRect(g.x + g.w * b, g.y - 8, g.w * (1 - b), g.h + 16);
    for (const k of [a, b]) { c.fillStyle = C.violeta; caja(c, g.x + g.w * k - 4, g.y - 10, 8, g.h + 20, 4); c.fill(); }
    texto(c, 'cruda', g.x, g.y + g.h + 30, { tam: 11, color: C.texto3 });
    c.fillStyle = C.jade; c.fillRect(g.x + 48, g.y + g.h + 24, 16, 3);
    texto(c, 'con filtro One Euro · recorte de la toma', g.x + 70, g.y + g.h + 30, { tam: 11, color: C.texto3 });
  },

  retarget(c, w, h, t) {
    const F = figura(t);
    const mitad = w / 2;
    const vI = { x: 16, y: 80, w: mitad - 24, h: h - 190 };
    const vD = { x: mitad + 8, y: 80, w: mitad - 24, h: h - 190 };
    const PI = aVisor(vI); const PD = aVisor(vD);
    texto(c, 'Persona (puntos)', vI.x + vI.w / 2, 70, { tam: 12, color: C.texto2, alin: 'center' });
    texto(c, 'Personaje (huesos)', vD.x + vD.w / 2, 70, { tam: 12, color: C.texto2, alin: 'center' });
    esqueleto(c, F, PI, { radio: 2.2 });
    // Rig: mismas direcciones, otras proporciones (brazo más corto, antebrazo más largo)
    const prop = { brazo: 0.85, ante: 1.15 };
    const huesos = [];
    for (const [o, co, m, mano, col] of [[F.oi, F.ci, F.mi, F.manoI, C.jade], [F.od, F.cd, F.md, F.manoD, C.maya]]) {
      const dB = [co[0] - o[0], co[1] - o[1]]; const dA = [m[0] - co[0], m[1] - co[1]];
      const codo = [o[0] + dB[0] * prop.brazo, o[1] + dB[1] * prop.brazo];
      const mun = [codo[0] + dA[0] * prop.ante, codo[1] + dA[1] * prop.ante];
      huesos.push([o, codo, C.texto], [codo, mun, C.texto]);
      const off = [mun[0] - m[0], mun[1] - m[1]];
      for (const [i, j] of CONEXIONES_MANO) {
        huesos.push([[mano[i][0] + off[0], mano[i][1] + off[1]], [mano[j][0] + off[0], mano[j][1] + off[1]], col]);
      }
    }
    huesos.push([F.oi, F.od, C.texto]);
    for (const [a, b, col] of huesos) {
      const [x0, y0] = PD(a); const [x1, y1] = PD(b);
      const L = Math.hypot(x1 - x0, y1 - y0); if (L < 1) continue;
      const ang = Math.atan2(y1 - y0, x1 - x0); const g = Math.min(7, L * 0.16);
      c.save(); c.translate(x0, y0); c.rotate(ang);
      c.beginPath(); c.moveTo(0, 0); c.lineTo(L * 0.18, -g); c.lineTo(L, 0); c.lineTo(L * 0.18, g); c.closePath();
      c.fillStyle = rgba(col === C.texto ? C.violeta : col, 0.85); c.fill(); c.restore();
    }
    // Flechas: misma dirección
    const pares = [[F.od, F.cd], [F.cd, F.md]];
    pares.forEach(([a, b]) => {
      const [x0, y0] = PI(a); const [x1, y1] = PI(b);
      const ang = Math.atan2(y1 - y0, x1 - x0);
      for (const [x, y] of [[(x0 + x1) / 2, (y0 + y1) / 2], PD([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2])]) {
        c.save(); c.translate(x, y); c.rotate(ang); c.strokeStyle = C.ambar; c.lineWidth = 2;
        c.beginPath(); c.moveTo(-10, -12); c.lineTo(10, -12); c.lineTo(5, -16); c.moveTo(10, -12); c.lineTo(5, -8); c.stroke(); c.restore();
      }
    });
    c.setLineDash([3, 6]); c.strokeStyle = rgba(C.texto3, 0.6); c.beginPath(); c.moveTo(mitad, 90); c.lineTo(mitad, h - 120); c.stroke(); c.setLineDash([]);
    const y = h - 74;
    texto(c, 'Cada hueso apunta como el segmento de la persona.', w / 2, y, { tam: 13, color: C.texto2, alin: 'center' });
    texto(c, 'Blender  ⇄  three.js:', w / 2 - 8, y + 34, { tam: 14, color: C.texto2, alin: 'right' });
    texto(c, '0.003°', w / 2 + 2, y + 35, { tam: 24, peso: 700, color: C.ambar });
  },

  avatar(c, w, h, t) {
    // El rig del personaje: huesos y articulaciones, con la mano que cuenta con los dedos
    const v = visor(w, h, 0.08, 56, 96);
    const P = aVisor(v);
    const g = c.createRadialGradient(w / 2, v.y + v.h * 0.5, 10, w / 2, v.y + v.h * 0.5, v.h * 0.8);
    g.addColorStop(0, rgba(C.violeta, 0.22)); g.addColorStop(1, rgba(C.violeta, 0));
    c.fillStyle = g; c.fillRect(0, 0, w, h);
    const F = figura(t);
    const hueso = (a, b, col, grosor = 0.16) => {
      const [x0, y0] = P(a); const [x1, y1] = P(b);
      const L = Math.hypot(x1 - x0, y1 - y0); if (L < 1) return;
      const gr = Math.min(9, L * grosor);
      c.save(); c.translate(x0, y0); c.rotate(Math.atan2(y1 - y0, x1 - x0));
      c.beginPath(); c.moveTo(0, 0); c.lineTo(L * 0.2, -gr); c.lineTo(L, 0); c.lineTo(L * 0.2, gr); c.closePath();
      c.fillStyle = rgba(col, 0.9); c.fill(); c.restore();
    };
    const articulacion = (p, r = 4) => { c.fillStyle = C.texto; c.beginPath(); c.arc(...P(p), r, 0, 6.283); c.fill(); };
    // Columna y cabeza
    const cadera = [0, 0.5]; const pecho = [0, -0.06]; const cuello = [0, -0.2];
    hueso(cadera, [0, 0.22], C.violeta); hueso([0, 0.22], pecho, C.violeta); hueso(pecho, cuello, C.violeta);
    hueso(pecho, F.oi, C.violeta, 0.1); hueso(pecho, F.od, C.violeta, 0.1);
    const cab = P([F.nariz[0], F.nariz[1] - 0.05]);
    c.strokeStyle = rgba(C.texto, 0.8); c.lineWidth = 2; c.beginPath();
    c.ellipse(cab[0], cab[1], v.h * 0.085, v.h * 0.105, 0, 0, 6.283); c.stroke();
    for (const [o, co, m, mano, col] of [[F.oi, F.ci, F.mi, F.manoI, C.jade], [F.od, F.cd, F.md, F.manoD, C.maya]]) {
      hueso(o, co, C.violeta); hueso(co, m, C.violeta);
      for (const [i, j] of CONEXIONES_MANO) if (i !== 0 || [1, 5, 9, 13, 17].includes(j)) hueso(mano[i], mano[j], col, 0.22);
      [o, co, m].forEach((p) => articulacion(p));
    }
    [cadera, [0, 0.22], pecho, cuello].forEach((p) => articulacion(p, 3));
    // Mano que cuenta, al lado
    const k = (t * 0.9) % 6.5;
    const mc = manoContando([0, 0], 1, Math.min(5, k));
    const ox = w - Math.max(56, w * 0.13); const oy = v.y + v.h * 0.78; const ms = Math.min(50, v.h * 0.15);
    c.strokeStyle = C.jade; c.lineWidth = 3; c.lineCap = 'round';
    for (const [i, j] of CONEXIONES_MANO) { c.beginPath(); c.moveTo(ox + mc[i][0] * ms, oy + mc[i][1] * ms); c.lineTo(ox + mc[j][0] * ms, oy + mc[j][1] * ms); c.stroke(); }
    texto(c, `${Math.min(5, Math.floor(k))} de 5 dedos`, ox, oy + 26, { tam: 11, color: C.texto3, alin: 'center' });
    texto(c, '78 huesos · 42 se mueven · 3 falanges por dedo', w / 2, h - 62, { tam: 12, color: C.texto2, alin: 'center' });
    texto(c, 'El avatar real está justo abajo  ↓', w / 2, h - 32, { tam: 14, peso: 500, color: C.texto, alin: 'center' });
  },
};

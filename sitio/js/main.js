// K'ab T'aan · sitio informativo. Todo lo que no es el diagrama del proceso ni el avatar 3D.
import { numeralMaya } from './maya.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const movimientoReducido = matchMedia('(prefers-reduced-motion: reduce)');

// ----------------------------------------------------------- numerales mayas de las secciones
for (const el of $$('[data-maya]')) {
  const n = Number(el.dataset.maya);
  const svg = numeralMaya(n, { titulo: `${n} en numeración maya` });
  el.insertAdjacentHTML('afterbegin', el.classList.contains('seccion-num') ? `<span class="glifo">${svg}</span>` : svg);
}

// ----------------------------------------------------------- barra superior y menú
const barra = $('#barra');
const progreso = $('#progreso');
const menu = $('#menu');
const menuBoton = $('#menu-boton');

function alBajar() {
  const y = scrollY;
  barra.classList.toggle('solida', y > 24);
  const total = document.documentElement.scrollHeight - innerHeight;
  progreso.style.transform = `scaleX(${total > 0 ? Math.min(1, y / total) : 0})`;
}
addEventListener('scroll', alBajar, { passive: true });
alBajar();

function abrirMenu(si) {
  menu.classList.toggle('abierto', si);
  menuBoton.setAttribute('aria-expanded', String(si));
  menuBoton.querySelector('.solo-lector').textContent = si ? 'Cerrar el menú' : 'Abrir el menú';
}
menuBoton.addEventListener('click', () => abrirMenu(menuBoton.getAttribute('aria-expanded') !== 'true'));
menu.addEventListener('click', (e) => { if (e.target.closest('a')) abrirMenu(false); });
addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && menu.classList.contains('abierto')) { abrirMenu(false); menuBoton.focus(); }
});

// Sección actual en el menú
const enlaces = new Map($$('.menu a').map((a) => [a.getAttribute('href').slice(1), a]));
const observaSecciones = new IntersectionObserver((entradas) => {
  for (const e of entradas) {
    if (!e.isIntersecting) continue;
    for (const a of enlaces.values()) a.classList.remove('activo');
    const a = enlaces.get(e.target.id);
    if (a) a.classList.add('activo');
  }
}, { rootMargin: '-45% 0px -50% 0px' });
$$('main section[id]').forEach((s) => observaSecciones.observe(s));

// ----------------------------------------------------------- aparecer al bajar
const observaRevelar = new IntersectionObserver((entradas) => {
  for (const e of entradas) {
    if (!e.isIntersecting) continue;
    e.target.classList.add('visible');
    observaRevelar.unobserve(e.target);
  }
}, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

// Escalonar los elementos hermanos que aparecen juntos
for (const el of $$('.revelar')) {
  const hermanos = [...el.parentElement.children].filter((h) => h.classList.contains('revelar'));
  const i = hermanos.indexOf(el);
  if (i > 0) el.style.setProperty('--retraso', `${Math.min(i, 6) * 0.08}s`);
  if (!el.closest('.heroe')) observaRevelar.observe(el);
}

// ----------------------------------------------------------- contadores
const formato = (v, dec) => v.toLocaleString('es-MX', { minimumFractionDigits: dec, maximumFractionDigits: dec });
const observaContar = new IntersectionObserver((entradas) => {
  for (const e of entradas) {
    if (!e.isIntersecting) continue;
    observaContar.unobserve(e.target);
    const el = e.target; const fin = Number(el.dataset.contar); const dec = Number(el.dataset.decimales || 0);
    if (movimientoReducido.matches) { el.textContent = formato(fin, dec); continue; }
    const t0 = performance.now(); const dur = 1400;
    const paso = (ahora) => {
      const k = Math.min(1, (ahora - t0) / dur);
      const e3 = 1 - (1 - k) ** 3;
      el.textContent = formato(fin * e3, dec);
      if (k < 1) requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  }
}, { threshold: 0.6 });
$$('[data-contar]').forEach((el) => observaContar.observe(el));

// ----------------------------------------------------------- subtítulo de la portada
const PALABRAS = [['Hola', 94], ['Buenos días', 91], ['Gracias', 96], ['Mucho gusto', 88], ['Por favor', 92], ['Adiós', 95]];
const subtPalabra = $('#subt-palabra'); const subtConf = $('#subt-conf'); const subtBarra = $('#subt-barra');
const maquetaPalabra = $('#maqueta-palabra');
let iPalabra = 0;
function siguientePalabra() {
  iPalabra = (iPalabra + 1) % PALABRAS.length;
  const [palabra, conf] = PALABRAS[iPalabra];
  subtPalabra.classList.add('cambiando');
  setTimeout(() => {
    subtPalabra.textContent = palabra;
    subtConf.textContent = conf;
    subtBarra.style.width = `${conf}%`;
    subtPalabra.classList.remove('cambiando');
  }, 380);
}
if (!movimientoReducido.matches) setInterval(() => { if (!document.hidden) siguientePalabra(); }, 2600);

// ----------------------------------------------------------- puntos de la portada
import('./heroe.js').then((m) => m.iniciarHeroe($('#heroe-puntos'), movimientoReducido.matches)).catch(() => {});

// ----------------------------------------------------------- diccionario
const VOCAB = [
  ['hola', 'Hola', 'Saludos'], ['adios', 'Adiós', 'Saludos'], ['bienvenido', 'Bienvenido', 'Saludos'],
  ['buenos dias', 'Buenos días', 'Saludos'], ['buenas tardes', 'Buenas tardes', 'Saludos'],
  ['buenas noches', 'Buenas noches', 'Saludos'], ['gracias', 'Gracias', 'Cortesía'], ['de nada', 'De nada', 'Cortesía'],
  ['por favor', 'Por favor', 'Cortesía'], ['perdon', 'Perdón', 'Cortesía'], ['mucho gusto', 'Mucho gusto', 'Cortesía'],
];
const sinAcentos = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
const vocab = $('#vocab');
function pintarVocab(q = '') {
  const b = sinAcentos(q);
  const hallados = VOCAB.filter(([clave, texto]) => !b || clave.includes(b) || sinAcentos(texto).includes(b));
  vocab.innerHTML = hallados.length
    ? hallados.map(([, texto, cat]) => `<li>${texto}<small>${cat}</small></li>`).join('')
    : `<li class="vacio">«${q.replace(/[<>&"]/g, '')}» todavía no está. En la app la grabas en Entrenar.</li>`;
}
$('#dicc-buscar').addEventListener('input', (e) => pintarVocab(e.target.value));
pintarVocab();

// ----------------------------------------------------------- elegir una o dos manos (ejemplo)
const manos = $$('.manos-elige button');
manos.forEach((b) => b.addEventListener('click', () => manos.forEach((o) => o.setAttribute('aria-pressed', String(o === b)))));

// ----------------------------------------------------------- recortar una toma (ejemplo)
iniciarRecorte();
function iniciarRecorte() {
  const ini = $('#recorte-ini'); const fin = $('#recorte-fin');
  const sel = $('#recorte-sel'); const dur = $('#recorte-dur'); const canvas = $('#recorte-canvas');
  const TOTAL = 2.4; // s de la toma de ejemplo
  // Altura de la muñeca a lo largo de una toma: reposo, sube, seña, baja, reposo
  const altura = (k) => {
    const sube = 1 / (1 + Math.exp(-(k - 0.2) * 28)); const baja = 1 / (1 + Math.exp((k - 0.78) * 28));
    return 0.12 + 0.7 * sube * baja + 0.07 * Math.sin(k * 40) * sube * baja;
  };
  function dibujar() {
    const r = canvas.getBoundingClientRect(); const dpr = Math.min(devicePixelRatio, 2);
    if (!r.width) return;
    canvas.width = r.width * dpr; canvas.height = r.height * dpr;
    const c = canvas.getContext('2d'); c.scale(dpr, dpr);
    const a = Number(ini.value) / 100; const b = Number(fin.value) / 100;
    const n = 120;
    for (let i = 0; i < n; i++) {
      const k = i / (n - 1); const h = altura(k) * (r.height - 14);
      const dentro = k >= a && k <= b;
      c.fillStyle = dentro ? `rgba(124, 92, 255, ${0.45 + 0.5 * altura(k)})` : 'rgba(154, 164, 181, .18)';
      const w = r.width / n;
      c.fillRect(i * w + 1, r.height - 7 - h, Math.max(1, w - 2), h);
    }
  }
  function actualizar(e) {
    let a = Number(ini.value); let b = Number(fin.value);
    if (b - a < 8) { if (e && e.target === ini) { a = b - 8; ini.value = a; } else { b = a + 8; fin.value = b; } }
    sel.style.left = `${a}%`; sel.style.width = `${b - a}%`;
    dur.textContent = `${formato(((b - a) / 100) * TOTAL, 2)} s`;
    dibujar();
  }
  ini.addEventListener('input', actualizar); fin.addEventListener('input', actualizar);
  new ResizeObserver(() => dibujar()).observe(canvas);
  actualizar();
}

// ----------------------------------------------------------- numerales mayas interactivos
const numeralIn = $('#numeral-in'); const numeralSalida = $('#numeral-salida');
function pintarNumeral() {
  let n = Math.floor(Number(numeralIn.value));
  if (!Number.isFinite(n) || n < 0) n = 0;
  if (n > 7999) n = 7999;
  numeralSalida.innerHTML = numeralMaya(n, { titulo: `${n} en numeración maya`, grande: true });
}
numeralIn.addEventListener('input', pintarNumeral);
pintarNumeral();

// ----------------------------------------------------------- maqueta de Traducir
if (!movimientoReducido.matches && maquetaPalabra) {
  let j = 0;
  setInterval(() => {
    if (document.hidden) return;
    j = (j + 1) % PALABRAS.length;
    maquetaPalabra.style.opacity = 0;
    setTimeout(() => { maquetaPalabra.textContent = PALABRAS[j][0]; maquetaPalabra.style.opacity = 1; }, 300);
  }, 3100);
}

// ----------------------------------------------------------- carga diferida: proceso y avatar
function alAcercarse(el, margen, cargar) {
  if (!el) return;
  const io = new IntersectionObserver((entradas) => {
    if (entradas.some((e) => e.isIntersecting)) { io.disconnect(); cargar(); }
  }, { rootMargin: margen });
  io.observe(el);
}
alAcercarse($('#proceso'), '600px 0px', () => import('./proceso.js').then((m) => m.iniciarProceso()));
alAcercarse($('#avatar'), '700px 0px', () => import('./avatar-sitio.js').then((m) => m.iniciarAvatar()).catch((err) => {
  console.error(err);
  const carga = $('#avatar-carga');
  carga.innerHTML = '<span>No se pudo cargar el avatar 3D en este navegador (necesita WebGL).</span>';
}));

// K'ab T'aan · interfaz. Habla con app/servidor_web.py:
//   /eventos  (estado + movimiento 3D, ~30 por segundo)   /video  (cámara)   /api/...  (acciones y datos)
import { Avatar } from './avatar.js';
import { crearEscenas } from './escenas.js';
import { buscarSenas, norm } from './texto.js';
import { crearAprender } from './vista_aprender.js';
import { crearDiccionario } from './vista_diccionario.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const TITULOS = {
  inicio: 'Inicio', traducir: 'Traducir', aprender: 'Aprender', diccionario: 'Diccionario de señas',
  entrenar: 'Entrenar el traductor', avatar: 'Avatar', ayuda: 'Ayuda',
};
const PIES = {
  traducir: 'El avatar repite cada seña reconocida y dice en señas lo que escribe el interlocutor.',
  avatar: 'El avatar te imita en vivo.',
  aprender: 'El avatar te enseña la seña.',
};
const MODOS_MANOS = ['dos', 'derecha', 'izquierda'];
const RECORTE_MIN = 0.3;          // s: el recorte más corto que se puede guardar
const PASO_TECLA = 1 / 30;        // s que mueve una flecha (un frame de la cámara)

const ui = {
  pagina: null,
  estado: {},
  seq: { palabra: null, texto: null, clip: null },
  revision: null,              // toma del avatar en revisión: { seq, clip, total, inicio, fin, t }
  clips: new Map(),            // palabra normalizada -> nombre del clip
  cacheClips: new Map(),       // nombre -> JSON
  avisoPrevio: '',
  entrenando: false,
  palabraAvatar: null,         // palabra que llega del Diccionario a la pantalla Avatar
  conectado: false,
};

// ------------------------------------------------------------------- servidor
async function accion(nombre, datos = {}) {
  try {
    const r = await fetch('/api/accion', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accion: nombre, ...datos }),
    });
    const j = await r.json();
    if (!j.ok) avisar(j.error || 'No se pudo hacer la acción', 'error');
    return j;
  } catch {
    avisar('Se perdió la conexión con la app', 'error');
    return { ok: false };
  }
}

const obtener = (url) => fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))));

function escuchar() {
  const fuente = new EventSource('/eventos');
  fuente.onmessage = (e) => {
    const { estado, mundo } = JSON.parse(e.data);
    if (!ui.conectado) { ui.conectado = true; escenas.marcar('estado'); }
    escenas.conexion(true);
    actualizar(estado);
    if (mundo && estado.modo === 'AVATAR' && ui.pagina === 'avatar' && !ui.revision) avatar.vivo(mundo, estado.manos);
  };
  fuente.onerror = () => { $('#chip-camara').className = 'chip mal'; escenas.conexion(false); };
}

// ----------------------------------------------------------------- navegación
function ir(pagina, dato = null) {
  if (ui.pagina === pagina) return;
  if (ui.pagina === 'aprender') aprender.alSalir();
  ui.pagina = pagina;
  $$('.pagina').forEach((p) => p.classList.toggle('visible', p.id === `pagina-${pagina}`));
  $$('.nav[data-pagina]').forEach((b) => b.classList.toggle('activa', b.dataset.pagina === pagina));
  $('#titulo').textContent = TITULOS[pagina];
  // Solo la pantalla visible recibe la cámara (un solo video a la vez)
  $$('img[data-video]').forEach((img) => {
    const visible = img.closest('.pagina').id === `pagina-${pagina}`;
    if (visible && !img.getAttribute('src')) img.src = '/video';
    if (!visible && img.getAttribute('src')) img.removeAttribute('src');
  });
  if (pagina === 'traducir') { avatar.montar($('#escenario-traducir')); avatar.detener(); accion('modo_deteccion'); }
  if (pagina === 'avatar') {
    avatar.montar($('#escenario-avatar')); avatar.detener();
    const palabra = ui.palabraAvatar !== null ? ui.palabraAvatar : (ui.estado.modo === 'AVATAR' ? ui.estado.palabra : '');
    ui.palabraAvatar = null;
    if (palabra) $('#avatar-palabra').value = palabra;
    accion('avatar_palabra', { palabra }); cargarClips();
  }
  if (pagina === 'aprender') { avatar.montar($('#escenario-aprender')); avatar.detener(); accion('modo_deteccion', { practica: true }); aprender.alEntrar(dato); }
  if (pagina === 'diccionario') { avatar.montar($('#escenario-diccionario')); avatar.detener(); diccionario.alEntrar(); }
  if (pagina === 'entrenar') { cargarDataset(); }
  // Fuera de Avatar no se imita, y fuera de Aprender se vuelven a armar oraciones
  const sinDeteccion = pagina !== 'traducir' && pagina !== 'aprender' && pagina !== 'avatar';
  if (sinDeteccion && pagina !== 'entrenar' && (ui.estado.modo === 'AVATAR' || ui.estado.practica)) accion('modo_deteccion');
  if (pagina === 'entrenar' && ui.estado.modo === 'AVATAR') accion('modo_deteccion');
}

// Abre otra pantalla con una palabra ya puesta (desde el Diccionario)
function irConPalabra(pagina, palabra) {
  if (pagina === 'entrenar') {
    ir('entrenar');
    $('#entrenar-palabra').value = palabra;
    accion('entrenar_palabra', { palabra, persona: $('#entrenar-persona').value });
  } else if (pagina === 'avatar') {
    ui.palabraAvatar = palabra;
    ir('avatar');
  } else {
    ir(pagina, palabra);
  }
}

let categoriasCache = null;
function categorias() {
  if (!categoriasCache) {
    categoriasCache = obtener('/datos/categorias.json').then((j) => j.categorias)
      .catch(() => { categoriasCache = null; return []; });
  }
  return categoriasCache;
}

// Insignias que se ganan fuera de Aprender (entrenar, grabar un movimiento, una oración)
async function revisarLogros() {
  try {
    const p = await obtener('/api/progreso');
    if (p.nuevas && p.nuevas.length) aprender.aplicarProgreso(p);
  } catch { /* se revisa la próxima vez */ }
}

// ---------------------------------------------------------- estado -> pantalla
function actualizar(e) {
  const antes = ui.estado;
  ui.estado = e;

  // Barra superior
  chip('#chip-camara', e.camara, e.camara ? `Cámara · ${e.fps} fps` : 'Sin cámara');
  chip('#chip-modelo', e.modelo_senas.length > 0, e.modelo_senas.length ? `Traductor · ${e.modelo_senas.length} señas` : 'Traductor sin entrenar');
  chip('#chip-clips', ui.clips.size > 0, `Avatar · ${ui.clips.size} señas`);
  const aviso = !e.cuerpo_visible ? 'No veo tus hombros' : e.aviso_encuadre;
  $('#chip-encuadre').textContent = aviso;
  $('#chip-encuadre').classList.toggle('oculto', !aviso || ui.pagina === 'inicio' || ui.pagina === 'ayuda');
  const voz = $('#btn-voz');
  voz.classList.toggle('apagado', !e.voz);
  voz.querySelector('.icono').style.setProperty('--i', `url(../assets/iconos/${e.voz ? 'voz' : 'silencio'}.png)`);
  $('#txt-voz').textContent = e.voz ? 'Voz' : 'Sin voz';

  // Cámara: sin señal, grabación y destellos
  const grabable = e.modo === 'TRAINING' || e.modo === 'AVATAR';
  $$('[data-camara]').forEach((c) => {
    c.classList.toggle('sin-senal', !e.camara);
    c.classList.toggle('armada', grabable && e.armado && !e.grabando);
    c.classList.toggle('grabando', grabable && e.grabando);
    c.classList.toggle('leyendo', e.modo === 'DETECTION' && e.grabando);
    c.classList.toggle('destello-ok', e.destello === 'ok');
    c.classList.toggle('destello-error', e.destello === 'error');
  });
  $$('[data-grabacion]').forEach((g) => {
    const visible = grabable && e.armado;
    g.classList.toggle('visible', visible);
    g.classList.toggle('rojo', e.grabando);
    g.innerHTML = e.grabando
      ? `● Grabando «${esc(e.palabra)}»… baja las manos al terminar<div class="progreso"><i style="width:${Math.round(e.progreso * 100)}%"></i></div>`
      : 'Listo: levanta las manos y haz la seña';
  });
  $$('[data-accion="grabar"]').forEach((b) => b.classList.toggle('activo', e.armado));
  $$('[data-manos]').forEach((b) => {
    const activo = b.dataset.manos === e.manos;
    b.classList.toggle('activo', activo);
    b.setAttribute('aria-pressed', String(activo));
  });
  $$('[data-txt-grabar]').forEach((s) => { s.textContent = e.armado ? 'Pausar (Espacio)' : 'Grabar (Espacio)'; });

  // Traducir
  if (e.seq_palabra !== ui.seq.palabra) {
    if (ui.seq.palabra !== null && e.prediccion) {
      const p = $('#palabra');
      p.textContent = e.prediccion;
      p.classList.remove('nueva', 'esperando'); void p.offsetWidth; p.classList.add('nueva');
      if (ui.pagina === 'traducir') decirEnSenas(e.prediccion);
    }
    ui.seq.palabra = e.seq_palabra;
  }
  $('#conf-relleno').style.width = `${Math.round(e.confianza * 100)}%`;
  $('#conf-texto').textContent = e.prediccion ? `Confianza ${Math.round(e.confianza * 100)} %` : '';
  $('#historial').innerHTML = e.historial.map((w) => `<span>${esc(w)}</span>`).join('');
  const oracion = $('#oracion');
  oracion.classList.toggle('cargando', e.oracion_cargando);
  if (e.oracion_cargando) oracion.textContent = 'Armando la oración…';
  else if (e.oracion) oracion.textContent = e.oracion;
  else oracion.textContent = e.modelo_senas.length
    ? 'Haz una seña: levanta las manos, hazla y bájalas.'
    : 'Primero entrena el traductor con tus señas (pantalla Entrenar).';
  $('.confianza').classList.toggle('oculto', !e.prediccion);
  $('#interlocutor').textContent = e.escuchando ? 'Escuchando…' : (e.interlocutor || 'Escribe o dicta lo que quieres decir.');
  $('#interlocutor').classList.toggle('vacio', !e.escuchando && !e.interlocutor);
  $('#btn-escuchar').classList.toggle('activo', e.escuchando);
  $('#btn-escuchar span:last-child').textContent = e.escuchando ? 'Terminar de dictar (S)' : 'Dictar con el micrófono (S)';
  if (e.seq_texto !== ui.seq.texto) {
    if (ui.seq.texto !== null && e.interlocutor && ui.pagina === 'traducir') decirEnSenas(e.interlocutor);
    ui.seq.texto = e.seq_texto;
  }

  // Entrenar
  if (e.modo === 'TRAINING') {
    $('#muestras').textContent = e.muestras_palabra;
    $('#palabra-entrenar').textContent = e.palabra;
  }
  $('#estado-entrenar').classList.toggle('oculto', e.modo !== 'TRAINING');
  if (antes.muestras_palabra !== e.muestras_palabra && ui.pagina === 'entrenar') cargarDataset();
  const btnEntrenar = $('#btn-entrenar');
  btnEntrenar.disabled = e.entrenando;
  btnEntrenar.querySelector('span:last-child').textContent = e.entrenando ? 'Entrenando…' : 'Entrenar el traductor';
  if (ui.entrenando && !e.entrenando) {
    cargarDataset();
    if (e.modelo_senas.length) {
      escenas.celebrar({ img: 'assets/img/estados/entrenado.png', titulo: '¡Traductor entrenado!',
        texto: `Ya reconoce ${e.modelo_senas.length} señas: ${e.modelo_senas.join(', ')}. Pruébalo en Traducir o practica en Aprender.` });
      revisarLogros();
    }
  }
  ui.entrenando = e.entrenando;
  $('#info-modelo').textContent = e.modelo_senas.length
    ? `El traductor conoce: ${e.modelo_senas.join(', ')}.` : 'El traductor todavía no está entrenado.';

  // Avatar
  if (e.modo === 'AVATAR') {
    $('#palabra-avatar').textContent = e.palabra || 'Sin palabra';
    $('#estado-avatar').textContent = e.palabra
      ? (ui.clips.has(norm(e.palabra)) ? 'ya tiene movimiento: una toma nueva lo reemplaza' : 'sin movimiento todavía')
      : 'Escribe la palabra y pulsa Elegir';
    $('#palabra-avatar').classList.toggle('tenue', !e.palabra);
  }
  if (e.seq_clip !== ui.seq.clip) {
    // Un clip nuevo reemplaza al anterior de esa palabra: lo guardado en caché ya no sirve
    if (ui.seq.clip !== null) { ui.cacheClips.clear(); cargarClips(); revisarLogros(); }   // el aviso lo da la app
    ui.seq.clip = e.seq_clip;
  }
  if (e.toma_pendiente && ui.pagina === 'avatar' && (!ui.revision || ui.revision.seq !== e.toma_seq)) abrirRevision(e.toma_seq);
  if (!e.toma_pendiente && ui.revision) cerrarRevision();

  if (e.oracion && e.oracion !== antes.oracion && !e.oracion_cargando) revisarLogros();
  aprender.alEstado(e);

  // Avisos de la app (lo que antes salía en la ventana de OpenCV)
  if (e.aviso && e.aviso !== ui.avisoPrevio) avisar(e.aviso, e.destello === 'error' ? 'error' : '');
  ui.avisoPrevio = e.aviso;

  $('#resumen-inicio').textContent = `${e.camara ? 'Cámara lista' : 'Buscando la cámara'} · `
    + `${e.modelo_senas.length ? `el traductor conoce ${e.modelo_senas.length} señas` : 'el traductor aún no está entrenado'} · `
    + `el avatar sabe ${ui.clips.size} señas`;
}

function chip(sel, ok, texto) {
  const c = $(sel);
  c.className = `chip ${ok ? 'ok' : 'mal'}`;
  c.innerHTML = `<i class="punto"></i>${esc(texto)}`;
}

// ------------------------------------------------------------------- datos
async function cargarDataset() {
  try {
    const { senas, personas } = await obtener('/api/dataset');
    const filas = Object.entries(senas).sort((a, b) => b[1] - a[1]);
    $('#tabla-senas').innerHTML = filas.length ? filas.map(([s, n]) => `
      <div class="fila"><span class="nombre">${esc(s)}</span><span class="detalle">${n} muestras</span>
        <button class="boton mini peligro" data-borrar-sena="${esc(s)}" title="Borrar"><span class="icono" style="--i:url(../assets/iconos/borrar.png)"></span></button></div>`).join('')
      + `<p class="ayuda-corta">Personas: ${Object.entries(personas).map(([p, n]) => `${esc(p)} (${n})`).join(', ')}</p>`
      : '<div class="fila vacia">Todavía no hay señas grabadas.</div>';
  } catch { /* el servidor no respondió: se reintenta en el próximo evento */ }
}

async function cargarClips() {
  try {
    const { clips } = await obtener('/api/clips');
    ui.clips = new Map(clips.map((c) => [norm(c), c]));
    $('#lista-clips').innerHTML = clips.length ? clips.map((c) => `
      <div class="fila"><span class="nombre">${esc(c)}</span>
        <button class="boton mini" data-ver-clip="${esc(c)}" title="Ver"><span class="icono" style="--i:url(../assets/iconos/reproducir.png)"></span></button>
        <button class="boton mini peligro" data-borrar-clip="${esc(c)}" title="Borrar"><span class="icono" style="--i:url(../assets/iconos/borrar.png)"></span></button></div>`).join('')
      : '<div class="fila vacia">El avatar todavía no sabe ninguna seña.</div>';
  } catch { /* idem */ }
}

async function clip(nombre) {
  if (!ui.cacheClips.has(nombre)) ui.cacheClips.set(nombre, await obtener(`/api/clip/${encodeURIComponent(nombre)}`));
  return ui.cacheClips.get(nombre);
}

// ------------------------------------------------- texto -> señas del avatar
async function decirEnSenas(texto) {
  const partes = buscarSenas(texto, ui.clips);
  const faltan = partes.filter((p) => !p.clip).map((p) => p.palabra);
  const lista = await Promise.all(partes.filter((p) => p.clip).map(async (p) => ({ palabra: p.palabra, clip: await clip(p.clip) })));
  const pie = $('#pie-traducir');
  if (!lista.length) {
    pie.innerHTML = `El avatar todavía no sabe «${esc(texto)}». Grábalo en <b>Avatar</b>.`;
    return;
  }
  avatar.reproducir(lista);
  if (faltan.length) avisar(`El avatar no sabe: ${faltan.join(', ')}`);
}

// ------------------------------------------- revisar y recortar la toma del avatar
async function abrirRevision(seq) {
  ui.revision = { seq, clip: null };
  let toma;
  try { toma = await obtener('/api/toma'); } catch { ui.revision = null; return; }
  if (!ui.revision || ui.revision.seq !== seq) return;          // se descartó mientras cargaba
  const total = toma.duration;
  Object.assign(ui.revision, { clip: toma, total, inicio: 0, fin: total, t: 0 });
  $('#rev-palabra').textContent = toma.word;
  $('#lt-total').textContent = `${segundos(total)} s`;
  $('#tarjeta-grabar-avatar').classList.add('oculto');
  $('#tarjeta-revision').classList.remove('oculto');
  avatar.revisar(toma);
  avatar.velocidad(ui.velocidad || 1);
  pintarRevision();
}

function cerrarRevision() {
  ui.revision = null;
  avatar.terminarRevision();
  $('#tarjeta-revision').classList.add('oculto');
  $('#tarjeta-grabar-avatar').classList.remove('oculto');
}

const segundos = (t) => t.toFixed(1).replace('.', ',');
const revisando = () => Boolean(ui.revision && ui.revision.clip);

function pintarRevision() {
  const r = ui.revision;
  if (!revisando()) return;
  const pct = (t) => `${(100 * t) / r.total}%`;
  $('#lt-rango').style.left = pct(r.inicio);
  $('#lt-rango').style.width = pct(r.fin - r.inicio);
  $('#asa-inicio').style.left = pct(r.inicio);
  $('#asa-fin').style.left = pct(r.fin);
  $('#lt-cabezal').style.left = pct(r.t);
  $('#rev-tiempos').innerHTML = `${segundos(r.inicio)} – ${segundos(r.fin)} s · dura <b>${segundos(r.fin - r.inicio)} s</b>`;
  const reproduciendo = avatar.rev && avatar.rev.reproduciendo;
  $('#rev-reproducir span:last-child').textContent = reproduciendo ? 'Pausa' : 'Reproducir';
  $('#rev-reproducir .icono').style.setProperty('--i', `url(../assets/iconos/${reproduciendo ? 'detener' : 'reproducir'}.png)`);
  $('#rev-velocidad').textContent = `Velocidad ${(ui.velocidad || 1) === 1 ? '1×' : '½×'}`;
}

// Mueve un extremo del recorte (o solo el cabezal) y muestra ese instante en el avatar
function moverRecorte(cual, t) {
  const r = ui.revision;
  if (!revisando()) return;
  if (cual === 'inicio') r.inicio = Math.min(Math.max(0, t), r.fin - RECORTE_MIN);
  if (cual === 'fin') r.fin = Math.max(Math.min(r.total, t), r.inicio + RECORTE_MIN);
  r.t = cual === 'inicio' ? r.inicio : cual === 'fin' ? r.fin : Math.min(Math.max(0, t), r.total);
  avatar.tramo(r.inicio, r.fin);
  avatar.irA(r.t);
  pintarRevision();
}

function conectarLineaDeTiempo() {
  const linea = $('#linea-tiempo');
  const tiempo = (ev) => {
    const caja = linea.getBoundingClientRect();
    return ((ev.clientX - caja.left) / caja.width) * ui.revision.total;
  };
  let arrastre = null;
  linea.addEventListener('pointerdown', (ev) => {
    if (!revisando()) return;
    arrastre = ev.target.id === 'asa-inicio' ? 'inicio' : ev.target.id === 'asa-fin' ? 'fin' : 'cabezal';
    linea.setPointerCapture(ev.pointerId);
    moverRecorte(arrastre, tiempo(ev));
    ev.preventDefault();
  });
  linea.addEventListener('pointermove', (ev) => { if (arrastre) moverRecorte(arrastre, tiempo(ev)); });
  const soltar = () => {
    if (!arrastre) return;
    const eraAsa = arrastre !== 'cabezal';
    arrastre = null;
    if (eraAsa) { avatar.reproducirTramo(true); pintarRevision(); }   // al soltar un extremo, se ve el recorte
  };
  linea.addEventListener('pointerup', soltar);
  linea.addEventListener('pointercancel', soltar);
  for (const [id, cual] of [['#asa-inicio', 'inicio'], ['#asa-fin', 'fin']]) {
    $(id).addEventListener('keydown', (ev) => {
      if (!revisando() || (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight')) return;
      ev.preventDefault();
      ev.stopPropagation();
      const paso = (ev.key === 'ArrowLeft' ? -1 : 1) * PASO_TECLA * (ev.shiftKey ? 10 : 1);
      moverRecorte(cual, ui.revision[cual] + paso);
    });
  }
  $('#rev-reproducir').addEventListener('click', alternarReproduccion);
  $('#rev-velocidad').addEventListener('click', () => {
    ui.velocidad = (ui.velocidad || 1) === 1 ? 0.5 : 1;
    avatar.velocidad(ui.velocidad);
    pintarRevision();
  });
  $('#rev-guardar').addEventListener('click', guardarToma);
  $('#rev-descartar').addEventListener('click', descartarToma);
  avatar.alTiempo = (t) => {
    if (!revisando()) return;
    ui.revision.t = t;
    $('#lt-cabezal').style.left = `${(100 * t) / ui.revision.total}%`;
  };
}

function alternarReproduccion() {
  if (!revisando()) return;
  avatar.reproducirTramo(!(avatar.rev && avatar.rev.reproduciendo));
  pintarRevision();
}

async function guardarToma() {
  const r = ui.revision;
  if (!revisando()) return;
  const recortada = r.inicio > 0.01 || r.fin < r.total - 0.01;
  const j = await accion('guardar_toma', recortada ? { inicio: r.inicio, fin: r.fin } : {});
  if (j.ok) cerrarRevision();
}

async function descartarToma() {
  if (!revisando()) return;
  const j = await accion('descartar_toma');
  if (j.ok) cerrarRevision();
}

// -------------------------------------------------------------------- avisos
function avisar(texto, tipo = '') {
  const d = document.createElement('div');
  d.className = `aviso ${tipo}`;
  d.textContent = texto;
  $('#avisos').appendChild(d);
  setTimeout(() => d.remove(), 4200);
  while ($('#avisos').children.length > 3) $('#avisos').firstChild.remove();
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// --------------------------------------------------------------- controles
function conectar() {
  $$('.nav[data-pagina]').forEach((b) => b.addEventListener('click', () => ir(b.dataset.pagina)));
  $$('[data-ir]').forEach((b) => b.addEventListener('click', () => ir(b.dataset.ir)));
  $$('[data-accion]').forEach((b) => b.addEventListener('click', () => accion(b.dataset.accion)));
  $$('[data-manos]').forEach((b) => b.addEventListener('click', () => accion('manos', { modo: b.dataset.manos })));
  conectarLineaDeTiempo();
  $('#btn-voz').addEventListener('click', () => accion('voz'));
  $('#btn-escuchar').addEventListener('click', () => accion('escuchar'));
  $('#btn-pantalla').addEventListener('click', pantallaCompleta);
  $('#btn-tutorial').addEventListener('click', () => escenas.abrirTutorial());
  $('#form-entrenar').addEventListener('submit', (ev) => {
    ev.preventDefault();
    accion('entrenar_palabra', { palabra: $('#entrenar-palabra').value, persona: $('#entrenar-persona').value });
    $('#entrenar-palabra').blur(); $('#entrenar-persona').blur();
  });
  $('#form-avatar').addEventListener('submit', (ev) => {
    ev.preventDefault();
    accion('avatar_palabra', { palabra: $('#avatar-palabra').value });
    $('#avatar-palabra').blur();
  });
  $('#form-interlocutor').addEventListener('submit', (ev) => {
    ev.preventDefault();
    const texto = $('#entrada-interlocutor').value.trim();
    if (!texto) return;
    accion('texto_interlocutor', { texto });
    $('#entrada-interlocutor').value = '';
  });
  document.addEventListener('click', async (ev) => {
    const b = ev.target.closest('button');
    if (!b) return;
    if (b.dataset.borrarSena && confirm(`¿Borrar todas las muestras de «${b.dataset.borrarSena}»?`)) {
      await accion('borrar_sena', { palabra: b.dataset.borrarSena }); cargarDataset();
    }
    if (b.dataset.borrarClip && confirm(`¿Borrar el movimiento de «${b.dataset.borrarClip}»?`)) {
      await accion('borrar_clip', { palabra: b.dataset.borrarClip }); ui.cacheClips.delete(b.dataset.borrarClip); cargarClips();
    }
    if (b.dataset.verClip) avatar.reproducir([{ palabra: b.dataset.verClip, clip: await clip(b.dataset.verClip) }]);
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.target.closest('input') || ev.ctrlKey || ev.altKey || ev.metaKey) return;
    const k = ev.key.toLowerCase();
    const grabando = ui.pagina === 'entrenar' || ui.pagina === 'avatar';
    if (revisando() && ui.pagina === 'avatar') {                  // revisando una toma
      if (k === 'enter') { ev.preventDefault(); guardarToma(); return; }
      if (k === 'escape') { ev.preventDefault(); descartarToma(); return; }
      if (k === ' ') {
        ev.preventDefault();
        document.activeElement?.blur();                       // que Espacio no "pulse" el botón enfocado
        alternarReproduccion();
        return;
      }
    }
    if (ui.pagina === 'aprender' && k === 'enter' && !$('#apr-siguiente').classList.contains('oculto')) {
      ev.preventDefault(); aprender.siguiente(); return;
    }
    if (k === ' ' && grabando) { ev.preventDefault(); accion('grabar'); }
    else if (k === 'm' && grabando) {
      const i = MODOS_MANOS.indexOf(ui.estado.manos);
      accion('manos', { modo: MODOS_MANOS[(i + 1) % MODOS_MANOS.length] });
    }
    else if (k === 'z') accion('deshacer');
    else if (k === 'v') accion('voz');
    else if (k === 's') accion('escuchar');
    else if (k === 'f') pantallaCompleta();
    else if (k === 'h') ir('ayuda');
  });
  avatar.alPalabra = (palabra) => {
    const pie = $(`#pie-${ui.pagina}`);
    if (pie) pie.innerHTML = palabra ? `Seña: <b>${esc(palabra)}</b>` : PIES[ui.pagina];
  };
}

function pantallaCompleta() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen().catch(() => {});
}

// ------------------------------------------------------------------- inicio
const avatar = new Avatar();
const escenas = crearEscenas($, $$);
const ctx = { ui, $, $$, esc, accion, obtener, avatar, clip, avisar, categorias, irConPalabra };
const aprender = crearAprender(ctx, escenas);
const diccionario = crearDiccionario(ctx);
window.inclusion = { ui, avatar, buscarSenas, norm, escenas, aprender, diccionario };   // para depurar y probar
conectar();
ir('inicio');
cargarClips();
escuchar();
avatar.montar($('#escenario-traducir'));
avatar.cargar().then(() => escenas.marcar('avatar')).catch((err) => {
  console.error(err);
  escenas.marcar('avatar');
  $$('.escenario').forEach((s) => { s.innerHTML = '<div class="cargando">No se pudo cargar el avatar.</div>'; });
});

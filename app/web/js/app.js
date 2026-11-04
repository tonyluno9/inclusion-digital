// INCLUSION · interfaz. Habla con app/servidor_web.py:
//   /eventos  (estado + movimiento 3D, ~30 por segundo)   /video  (cámara)   /api/...  (acciones y datos)
import { Avatar } from './avatar.js';
import { buscarSenas, norm } from './texto.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const TITULOS = { inicio: 'Inicio', traducir: 'Traducir', entrenar: 'Entrenar el traductor', avatar: 'Avatar', ayuda: 'Ayuda' };

const ui = {
  pagina: null,
  estado: {},
  seq: { palabra: null, texto: null, clip: null },
  clips: new Map(),            // palabra normalizada -> nombre del clip
  cacheClips: new Map(),       // nombre -> JSON
  avisoPrevio: '',
  entrenando: false,
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
    avisar('Se perdió la conexión con INCLUSION', 'error');
    return { ok: false };
  }
}

const obtener = (url) => fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))));

function escuchar() {
  const fuente = new EventSource('/eventos');
  fuente.onmessage = (e) => {
    const { estado, mundo } = JSON.parse(e.data);
    actualizar(estado);
    if (mundo && estado.modo === 'AVATAR' && ui.pagina === 'avatar') avatar.vivo(mundo);
  };
  fuente.onerror = () => { $('#chip-camara').className = 'chip mal'; };
}

// ----------------------------------------------------------------- navegación
function ir(pagina) {
  if (ui.pagina === pagina) return;
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
  if (pagina === 'avatar') { avatar.montar($('#escenario-avatar')); avatar.detener(); accion('avatar_palabra', { palabra: ui.estado.modo === 'AVATAR' ? ui.estado.palabra : '' }); cargarClips(); }
  if (pagina === 'entrenar') { cargarDataset(); if (ui.estado.modo === 'AVATAR') accion('modo_deteccion'); }
  if (pagina === 'inicio' || pagina === 'ayuda') { if (ui.estado.modo === 'AVATAR') accion('modo_deteccion'); }
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
  if (ui.entrenando && !e.entrenando) cargarDataset();
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
    if (ui.seq.clip !== null) { cargarClips(); avisar(`Movimiento guardado: «${e.palabra}»`, 'ok'); }
    ui.seq.clip = e.seq_clip;
  }

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
  $('#btn-voz').addEventListener('click', () => accion('voz'));
  $('#btn-escuchar').addEventListener('click', () => accion('escuchar'));
  $('#btn-pantalla').addEventListener('click', pantallaCompleta);
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
    if (k === ' ' && (ui.pagina === 'entrenar' || ui.pagina === 'avatar')) { ev.preventDefault(); accion('grabar'); }
    else if (k === 'z') accion('deshacer');
    else if (k === 'v') accion('voz');
    else if (k === 's') accion('escuchar');
    else if (k === 'f') pantallaCompleta();
    else if (k === 'h') ir('ayuda');
  });
  avatar.alPalabra = (palabra) => {
    const pie = ui.pagina === 'avatar' ? $('#pie-avatar') : $('#pie-traducir');
    pie.innerHTML = palabra ? `Seña: <b>${esc(palabra)}</b>`
      : (ui.pagina === 'avatar' ? 'El avatar te imita en vivo.' : 'El avatar repite cada seña reconocida y dice en señas lo que escribe el interlocutor.');
  };
}

function pantallaCompleta() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen().catch(() => {});
}

// ------------------------------------------------------------------- inicio
const avatar = new Avatar();
window.inclusion = { ui, avatar, buscarSenas, norm };      // para depurar y para las pruebas
conectar();
ir('inicio');
cargarClips();
escuchar();
avatar.montar($('#escenario-traducir'));
avatar.cargar().catch((err) => {
  console.error(err);
  $$('.escenario').forEach((s) => { s.innerHTML = '<div class="cargando">No se pudo cargar el avatar.</div>'; });
});

// Copiado de app/web/js/vista_aprender.js por sitio/herramientas/copiar_interfaz.py (solo cambian las rutas). No lo edites aquí.
// Pantalla Aprender (RF-35): el avatar enseña una seña, la persona la hace y el traductor la
// califica. Estrellas, racha e insignias vienen del servidor (modules/progreso.py).
import { candidatas, coincide, elegirPalabra } from './aprender.js';

const SIGUIENTE = 3500;          // ms tras un acierto para pasar a la siguiente seña
const plural = (n, una, varias) => `${n} ${n === 1 ? una : varias}`;
const icono = (n) => `<span class="icono" style="--i:url(../assets/iconos/${n}.png)"></span>`;

export function crearAprender(ctx, escenas) {
  const { $, esc } = ctx;
  let palabras = [];
  let progreso = null;
  let actual = null;
  let pedida = null;            // clave que llega desde el Diccionario
  let seqVisto = null;
  let resuelto = false;
  let fallos = 0;
  let lento = false;
  let temporizador = null;

  async function alEntrar(clave = null) {
    pedida = clave;
    try {
      const [d, p] = await Promise.all([ctx.obtener('/api/diccionario'), ctx.obtener('/api/progreso')]);
      palabras = d.palabras;
      aplicarProgreso(p);
    } catch { return; }
    nueva();
  }

  function alSalir() {
    clearTimeout(temporizador);
    actual = null;
  }

  function aplicarProgreso(p) {
    progreso = p;
    $('#apr-estrellas').textContent = p.estrellas;
    $('#apr-racha').textContent = plural(p.racha, 'día', 'días');
    $('#apr-racha-caja').classList.toggle('encendida', p.practico_hoy);
    $('#apr-aprendidas').textContent = p.aprendidas.length;
    const ganadas = p.insignias.filter((i) => i.ganada).length;
    $('#apr-logros').textContent = `${ganadas} / ${p.insignias.length}`;
    for (const id of p.nuevas || []) {
      const i = p.insignias.find((x) => x.id === id);
      escenas.celebrar({ insignia: true, img: `../assets/img/insignias/${id}.webp`, titulo: '¡Nueva insignia!', texto: `${i.nombre}. ${i.como}` });
    }
  }

  function nueva() {
    clearTimeout(temporizador);
    const lista = candidatas(palabras);
    if (!lista.length) { pintarVacio(); return; }
    const deseada = pedida && palabras.find((p) => p.clave === pedida && p.traductor);
    actual = deseada || elegirPalabra(lista, progreso ? progreso.palabras : {}, actual && actual.clave);
    pedida = null;
    resuelto = false;
    fallos = 0;
    seqVisto = ctx.ui.estado.seq_palabra;
    $('#apr-vacio').classList.add('oculto');
    $('#apr-reto').classList.remove('oculto');
    const nombre = $('#apr-palabra');
    nombre.textContent = actual.nombre;
    nombre.classList.remove('nueva'); void nombre.offsetWidth; nombre.classList.add('nueva');
    pintarMejor();
    estado('mira', actual.movimiento
      ? 'Mira al avatar y luego hazla tú: levanta las manos, haz la seña y bájalas.'
      : 'El avatar aún no sabe esta seña. Hazla de memoria: levanta las manos, haz la seña y bájalas.');
    $('#apr-siguiente').classList.add('oculto');
    $('#apr-ver').classList.toggle('oculto', !actual.movimiento);
    $('#apr-lento').classList.toggle('oculto', !actual.movimiento);
    demostrar();
  }

  function pintarMejor() {
    const datos = actual && progreso && progreso.palabras[actual.clave];
    const mejor = datos ? datos.mejor : 0;
    $('#apr-mejor').innerHTML = [1, 2, 3].map((k) => `<i class="${k <= mejor ? 'llena' : ''}"></i>`).join('');
  }

  async function demostrar() {
    if (!actual || !actual.movimiento) { ctx.avatar.detener(); return; }
    try {
      ctx.avatar.reproducir([{ palabra: actual.nombre, clip: await ctx.clip(actual.movimiento) }], { velocidad: lento ? 0.5 : 1 });
    } catch { ctx.avisar('No se pudo cargar el movimiento', 'error'); }
  }

  function estado(tipo, texto, extra = '') {
    const img = { bien: 'estados/bien_hecho', otra: 'estados/otra_vez' }[tipo];
    $('#apr-estado').className = `apr-estado ${tipo}`;
    $('#apr-estado').innerHTML = `${img ? `<img src="../assets/img/${img}.webp" alt="">` : icono('consejo')}
      <div><p>${texto}</p>${extra}</div>`;
  }

  // Cada seña nueva que reconoce el traductor (por SSE) se compara con la que se pide
  function alEstado(e) {
    if (!actual || resuelto || ctx.ui.pagina !== 'aprender') return;
    if (e.seq_palabra === seqVisto) return;
    seqVisto = e.seq_palabra;
    if (e.prediccion) evaluar(e.prediccion, e.confianza);
  }

  async function evaluar(prediccion, confianza) {
    const acierto = coincide(prediccion, actual);
    if (acierto) resuelto = true;
    const r = await ctx.accion('practica', { palabra: actual.clave, acierto, confianza });
    if (!r.ok) return;
    const { estrellas, nuevas, resumen } = r.resultado;
    if (acierto) {
      const fila = [1, 2, 3].map((k) => `<i class="${k <= estrellas ? 'llena' : ''}" style="animation-delay:${k * 0.15}s"></i>`).join('');
      estado('bien', `<b>¡Bien hecho!</b> El traductor reconoció «${esc(actual.nombre)}» con ${Math.round(confianza * 100)} % de confianza.`,
        `<div class="estrellas-ganadas">${fila}</div>`);
      $('#apr-siguiente').classList.remove('oculto');
      temporizador = setTimeout(() => { if (!escenas.encima()) nueva(); }, SIGUIENTE);
    } else {
      fallos += 1;
      estado('otra', `<b>Inténtalo otra vez.</b> Entendí «${esc(prediccion)}».`
        + (fallos >= 2 && actual.movimiento ? ' Mírala de nuevo, más despacio.' : ''));
      if (fallos >= 2 && actual.movimiento && !lento) { lento = true; pintarLento(); demostrar(); }
      $('#apr-siguiente').classList.toggle('oculto', fallos < 3);
    }
    aplicarProgreso({ ...resumen, nuevas });
    pintarMejor();
  }

  function pintarVacio() {
    actual = null;
    $('#apr-reto').classList.add('oculto');
    $('#apr-vacio').classList.remove('oculto');
    ctx.avatar.detener();
  }

  function pintarLento() {
    $('#apr-lento span:last-child').textContent = lento ? 'Velocidad ½×' : 'Velocidad 1×';
    $('#apr-lento').classList.toggle('activo-suave', lento);
  }

  function abrirLogros() {
    if (!progreso) return;
    $('#logros-rejilla').innerHTML = progreso.insignias.map((i) => `
      <div class="logro ${i.ganada ? 'ganada' : ''}">
        <img src="../assets/img/insignias/${i.id}.webp" alt="">
        <b>${esc(i.nombre)}</b>
        <small>${i.ganada ? `Ganada el ${i.ganada.split('-').reverse().join('/')}` : esc(i.como)}</small>
      </div>`).join('');
    $('#logros-resumen').textContent = `${plural(progreso.estrellas, 'estrella', 'estrellas')} · `
      + `${plural(progreso.aciertos, 'acierto', 'aciertos')} de ${plural(progreso.intentos, 'intento', 'intentos')} · `
      + `racha de ${plural(progreso.racha, 'día', 'días')}`;
    $('#logros').classList.remove('oculto');
    $('#logros-cerrar').focus();
  }

  $('#apr-ver').addEventListener('click', demostrar);
  $('#apr-lento').addEventListener('click', () => { lento = !lento; pintarLento(); demostrar(); });
  $('#apr-saltar').addEventListener('click', nueva);
  $('#apr-siguiente').addEventListener('click', nueva);
  $('#apr-abrir-logros').addEventListener('click', abrirLogros);
  $('#logros-cerrar').addEventListener('click', () => $('#logros').classList.add('oculto'));
  $('#logros').addEventListener('click', (ev) => { if (ev.target.id === 'logros') $('#logros').classList.add('oculto'); });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && !$('#logros').classList.contains('oculto')) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
      $('#logros').classList.add('oculto');
    }
  }, true);
  pintarLento();

  return { alEntrar, alSalir, alEstado, aplicarProgreso, siguiente: nueva, repetir: demostrar };
}

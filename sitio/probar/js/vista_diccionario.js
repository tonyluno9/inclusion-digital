// Copiado de app/web/js/vista_diccionario.js por sitio/herramientas/copiar_interfaz.py (solo cambian las rutas). No lo edites aquí.
// Pantalla Diccionario (RF-34): todas las señas por categoría, con buscador; el avatar hace
// la que se toque. La lógica de agrupar está en diccionario.js (probada con Node).
import { agrupar } from './diccionario.js';

const MANOS = { dos: ['dos_manos', 'Se hace con las dos manos', ''], derecha: ['una_mano', 'Se hace con la mano derecha', ''],
  izquierda: ['una_mano', 'Se hace con la mano izquierda', 'espejo'] };
const icono = (n, extra = '') => `<span class="icono ${extra}" style="--i:url(../assets/iconos/${n}.png)"></span>`;

export function crearDiccionario(ctx) {
  const { $, esc } = ctx;
  let palabras = [];
  let categorias = [];
  const filtro = { texto: '', categoria: '' };
  let elegida = null;
  let lento = false;

  async function alEntrar() {
    try {
      const [d, c] = await Promise.all([ctx.obtener('/api/diccionario'), ctx.categorias()]);
      palabras = d.palabras;
      categorias = c;
    } catch { return; }
    pintarFiltros();
    pintar();
    const actual = elegida && palabras.find((p) => p.clave === elegida);
    if (actual) mostrar(actual, false); else pintarVacio();
  }

  function pintarFiltros() {
    const todas = [{ id: '', nombre: 'Todas' }, ...categorias, { id: 'otras', nombre: 'Otras' }];
    $('#dic-filtros').innerHTML = todas.map((c) => `
      <button type="button" class="filtro ${filtro.categoria === c.id ? 'activo' : ''}" data-filtro="${c.id}">${esc(c.nombre)}</button>`).join('');
  }

  function tarjeta(p) {
    const manos = MANOS[p.manos];
    return `<button type="button" class="palabra-tarjeta ${p.clave === elegida ? 'activa' : ''}" data-clave="${esc(p.clave)}">
      <b>${esc(p.nombre)}</b>
      <span class="marcas">
        <span class="marca ${p.traductor ? 'si' : ''}" title="${p.traductor ? 'El traductor la reconoce' : 'El traductor aún no la reconoce'}">${icono('subtitulos')}</span>
        <span class="marca ${p.movimiento ? 'si' : ''}" title="${p.movimiento ? 'El avatar sabe hacerla' : 'El avatar aún no la sabe'}">${icono('avatar')}</span>
        ${manos ? `<span class="marca si" title="${manos[1]}">${icono(manos[0], manos[2])}</span>` : ''}
      </span>
      <small>${p.muestras} muestra${p.muestras === 1 ? '' : 's'}</small>
    </button>`;
  }

  function pintar() {
    const grupos = agrupar(palabras, categorias, filtro);
    $('#dic-secciones').innerHTML = grupos.length ? grupos.map((g) => `
      <section class="tarjeta dic-seccion">
        <header>
          ${g.categoria.id === 'otras' ? `<span class="dic-otras">${icono('consejo', 'grande')}</span>`
            : `<img src="../assets/img/categorias/${g.categoria.id}.webp" alt="">`}
          <div><h3>${esc(g.categoria.nombre)}</h3>
            <span>${g.palabras.length ? `${g.palabras.length} seña${g.palabras.length === 1 ? '' : 's'}` : 'Ninguna grabada todavía'}</span></div>
        </header>
        ${g.palabras.length ? `<div class="dic-palabras">${g.palabras.map(tarjeta).join('')}</div>` : ''}
        ${g.porAprender.length ? `<div class="dic-faltan"><span>Por grabar:</span>${g.porAprender.slice(0, 12).map((p) => `
          <button type="button" class="chip-faltan" data-grabar="${esc(p)}" title="Grabar «${esc(p)}» en Entrenar">${esc(p)}</button>`).join('')}</div>` : ''}
      </section>`).join('')
      : `<div class="tarjeta vacio-grande">
          <img src="../assets/img/entrenando.webp" alt="">
          <h3>${filtro.texto ? `No encontré «${esc(filtro.texto)}»` : 'Todavía no hay señas'}</h3>
          <p>Graba una seña en <b>Entrenar</b> y aparecerá aquí.</p>
          ${filtro.texto ? `<button type="button" class="boton primario" data-grabar="${esc(filtro.texto)}">${icono('senas')}Grabar «${esc(filtro.texto)}»</button>` : ''}
        </div>`;
  }

  function pintarVacio() {
    $('#dic-detalle').innerHTML = `<p class="dic-ayuda">${icono('consejo')} Toca una seña para que el avatar te la enseñe.</p>`;
  }

  async function mostrar(p, reproducir = true) {
    elegida = p.clave;
    document.querySelectorAll('.palabra-tarjeta').forEach((t) => t.classList.toggle('activa', t.dataset.clave === p.clave));
    const manos = MANOS[p.manos];
    $('#dic-detalle').innerHTML = `
      <h2>${esc(p.nombre)}</h2>
      <ul class="dic-estado">
        <li class="${p.traductor ? 'si' : ''}">${icono(p.traductor ? 'correcto' : 'incorrecto')}
          ${p.traductor ? 'El traductor la reconoce' : 'El traductor aún no la reconoce'} · ${p.muestras} muestra${p.muestras === 1 ? '' : 's'}</li>
        <li class="${p.movimiento ? 'si' : ''}">${icono(p.movimiento ? 'correcto' : 'incorrecto')}
          ${p.movimiento ? 'El avatar sabe hacerla' : 'El avatar todavía no sabe hacerla'}</li>
        ${manos ? `<li class="si">${icono(manos[0], manos[2])}${manos[1]}</li>` : ''}
      </ul>
      <div class="botones">
        ${p.movimiento ? `<button type="button" class="boton" data-dic="ver">${icono('repetir')}Ver otra vez</button>
          <button type="button" class="boton ${lento ? 'activo-suave' : ''}" data-dic="lento">${icono('lento')}${lento ? 'Velocidad ½×' : 'Velocidad 1×'}</button>` : ''}
        ${p.traductor ? `<button type="button" class="boton primario" data-dic="practicar">${icono('aprender')}Practicar</button>` : ''}
        <button type="button" class="boton" data-dic="muestras">${icono('senas')}Grabar muestras</button>
        <button type="button" class="boton" data-dic="movimiento">${icono('avatar')}${p.movimiento ? 'Regrabar movimiento' : 'Grabar movimiento'}</button>
      </div>`;
    if (reproducir) ver(p);
  }

  async function ver(p) {
    if (!p.movimiento) { ctx.avatar.detener(); return; }
    try {
      ctx.avatar.reproducir([{ palabra: p.nombre, clip: await ctx.clip(p.movimiento) }], { velocidad: lento ? 0.5 : 1 });
    } catch { ctx.avisar('No se pudo cargar el movimiento', 'error'); }
  }

  const actual = () => palabras.find((p) => p.clave === elegida);
  $('#dic-buscar').addEventListener('input', (ev) => { filtro.texto = ev.target.value; pintar(); });
  $('#pagina-diccionario').addEventListener('click', (ev) => {
    const b = ev.target.closest('button');
    if (!b) return;
    if (b.dataset.filtro !== undefined) { filtro.categoria = b.dataset.filtro; pintarFiltros(); pintar(); }
    if (b.dataset.clave) mostrar(palabras.find((p) => p.clave === b.dataset.clave));
    if (b.dataset.grabar) ctx.irConPalabra('entrenar', b.dataset.grabar);
    const p = actual();
    if (!p || !b.dataset.dic) return;
    if (b.dataset.dic === 'ver') ver(p);
    if (b.dataset.dic === 'lento') { lento = !lento; mostrar(p); }
    if (b.dataset.dic === 'practicar') ctx.irConPalabra('aprender', p.clave);
    if (b.dataset.dic === 'muestras') ctx.irConPalabra('entrenar', p.palabra);
    if (b.dataset.dic === 'movimiento') ctx.irConPalabra('avatar', p.palabra);
  });

  return { alEntrar };
}

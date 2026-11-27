// «Pruébalo» en el celular: barra de abajo con «Más», sin atajos de teclado en pantallas
// táctiles, la pantalla no se apaga con la cámara encendida, instalar como app y funcionar
// sin internet (sw.js). La app de escritorio no usa nada de esto.

const PRINCIPALES = ['inicio', 'traducir', 'aprender', 'diccionario'];
const tactil = () => matchMedia('(hover: none) and (pointer: coarse)').matches;
const angosta = () => matchMedia('(max-width: 760px)').matches;
// En la computadora del desarrollador el service worker estorba (guarda versiones viejas):
// en 127.0.0.1 o localhost solo se registra con ?sw=1.
const local = ['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname);

export function crearMovil({ $, $$, motor, avisar }) {
  // ------------------------------------------------ barra de abajo con «Más»
  const lateral = $('.lateral');
  const secundarios = $$('.lateral .nav').filter((b) => !PRINCIPALES.includes(b.dataset.pagina));
  secundarios.forEach((b) => b.classList.add('nav-secundario'));
  const mas = document.createElement('button');
  mas.type = 'button';
  mas.className = 'nav nav-mas';
  mas.setAttribute('aria-haspopup', 'true');
  mas.setAttribute('aria-expanded', 'false');
  mas.innerHTML = '<span class="icono" style="--i:url(../assets/iconos/ajustes.png)"></span>Más';
  $('.lateral nav').appendChild(mas);

  const hoja = document.createElement('div');
  hoja.className = 'hoja-mas oculto';
  hoja.id = 'hoja-mas';
  hoja.setAttribute('role', 'menu');
  hoja.setAttribute('aria-label', 'Más opciones');
  document.body.appendChild(hoja);
  const fondo = document.createElement('div');
  fondo.className = 'hoja-fondo oculto';
  document.body.appendChild(fondo);

  // La hoja copia el ícono y el texto de cada botón al abrirse (así «Voz / Sin voz» sale al día)
  // y al tocar una opción pulsa el botón original, que ya tiene su acción.
  function pintarHoja() {
    const opciones = secundarios.filter((b) => !(b.id === 'btn-pantalla' && !document.fullscreenEnabled));
    hoja.innerHTML = opciones.map((b, i) => `<button type="button" role="menuitem" class="opcion-mas ${b.classList.contains('activa') ? 'activa' : ''} ${b.classList.contains('apagado') ? 'apagado' : ''}" data-opcion="${i}">${b.innerHTML}</button>`).join('')
      + (instalar.disponible() ? `<button type="button" role="menuitem" class="opcion-mas destacada" data-instalar><span class="icono" style="--i:url(../assets/iconos/exportar.png)"></span>Instalar app</button>` : '');
    hoja._opciones = opciones;
  }
  function abrir(si) {
    if (si) pintarHoja();
    hoja.classList.toggle('oculto', !si);
    fondo.classList.toggle('oculto', !si);
    mas.setAttribute('aria-expanded', String(si));
    if (si) hoja.querySelector('button')?.focus();
  }
  mas.addEventListener('click', () => abrir(hoja.classList.contains('oculto')));
  fondo.addEventListener('click', () => abrir(false));
  hoja.addEventListener('click', (ev) => {
    const b = ev.target.closest('button');
    if (!b) return;
    abrir(false);
    if (b.dataset.instalar !== undefined) { instalar.pedir(); return; }
    const original = hoja._opciones[Number(b.dataset.opcion)];
    if (original) original.click();
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && !hoja.classList.contains('oculto')) { ev.stopImmediatePropagation(); abrir(false); mas.focus(); }
  }, true);
  // «Más» se marca cuando la pantalla abierta es una de las que viven ahí (Entrenar, Avatar, Ayuda)
  const marcarMas = () => mas.classList.toggle('activa', secundarios.some((b) => b.classList.contains('activa')));
  new MutationObserver(marcarMas).observe(lateral, { subtree: true, attributes: true, attributeFilter: ['class'] });
  marcarMas();

  // ------------------------------------- sin atajos de teclado en pantallas táctiles
  // Los textos de los botones dicen «Grabar (Espacio)», «Guardar (Enter)»…: en un celular no hay
  // teclado, así que se quita lo que está entre paréntesis cuando es una tecla.
  const ATAJO = /\s*\((?:Espacio|Enter|Esc|[A-Z])\)/g;
  function limpiar(nodo) {
    const caminante = document.createTreeWalker(nodo, NodeFilter.SHOW_TEXT);
    for (let t = caminante.currentNode; t; t = caminante.nextNode()) {
      if (t.nodeType === 3 && ATAJO.test(t.nodeValue)) { ATAJO.lastIndex = 0; t.nodeValue = t.nodeValue.replace(ATAJO, ''); }
      ATAJO.lastIndex = 0;
    }
  }
  if (tactil()) {
    document.documentElement.classList.add('tactil');
    limpiar(document.body);
    new MutationObserver((cambios) => {
      for (const c of cambios) {
        const nodo = c.type === 'characterData' ? c.target.parentNode : c.target;
        if (nodo && nodo.closest && nodo.closest('button, .ayuda-corta, .grabacion, label')) limpiar(nodo);
      }
    }).observe(document.body, { subtree: true, childList: true, characterData: true });
  }

  // ------------------------------- que la pantalla no se apague con la cámara encendida
  // Mientras alguien hace señas no toca el celular: sin esto, la pantalla se apaga a los 30 s.
  let candado = null;
  let camaraEncendida = false;
  async function pedirCandado() {
    if (!('wakeLock' in navigator) || candado || document.visibilityState !== 'visible') return;
    try {
      candado = await navigator.wakeLock.request('screen');
      candado.addEventListener('release', () => { candado = null; });
    } catch { candado = null; /* sin batería o sin permiso: no pasa nada */ }
  }
  function soltarCandado() { if (candado) { candado.release().catch(() => {}); candado = null; } }
  motor.escuchar(({ estado }) => {
    if (estado.camara === camaraEncendida) return;
    camaraEncendida = estado.camara;
    document.documentElement.classList.toggle('camara-encendida', camaraEncendida);
    if (camaraEncendida) pedirCandado(); else soltarCandado();
  });
  document.addEventListener('visibilitychange', () => { if (camaraEncendida && document.visibilityState === 'visible') pedirCandado(); });

  // ------------------------------------------------------- instalar como app
  let aviso = null;                    // el evento beforeinstallprompt (Chrome, Edge, Android)
  const instalada = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const instalar = {
    disponible: () => !instalada() && (Boolean(aviso) || ios),
    async pedir() {
      if (aviso) {
        aviso.prompt();
        const { outcome } = await aviso.userChoice;
        aviso = null;
        if (outcome === 'accepted') avisar('Listo: K\'ab T\'aan quedó en tu pantalla de inicio.', 'ok');
        pintarInstalar();
      } else if (ios) {
        avisar('En el iPhone: toca Compartir (el cuadro con la flecha) y luego «Agregar a pantalla de inicio».');
      }
    },
  };
  function pintarInstalar() {
    const caja = $('#tarjeta-instalar');
    if (!caja) return;
    caja.classList.toggle('oculto', instalada());
    $('#instalar-boton').classList.toggle('oculto', !aviso);
    $('#instalar-ios').classList.toggle('oculto', !(ios && !aviso));
    $('#instalar-otros').classList.toggle('oculto', Boolean(aviso) || ios);
  }
  window.addEventListener('beforeinstallprompt', (ev) => { ev.preventDefault(); aviso = ev; pintarInstalar(); });
  window.addEventListener('appinstalled', () => { aviso = null; pintarInstalar(); });
  $('#instalar-boton')?.addEventListener('click', () => instalar.pedir());
  pintarInstalar();

  // ------------------------------------------------------ funcionar sin internet
  const quiereSw = !local || new URLSearchParams(location.search).get('sw') === '1';
  if ('serviceWorker' in navigator && quiereSw) {
    navigator.serviceWorker.register('./sw.js').catch((e) => console.warn('[Sin internet] No se pudo registrar sw.js:', e));
  }

  return { abrirMas: abrir, angosta, tactil, instalar };
}

// Lo que solo existe en «Pruébalo» (no en la app de escritorio): encender la cámara con permiso,
// qué hacer si se niega, el aviso antes de dictar, tus datos (guardar, abrir, borrar), el aviso
// de prueba de concepto y los navegadores que no pueden con la página.
const PAGINAS_CON_CAMARA = ['traducir', 'aprender', 'entrenar', 'avatar'];
const CLAVE_DICTADO = 'kabtaan.dictadoAceptado';
const leer = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const escribir = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };

const MOTIVOS = {
  negada: ['No tengo permiso para usar tu cámara',
    'Para dárselo, toca el ícono de la cámara o del candado en la barra de direcciones, elige «Permitir» y vuelve a intentarlo. '
    + 'Sin cámara puedes usar el Diccionario, escribir para que el avatar lo diga en señas y ver los movimientos.'],
  'no-hay': ['No encontré ninguna cámara', 'Conecta una cámara web y vuelve a intentarlo. Mientras, puedes usar el Diccionario y el avatar.'],
  ocupada: ['La cámara está ocupada', 'Otra aplicación (o la app de K\'ab T\'aan, o una videollamada) la está usando. Ciérrala y vuelve a intentarlo.'],
  'sin-api': ['Este navegador no da acceso a la cámara', 'Prueba con Chrome, Edge o Firefox actualizados. La página tiene que abrirse con https://.'],
  otro: ['No se pudo encender la cámara', 'Vuelve a intentarlo. Si sigue sin funcionar, recarga la página.'],
};

export function crearPruebalo(ctx) {
  const { $, $$, esc, camara, motor, avisar, escenas } = ctx;
  let encendiendo = false;
  let error = null;           // [título, texto] del último intento fallido
  let progreso = '';
  const sinCamara = ctx.revisarNavegador().filter((f) => f === 'camara' || f === 'https');

  // ------------------------------------------------------------ cámara
  function pintarCajas() {
    const icono = (n) => `<span class="icono" style="--i:url(../assets/iconos/${n}.png)"></span>`;
    let html;
    if (encendiendo) {
      html = `<img src="../assets/img/entrenando.webp" alt=""><p class="encender-titulo">${esc(progreso || 'Encendiendo…')}</p>
        <div class="carga-barra mini"><i></i></div>
        <p class="encender-nota">La primera vez se descargan unos 30 MB (MediaPipe y los modelos). Después quedan guardados.</p>`;
    } else if (sinCamara.length) {
      html = `<img src="../assets/img/sin_camara.webp" alt=""><p class="encender-titulo">${esc(MOTIVOS['sin-api'][0])}</p>
        <p class="encender-nota">${esc(MOTIVOS['sin-api'][1])}</p>`;
    } else {
      html = `<img src="../assets/img/sin_camara.webp" alt="">
        ${error ? `<p class="encender-titulo">${esc(error[0])}</p><p class="encender-nota">${esc(error[1])}</p>`
          : '<p class="encender-titulo">La cámara está apagada</p>'}
        <button type="button" class="boton primario" data-encender-camara>${icono('camara')}${error ? 'Intentar otra vez' : 'Encender la cámara'}</button>
        <p class="encender-nota">Tu video se procesa en este navegador y <b>no sale de tu computadora</b>.</p>`;
    }
    $$('[data-encender]').forEach((c) => { c.innerHTML = html; });
  }

  async function encender() {
    if (encendiendo || camara.activa) return;
    encendiendo = true;
    error = null;
    progreso = '';
    pintarCajas();
    try {
      await camara.encender((texto) => { progreso = texto; pintarCajas(); });
      ponerBotonApagar();
    } catch (e) {
      console.warn('[Cámara]', e);
      error = MOTIVOS[e.motivo] || [MOTIVOS.otro[0], e.motivo ? MOTIVOS.otro[1] : `No se pudo cargar MediaPipe (${e.message}). Revisa tu conexión y recarga la página.`];
    } finally {
      encendiendo = false;
      pintarCajas();
      motor.publicar();
    }
  }

  function apagar() {
    camara.apagar();
    quitarBotonApagar();
    pintarCajas();
    motor.publicar();
  }

  function ponerBotonApagar() {
    $$('[data-camara]').forEach((c) => {
      if (c.querySelector('.btn-apagar-camara')) return;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn-apagar-camara';
      b.title = 'Apagar la cámara';
      b.setAttribute('aria-label', 'Apagar la cámara');
      b.innerHTML = '<span class="icono" style="--i:url(../assets/iconos/detener.png)"></span><span>Apagar</span>';
      c.appendChild(b);
    });
  }

  function quitarBotonApagar() { $$('.btn-apagar-camara').forEach((b) => b.remove()); }

  document.addEventListener('click', (ev) => {
    if (ev.target.closest('[data-encender-camara]')) encender();
    if (ev.target.closest('.btn-apagar-camara')) apagar();
  });

  // --------------------------------------------------------- dictado
  // Antes del primer dictado se explica qué servicio procesa el audio (captura: va antes que app.js)
  function quiereDictar(ev) {
    if (leer(CLAVE_DICTADO) || (motor.app.stt && motor.app.stt.isRecording)) return;
    if (!motor.app.stt.disponible) return;          // el motor ya avisa que no hay dictado
    ev.preventDefault();
    ev.stopImmediatePropagation();
    $('#aviso-dictado').classList.remove('oculto');
    $('#ad-si').focus();
  }
  $('#btn-escuchar').addEventListener('click', quiereDictar, true);
  document.addEventListener('keydown', (ev) => {
    if (ev.key.toLowerCase() === 's' && !ev.target.closest('input') && !ev.ctrlKey && !ev.altKey && !ev.metaKey) quiereDictar(ev);
    if (ev.key === 'Escape' && !$('#aviso-dictado').classList.contains('oculto')) $('#aviso-dictado').classList.add('oculto');
  }, true);
  $('#ad-si').addEventListener('click', () => {
    escribir(CLAVE_DICTADO, '1');
    $('#aviso-dictado').classList.add('oculto');
    ctx.accion('escuchar');
  });
  $('#ad-no').addEventListener('click', () => {
    $('#aviso-dictado').classList.add('oculto');
    $('#entrada-interlocutor').focus();
  });

  // ------------------------------------------------------------ datos
  function pintarDatos() {
    const app = motor.app;
    const [senas] = app.collector.stats();
    const n = app.collector.count();
    const propios = app.clips.propios.size;
    const prog = app.progreso.datos;
    $('#datos-resumen').innerHTML = `${n} muestra${n === 1 ? '' : 's'} de ${Object.keys(senas).length} seña${Object.keys(senas).length === 1 ? '' : 's'} · `
      + `${propios} movimiento${propios === 1 ? '' : 's'} del avatar · traductor ${app.logic.origen === 'propio' ? '<b>tuyo</b>' : app.logic.origen === 'fabrica' ? 'de demostración' : 'sin entrenar'} · `
      + `${prog.estrellas} estrella${prog.estrellas === 1 ? '' : 's'}${motor.almacen.persistente ? '' : ' · <span class="naranja">no se guardan al cerrar</span>'}`;
  }

  $('#datos-exportar').addEventListener('click', () => {
    const datos = motor.almacen.exportar();
    const blob = new Blob([JSON.stringify(datos)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `kabtaan-mis-datos-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  });
  $('#datos-importar').addEventListener('change', async (ev) => {
    const archivo = ev.target.files && ev.target.files[0];
    ev.target.value = '';
    if (!archivo) return;
    if (!confirm('Abrir este archivo reemplaza los datos que tienes ahora en este navegador. ¿Seguir?')) return;
    try {
      await motor.almacen.importar(JSON.parse(await archivo.text()));
      location.reload();
    } catch (e) { avisar(`No se pudo abrir: ${e.message}`, 'error'); }
  });
  $('#datos-borrar').addEventListener('click', async () => {
    if (!confirm('¿Borrar todas tus muestras, movimientos, tu traductor y tu progreso de este navegador? No se puede deshacer.')) return;
    await motor.almacen.borrarTodo();
    try { localStorage.clear(); } catch { /* nada */ }
    location.reload();
  });

  // -------------------------------------- traductor propio o de demostración
  $('#btn-volver-demo').addEventListener('click', async () => {
    if (!confirm('¿Borrar tu traductor y volver al de demostración? Tus muestras no se borran: puedes volver a entrenarlo.')) return;
    await motor.almacen.escribir('modelo', null);
    motor.app.reloadModel();
    motor.publicar();
  });

  // ------------------------------------------------- modo rápido (pose «lite»)
  // Meta: 15 cuadros por segundo o más. Si con el modelo «full» va más lento varios segundos
  // seguidos, se ofrece el «lite» (el traductor solo usa hombros, codos y muñecas del cuerpo).
  const META_FPS = 15;
  const muestrasFps = [];
  let rapidoOfrecido = leer('kabtaan.rapidoOfrecido') === '1';
  function pintarModo() {
    $('#btn-modo-pose').textContent = camara.poseModelo === 'lite' ? 'Volver al modo normal' : 'Usar el modo rápido';
  }
  async function cambiarModo(modelo) {
    $('#aviso-rapido').classList.add('oculto');
    await camara.cambiarPose(modelo);
    muestrasFps.length = 0;
    pintarModo();
    avisar(modelo === 'lite' ? 'Modo rápido: el cuerpo se calcula con el modelo «lite».' : 'Modo normal: el cuerpo se calcula con el modelo «full», como en la app.');
  }
  function revisarRendimiento(estado) {
    if (!estado.camara || camara.poseModelo !== 'full' || rapidoOfrecido) { muestrasFps.length = 0; return; }
    muestrasFps.push(estado.fps);
    if (muestrasFps.length < 8) return;                   // ~8 s con la cámara encendida
    const recientes = muestrasFps.slice(-5).sort((a, b) => a - b);
    if (recientes[2] >= META_FPS) return;
    rapidoOfrecido = true;
    escribir('kabtaan.rapidoOfrecido', '1');
    $('#ar-texto').textContent = `Tu computadora va a ${Math.round(recientes[2])} cuadros por segundo y las señas se leen mejor con 15 o más. `
      + 'El modo rápido usa un modelo del cuerpo más ligero.';
    $('#aviso-rapido').classList.remove('oculto');
  }
  $('#ar-si').addEventListener('click', () => cambiarModo('lite'));
  $('#ar-no').addEventListener('click', () => $('#aviso-rapido').classList.add('oculto'));
  $('#btn-modo-pose').addEventListener('click', () => cambiarModo(camara.poseModelo === 'lite' ? 'full' : 'lite'));
  pintarModo();

  // ------------------------------------------------------- estado
  let ultimoRend = 0;
  motor.escuchar(({ estado }) => {
    $('#volver-demo').classList.toggle('oculto', !(estado.modelo_origen === 'propio' && motor.app.logic.fabrica));
    const ahora = performance.now();
    if (ahora - ultimoRend < 1000) return;
    ultimoRend = ahora;
    revisarRendimiento(estado);
    $('#info-rendimiento').textContent = estado.camara
      ? `${estado.fps} cuadros por segundo (${camara.delegado === 'GPU' ? 'con la tarjeta gráfica' : camara.delegado === 'CPU' ? 'con el procesador' : camara.delegado}, cuerpo «${camara.poseModelo}»)`
      : 'cámara apagada';
    const m = motor.app.logic;
    $('#poc-modelo').textContent = m.origen === 'propio'
      ? `Estás usando tu propio traductor: conoce ${m.classes.length} seña${m.classes.length === 1 ? '' : 's'}.`
      : m.origen === 'fabrica'
        ? `El traductor de demostración conoce ${m.classes.length} señas (${m.classes.map((c) => ({ adios: 'adiós' }[c] || c)).join(', ')}), grabadas por una sola persona: contigo puede equivocarse.`
        : 'Esta página no trae un traductor de demostración: grábale tus señas en Entrenar.';
    if (ctx.ui.pagina === 'ayuda') pintarDatos();
  });

  // --------------------------------------------------------- navegador
  const faltan = ctx.revisarNavegador();
  if (faltan.includes('webgl')) {
    const aviso = $('#aviso-navegador');
    aviso.innerHTML = '<b>Tu navegador no tiene WebGL</b>: el avatar 3D no se puede mostrar. El traductor puede funcionar igual. '
      + 'Prueba con Chrome o Edge actualizados, o activa la aceleración por hardware.';
    aviso.classList.remove('oculto');
  }

  pintarCajas();
  return {
    encender,
    apagar,
    alCambiarPagina(pagina) {
      if (pagina === 'ayuda') pintarDatos();
      void PAGINAS_CON_CAMARA;
    },
  };
}

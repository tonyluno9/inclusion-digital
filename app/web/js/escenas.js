// Pantalla de carga y tutorial (RF-33), escenarios del avatar, celebraciones y aviso de
// «sin conexión» (RF-36). Todo lo que se superpone a las pantallas de la app.

const CLAVE_TUTORIAL = 'kabtaan.tutorialVisto';
const CLAVE_ESCENARIO = 'kabtaan.escenario';
const CARGA_MIN = 1200;          // ms: la portada se ve al menos esto
const CARGA_MAX = 8000;          // ms: aunque algo no responda, la app se muestra
const SIN_CONEXION = 3000;       // ms sin eventos del servidor para avisar

export const ESCENARIOS = [
  { id: 'estudio', nombre: 'Estudio', img: '/assets/img/fondo_avatar.jpg' },
  { id: 'jade', nombre: 'Jade', img: '/assets/img/escenarios/maya.jpg' },
  { id: 'aula', nombre: 'Aula', img: '/assets/img/escenarios/aula.jpg' },
  { id: 'plaza', nombre: 'Plaza', img: '/assets/img/escenarios/plaza.jpg' },
];

const PASOS = [
  ['Colócate frente a la cámara', 'A un metro, con la cabeza, los hombros y los codos a la vista. Luz de frente y nada brillante detrás de ti.'],
  ['Haz la seña', 'Levanta las manos, haz la seña y bájalas. Al bajar las manos, la seña termina.'],
  ["K'ab T'aan la traduce", 'La seña aparece como subtítulo y se escucha en voz alta. Varias señas seguidas forman una oración.'],
  ['El avatar te responde', 'Lo que la otra persona escribe o dicta, el avatar lo dice en señas. Practica en Aprender y consulta el Diccionario.'],
];

// localStorage puede no existir o fallar (ventana privada, datos bloqueados): la app sigue igual
const leer = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const escribir = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };

export function crearEscenas($, $$) {
  // ------------------------------------------------------------ carga
  const inicio = performance.now();
  const listo = { estado: false, avatar: false };
  let cargaFuera = false;

  function ocultarCarga() {
    if (cargaFuera) return;
    cargaFuera = true;
    const espera = Math.max(0, CARGA_MIN - (performance.now() - inicio));
    setTimeout(() => {
      $('#carga').classList.add('saliendo');
      setTimeout(() => {
        $('#carga').classList.add('oculto');
        if (!leer(CLAVE_TUTORIAL)) abrirTutorial();
      }, 450);
    }, espera);
  }
  setTimeout(ocultarCarga, CARGA_MAX);

  function marcar(cosa) {
    listo[cosa] = true;
    if (listo.estado && listo.avatar) ocultarCarga();
  }

  // ---------------------------------------------------------- tutorial
  let paso = 0;
  function pintarPaso() {
    const [titulo, texto] = PASOS[paso];
    $('#tut-img').src = `assets/img/tutorial/paso_${paso + 1}.png`;
    $('#tut-numero').textContent = `Paso ${paso + 1} de ${PASOS.length}`;
    $('#tut-titulo').textContent = titulo;
    $('#tut-texto').textContent = texto;
    $('#tut-puntos').innerHTML = PASOS.map((_, i) => `<i class="${i === paso ? 'activo' : ''}"></i>`).join('');
    $('#tut-anterior').disabled = paso === 0;
    $('#tut-siguiente span').textContent = paso === PASOS.length - 1 ? '¡Empezar!' : 'Siguiente';
  }
  function abrirTutorial() {
    paso = 0;
    pintarPaso();
    $('#tutorial').classList.remove('oculto');
    $('#tut-siguiente').focus();
  }
  function cerrarTutorial() {
    $('#tutorial').classList.add('oculto');
    escribir(CLAVE_TUTORIAL, '1');
  }
  function mover(d) {
    if (paso + d >= PASOS.length) { cerrarTutorial(); return; }
    paso = Math.max(0, paso + d);
    pintarPaso();
  }
  $('#tut-siguiente').addEventListener('click', () => mover(1));
  $('#tut-anterior').addEventListener('click', () => mover(-1));
  $('#tut-saltar').addEventListener('click', cerrarTutorial);

  // --------------------------------------------------------- escenarios
  function aplicarEscenario(id) {
    const e = ESCENARIOS.find((x) => x.id === id) || ESCENARIOS[0];
    document.documentElement.style.setProperty('--fondo-escenario', `url("${e.img}")`);
    $$('.menu-escenario button').forEach((b) => b.classList.toggle('activo', b.dataset.escenario === e.id));
    escribir(CLAVE_ESCENARIO, e.id);
  }
  // Un botón con su menú sobre cada escenario del avatar
  $$('.escenario-tarjeta').forEach((tarjeta) => {
    const caja = document.createElement('div');
    caja.className = 'selector-escenario';
    caja.innerHTML = `<button type="button" class="btn-escenario" title="Cambiar el escenario del avatar" aria-label="Cambiar el escenario">
        <span class="icono" style="--i:url(../assets/iconos/escenario.png)"></span></button>
      <div class="menu-escenario oculto" role="menu">${ESCENARIOS.map((e) => `
        <button type="button" role="menuitem" data-escenario="${e.id}"><img src="${e.img}" alt=""><span>${e.nombre}</span></button>`).join('')}
      </div>`;
    tarjeta.appendChild(caja);
  });
  document.addEventListener('click', (ev) => {
    const abrir = ev.target.closest('.btn-escenario');
    const opcion = ev.target.closest('[data-escenario]');
    $$('.menu-escenario').forEach((m) => {
      if (!abrir || m.parentElement !== abrir.parentElement) m.classList.add('oculto');
    });
    if (abrir) abrir.nextElementSibling.classList.toggle('oculto');
    if (opcion) aplicarEscenario(opcion.dataset.escenario);
  });
  aplicarEscenario(leer(CLAVE_ESCENARIO));

  // -------------------------------------------------------- celebraciones
  const cola = [];
  function celebrar(c) {
    cola.push(c);
    if (cola.length === 1) mostrarCelebracion();
  }
  function mostrarCelebracion() {
    const c = cola[0];
    if (!c) return;
    const m = $('#celebracion');
    m.classList.toggle('insignia', Boolean(c.insignia));
    $('#cel-img').src = c.img;
    $('#cel-titulo').textContent = c.titulo;
    $('#cel-texto').textContent = c.texto || '';
    m.classList.remove('oculto');
    $('#cel-ok').focus();
  }
  function cerrarCelebracion() {
    cola.shift();
    $('#celebracion').classList.add('oculto');
    if (cola.length) setTimeout(mostrarCelebracion, 250);
  }
  $('#cel-ok').addEventListener('click', cerrarCelebracion);

  // -------------------------------------------------------- sin conexión
  let temporizador = null;
  function conexion(ok) {
    if (ok) {
      clearTimeout(temporizador);
      temporizador = null;
      $('#sin-conexion').classList.add('oculto');
    } else if (!temporizador) {
      temporizador = setTimeout(() => $('#sin-conexion').classList.remove('oculto'), SIN_CONEXION);
    }
  }

  // Esc cierra lo que esté encima; las flechas mueven el tutorial
  document.addEventListener('keydown', (ev) => {
    if (!$('#tutorial').classList.contains('oculto')) {
      if (ev.key === 'Escape') cerrarTutorial();
      else if (ev.key === 'ArrowRight') mover(1);
      else if (ev.key === 'ArrowLeft') mover(-1);
      else return;
      ev.preventDefault();
      ev.stopImmediatePropagation();
    } else if (!$('#celebracion').classList.contains('oculto') && (ev.key === 'Escape' || ev.key === 'Enter')) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
      cerrarCelebracion();
    }
  }, true);

  const encima = () => !$('#tutorial').classList.contains('oculto') || !$('#celebracion').classList.contains('oculto');
  return { marcar, abrirTutorial, aplicarEscenario, celebrar, conexion, encima };
}

// Service worker de «Pruébalo»: la app se puede instalar en el celular y abrir sin internet.
//
// - Código y datos (HTML, CSS, JS, JSON): primero la red, para que siempre llegue la versión nueva;
//   si no hay internet, lo guardado.
// - Recursos grandes que no cambian (MediaPipe y sus modelos, three.js, imágenes, fuente, avatar):
//   primero lo guardado (se descargan una sola vez, unos 30 MB).
// Si cambia algo de sitio/vendor o de sitio/assets, sube VERSION para que se descargue de nuevo.
const VERSION = 'kabtaan-probar-v1';
const GUARDADO = `${VERSION}-recursos`;
const CODIGO = `${VERSION}-codigo`;
const INICIO = ['./', './index.html', './app.css', './probar.css', './manifest.webmanifest'];

self.addEventListener('install', (ev) => {
  ev.waitUntil(caches.open(CODIGO).then((c) => c.addAll(INICIO)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil((async () => {
    for (const nombre of await caches.keys()) {
      if (!nombre.startsWith(VERSION)) await caches.delete(nombre);
    }
    await self.clients.claim();
  })());
});

const esRecurso = (url) => /\/(vendor|assets)\//.test(url.pathname)
  || /\.(wasm|task|glb|webp|png|jpg|woff2?)$/.test(url.pathname);

self.addEventListener('fetch', (ev) => {
  const peticion = ev.request;
  if (peticion.method !== 'GET') return;
  const url = new URL(peticion.url);
  if (url.origin !== self.location.origin) return;
  ev.respondWith(esRecurso(url) ? primeroGuardado(peticion) : primeroRed(peticion));
});

async function primeroGuardado(peticion) {
  const cache = await caches.open(GUARDADO);
  const guardada = await cache.match(peticion);
  if (guardada) return guardada;
  const respuesta = await fetch(peticion);
  if (respuesta.ok && respuesta.status === 200) cache.put(peticion, respuesta.clone());
  return respuesta;
}

async function primeroRed(peticion) {
  const cache = await caches.open(CODIGO);
  try {
    const respuesta = await fetch(peticion);
    if (respuesta.ok && respuesta.status === 200) cache.put(peticion, respuesta.clone());
    return respuesta;
  } catch (e) {
    const guardada = await cache.match(peticion, { ignoreSearch: peticion.mode === 'navigate' });
    if (guardada) return guardada;
    throw e;
  }
}

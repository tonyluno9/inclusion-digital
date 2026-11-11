// Web Worker: entrena el traductor sin congelar la cámara ni la página.
// Recibe { muestras }, manda { tipo: 'progreso', hecho, total } y al final { tipo: 'listo', modelo }
// o { tipo: 'error', mensaje }.
import { entrenarModelo } from './entrenamiento.js';

self.onmessage = (ev) => {
  try {
    const modelo = entrenarModelo(ev.data.muestras, {
      alProgreso: (hecho, total) => { if (hecho % 5 === 0 || hecho === total) self.postMessage({ tipo: 'progreso', hecho, total }); },
    });
    self.postMessage({ tipo: 'listo', modelo });
  } catch (e) {
    self.postMessage({ tipo: 'error', mensaje: e.message || String(e) });
  }
};

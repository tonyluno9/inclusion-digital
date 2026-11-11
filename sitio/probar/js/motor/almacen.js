// Datos del visitante, guardados SOLO en su navegador (IndexedDB): muestras grabadas, clips del
// avatar, manos por palabra, progreso de Aprender y su traductor entrenado. Nada sale de aquí.
// Si IndexedDB no está disponible (ventana privada, datos bloqueados), todo funciona igual en
// memoria y se avisa que se perderá al cerrar la página.
const BD = 'kabtaan-probar';
const TABLA = 'datos';
export const CLAVES = ['muestras', 'clips', 'clipsPrevios', 'manos', 'progreso', 'modelo'];
export const FORMATO_EXPORTE = 'kabtaan-datos-navegador';

export class Almacen {
  constructor() {
    this.memoria = new Map();
    this.bd = null;
    this.persistente = false;
    this.error = '';
  }

  async abrir() {
    try {
      this.bd = await new Promise((ok, mal) => {
        const pet = indexedDB.open(BD, 1);
        pet.onupgradeneeded = () => pet.result.createObjectStore(TABLA);
        pet.onsuccess = () => ok(pet.result);
        pet.onerror = () => mal(pet.error);
        pet.onblocked = () => mal(new Error('bloqueado'));
      });
      for (const clave of CLAVES) {
        const v = await this._tx('readonly', (t) => t.get(clave));
        if (v !== undefined) this.memoria.set(clave, v);
      }
      this.persistente = true;
    } catch (e) {
      this.bd = null;
      this.error = 'Tu navegador no deja guardar datos: lo que grabes se perderá al cerrar la página.';
    }
    return this;
  }

  _tx(modo, fn) {
    return new Promise((ok, mal) => {
      const t = this.bd.transaction(TABLA, modo);
      const pet = fn(t.objectStore(TABLA));
      t.oncomplete = () => ok(pet ? pet.result : undefined);
      t.onerror = () => mal(t.error);
      t.onabort = () => mal(t.error);
    });
  }

  leer(clave, porDefecto = null) {
    return this.memoria.has(clave) ? this.memoria.get(clave) : porDefecto;
  }

  /** Guarda en memoria al instante y en IndexedDB en segundo plano. */
  escribir(clave, valor) {
    this.memoria.set(clave, valor);
    if (!this.bd) return Promise.resolve();
    return this._tx('readwrite', (t) => t.put(valor, clave)).catch((e) => {
      this.error = `No se pudo guardar (${e && e.name ? e.name : 'error'}). ¿Falta espacio en el navegador?`;
    });
  }

  async borrarTodo() {
    this.memoria.clear();
    if (this.bd) await this._tx('readwrite', (t) => t.clear()).catch(() => {});
  }

  /** Todo en un objeto JSON (los Float32Array como listas). */
  exportar() {
    const datos = {};
    for (const clave of CLAVES) {
      if (!this.memoria.has(clave)) continue;
      let v = this.memoria.get(clave);
      if (clave === 'muestras') v = v.map((m) => ({ ...m, seq: Array.from(m.seq) }));
      datos[clave] = v;
    }
    return { formato: FORMATO_EXPORTE, version: 1, exportado: new Date().toISOString(), datos };
  }

  /** Reemplaza los datos del navegador por los de un exporte. */
  async importar(obj) {
    if (!obj || obj.formato !== FORMATO_EXPORTE || !obj.datos) throw new Error('El archivo no es un exporte de K\'ab T\'aan');
    await this.borrarTodo();
    for (const clave of CLAVES) {
      if (!(clave in obj.datos)) continue;
      let v = obj.datos[clave];
      if (clave === 'muestras') v = v.map((m) => ({ ...m, seq: Float32Array.from(m.seq) }));
      await this.escribir(clave, v);
    }
  }
}

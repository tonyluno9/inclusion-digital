// Copiado de app/web/js/aprender.js por sitio/herramientas/copiar_interfaz.py (solo cambian las rutas). No lo edites aquí.
// Aprender (RF-35): qué seña practicar y si la persona la hizo bien.
// Lógica pura, sin DOM, para probarla con Node (web/tests/aprender.test.mjs).
import { norm } from './texto.js';

// Se pueden practicar las señas que el traductor reconoce. Primero las que el avatar sabe
// hacer (así hay una demostración); si ninguna tiene movimiento, todas las del traductor.
export function candidatas(palabras) {
  const traductor = palabras.filter((p) => p.traductor);
  const conAvatar = traductor.filter((p) => p.movimiento);
  return conAvatar.length ? conAvatar : traductor;
}

// Elige la siguiente: las menos acertadas salen más seguido y no se repite la anterior.
// progreso: { clave: { aciertos } }; azar: función como Math.random (para las pruebas).
export function elegirPalabra(lista, progreso = {}, anterior = null, azar = Math.random) {
  if (!lista.length) return null;
  const opciones = lista.length > 1 ? lista.filter((p) => p.clave !== anterior) : lista;
  const pesos = opciones.map((p) => 1 / (1 + ((progreso[p.clave] || {}).aciertos || 0)));
  let r = azar() * pesos.reduce((a, b) => a + b, 0);
  for (let i = 0; i < opciones.length; i += 1) {
    r -= pesos[i];
    if (r < 0) return opciones[i];
  }
  return opciones[opciones.length - 1];
}

// ¿La seña reconocida es la que se pedía? (sin acentos ni mayúsculas)
export function coincide(prediccion, palabra) {
  return Boolean(prediccion) && norm(prediccion) === norm(palabra.nombre || palabra.clave);
}

// Igual que estrellas_por_confianza de modules/progreso.py
export function estrellas(confianza) {
  return confianza >= 0.9 ? 3 : confianza >= 0.75 ? 2 : 1;
}

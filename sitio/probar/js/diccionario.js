// Copiado de app/web/js/diccionario.js por sitio/herramientas/copiar_interfaz.py (solo cambian las rutas). No lo edites aquí.
// Diccionario de señas (RF-34): agrupa las palabras que la app conoce por categoría.
// Lógica pura, sin DOM, para probarla con Node (web/tests/diccionario.test.mjs).
import { norm } from './texto.js';

export const OTRAS = { id: 'otras', nombre: 'Otras', palabras: [] };

// palabras: [{ clave, nombre, ... }] (de /api/diccionario); categorias: [{ id, nombre, palabras }]
// filtro: { texto, categoria } -> [{ categoria, palabras: [...], porAprender: [clave] }]
// Cada palabra va en la primera categoría que la nombra; las demás, en «Otras».
export function agrupar(palabras, categorias, filtro = {}) {
  const texto = norm(filtro.texto || '');
  const lista = [...categorias, OTRAS];
  const deCategoria = new Map();
  for (const c of categorias) for (const p of c.palabras) if (!deCategoria.has(norm(p))) deCategoria.set(norm(p), c.id);
  const conocidas = new Set(palabras.map((p) => p.clave));
  const coincide = (p) => !texto || norm(p.nombre).includes(texto) || p.clave.includes(texto);
  return lista
    .filter((c) => !filtro.categoria || filtro.categoria === c.id)
    .map((c) => ({
      categoria: c,
      palabras: palabras.filter((p) => (deCategoria.get(p.clave) || OTRAS.id) === c.id && coincide(p))
        .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es')),
      // Palabras de la categoría que la app todavía no tiene (para invitar a grabarlas)
      porAprender: c.palabras.map(norm).filter((p, i, a) => a.indexOf(p) === i && !conocidas.has(p))
        .filter((p) => !texto || p.includes(texto)),
    }))
    .filter((g) => g.palabras.length || (g.porAprender.length && (filtro.categoria || texto)));
}

// Resumen de lo que la app sabe hacer con una palabra
export function estadoPalabra(p) {
  return {
    traductor: Boolean(p.traductor),
    avatar: Boolean(p.movimiento),
    completa: Boolean(p.traductor && p.movimiento),
  };
}

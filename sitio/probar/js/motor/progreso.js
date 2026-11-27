// Port de app/modules/progreso.py: estrellas, racha de días e insignias de Aprender.
// Los datos son el mismo dict que progreso.json de la app (se guarda en el navegador).

export const INSIGNIAS = [
  ['primera_sena', 'Primera seña', 'Haz bien una seña en Aprender.'],
  ['diez_senas', 'Diez señas', 'Haz bien 10 señas distintas.'],
  ['racha_3', 'Racha de 3 días', 'Practica 3 días seguidos.'],
  ['racha_7', 'Racha de 7 días', 'Practica 7 días seguidos.'],
  ['saludos', 'Maestro de los saludos', 'Haz bien los saludos que conoce el traductor (al menos 2).'],
  ['primer_movimiento', 'Primer movimiento', 'Graba el movimiento de una seña para el avatar.'],
  ['traductor', 'Traductor entrenado', 'Entrena el traductor con tus señas.'],
  ['conversacion', 'Primera conversación', 'Traduce una oración completa.'],
  ['explorador', 'Explorador', 'Haz bien señas de 3 categorías distintas.'],
];
const DIEZ = 10;
const SALUDOS_MIN = 2;
const CATEGORIAS_MIN = 3;

/** Minúsculas, sin acentos ni signos («¡Adiós!» -> «adios»), como normalizar() de Python. */
export function normalizar(texto) {
  const sin = String(texto).toLowerCase().normalize('NFD').replace(/\p{Mn}/gu, '');
  return sin.replace(/[^a-z0-9 ]+/g, ' ').split(/\s+/).filter(Boolean).join(' ');
}

export const estrellasPorConfianza = (c) => (c >= 0.9 ? 3 : c >= 0.75 ? 2 : 1);

/** Fecha local de hoy como «AAAA-MM-DD» (date.today() de Python). */
export function hoyISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const diaAnterior = (iso) => {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
};

export const vacio = () => ({ estrellas: 0, aciertos: 0, intentos: 0, oraciones: 0, palabras: {}, dias: [], insignias: {} });

export class Progreso {
  /** datos: lo guardado (o null); hoy: función que da la fecha ISO de hoy. */
  constructor(datos = null, hoy = hoyISO) {
    this.hoy = hoy;
    this.datos = vacio();
    if (datos && typeof datos === 'object' && !Array.isArray(datos)) {
      for (const k of Object.keys(this.datos)) if (k in datos) this.datos[k] = datos[k];
    }
  }

  /** Un intento en Aprender. Devuelve las estrellas ganadas (0 si falló). */
  registrarIntento(palabra, acierto, confianza = 0) {
    const clave = normalizar(palabra);
    const d = this.datos;
    const p = d.palabras[clave] || (d.palabras[clave] = { aciertos: 0, intentos: 0, mejor: 0 });
    p.intentos += 1;
    d.intentos += 1;
    let estrellas = 0;
    if (acierto) {
      estrellas = estrellasPorConfianza(confianza);
      p.aciertos += 1;
      p.mejor = Math.max(p.mejor, estrellas);
      d.aciertos += 1;
      d.estrellas += estrellas;
      const hoy = this.hoy();
      if (!d.dias.includes(hoy)) d.dias = [...d.dias, hoy].sort();
    }
    return estrellas;
  }

  registrarOracion() { this.datos.oraciones += 1; }

  /** Días seguidos con al menos un acierto, hasta hoy (o hasta ayer: hoy aún no termina). */
  racha() {
    const dias = new Set(this.datos.dias);
    let dia = this.hoy();
    if (!dias.has(dia)) dia = diaAnterior(dia);
    let n = 0;
    while (dias.has(dia)) { n += 1; dia = diaAnterior(dia); }
    return n;
  }

  aprendidas() {
    return Object.entries(this.datos.palabras).filter(([, v]) => v.aciertos > 0).map(([p]) => p).sort();
  }

  /** Otorga las insignias que ya se cumplen. Devuelve las ids nuevas. */
  evaluar(categorias = {}, conocidas = [], clips = 0, modelo = false) {
    const aprendidas = new Set(this.aprendidas());
    const cats = Object.fromEntries(Object.entries(categorias || {}).map(([c, ps]) => [c, new Set(ps.map(normalizar))]));
    const conoc = new Set([...conocidas].map(normalizar));
    const racha = this.racha();
    const saludos = [...(cats.saludos || [])].filter((p) => conoc.has(p));
    const cumple = {
      primera_sena: aprendidas.size >= 1,
      diez_senas: aprendidas.size >= DIEZ,
      racha_3: racha >= 3,
      racha_7: racha >= 7,
      saludos: saludos.length >= SALUDOS_MIN && saludos.every((p) => aprendidas.has(p)),
      primer_movimiento: clips >= 1,
      traductor: Boolean(modelo),
      conversacion: this.datos.oraciones >= 1,
      explorador: Object.values(cats).filter((ps) => [...ps].some((p) => aprendidas.has(p))).length >= CATEGORIAS_MIN,
    };
    const nuevas = INSIGNIAS.map(([i]) => i).filter((i) => cumple[i] && !(i in this.datos.insignias));
    for (const i of nuevas) this.datos.insignias[i] = this.hoy();
    return nuevas;
  }

  resumen() {
    const d = this.datos;
    return {
      estrellas: d.estrellas,
      aciertos: d.aciertos,
      intentos: d.intentos,
      racha: this.racha(),
      practico_hoy: d.dias.includes(this.hoy()),
      aprendidas: this.aprendidas(),
      palabras: d.palabras,
      insignias: INSIGNIAS.map(([id, nombre, como]) => ({ id, nombre, como, ganada: d.insignias[id] ?? null })),
    };
  }
}

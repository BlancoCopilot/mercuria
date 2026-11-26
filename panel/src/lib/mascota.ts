// Reacciones de Gota, la mascota animada de abajo a la derecha.
//
// Cualquier parte de la app puede hacerla reaccionar sin tocar su componente:
//   reaccionar("celular")            → la muestra unos segundos y vuelve sola
//   reaccionar("hablando", 0)        → la deja así hasta soltarla (por ejemplo, durante una llamada con la IA)
//   soltarReaccion()                 → vuelve a su estado normal
//
// Por debajo es un evento del navegador ("mercuria:mascota"), así que no hace falta
// importar ni envolver nada con un proveedor.

export type Reaccion =
  | "quieto"     // de pie, sonriendo
  | "saludando"  // saluda con la mano
  | "hablando"   // habla contenta (respuesta del chat o llamada)
  | "laptop"     // busca en su laptop (pensando)
  | "celular"    // sostiene un celular (denunciar)
  | "senalando"  // señala algo en la pantalla
  | "caminando"  // camina (al cambiar de página)
  | "sorpresa"   // se sorprende (aviso de riesgo medio, error)
  | "asustado";  // se asusta (zona de riesgo alto)

/** Duración natural de cada animación, en ms (una vuelta). */
export const DURACION: Record<Reaccion, number> = {
  quieto: 0,
  saludando: 2620,
  hablando: 2110,
  laptop: 4280,
  celular: 2340,
  senalando: 3270,
  caminando: 1200,
  sorpresa: 3480,
  asustado: 3450,
};

/** Las que se reproducen una sola vez y se quedan en su último cuadro. */
export const UNA_VEZ: ReadonlySet<Reaccion> = new Set(["senalando", "sorpresa", "asustado"]);

/** Globo corto que acompaña a cada reacción (null = sin globo). */
export const GLOBO: Partial<Record<Reaccion, string>> = {
  saludando: "¡Hola! Soy Gota. Tócame si tienes dudas.",
  laptop: "Déjame buscar…",
  hablando: "¡Esto encontré!",
  celular: "Tu denuncia es anónima.",
  senalando: "Mira el riesgo de tu río.",
  sorpresa: "Ojo: hay riesgo cerca.",
  asustado: "¡Cuidado! Zona de riesgo alto.",
};

export interface DetalleReaccion { reaccion: Reaccion | null; ms?: number; globo?: string | null }

export const EVENTO = "mercuria:mascota";

/** Hace reaccionar a Gota. `ms` = cuánto dura (por defecto, una vuelta de la animación; 0 = hasta soltarla). */
export function reaccionar(reaccion: Reaccion, ms?: number, globo?: string | null) {
  window.dispatchEvent(new CustomEvent<DetalleReaccion>(EVENTO, { detail: { reaccion, ms, globo } }));
}

/** Termina una reacción fija (la que se pidió con ms = 0). */
export function soltarReaccion() {
  window.dispatchEvent(new CustomEvent<DetalleReaccion>(EVENTO, { detail: { reaccion: null } }));
}

export function srcDe(r: Reaccion) {
  return `${import.meta.env.BASE_URL}mascota/${r}.webp`;
}

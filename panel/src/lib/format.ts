import type { Nivel } from "./api";

const nf = (d: number) => new Intl.NumberFormat("es-BO", { maximumFractionDigits: d, minimumFractionDigits: 0 });

/** Número con cifras significativas razonables (0,0123 → "0,012"; 1234 → "1.234"). */
export function num(x: number | null | undefined, sig = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "—";
  if (x === 0) return "0";
  const a = Math.abs(x);
  const d = a >= 100 ? 0 : Math.max(0, sig - 1 - Math.floor(Math.log10(a)));
  return nf(Math.min(d, 4)).format(x);
}

export const int = (x: number | null | undefined) => (x === null || x === undefined ? "—" : nf(0).format(x));
export const pct = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${nf(0).format(x * 100)} %`);

export function rango(p05: number | null | undefined, p95: number | null | undefined): string {
  return `${num(p05)}–${num(p95)}`;
}

export const NIVEL_TEXTO: Record<Nivel, string> = { bajo: "Bajo", medio: "Medio", alto: "Alto", sin_datos: "Sin datos" };

export function confianzaTexto(c: number | null | undefined): string {
  if (c === null || c === undefined) return "sin estimación";
  if (c >= 0.85) return "estimación firme";
  if (c >= 0.6) return "estimación razonable";
  return "no sabemos bien";
}

export const LEGAL_TEXTO: Record<string, string> = {
  con_concesion: "Con concesión registrada",
  sin_concesion: "Sin concesión registrada",
  en_area_protegida: "En área protegida",
  indeterminado: "Sin capa de concesiones",
};

export const MATRIZ: Record<string, { nombre: string; unidad: string }> = {
  agua: { nombre: "Agua", unidad: "µg/L" },
  sedimento: { nombre: "Sedimento", unidad: "mg/kg" },
  pez: { nombre: "Pez carnívoro", unidad: "mg/kg" },
};

export function fecha(s: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }): string {
  if (!s) return "—";
  const d = new Date(s.length === 10 ? `${s}T12:00:00` : s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString("es-BO", opts);
}

export function hace(s: string | null | undefined): string {
  if (!s) return "";
  const min = Math.round((Date.now() - new Date(s).getTime()) / 60000);
  if (min < 1) return "hace un momento";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  return `hace ${Math.round(h / 24)} días`;
}

/** Enlace para pedir indicaciones de cómo llegar (solo se envía el destino). */
export const comoLlegar = (lat: number, lon: number) => `https://www.google.com/maps/dir/?api=1&destination=${lat.toFixed(5)},${lon.toFixed(5)}`;

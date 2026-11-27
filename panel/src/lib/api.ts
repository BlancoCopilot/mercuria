// Cliente de la API de RastroHg. En la web: mismo origen (Caddy en producción, proxy de Vite en desarrollo).
// En la app de celular (Capacitor) no hay mismo origen: VITE_API_URL trae el servidor (https://...).
export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const PLATAFORMA = (import.meta.env.VITE_PLATFORM ?? "web") as "web" | "android";

/** Rutas relativas del servidor (/v1/..., /media/...) a URL completa. */
export const url = (path: string) => (path.startsWith("/") ? API_BASE + path : path);

export type Rol = "admin" | "laboratorio" | "promotor" | "lider" | "autoridad" | "investigador";
export type Nivel = "bajo" | "medio" | "alto" | "sin_datos";
export type Matriz = "agua" | "sedimento" | "pez";

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

const TOKEN_KEY = "rastrohg.token";
const DEVICE_KEY = "rastrohg.device";

function safeGet(k: string): string | null {
  try { return localStorage.getItem(k); } catch { return null; }
}
function safeSet(k: string, v: string | null) {
  try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* modo privado */ }
}

export const session = {
  get token() { return safeGet(TOKEN_KEY); },
  set token(v: string | null) { safeSet(TOKEN_KEY, v); },
};

function message(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(" · ") || "Datos no válidos";
  if (status === 0) return "Sin conexión con el servidor";
  return `Error ${status}`;
}

export async function api<T = unknown>(path: string, opts: RequestInit & { auth?: boolean; device?: boolean } = {}): Promise<T> {
  const headers = new Headers(opts.headers);
  if (opts.body && !(opts.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (opts.auth !== false && session.token) headers.set("Authorization", `Bearer ${session.token}`);
  if (opts.device) {
    const dev = await ensureDevice();
    headers.set("X-Device-Token", dev);
  }
  let res: Response;
  try {
    res = await fetch(url(path), { ...opts, headers });
  } catch {
    throw new ApiError(0, "Sin conexión con el servidor");
  }
  const text = await res.text();
  const data = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;
  if (!res.ok) {
    const detail = (data as { detail?: unknown })?.detail ?? data;
    if (res.status === 401 && opts.auth !== false && session.token) session.token = null;
    throw new ApiError(res.status, message(detail, res.status), detail);
  }
  return data as T;
}

export const post = <T,>(path: string, body: unknown, opts: RequestInit & { device?: boolean } = {}) =>
  api<T>(path, { ...opts, method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) });

/** Dispositivo anónimo: el token vive solo en este navegador; el servidor guarda su hash. */
export async function ensureDevice(): Promise<string> {
  const existing = safeGet(DEVICE_KEY);
  if (existing) return existing;
  const r = await api<{ device_token: string }>("/v1/devices", {
    method: "POST", auth: false, body: JSON.stringify({ platform: PLATAFORMA, lang: "es" }),
  });
  safeSet(DEVICE_KEY, r.device_token);
  return r.device_token;
}

export function uuid(): string {
  if (crypto.randomUUID) return crypto.randomUUID();
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (+c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (+c / 4)))).toString(16));
}

// ── Tipos de respuesta ─────────────────────────────────────
export interface Celda { h3: string; clase: Exclude<Nivel, "sin_datos">; riesgo: number; confianza: number; palida: boolean; version: number }
export interface MapVersion { version: number; created_at: string; triggers: { tipo: string }[]; reaches_changed: number; cells_changed: number }
export interface Comunidad { id: number; name: string; municipio: string | null; poblacion: number | null; h3: string; km?: number }
export interface Frase { clave: string; texto: string; audio_url: string | null; traduccion_pendiente: boolean }
export interface Pez { codigo: string; nombre: string; grupo: string; mg_kg_p50: number; mg_kg_p95: number; comidas_semana_adulto: number; comidas_semana_nino: number; consejo: "comer" | "limitar" | "evitar"; nota?: string }
export interface Ficha {
  comunidad: { id: number; nombre: string; h3: string; poblacion: number | null; sintetico: boolean };
  idioma: string; nivel: Nivel; confianza: number | null; palida: boolean; version_mapa: number | null;
  frases: Frase[]; peces: Pez[];
  centro_salud: { id: number; name: string; phone: string | null; level: string | null; km: number } | null;
  aviso: string;
}
export interface SitioProps {
  id: number; legal_status: "con_concesion" | "sin_concesion" | "en_area_protegida" | "indeterminado";
  origin: string; status: string; area_ha: number; first_detected: string | null; last_detected: string | null;
  confianza: number; sintetico: boolean; hg_total_p05: number | null; hg_total_p50: number | null; hg_total_p95: number | null;
  area_protegida?: string | null; h3?: string;
}
export interface CeldaDetalle {
  h3: string; risk_class: Exclude<Nivel, "sin_datos">; risk: number; confidence: number; palida: boolean; hazard: number;
  exposure: number; vulnerability: number; version_id: number;
  drivers: Record<string, { reach_id: number; peligro: number; mediana: number; unidad: string }>;
  insumos: { poblacion: number; n_tomas_agua: number; n_zonas_pesca: number; comidas_pescado_semana: number | null } | null;
  comunidades: { id: number; name: string }[];
  historial: { version_id: number; risk_class: string; risk: number; confidence: number }[];
}

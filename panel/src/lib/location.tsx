import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { cellToLatLng, gridDisk, latLngToCell } from "h3-js";
import { api, ApiError, type CeldaDetalle, type Comunidad, type Nivel } from "./api";

// Ubicación al entrar: se pide en cada visita (sesión del navegador) para avisar si la persona
// está en una zona de riesgo. Privacidad: las coordenadas exactas no salen del teléfono; se
// convierten aquí a la celda H3 (~5 km²) y al servidor solo se le pide el riesgo de esa celda.

export type Estado = "inicio" | "preguntar" | "ubicando" | "listo" | "denegado" | "sin_senal" | "descartado";

export interface Zona {
  h3: string;
  nivel: Nivel;               // nivel de la celda propia (o "sin_datos")
  confianza: number | null;
  palida: boolean;
  cercaAlto: boolean;         // hay una celda vecina (≈3 km) en riesgo alto
  peorVecino: Nivel;
  comunidad: { id: number; name: string } | null;
  lat: number; lon: number;   // centro de la celda (aproximado), no la posición exacta
}

/** Posición exacta: solo vive en este navegador (para dibujar "estás aquí"); nunca se envía. */
export interface Posicion { lat: number; lon: number; precision: number }

interface LocCtx { estado: Estado; zona: Zona | null; pos: Posicion | null; ubicar: () => void; descartar: () => void; cerrarAviso: () => void; avisoCerrado: boolean }
const Ctx = createContext<LocCtx | null>(null);

const SES_NO = "rastrohg.ubic-no";
const SES_CERRADO = "rastrohg.ubic-aviso";
const ORDEN: Record<Nivel, number> = { sin_datos: -1, bajo: 0, medio: 1, alto: 2 };

function ses(k: string, v?: string | null): string | null {
  try {
    if (v === undefined) return sessionStorage.getItem(k);
    if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v);
  } catch { /* modo privado */ }
  return null;
}

async function celda(h: string): Promise<CeldaDetalle | null> {
  try { return await api<CeldaDetalle>(`/v1/map/cells/${h}`, { auth: false }); }
  catch (e) { if (e instanceof ApiError && e.status === 404) return null; throw e; }
}

export async function zonaDe(lat: number, lon: number): Promise<Zona> {
  const h = latLngToCell(lat, lon, 7);
  const vecinos = gridDisk(h, 1).filter((x) => x !== h);
  const [propia, ...otras] = await Promise.all([celda(h), ...vecinos.map(celda)]);
  const nivelDe = (c: CeldaDetalle | null): Nivel => (c ? c.risk_class : "sin_datos");
  const peor = otras.reduce<Nivel>((acc, c) => (ORDEN[nivelDe(c)] > ORDEN[acc] ? nivelDe(c) : acc), "sin_datos");
  const [clat, clon] = cellToLatLng(h);
  let comunidad = propia?.comunidades?.[0] ?? otras.find((c) => c?.comunidades?.length)?.comunidades[0] ?? null;
  if (!comunidad) {
    const cerca = await api<Comunidad[]>(`/v1/communities?lat=${clat.toFixed(3)}&lon=${clon.toFixed(3)}&limit=1`, { auth: false }).catch(() => []);
    if (cerca[0] && (cerca[0].km ?? 99) < 25) comunidad = { id: cerca[0].id, name: cerca[0].name };
  }
  return {
    h3: h, nivel: nivelDe(propia), confianza: propia?.confidence ?? null, palida: propia?.palida ?? false,
    cercaAlto: peor === "alto" && nivelDe(propia) !== "alto", peorVecino: peor, comunidad, lat: clat, lon: clon,
  };
}

export function LocationProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>("inicio");
  const [zona, setZona] = useState<Zona | null>(null);
  const [pos, setPos] = useState<Posicion | null>(null);
  const [avisoCerrado, setAvisoCerrado] = useState(false);

  const ubicar = useCallback(() => {
    if (!("geolocation" in navigator)) { setEstado("sin_senal"); return; }
    setEstado("ubicando");
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        setPos({ lat: p.coords.latitude, lon: p.coords.longitude, precision: p.coords.accuracy });
        try {
          const z = await zonaDe(p.coords.latitude, p.coords.longitude);
          setZona(z);
          setAvisoCerrado(ses(SES_CERRADO) === `${z.h3}:${z.nivel}`);
          setEstado("listo");
        } catch { setEstado("sin_senal"); }
      },
      (err) => setEstado(err.code === err.PERMISSION_DENIED ? "denegado" : "sin_senal"),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 10 * 60 * 1000 },
    );
  }, []);

  // Al entrar: si ya hay permiso, ubica directo; si no, muestra nuestra explicación antes del permiso del navegador.
  useEffect(() => {
    if (ses(SES_NO) === "1") { setEstado("descartado"); return; }
    if (!("geolocation" in navigator)) { setEstado("sin_senal"); return; }
    const perms = (navigator as Navigator & { permissions?: Permissions }).permissions;
    if (!perms?.query) { setEstado("preguntar"); return; }
    perms.query({ name: "geolocation" as PermissionName })
      .then((st) => (st.state === "granted" ? ubicar() : setEstado(st.state === "denied" ? "denegado" : "preguntar")))
      .catch(() => setEstado("preguntar"));
  }, [ubicar]);

  const descartar = useCallback(() => { ses(SES_NO, "1"); setEstado("descartado"); }, []);
  const cerrarAviso = useCallback(() => {
    if (zona) ses(SES_CERRADO, `${zona.h3}:${zona.nivel}`);
    setAvisoCerrado(true);
  }, [zona]);

  return <Ctx.Provider value={{ estado, zona, pos, ubicar, descartar, cerrarAviso, avisoCerrado }}>{children}</Ctx.Provider>;
}

export function useUbicacion() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useUbicacion fuera de LocationProvider");
  return c;
}

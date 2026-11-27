import { useCallback, useEffect, useRef, useState } from "react";
import { useUbicacion } from "../lib/location";
import { alertaPara, claveAlerta } from "./alerta";
import {
  alVolver, configurarRevisor, fondoConcedido, notificacionesConcedidas, notificar, pedirFondo,
  pedirNotificaciones, pedirUbicacion, ubicacionConcedida,
} from "./native";

const K_ACTIVAS = "mercuria.alertas";
const K_ULTIMA = "mercuria.ultima_alerta";
const CADA_MS = 5 * 60 * 1000;   // con la app abierta, se revisa la zona cada 5 minutos

const leer = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const guardar = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* */ } };

export interface EstadoAlertas {
  activas: boolean;            // la persona pidió que le avisemos
  notificaciones: boolean;     // Android deja mostrar notificaciones
  fondo: boolean;              // ubicación "Permitir todo el tiempo" (avisa con la app cerrada)
}

/**
 * Revisa la zona al abrir la app, al volver a ella y cada 5 minutos; si la zona tiene riesgo
 * medio o alto (o hay una alta a menos de 3 km), manda una notificación una sola vez por zona.
 * Con la app cerrada lo hace el revisor en segundo plano (runner/zona.ts).
 */
export function useAlertas() {
  const { estado, zona, ubicar } = useUbicacion();
  const [st, setSt] = useState<EstadoAlertas>({ activas: leer(K_ACTIVAS) === "1", notificaciones: false, fondo: false });
  const ubicarRef = useRef(ubicar);
  ubicarRef.current = ubicar;
  const estadoRef = useRef(estado);
  estadoRef.current = estado;

  const refrescar = useCallback(async () => {
    const [notificaciones, fondo] = await Promise.all([notificacionesConcedidas(), fondoConcedido()]);
    setSt((s) => ({ ...s, notificaciones, fondo }));
  }, []);

  // Al abrir: si ya hay permiso de ubicación, ubicar sin preguntar.
  useEffect(() => {
    ubicacionConcedida().then((ok) => { if (ok) ubicarRef.current(); });
    refrescar();
    configurarRevisor({ alertas: leer(K_ACTIVAS) === "1" });
  }, [refrescar]);

  // Al volver a la app (por ejemplo, desde Ajustes o desde la notificación) y cada 5 minutos.
  useEffect(() => {
    const off = alVolver(() => {
      refrescar();
      ubicacionConcedida().then((ok) => { if (ok) ubicarRef.current(); });
    });
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible" && estadoRef.current === "listo") ubicarRef.current();
    }, CADA_MS);
    return () => { off(); window.clearInterval(t); };
  }, [refrescar]);

  // Cada zona nueva: avisar si corresponde, una sola vez por zona y nivel.
  useEffect(() => {
    if (estado !== "listo" || !zona) return;
    const nivel = zona.nivel === "sin_datos" ? null : zona.nivel;
    const clave = claveAlerta(zona.h3, nivel, zona.cercaAlto);
    if (leer(K_ULTIMA) === clave) return;
    guardar(K_ULTIMA, clave);
    configurarRevisor({ visto: clave });
    const a = alertaPara(nivel, zona.cercaAlto, zona.comunidad?.name);
    if (a && st.activas) notificar(a);
  }, [estado, zona, st.activas]);

  /** Activar: ubicación → notificaciones → "Permitir todo el tiempo". Cada paso es opcional para el siguiente. */
  const activar = useCallback(async () => {
    const ubic = await pedirUbicacion();
    if (!ubic) return false;
    const notificaciones = await pedirNotificaciones();
    guardar(K_ACTIVAS, "1");
    // Al activar se avisa también de la zona actual (si tiene riesgo): confirma que los avisos funcionan.
    try { localStorage.removeItem(K_ULTIMA); } catch { /* */ }
    await configurarRevisor({ alertas: true, visto: "" });
    setSt((s) => ({ ...s, activas: true, notificaciones }));
    ubicarRef.current();
    return true;
  }, []);

  const pedirSegundoPlano = useCallback(async () => {
    const fondo = await pedirFondo();
    setSt((s) => ({ ...s, fondo }));
    return fondo;
  }, []);

  const desactivar = useCallback(async () => {
    guardar(K_ACTIVAS, "0");
    await configurarRevisor({ alertas: false });
    setSt((s) => ({ ...s, activas: false }));
  }, []);

  return { ...st, activar, desactivar, pedirSegundoPlano, refrescar };
}

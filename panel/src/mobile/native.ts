// Puente con Android (Capacitor). En el navegador (vista previa con `npm run dev:movil`) todo
// degrada a las APIs web o a no hacer nada, para poder diseñar sin compilar la APK.
import { Capacitor, registerPlugin, SystemBars, SystemBarsStyle } from "@capacitor/core";
import { App } from "@capacitor/app";
import { Geolocation } from "@capacitor/geolocation";
import { LocalNotifications } from "@capacitor/local-notifications";
import { BackgroundRunner } from "@capacitor/background-runner";
import { TextToSpeech } from "@capacitor-community/text-to-speech";
import { CANAL_RIESGO, ID_NOTIFICACION, RUNNER_LABEL, type Alerta } from "./alerta";
import { UbicacionDenegada, usarFuenteUbicacion } from "../lib/location";

export const nativo = Capacitor.isNativePlatform();

/** Plugin propio (android/app/.../FondoPlugin.java): ubicación "Permitir todo el tiempo" y ajustes de la app. */
interface FondoPlugin {
  estado(): Promise<{ fondo: boolean }>;
  pedir(): Promise<{ fondo: boolean }>;
  abrirAjustes(): Promise<void>;
}
const Fondo = registerPlugin<FondoPlugin>("Fondo");

export async function iniciarNativo() {
  if (!nativo) return;
  // GPS nativo: más confiable que la geolocalización del WebView (que en algunos teléfonos no recibe la posición).
  usarFuenteUbicacion(async () => {
    try {
      const p = await Geolocation.getCurrentPosition({ enableHighAccuracy: false, timeout: 20000, maximumAge: 5 * 60 * 1000 });
      return { lat: p.coords.latitude, lon: p.coords.longitude, precision: p.coords.accuracy };
    } catch (e) {
      if (/denied|permission/i.test(String((e as Error)?.message ?? e))) throw new UbicacionDenegada(String(e));
      // Sin una posición reciente: intentar con GPS de alta precisión
      const p = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 30000 });
      return { lat: p.coords.latitude, lon: p.coords.longitude, precision: p.coords.accuracy };
    }
  });
  await SystemBars.setStyle({ style: SystemBarsStyle.Light }).catch(() => {});
  await LocalNotifications.createChannel({
    id: CANAL_RIESGO, name: "Zona con riesgo por mercurio",
    description: "Aviso cuando entras a una zona de riesgo medio o alto", importance: 5, visibility: 1, vibration: true,
  }).catch(() => {});
}

// ── Permisos ────────────────────────────────────────────────
export async function ubicacionConcedida(): Promise<boolean> {
  if (!nativo) {
    const st = await navigator.permissions?.query({ name: "geolocation" as PermissionName }).catch(() => null);
    return st?.state === "granted";
  }
  const p = await Geolocation.checkPermissions().catch(() => null);
  return p?.location === "granted" || p?.coarseLocation === "granted";
}

export async function pedirUbicacion(): Promise<boolean> {
  if (!nativo) return true;   // el navegador pregunta solo al pedir la posición
  const p = await Geolocation.requestPermissions({ permissions: ["location", "coarseLocation"] }).catch(() => null);
  return p?.location === "granted" || p?.coarseLocation === "granted";
}

export async function pedirNotificaciones(): Promise<boolean> {
  if (!nativo) return false;
  const p = await LocalNotifications.requestPermissions().catch(() => null);
  return p?.display === "granted";
}

export async function notificacionesConcedidas(): Promise<boolean> {
  if (!nativo) return false;
  const p = await LocalNotifications.checkPermissions().catch(() => null);
  return p?.display === "granted";
}

/** Ubicación en segundo plano ("Permitir todo el tiempo"): sin ella, solo se avisa con la app abierta. */
export const fondoConcedido = async () => (nativo ? (await Fondo.estado().catch(() => ({ fondo: false }))).fondo : false);
export const pedirFondo = async () => (nativo ? (await Fondo.pedir().catch(() => ({ fondo: false }))).fondo : false);
export const abrirAjustes = () => (nativo ? Fondo.abrirAjustes().catch(() => {}) : Promise.resolve());

// ── Alertas ────────────────────────────────────────────────
export async function notificar(a: Alerta) {
  if (!nativo) return;
  await LocalNotifications.schedule({
    notifications: [{ id: ID_NOTIFICACION, title: a.title, body: a.body, largeBody: a.body, channelId: CANAL_RIESGO, smallIcon: "ic_stat_gota", autoCancel: true,
      isExactNotification: false }],   // aviso inmediato: sin alarma exacta (evita la pantalla "Alarmas y recordatorios")
  }).catch(() => {});
}

/** Le dice al revisor en segundo plano si las alertas están activas y qué zona ya se avisó. */
export async function configurarRevisor(details: { alertas?: boolean; visto?: string }) {
  if (!nativo) return;
  await BackgroundRunner.dispatchEvent({ label: RUNNER_LABEL, event: "configurar", details }).catch(() => {});
}

// ── Ciclo de vida ──────────────────────────────────────────
export function alVolver(fn: () => void): () => void {
  if (!nativo) {
    const h = () => { if (document.visibilityState === "visible") fn(); };
    document.addEventListener("visibilitychange", h);
    return () => document.removeEventListener("visibilitychange", h);
  }
  const l = App.addListener("appStateChange", (s) => { if (s.isActive) fn(); });
  return () => { l.then((x) => x.remove()); };
}

export function alAtras(fn: () => boolean): () => void {
  if (!nativo) return () => {};
  const l = App.addListener("backButton", () => { if (!fn()) App.exitApp(); });
  return () => { l.then((x) => x.remove()); };
}

// ── Leer en voz alta (el WebView de Android no trae speechSynthesis) ──
export async function hablar(texto: string): Promise<void> {
  if (nativo) {
    for (const lang of ["es-BO", "es-US", "es-ES"]) {
      try { await TextToSpeech.speak({ text: texto, lang, rate: 0.95 }); return; }
      catch (e) { if (!/language/i.test(String(e))) throw e; }
    }
    return;
  }
  await new Promise<void>((ok) => {
    if (!("speechSynthesis" in window)) { ok(); return; }
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "es-BO"; u.rate = 0.92; u.onend = () => ok(); u.onerror = () => ok();
    window.speechSynthesis.speak(u);
  });
}

export async function callar() {
  if (nativo) await TextToSpeech.stop().catch(() => {});
  else window.speechSynthesis?.cancel();
}

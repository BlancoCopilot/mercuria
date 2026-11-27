// Revisor de zona en segundo plano (Capacitor Background Runner). Android lo ejecuta cada ~15 min,
// aunque la app esté cerrada. No hay DOM ni React: solo fetch, CapacitorKV, CapacitorGeolocation y
// CapacitorNotifications, en un motor JS pequeño (QuickJS) que no aguanta librerías grandes como h3-js.
// Por eso la celda la calcula el servidor (/v1/map/zona). Privacidad: se manda la posición redondeada
// a 2 decimales (~1 km); el servidor no la guarda.
import { alertaPara, CANAL_RIESGO, claveAlerta, ID_NOTIFICACION, type NivelCelda } from "../alerta";

type Done = (v?: unknown) => void;
declare function addEventListener(ev: string, fn: (resolve: Done, reject: Done, args: Record<string, unknown>) => void): void;
declare const CapacitorKV: { get(k: string): { value?: string | null } | null; set(k: string, v: string): void };
declare const CapacitorGeolocation: { getCurrentPosition(): Promise<{ latitude: number; longitude: number }> | { latitude: number; longitude: number } };
declare const CapacitorNotifications: { schedule(n: Record<string, unknown>[]): void };

const API = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

const kv = (k: string) => { try { return CapacitorKV.get(k)?.value ?? null; } catch { return null; } };

// La app avisa si las alertas están activas y qué zona ya mostró (para no repetir).
addEventListener("configurar", (resolve, reject, args) => {
  try {
    if (typeof args.alertas === "boolean") CapacitorKV.set("alertas", args.alertas ? "1" : "0");
    if (typeof args.visto === "string") CapacitorKV.set("ultimo", args.visto);
    resolve();
  } catch (e) { reject(String(e)); }
});

addEventListener("revisarZona", async (resolve) => {
  try {
    if (kv("alertas") !== "1") { resolve({ omitido: "alertas apagadas" }); return; }
    const p = await CapacitorGeolocation.getCurrentPosition();
    const r = await fetch(`${API}/v1/map/zona?lat=${p.latitude.toFixed(2)}&lon=${p.longitude.toFixed(2)}`);
    if (r.status !== 200) { resolve({ error: "zona " + r.status }); return; }
    const z = await r.json() as { h3: string; nivel: NivelCelda; cerca_alto: boolean; comunidad: string | null };
    const clave = claveAlerta(z.h3, z.nivel, z.cerca_alto);
    const alerta = alertaPara(z.nivel, z.cerca_alto, z.comunidad);
    if (alerta && kv("ultimo") !== clave) {
      CapacitorNotifications.schedule([{
        id: ID_NOTIFICACION, title: alerta.title, body: alerta.body, largeBody: alerta.body,
        channelId: CANAL_RIESGO, smallIcon: "ic_stat_gota", autoCancel: true,
      }]);
    }
    CapacitorKV.set("ultimo", clave);   // también en zona baja: al volver a entrar a una de riesgo, avisa otra vez
    resolve({ clave, aviso: !!alerta });
  } catch (e) {
    console.error("revisarZona: " + String(e));
    resolve({ error: String(e) });      // resolver siempre: si no, Android puede matar la tarea
  }
});

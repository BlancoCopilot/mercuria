import { ensureDevice, post } from "./api";

// Reportes anónimos: se guardan primero en el teléfono. Si no hay señal, quedan en cola y se
// envían solos cuando vuelve la conexión. El servidor ignora duplicados (client_uuid).
// La comparten la página /denunciar de la web y la pestaña "Avisar" de la app.
const QUEUE_KEY = "rastrohg.cola_denuncias";

export interface Pendiente {
  client_uuid: string; kind: string; description: string | null;
  lat: number; lon: number; area_ha: number | null; created_client_at: string;
}

export function readQueue(): Pendiente[] { try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch { return []; } }
export function writeQueue(q: Pendiente[]) { try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch { /* */ } }

/** Envía lo que esté en cola. Devuelve cuántos quedaron enviados (0 si no había o no hay señal). */
export async function enviarCola(): Promise<number> {
  const q = readQueue();
  if (!q.length || !navigator.onLine) return 0;
  await ensureDevice();
  const r = await post<{ reports: { aceptadas: string[]; duplicadas: string[] } }>("/v1/sync", { since_version: 0, reports: q }, { device: true });
  const done = new Set([...r.reports.aceptadas, ...r.reports.duplicadas]);
  writeQueue(readQueue().filter((x) => !done.has(x.client_uuid)));
  return done.size;
}

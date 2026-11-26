import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { post } from "./api";
import type { Mood } from "../components/Mascot";
import { useUbicacion } from "./location";

// Estado único del chat: lo comparten el widget flotante y la página /preguntar,
// y sobrevive a la navegación (y a recargar la pestaña, vía sessionStorage).

export interface Fuente { archivo?: string; titulo?: string; pagina?: number | null; [k: string]: unknown }
export interface Turno { rol: "usuario" | "asistente"; texto: string; fuentes?: Fuente[] }
interface Respuesta { respuesta: string; fuentes: Fuente[]; sin_modelo: boolean; error: string | null }

interface ChatCtx {
  turnos: Turno[]; draft: string; setDraft: (s: string) => void;
  tema: string | null; setTema: (t: string | null) => void;
  busy: boolean; err: string | null; mood: Mood;
  ask: (pregunta: string) => Promise<void>; clear: () => void;
  open: boolean; setOpen: (o: boolean) => void;
}

const Ctx = createContext<ChatCtx | null>(null);
const KEY = "rastrohg.chat";

function load(): Turno[] {
  try { return JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch { return []; }
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [turnos, setTurnos] = useState<Turno[]>(load);
  const [draft, setDraft] = useState("");
  const [tema, setTema] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [talking, setTalking] = useState(false);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const { zona } = useUbicacion();

  useEffect(() => { try { sessionStorage.setItem(KEY, JSON.stringify(turnos.slice(-30))); } catch { /* */ } }, [turnos]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const ask = useCallback(async (pregunta: string) => {
    const p = pregunta.trim();
    if (!p || busy) return;
    setErr(null);
    window.clearTimeout(timer.current);
    setTalking(false);
    const hist = turnos.slice(-10).map((t) => ({ rol: t.rol, texto: t.texto.slice(0, 2000) }));
    setTurnos((t) => [...t, { rol: "usuario", texto: p }]);
    setDraft("");
    setBusy(true);
    try {
      // la zona (centro de la celda, no la posición exacta) permite responder según el riesgo local
      const donde = zona ? { lat: zona.lat, lon: zona.lon, comunidad_id: zona.comunidad?.id ?? null } : {};
      const r = await post<Respuesta>("/v1/chat", { pregunta: p, historial: hist, tema, ...donde });
      setTurnos((t) => [...t, { rol: "asistente", texto: r.respuesta, fuentes: r.fuentes }]);
      // mueve la boca un tiempo proporcional al largo de la respuesta (entre 1,5 y 6 s)
      setTalking(true);
      timer.current = window.setTimeout(() => setTalking(false), Math.min(6000, Math.max(1500, r.respuesta.length * 30)));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [busy, turnos, tema, zona]);

  const clear = useCallback(() => { setTurnos([]); setErr(null); setTalking(false); }, []);
  const mood: Mood = busy ? "thinking" : talking ? "talking" : draft.trim() ? "listening" : "idle";

  return (
    <Ctx.Provider value={{ turnos, draft, setDraft, tema, setTema, busy, err, mood, ask, clear, open, setOpen }}>
      {children}
    </Ctx.Provider>
  );
}

export function useChat() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useChat fuera de ChatProvider");
  return c;
}

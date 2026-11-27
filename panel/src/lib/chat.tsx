import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { post } from "./api";
import type { Mood } from "../components/Mascot";
import { useUbicacion } from "./location";
import { useVoz } from "./voice";

// Estado único del chat: lo comparten el widget flotante y la página /preguntar,
// y sobrevive a la navegación (y a recargar la pestaña, vía sessionStorage).

export interface Fuente { archivo?: string; titulo?: string; pagina?: number | null; url?: string | null; tipo?: string; [k: string]: unknown }
export interface Turno { rol: "usuario" | "asistente"; texto: string; fuentes?: Fuente[]; voz?: boolean }
interface Respuesta { respuesta: string; fuentes: Fuente[]; sin_modelo: boolean; error: string | null }

interface ChatCtx {
  turnos: Turno[]; draft: string; setDraft: (s: string) => void;
  tema: string | null; setTema: (t: string | null) => void;
  busy: boolean; err: string | null; mood: Mood;
  ask: (pregunta: string) => Promise<void>; clear: () => void;
  open: boolean; setOpen: (o: boolean) => void;
  voz: ReturnType<typeof useVoz>;
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

  // ── Voz: la transcripción entra al mismo hilo; un turno por cada cambio de quien habla ──
  const pendientes = useRef<Fuente[]>([]);
  const mismas = (a: Fuente, b: Fuente) => (a.url ? a.url === b.url : a.titulo === b.titulo && a.pagina === b.pagina);
  const unir = (prev: Fuente[] = [], nuevas: Fuente[]) => [...prev, ...nuevas.filter((n) => !prev.some((p) => mismas(p, n)))];
  // GPT-Live conversa como una persona: dice "Mm-hm" o "¡Hola!" mientras uno habla. Esos fragmentos cortos de
  // Gota se retienen y, si la persona sigue hablando, se descartan; así no parten su pregunta en burbujas.
  const buf = useRef<{ texto: string; timer?: number }>({ texto: "" });
  const pegar = (x: string) => x.replace(/([¿¡])\s+/g, "$1");     // la transcripción llega como " ¿" + " en"
  const sumar = (rol: "usuario" | "asistente", delta: string) => setTurnos((t) => {
    const last = t[t.length - 1];
    const extra = rol === "asistente" && pendientes.current.length ? pendientes.current.splice(0) : [];
    if (last && last.voz && last.rol === rol) {
      return [...t.slice(0, -1), { ...last, texto: pegar(last.texto + delta), fuentes: extra.length ? unir(last.fuentes, extra) : last.fuentes }];
    }
    const texto = pegar(delta.replace(/^[\s,.!?;:]+/, ""));
    return texto ? [...t, { rol, texto, voz: true, fuentes: extra.length ? extra : undefined }] : t;
  });
  const soltar = () => {
    window.clearTimeout(buf.current.timer);
    const texto = buf.current.texto;
    buf.current = { texto: "" };
    if (texto) sumar("asistente", texto);
  };
  const enCurso = useRef<"usuario" | "asistente" | null>(null);
  const voz = useVoz({
    onTexto: (rol, delta) => {
      if (!delta) return;
      if (rol === "usuario") {
        window.clearTimeout(buf.current.timer);
        buf.current = { texto: "" };            // interjección de Gota mientras la persona hablaba
        enCurso.current = "usuario";
        sumar("usuario", delta);
        return;
      }
      if (enCurso.current === "asistente") { sumar("asistente", delta); return; }
      buf.current.texto += delta;
      window.clearTimeout(buf.current.timer);
      if (buf.current.texto.trim().length >= 24) { enCurso.current = "asistente"; soltar(); }
      else buf.current.timer = window.setTimeout(() => { enCurso.current = "asistente"; soltar(); }, 1400);
    },
    onFuentes: (f) => {
      // las fuentes llegan antes que la respuesta hablada: se guardan y se pegan al siguiente turno de Gota,
      // salvo las citas web, que llegan mientras Gota ya está hablando
      setTurnos((t) => {
        const last = t[t.length - 1];
        if (f.some((x) => x.tipo === "web") && last?.voz && last.rol === "asistente") {
          return [...t.slice(0, -1), { ...last, fuentes: unir(last.fuentes, f) }];
        }
        pendientes.current = unir(pendientes.current, f);
        return t;
      });
    },
    contexto: () => ({
      historial: turnos.filter((t) => !t.voz).slice(-6).map((t) => ({ rol: t.rol, texto: t.texto.slice(0, 2000) })),
      ...(zona ? { lat: zona.lat, lon: zona.lon, comunidad_id: zona.comunidad?.id ?? null } : {}),
    }),
  });

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
  const mood: Mood = voz.activo
    ? (voz.hablaGota ? "talking" : voz.buscando ? "thinking" : voz.estado === "activo" ? "listening" : "thinking")
    : busy ? "thinking" : talking ? "talking" : draft.trim() ? "listening" : "idle";

  return (
    <Ctx.Provider value={{ turnos, draft, setDraft, tema, setTema, busy, err, mood, ask, clear, open, setOpen, voz }}>
      {children}
    </Ctx.Provider>
  );
}

export function useChat() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useChat fuera de ChatProvider");
  return c;
}

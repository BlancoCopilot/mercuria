import { useEffect, useRef } from "react";
import { useChat, type Fuente } from "../lib/chat";
import { Mascot, type Mood } from "./Mascot";
import { PhoneIcon } from "./CallScreen";

export const TEMAS = [
  { id: null, label: "Todo" }, { id: "peces", label: "Pescado" }, { id: "salud", label: "Salud" },
  { id: "mineria", label: "Minería" }, { id: "agua", label: "Agua" },
] as const;

const SUGERENCIAS = [
  "¿Qué pescado puedo dar a mis hijos?",
  "¿Cuáles son los síntomas del mercurio?",
  "¿Es peligroso quemar la amalgama en casa?",
];

/** Texto de estado durante la conversación por voz (null = usar el del modo texto). */
export function estadoVoz(v: ReturnType<typeof useChat>["voz"]): string | null {
  if (v.estado === "pidiendo_mic") return "Permite el micrófono para hablar conmigo.";
  if (v.estado === "conectando") return "Conectando…";
  if (v.estado === "cerrando") return "Terminando…";
  if (v.estado === "error") return v.error;
  if (v.estado !== "activo") return null;
  if (v.hablaGota) return "Hablando…";
  if (v.buscando === "documentos") return "Buscando en los documentos…";
  if (v.buscando === "internet") return "Buscando en internet…";
  if (v.buscando === "pensando") return "Pensando…";
  if (v.silenciado) return "Micrófono en silencio";
  return v.hablaPersona ? "Te escucho…" : "Habla cuando quieras";
}

const MicIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><rect x="6.2" y="1.8" width="5.6" height="9.4" rx="2.8" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M3.6 8.4a5.4 5.4 0 0 0 10.8 0M9 13.8v2.6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
);

export const BURBUJA: Record<Mood, string> = {
  idle: "Hola, soy Gota. Pregúntame sobre el mercurio, el pescado o la salud.",
  listening: "Te escucho…",
  thinking: "Buscando en los estudios y guías…",
  talking: "Esto encontré. Abajo están las fuentes.",
};

/** Una etiqueta por documento y página (el RAG puede citar varios fragmentos del mismo). */
const unicas = (fs: Fuente[]) => fs.filter((f, i) => fs.findIndex((g) => g.titulo === f.titulo && g.pagina === f.pagina) === i);

/** Conversación + campo de pregunta. `compact` = versión del widget flotante. */
export function ChatThread({ compact, autoFocus }: { compact?: boolean; autoFocus?: boolean }) {
  const { turnos, draft, setDraft, busy, err, ask, tema, setTema, voz } = useChat();
  const scroller = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLElement | null>(null);              // barra de abajo: el campo o la barra de voz
  const setBar = (el: HTMLElement | null) => { bar.current = el; };
  const input = useRef<HTMLInputElement>(null);
  // Sigue la conversación solo si la persona está abajo: si sube a leer, no se la mueve.
  // (Antes se usaba scrollIntoView del final del hilo: movía toda la página, dejaba la barra con
  // "Terminar" fuera de la vista y, con la voz actualizando varias veces por segundo, impedía bajar.)
  const siguiendo = useRef(true);

  useEffect(() => {
    const medir = () => {
      if (compact) {
        const sc = scroller.current;
        if (sc) siguiendo.current = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 80;
      } else if (bar.current) {
        siguiendo.current = bar.current.getBoundingClientRect().bottom <= window.innerHeight + 80;
      }
    };
    const target: HTMLElement | Window | null = compact ? scroller.current : window;
    target?.addEventListener("scroll", medir, { passive: true });
    return () => target?.removeEventListener("scroll", medir);
  }, [compact]);

  useEffect(() => {
    if (!siguiendo.current) return;
    const suave: ScrollBehavior = voz.activo ? "auto" : "smooth";      // con voz llegan muchas palabras por segundo
    if (compact) {
      const sc = scroller.current;
      if (sc) sc.scrollTo({ top: sc.scrollHeight, behavior: suave });   // solo el área del chat, nunca la página
    } else if (bar.current) {
      const falta = bar.current.getBoundingClientRect().bottom + 16 - window.innerHeight;
      if (falta > 0) window.scrollBy({ top: falta, behavior: suave });   // que se vea la barra (y "Terminar")
    }
  }, [turnos, busy, voz.activo, compact]);
  useEffect(() => { if (autoFocus) input.current?.focus(); }, [autoFocus]);

  return (
    <div className={compact ? "thread thread-compact" : "thread"}>
      <div ref={scroller} className="thread-scroll" aria-live="polite">
        {!compact && (
          <div className="tabs" role="group" aria-label="Tema">
            {TEMAS.map((t) => <button key={String(t.id)} className="btn btn-pill" aria-pressed={tema === t.id} onClick={() => setTema(t.id)}>{t.label}</button>)}
          </div>
        )}
        <div className="chat">
          {turnos.length === 0 && (
            <div className="stack" style={{ gap: 10 }}>
              <span className="label">Puedes empezar con</span>
              {SUGERENCIAS.map((s) => <button key={s} className="btn btn-pill sugerencia" onClick={() => ask(s)}>{s}</button>)}
            </div>
          )}
          {turnos.map((t, i) => t.rol === "usuario" ? (
            <div key={i} className="msg msg-user">{t.voz && <span className="msg-voz" title="Dicho por voz"><MicIcon /></span>}{t.texto}</div>
          ) : (
            <div key={i} className="msg-row">
              <span className="avatar"><Mascot size={compact ? 30 : 36} label="Gota" still /></span>
              <div className="msg msg-bot">
                {t.texto}
                {t.fuentes && t.fuentes.length > 0 && (
                  <div className="fuentes">
                    {unicas(t.fuentes).slice(0, 5).map((f, j) => f.url ? (
                      <a key={j} className="tag tag-web" href={f.url} target="_blank" rel="noopener noreferrer" title={`Internet: ${f.titulo ?? f.archivo}`}>
                        <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.8" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M1.2 6h9.6M6 1.2c-2.6 2.8-2.6 6.8 0 9.6M6 1.2c2.6 2.8 2.6 6.8 0 9.6" fill="none" stroke="currentColor" strokeWidth="1.2" /></svg>
                        {String(f.archivo ?? f.titulo)}
                      </a>
                    ) : (
                      <span key={j} className="tag" title={String(f.archivo ?? f.titulo ?? "")}>
                        {String(f.titulo ?? f.archivo ?? "Fuente")}{f.pagina ? `, p. ${f.pagina}` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="msg-row">
              <span className="avatar"><Mascot size={compact ? 30 : 36} mood="thinking" label="Gota pensando" /></span>
              <div className="msg msg-bot"><span className="skeleton" style={{ display: "block", width: 160, height: 14 }} /></div>
            </div>
          )}
          {err && <p className="field-error" role="alert">No pude responder: {err}</p>}
        </div>
      </div>

      <form ref={setBar} className={compact ? "ask-row" : "marigold-bar"} style={compact ? undefined : { marginTop: 16 }}
        onSubmit={(e) => { e.preventDefault(); ask(draft); }}>
        <div className="field">
          <label className={compact ? "visually-hidden" : "label"} htmlFor={compact ? "pregunta-w" : "pregunta"}>Tu pregunta</label>
          <input ref={input} id={compact ? "pregunta-w" : "pregunta"} className="input" value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Escribe en palabras simples" maxLength={500} autoComplete="off" enterKeyHint="send" />
        </div>
        <button className="btn btn-pill voz-mic" type="button" onClick={voz.empezar} disabled={busy || voz.activo}
          aria-label="Llamar a Gota: conversar por voz" title="Llamar a Gota: conversar por voz">
          <PhoneIcon />{!compact && <span>Llamar</span>}
        </button>
        <button className="btn" type="submit" disabled={busy || !draft.trim()} aria-label="Preguntar">
          {compact ? (
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M3 9h11M10 4.5L14.5 9 10 13.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
          ) : "Preguntar"}
        </button>
      </form>
    </div>
  );
}

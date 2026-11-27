import { useEffect, useRef } from "react";
import { useChat, type Fuente } from "../lib/chat";
import type { Mood } from "./Mascot";
import { GotaImg } from "./GotaImg";

export const TEMAS = [
  { id: null, label: "Todo" }, { id: "peces", label: "Pescado" }, { id: "salud", label: "Salud" },
  { id: "mineria", label: "Minería" }, { id: "agua", label: "Agua" },
] as const;

const SUGERENCIAS = [
  "¿Qué pescado puedo dar a mis hijos?",
  "¿Cuáles son los síntomas del mercurio?",
  "¿Es peligroso quemar la amalgama en casa?",
];

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
  const { turnos, draft, setDraft, busy, err, ask, tema, setTema } = useChat();
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turnos, busy]);
  useEffect(() => { if (autoFocus) input.current?.focus(); }, [autoFocus]);

  return (
    <div className={compact ? "thread thread-compact" : "thread"}>
      <div className="thread-scroll" aria-live="polite">
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
            <div key={i} className="msg msg-user">{t.texto}</div>
          ) : (
            <div key={i} className="msg-row">
              <span className="avatar"><GotaImg size={compact ? 40 : 50} label="Gota" still /></span>
              <div className="msg msg-bot">
                {t.texto}
                {t.fuentes && t.fuentes.length > 0 && (
                  <div className="fuentes">
                    {unicas(t.fuentes).slice(0, 5).map((f, j) => (
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
              <span className="avatar"><GotaImg size={compact ? 40 : 50} mood="thinking" label="Gota pensando" /></span>
              <div className="msg msg-bot"><span className="skeleton" style={{ display: "block", width: 160, height: 14 }} /></div>
            </div>
          )}
          {err && <p className="field-error" role="alert">No pude responder: {err}</p>}
          <div ref={end} />
        </div>
      </div>

      <form className={compact ? "ask-row" : "marigold-bar"} style={compact ? undefined : { marginTop: 16 }}
        onSubmit={(e) => { e.preventDefault(); ask(draft); }}>
        <div className="field">
          <label className={compact ? "visually-hidden" : "label"} htmlFor={compact ? "pregunta-w" : "pregunta"}>Tu pregunta</label>
          <input ref={input} id={compact ? "pregunta-w" : "pregunta"} className="input" value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Escribe en palabras simples" maxLength={500} autoComplete="off" enterKeyHint="send" />
        </div>
        <button className="btn" type="submit" disabled={busy || !draft.trim()} aria-label="Preguntar">
          {compact ? (
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M3 9h11M10 4.5L14.5 9 10 13.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
          ) : "Preguntar"}
        </button>
      </form>
    </div>
  );
}

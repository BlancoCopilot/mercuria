import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useChat } from "../lib/chat";
import { ChatThread, estadoVoz } from "./ChatThread";
import { Mascot, type Mood } from "./Mascot";

// Estado corto (una línea) para la cabecera del widget
const ESTADO: Record<Mood, string> = {
  idle: "¿En qué te ayudo?",
  listening: "Te escucho…",
  thinking: "Buscando…",
  talking: "Esto encontré",
};

// Chat siempre a mano: Gota abajo a la derecha en todas las pantallas; al tocarla se despliega el chat.
// En celular el chat ocupa la pantalla. No aparece en /preguntar (ahí el chat ya es la página).
export function ChatWidget() {
  const { open, setOpen, mood, turnos, err, clear, voz } = useChat();
  const loc = useLocation();
  const fab = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [hint, setHint] = useState(() => { try { return !localStorage.getItem("rastrohg.chat-visto"); } catch { return false; } });
  const enPagina = loc.pathname.startsWith("/preguntar");

  useEffect(() => { if (enPagina) setOpen(false); }, [enPagina, setOpen]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); fab.current?.focus(); } };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  // En celular, con el chat abierto, la página de fondo no se desplaza
  useEffect(() => {
    if (!open || !window.matchMedia("(max-width: 720px)").matches) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  if (enPagina) return null;

  const abrir = () => {
    setOpen(true);
    setHint(false);
    try { localStorage.setItem("rastrohg.chat-visto", "1"); } catch { /* */ }
  };

  return (
    <>
      {open && (
        <div ref={panel} className="chat-panel" role="dialog" aria-modal="false" aria-label="Chat con Gota">
          <header className="chat-panel-head">
            <Mascot mood={mood} size={58} />
            <div className="chat-panel-title">
              <strong>Gota</strong>
              <span className="small muted" aria-live="polite">{estadoVoz(voz) ?? (err ? "Uy, no pude responder." : ESTADO[mood])}</span>
            </div>
            <div className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
              {turnos.length > 0 && !voz.activo && <button className="btn btn-quiet small" onClick={clear} title="Empezar una conversación nueva">Nueva</button>}
              <Link className="btn btn-quiet small hide-sm" to="/preguntar" onClick={() => setOpen(false)} title="Abrir el chat en pantalla completa">Ampliar</Link>
              <button className="icon-btn" onClick={() => { if (voz.activo) voz.terminar(); setOpen(false); fab.current?.focus(); }} aria-label="Cerrar chat">
                <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
              </button>
            </div>
          </header>
          <ChatThread compact autoFocus />
        </div>
      )}

      {!open && hint && (
        <button className="fab-hint" onClick={abrir}>¿Dudas sobre el mercurio? Pregúntame</button>
      )}
      <button ref={fab} className="fab" data-open={open} onClick={() => (open ? setOpen(false) : abrir())}
        aria-expanded={open} aria-label={open ? "Cerrar chat con Gota" : "Abrir chat: pregúntale a Gota"}>
        <Mascot mood={open ? mood : "idle"} size={64} label="" />
      </button>
    </>
  );
}

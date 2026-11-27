import { useEffect, useRef, useState } from "react";
import { useChat } from "../lib/chat";
import { estadoVoz } from "./ChatThread";
import { Mascot } from "./Mascot";

// Llamada con Gota: pantalla de llamada (tarjeta centrada en computadora, pantalla completa en celular).
// Gota grande mueve la boca con su voz real; anillos que laten cuando alguien habla; cronómetro;
// subtítulos en vivo; botones redondos de silenciar y colgar. Lo hablado queda transcrito en el chat.

export const PhoneIcon = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
    <path fill="currentColor" d="M6.62 10.79a15.05 15.05 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.02-.24c1.12.37 2.33.57 3.57.57a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1C10.61 21 3 13.39 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1.02l-2.2 2.2z" />
  </svg>
);

const HangUpIcon = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" aria-hidden="true">
    <path fill="currentColor" d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08a.96.96 0 0 1-.29-.7c0-.28.11-.53.29-.71C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.67c.18.18.29.43.29.71 0 .28-.11.53-.29.71l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.11-.7-.28a11.3 11.3 0 0 0-2.67-1.85.99.99 0 0 1-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z" />
  </svg>
);

const MicIcon = ({ off }: { off?: boolean }) => (
  <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <rect x="8.5" y="2.5" width="7" height="12" rx="3.5" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3.5" />
    {off && <path d="M3.5 3.5l17 17" strokeWidth="2" />}
  </svg>
);

const mmss = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

export function CallScreen() {
  const { voz, turnos, setOpen } = useChat();
  const visible = voz.activo || voz.estado === "cerrando" || voz.estado === "error";
  const [ahora, setAhora] = useState(() => Date.now());
  const dur = useRef(0);
  const colgar = useRef<HTMLButtonElement>(null);
  const antes = useRef(voz.estado);

  useEffect(() => {
    if (!voz.desde) return;
    const t = window.setInterval(() => setAhora(Date.now()), 500);
    return () => window.clearInterval(t);
  }, [voz.desde]);
  if (voz.desde) dur.current = Math.max(0, Math.floor((ahora - voz.desde) / 1000));

  // al colgar, abre el chat para ver la transcripción (en /preguntar el chat ya es la página)
  useEffect(() => {
    if (antes.current === "cerrando" && voz.estado === "apagado") setOpen(true);
    if (voz.estado === "conectando" || voz.estado === "pidiendo_mic") dur.current = 0;
    antes.current = voz.estado;
  }, [voz.estado, setOpen]);

  useEffect(() => { if (visible) colgar.current?.focus(); }, [visible]);

  useEffect(() => {
    if (!visible) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [visible]);

  if (!visible) return null;

  const fallo = voz.estado === "error";
  const terminada = voz.estado === "cerrando";
  const llamando = voz.estado === "conectando" || voz.estado === "pidiendo_mic";
  const mute = voz.silenciado && !terminada;      // al colgar, el servidor silencia la entrada: no mostrarlo
  const estado = fallo ? (voz.error ?? "No se pudo conectar.") : terminada ? "Llamada terminada"
    : voz.estado === "conectando" ? "Llamando…" : estadoVoz(voz);
  const quien = voz.hablaGota ? "gota" : voz.hablaPersona && !voz.silenciado ? "persona" : "";
  const mood = voz.hablaGota ? "talking" : voz.buscando || llamando ? "thinking" : "idle";

  // subtítulo: lo último que se dijo en esta llamada
  const ultimo = [...turnos].reverse().find((t) => t.voz);
  const sub = ultimo && voz.desde ? (ultimo.texto.length > 150 ? "…" + ultimo.texto.slice(-150).replace(/^\S*\s/, "") : ultimo.texto) : null;

  return (
    <div className="call-backdrop">
      <div className="call" role="dialog" aria-modal="true" aria-label="Llamada con Gota" data-estado={voz.estado}>
        <header className="call-top">
          <span className="call-kicker"><PhoneIcon size={14} /> Llamada con Gota</span>
          <span className="call-timer num" aria-label={`Duración ${mmss(dur.current)}`}>
            {voz.desde || terminada ? mmss(dur.current) : ""}
          </span>
        </header>

        <div className="call-center">
          <div className="call-avatar" data-who={quien} data-llamando={llamando}>
            <span className="call-ring" aria-hidden="true" />
            <span className="call-ring call-ring-2" aria-hidden="true" />
            <Mascot mood={mood} size={176} label="Gota" />
          </div>
          <h2 className="call-name">Gota</h2>
          <p className={fallo ? "call-status call-status-error" : "call-status"} aria-live="polite">{estado}</p>
          {voz.restante !== null && voz.restante <= 60 && !terminada && (
            <p className="call-warn">La llamada se corta en {voz.restante} s</p>
          )}
        </div>

        <div className="call-sub" aria-hidden={!sub}>
          {sub ? <><span className="call-sub-who">{ultimo!.rol === "usuario" ? "Tú" : "Gota"}</span>{sub}</>
            : <span className="muted">{llamando ? "Conectando la llamada…" : "Aquí aparece lo que se dice."}</span>}
        </div>

        <footer className="call-actions">
          {fallo ? (
            <>
              <button className="call-btn" onClick={voz.descartar}>
                <span className="call-btn-circle"><svg width="22" height="22" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg></span>
                <span className="call-btn-label">Cerrar</span>
              </button>
              <button ref={colgar} className="call-btn call-btn-go" onClick={() => { voz.descartar(); void voz.empezar(); }}>
                <span className="call-btn-circle"><PhoneIcon size={28} /></span>
                <span className="call-btn-label">Volver a llamar</span>
              </button>
            </>
          ) : (
            <>
              <button className="call-btn" onClick={voz.silenciar} aria-pressed={mute} disabled={voz.estado !== "activo"}>
                <span className="call-btn-circle"><MicIcon off={mute} /></span>
                <span className="call-btn-label">{mute ? "Activar micrófono" : "Silenciar"}</span>
              </button>
              <button ref={colgar} className="call-btn call-btn-end" onClick={voz.terminar} disabled={terminada}>
                <span className="call-btn-circle"><HangUpIcon /></span>
                <span className="call-btn-label">Colgar</span>
              </button>
            </>
          )}
        </footer>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, post } from "./api";

// Conversación por voz con Gota (GPT-Live por WebRTC).
// El servidor crea la sesión con la oferta SDP (la clave de OpenAI nunca llega al navegador).
// GPT-Live escucha y habla; las preguntas las resuelve un modelo de texto que llama a
// `buscar_documentos` (lo atendemos aquí con /v1/chat/voz/buscar) o busca en internet.

export type EstadoVoz = "apagado" | "pidiendo_mic" | "conectando" | "activo" | "cerrando" | "error";
export type Buscando = null | "documentos" | "internet" | "pensando";
export interface FuenteVoz { tipo: string; titulo?: string; archivo?: string; pagina?: number | null; url?: string; [k: string]: unknown }

interface Opciones {
  /** Fragmento de transcripción (en orden de llegada). */
  onTexto: (rol: "usuario" | "asistente", delta: string) => void;
  /** Fuentes consultadas para la respuesta en curso. */
  onFuentes: (f: FuenteVoz[]) => void;
  /** Datos para iniciar: zona aproximada y chat previo. */
  contexto: () => { historial: { rol: string; texto: string }[]; lat?: number; lon?: number; comunidad_id?: number | null };
}

type Evento = { type: string; [k: string]: unknown };
type Item = { type?: string; name?: string; call_id?: string; arguments?: string };

const UMBRAL_HABLA = 0.035;

function nivel(an: AnalyserNode, buf: Uint8Array<ArrayBuffer>): number {
  an.getByteTimeDomainData(buf);
  let s = 0;
  for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; s += v * v; }
  return Math.sqrt(s / buf.length);
}

export function useVoz({ onTexto, onFuentes, contexto }: Opciones) {
  const [estado, setEstado] = useState<EstadoVoz>("apagado");
  const [error, setError] = useState<string | null>(null);
  const [hablaGota, setHablaGota] = useState(false);
  const [hablaPersona, setHablaPersona] = useState(false);
  const [buscando, setBuscando] = useState<Buscando>(null);
  const [silenciado, setSilenciado] = useState(false);
  const [restante, setRestante] = useState<number | null>(null);
  const [desde, setDesde] = useState<number | null>(null);          // inicio de la llamada (para el cronómetro)

  const pc = useRef<RTCPeerConnection | null>(null);
  const dc = useRef<RTCDataChannel | null>(null);
  const mic = useRef<MediaStream | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const raf = useRef<number>(0);
  const fin = useRef<number>(0);
  const tick = useRef<number>(0);
  // fuentes de la delegación en curso: los documentos solo cuentan si no hizo falta buscar en internet
  const deleg = useRef<{ docs: FuenteVoz[]; web: boolean }>({ docs: [], web: false });
  const cb = useRef({ onTexto, onFuentes, contexto });
  cb.current = { onTexto, onFuentes, contexto };

  const limpiar = useCallback(() => {
    cancelAnimationFrame(raf.current);
    window.clearTimeout(fin.current);
    window.clearInterval(tick.current);
    dc.current?.close(); dc.current = null;
    pc.current?.getSenders().forEach((s) => s.track?.stop());
    pc.current?.close(); pc.current = null;
    mic.current?.getTracks().forEach((t) => t.stop()); mic.current = null;
    if (audio.current) { audio.current.srcObject = null; audio.current.remove(); audio.current = null; }
    ctx.current?.close().catch(() => {}); ctx.current = null;
    setHablaGota(false); setHablaPersona(false); setBuscando(null); setSilenciado(false); setRestante(null); setDesde(null);
  }, []);

  useEffect(() => limpiar, [limpiar]);

  const enviar = (e: Evento) => { if (dc.current?.readyState === "open") dc.current.send(JSON.stringify(e)); };

  const terminar = useCallback(() => {
    if (!pc.current) { setEstado("apagado"); return; }
    setEstado("cerrando");
    enviar({ type: "session.close" });
    // se espera session.closed; si no llega, se corta igual
    window.setTimeout(() => { limpiar(); setEstado((s) => (s === "error" ? s : "apagado")); }, 1200);
  }, [limpiar]);

  const atenderHerramienta = async (it: Item) => {
    let out: unknown;
    try {
      const args = JSON.parse(it.arguments || "{}") as { pregunta?: string; tema?: string | null };
      const r = await post<{ documentos: string; fuentes: FuenteVoz[] }>("/v1/chat/voz/buscar", { pregunta: args.pregunta || "", tema: args.tema ?? null });
      deleg.current.docs = r.fuentes;
      out = { documentos: r.documentos };
    } catch (e) {
      out = { error: `No se pudo buscar en los documentos (${(e as Error).message}). Usa la búsqueda web o dilo.` };
    }
    enviar({ type: "response.item.create", item: { type: "function_call_output", call_id: it.call_id, output: JSON.stringify(out) } });
    enviar({ type: "response.create" });
    setBuscando("pensando");
  };

  const onEvento = (ev: Evento) => {
    switch (ev.type) {
      case "session.started": setEstado("activo"); setDesde(Date.now()); break;
      case "session.input_transcript.delta": cb.current.onTexto("usuario", String(ev.delta ?? "")); break;
      case "session.output_transcript.delta": cb.current.onTexto("asistente", String(ev.delta ?? "")); setBuscando(null); break;
      case "session.delegation.created": deleg.current = { docs: [], web: false }; setBuscando("pensando"); break;
      case "session.input_audio.muted": setSilenciado(true); break;
      case "session.input_audio.unmuted": setSilenciado(false); break;
      case "session.closed": limpiar(); setEstado("apagado"); break;
      case "error": {
        const er = ev.error as { message?: string; code?: string } | undefined;
        console.warn("[voz] error", er);
        if (er?.code !== "function_call_outputs_required") setError(er?.message || "Error en la conversación");
        break;
      }
      case "response.event": {
        const r = ev.event as { type: string; item?: Item; annotation?: { type?: string; url?: string; title?: string } };
        if (r.type === "response.output_item.added" && r.item?.type === "web_search_call") { deleg.current.web = true; setBuscando("internet"); }
        else if (r.type === "response.output_item.done" && r.item?.type === "message") {
          if (!deleg.current.web && deleg.current.docs.length) cb.current.onFuentes(deleg.current.docs);
          deleg.current.docs = [];
        }
        else if (r.type === "response.output_item.done" && r.item?.type === "function_call" && r.item.name === "buscar_documentos") {
          setBuscando("documentos");
          void atenderHerramienta(r.item);
        } else if (r.type === "response.output_text.annotation.added" && r.annotation?.type === "url_citation" && r.annotation.url) {
          let host = r.annotation.url;
          try { host = new URL(r.annotation.url).hostname.replace(/^www\./, ""); } catch { /* */ }
          cb.current.onFuentes([{ tipo: "web", url: r.annotation.url.replace(/[?&]utm_source=openai$/, ""), titulo: r.annotation.title || host, archivo: host }]);
        } else if (r.type === "response.failed") setBuscando(null);
        break;
      }
    }
  };

  const empezar = useCallback(async () => {
    if (pc.current) return;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || !window.RTCPeerConnection) {
      setError("Este navegador no permite hablar con Gota. Prueba con Chrome, Safari o Firefox actualizados."); setEstado("error"); return;
    }
    setEstado("pidiendo_mic");
    try {
      mic.current = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    } catch {
      setError("Necesito permiso para usar el micrófono. Actívalo en el candado de la barra de direcciones."); setEstado("error"); return;
    }
    setEstado("conectando");
    try {
      const conn = new RTCPeerConnection();
      pc.current = conn;
      const el = document.createElement("audio");
      el.autoplay = true; el.setAttribute("playsinline", "");
      document.body.appendChild(el);
      audio.current = el;
      const ac = new AudioContext();
      ctx.current = ac;
      const anMic = ac.createAnalyser(); anMic.fftSize = 512;
      ac.createMediaStreamSource(mic.current).connect(anMic);
      let anGota: AnalyserNode | null = null;
      conn.ontrack = (e) => {
        el.srcObject = e.streams[0];
        anGota = ac.createAnalyser(); anGota.fftSize = 512;
        ac.createMediaStreamSource(e.streams[0]).connect(anGota);
      };
      conn.onconnectionstatechange = () => {
        if (conn.connectionState === "failed" || conn.connectionState === "disconnected") {
          setError("Se cortó la conexión."); limpiar(); setEstado("error");
        }
      };
      conn.addTrack(mic.current.getAudioTracks()[0], mic.current);
      const ch = conn.createDataChannel("oai-events");
      dc.current = ch;
      ch.onmessage = (m) => { try { onEvento(JSON.parse(m.data)); } catch { /* */ } };

      // nivel de voz de cada lado → boca de Gota / "te escucho"
      const buf = new Uint8Array(new ArrayBuffer(512));
      // se mantiene "hablando" 450 ms después del último sonido: si no, parpadea entre sílabas
      let ultPersona = 0, ultGota = 0;
      const loop = () => {
        const t = performance.now();
        if (nivel(anMic, buf) > UMBRAL_HABLA) ultPersona = t;
        if (anGota && nivel(anGota, buf) > UMBRAL_HABLA * 0.6) ultGota = t;
        setHablaPersona(t - ultPersona < 450);
        setHablaGota(t - ultGota < 450);
        raf.current = requestAnimationFrame(loop);
      };
      loop();

      const offer = await conn.createOffer();
      await conn.setLocalDescription(offer);
      const r = await post<{ sdp: string; session_id: string; max_minutes: number }>("/v1/chat/voz", { sdp: offer.sdp, ...cb.current.contexto() });
      await conn.setRemoteDescription({ type: "answer", sdp: r.sdp });
      void ac.resume();
      const hasta = Date.now() + r.max_minutes * 60_000;
      setRestante(r.max_minutes * 60);
      tick.current = window.setInterval(() => setRestante(Math.max(0, Math.round((hasta - Date.now()) / 1000))), 1000);
      fin.current = window.setTimeout(() => terminar(), r.max_minutes * 60_000);
    } catch (e) {
      limpiar();
      setError(e instanceof ApiError ? e.message : "No se pudo iniciar la voz. Intenta de nuevo o escribe tu pregunta.");
      setEstado("error");
    }
  }, [limpiar, terminar]);   // eslint-disable-line react-hooks/exhaustive-deps

  const silenciar = useCallback(() => {
    const t = mic.current?.getAudioTracks()[0];
    if (!t) return;
    t.enabled = !t.enabled;            // corta el audio en el navegador
    setSilenciado(!t.enabled);
    enviar({ type: t.enabled ? "session.input_audio.unmute" : "session.input_audio.mute" });
  }, []);

  /** Cierra la pantalla de una llamada que falló. */
  const descartar = useCallback(() => { setError(null); setEstado("apagado"); }, []);

  return { estado, error, hablaGota, hablaPersona, buscando, silenciado, restante, desde, empezar, terminar, silenciar, descartar,
    activo: estado === "activo" || estado === "conectando" || estado === "pidiendo_mic" };
}

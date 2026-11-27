import { useCallback, useEffect, useState } from "react";
import { uuid } from "../lib/api";
import { enviarCola, readQueue, writeQueue } from "../lib/cola";
import { IconAgua, IconCheck, IconMineria, IconOtro, IconPez, IconSalud, IconUbicar } from "./icons";
import { pedirUbicacion } from "./native";
import { posicionActual } from "../lib/location";

// Avisar: lo mismo que /denunciar en la web, sin mapa: el lugar es donde está el teléfono.
const TIPOS = [
  { id: "mineria", label: "Minería nueva", help: "Dragas, balsas, desmonte", Icon: IconMineria },
  { id: "peces_muertos", label: "Peces muertos", help: "Flotando o enfermos", Icon: IconPez },
  { id: "agua_turbia", label: "Agua rara", help: "Color, olor o espuma", Icon: IconAgua },
  { id: "salud", label: "Gente enferma", help: "Varias personas con síntomas", Icon: IconSalud },
  { id: "otro", label: "Otra cosa", help: "Algo que te preocupa", Icon: IconOtro },
];

type Lugar = { estado: "buscando" } | { estado: "listo"; lat: number; lon: number; precision: number } | { estado: "error" };

export function AvisarScreen() {
  const [kind, setKind] = useState<string | null>(null);
  const [desc, setDesc] = useState("");
  const [lugar, setLugar] = useState<Lugar>({ estado: "buscando" });
  const [pendientes, setPendientes] = useState(readQueue().length);
  const [msg, setMsg] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const ubicar = useCallback(async () => {
    setLugar({ estado: "buscando" });
    if (!(await pedirUbicacion())) { setLugar({ estado: "error" }); return; }
    try {
      const p = await posicionActual();
      setLugar({ estado: "listo", lat: p.lat, lon: p.lon, precision: p.precision });
    } catch { setLugar({ estado: "error" }); }
  }, []);

  const enviar = useCallback(async () => {
    setEnviando(true);
    try {
      const n = await enviarCola();
      if (n) setMsg(n === 1 ? "Aviso enviado. Gracias." : `${n} avisos enviados. Gracias.`);
    } catch {
      setMsg("Sin señal: tu aviso quedó guardado y se enviará solo.");
    } finally {
      setPendientes(readQueue().length);
      setEnviando(false);
    }
  }, []);

  useEffect(() => {
    ubicar();
    enviar();
    const on = () => enviar();
    window.addEventListener("online", on);
    return () => window.removeEventListener("online", on);
  }, [ubicar, enviar]);

  const listo = !!kind && lugar.estado === "listo";
  const guardar = () => {
    if (!kind || lugar.estado !== "listo") return;
    writeQueue([...readQueue(), {
      client_uuid: uuid(), kind, description: desc.trim() || null, lat: lugar.lat, lon: lugar.lon,
      area_ha: null, created_client_at: new Date().toISOString(),
    }]);
    setKind(null); setDesc("");
    setPendientes(readQueue().length);
    if (navigator.onLine) enviar(); else setMsg("Sin señal: tu aviso quedó guardado y se enviará solo.");
  };

  return (
    <div className="m-page">
      <header className="m-titulo">
        <h1>Avisar</h1>
        <p className="lead">Es anónimo: no pedimos tu nombre. Funciona sin señal.</p>
      </header>

      <fieldset className="m-tipos">
        <legend className="m-label">¿Qué viste?</legend>
        {TIPOS.map(({ id, label, help, Icon }) => (
          <label key={id} className="m-tipo" data-on={kind === id}>
            <input type="radio" name="tipo" value={id} checked={kind === id} onChange={() => setKind(id)} className="visually-hidden" />
            <Icon />
            <span className="m-tipo-label">{label}</span>
            <span className="caption m-tipo-help">{help}</span>
          </label>
        ))}
      </fieldset>

      <div className="field-row">
        <label className="m-label" htmlFor="m-desc">¿Algo más? <span className="muted">(si quieres)</span></label>
        <textarea id="m-desc" className="textarea" maxLength={1000} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Qué, desde cuándo, cuántos…" />
      </div>

      <div className="m-donde" data-estado={lugar.estado}>
        <IconUbicar />
        <p className="small">
          {lugar.estado === "buscando" && "Buscando dónde estás…"}
          {lugar.estado === "listo" && <>Lugar: donde estás ahora <span className="muted">(± {Math.round(lugar.precision)} m)</span></>}
          {lugar.estado === "error" && "No pudimos saber dónde estás. Activa la ubicación del teléfono."}
        </p>
        {lugar.estado !== "buscando" && <button className="btn btn-pill" onClick={ubicar}>{lugar.estado === "error" ? "Intentar" : "Actualizar"}</button>}
      </div>

      <button className="btn btn-block m-cta" onClick={guardar} disabled={!listo || enviando}>
        {navigator.onLine ? "Enviar aviso" : "Guardar para enviar después"}
      </button>
      {!kind && <p className="caption muted m-centrado">Elige qué viste para poder enviar.</p>}

      {msg && <p className="m-ok" role="status"><IconCheck /> {msg}</p>}
      {pendientes > 0 && (
        <p className="notice notice-warn small" role="status">
          {pendientes === 1 ? "1 aviso espera señal." : `${pendientes} avisos esperan señal.`} Se enviarán solos.
        </p>
      )}
    </div>
  );
}

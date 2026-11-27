import { useCallback, useEffect, useState } from "react";
import { uuid } from "../lib/api";
import { enviarCola, readQueue, writeQueue, type Pendiente } from "../lib/cola";
import { PageHead } from "../components/Layout";
import { PointPicker } from "../components/PointPicker";
import { Toast } from "../components/ui";
import { useToast } from "../lib/hooks";
import { fecha } from "../lib/format";

const TIPOS = [
  { id: "mineria", label: "Minería nueva", help: "Dragas, balsas, desmonte o maquinaria" },
  { id: "peces_muertos", label: "Peces muertos", help: "Muchos peces flotando o enfermos" },
  { id: "agua_turbia", label: "Agua turbia o rara", help: "Color, olor o espuma inusual" },
  { id: "salud", label: "Problema de salud", help: "Varias personas con síntomas" },
  { id: "otro", label: "Otro", help: "Cualquier otra cosa que preocupe" },
];

export default function ReportPage() {
  const [kind, setKind] = useState("mineria");
  const [desc, setDesc] = useState("");
  const [area, setArea] = useState("");
  const [pt, setPt] = useState<{ lat: number; lon: number } | null>(null);
  const [queue, setQueue] = useState<Pendiente[]>(readQueue);
  const [online, setOnline] = useState(navigator.onLine);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const { toast, show } = useToast();

  const flush = useCallback(async () => {
    if (!readQueue().length || !navigator.onLine) return;
    setSending(true);
    try {
      const n = await enviarCola();
      setQueue(readQueue());
      show(n === 1 ? "Denuncia enviada. Gracias." : `${n} denuncias enviadas. Gracias.`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSending(false);
    }
  }, [show]);

  useEffect(() => {
    const on = () => { setOnline(true); flush(); };
    const offl = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", offl);
    flush();
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", offl); };
  }, [flush]);

  const ubicar = () => {
    setErr(null);
    navigator.geolocation?.getCurrentPosition(
      (p) => setPt({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => setErr("No pudimos obtener tu ubicación. Marca el lugar en el mapa."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!pt) { setErr("Marca el lugar en el mapa o usa tu ubicación."); return; }
    const item: Pendiente = {
      client_uuid: uuid(), kind, description: desc.trim() || null, lat: pt.lat, lon: pt.lon,
      area_ha: kind === "mineria" && area ? Number(area) : null, created_client_at: new Date().toISOString(),
    };
    const q = [...readQueue(), item];
    writeQueue(q);
    setQueue(q);
    setDesc(""); setArea("");
    if (navigator.onLine) flush(); else show("Sin señal: guardada. Se enviará sola cuando vuelva la conexión.");
  };

  return (
    <div className="page">
      <PageHead title="Reportar de forma anónima">
        No pedimos tu nombre ni guardamos tu ubicación exacta en el mapa público: solo la zona. Funciona sin señal.
      </PageHead>

      <div className="grid-2">
        <form className="form-panel" onSubmit={submit} noValidate>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }} className="stack">
            <legend className="label" style={{ marginBottom: 8 }}>¿Qué viste?</legend>
            {TIPOS.map((t) => (
              <label key={t.id} className="check">
                <input type="radio" name="kind" value={t.id} checked={kind === t.id} onChange={() => setKind(t.id)} />
                <span><span style={{ fontWeight: 500 }}>{t.label}</span><br /><span className="small muted">{t.help}</span></span>
              </label>
            ))}
          </fieldset>
          {kind === "mineria" && (
            <div className="field-row">
              <label className="label" htmlFor="area">Tamaño aproximado (hectáreas, opcional)</label>
              <input id="area" className="input num" type="number" inputMode="decimal" min="0.1" max="500" step="0.1" value={area} onChange={(e) => setArea(e.target.value)} placeholder="Ej.: 2 (una cancha de fútbol ≈ 0,7)" />
            </div>
          )}
          <div className="field-row">
            <label className="label" htmlFor="desc">Detalles (opcional)</label>
            <textarea id="desc" className="textarea" maxLength={1000} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Qué, desde cuándo, cuántos…" />
          </div>
          {err && <p className="field-error" role="alert">{err}</p>}
          <button className="btn btn-block" type="submit" disabled={sending}>{online ? "Enviar" : "Guardar para enviar después"}</button>
          <p className="caption muted">Cada denuncia pesa poco en el mapa (0,2 frente a 1 de un dato de laboratorio) hasta que un líder la valide o el satélite la confirme.</p>
        </form>

        <div className="stack">
          <div className="spread">
            <span className="label">Lugar {pt && <span className="muted num" style={{ textTransform: "none", letterSpacing: 0 }}>· {pt.lat.toFixed(4)}, {pt.lon.toFixed(4)}</span>}</span>
            <button className="btn btn-pill" type="button" onClick={ubicar}>Usar mi ubicación</button>
          </div>
          <PointPicker value={pt} onChange={setPt} />
          <p className="small muted">Toca el mapa para marcar el lugar. Puedes arrastrar el punto.</p>

          {queue.length > 0 && (
            <div className="notice notice-warn" role="status">
              <strong style={{ fontWeight: 500 }}>{queue.length === 1 ? "1 denuncia" : `${queue.length} denuncias`} esperando señal</strong>
              <span className="small">Última guardada el {fecha(queue[queue.length - 1].created_client_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}.</span>
              {online && <div><button className="btn btn-pill" onClick={flush} disabled={sending}>{sending ? "Enviando…" : "Enviar ahora"}</button></div>}
            </div>
          )}
        </div>
      </div>
      <Toast msg={toast} />
    </div>
  );
}

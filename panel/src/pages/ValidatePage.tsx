import { useEffect, useState } from "react";
import { api, post, session } from "../lib/api";
import { useApi, useToast } from "../lib/hooks";
import { fecha, num } from "../lib/format";
import { PageHead } from "../components/Layout";
import { PointPicker } from "../components/PointPicker";
import { Empty, ErrorNote, Skeleton, Toast } from "../components/ui";

interface Denuncia { id: string; kind: string; description: string | null; status: string; area_ha: number | null; site_id: number | null; tiene_foto: boolean; lat: number; lon: number; created_client_at: string; received_at: string }
interface Trad { key: string; es: string; traduccion: { id: number; text: string; audio_path: string | null; status: string } | null }

const TIPO: Record<string, string> = { mineria: "Minería nueva", agua_turbia: "Agua turbia", peces_muertos: "Peces muertos", salud: "Salud", otro: "Otro" };
const LANGS = [["qu", "Quechua"], ["ay", "Aymara"], ["gn", "Guaraní"]] as const;

export default function ValidatePage() {
  const [tab, setTab] = useState<"denuncias" | "traducciones">("denuncias");
  const { toast, show } = useToast();
  return (
    <div className="page">
      <PageHead title="Validación comunitaria">Revisa las denuncias de tu zona y graba las frases de la ficha en tu idioma.</PageHead>
      <div className="tabs" style={{ marginBottom: 32 }}>
        <button className="btn btn-pill" aria-pressed={tab === "denuncias"} onClick={() => setTab("denuncias")}>Denuncias pendientes</button>
        <button className="btn btn-pill" aria-pressed={tab === "traducciones"} onClick={() => setTab("traducciones")}>Traducciones y audio</button>
      </div>
      {tab === "denuncias" ? <Denuncias onMsg={show} /> : <Traducciones onMsg={show} />}
      <Toast msg={toast} />
    </div>
  );
}

function Denuncias({ onMsg }: { onMsg: (m: string) => void }) {
  const { data, error, loading, reload } = useApi<Denuncia[]>("/v1/reports?status=pendiente");
  const [sel, setSel] = useState<Denuncia | null>(null);
  const [foto, setFoto] = useState<string | null>(null);

  useEffect(() => { if (data?.length && !sel) setSel(data[0]); }, [data, sel]);
  useEffect(() => {
    setFoto(null);
    if (!sel?.tiene_foto) return;
    let url: string | null = null;
    fetch(`/v1/reports/${sel.id}/photo`, { headers: { Authorization: `Bearer ${session.token}` } })
      .then((r) => (r.ok ? r.blob() : null)).then((b) => { if (b) { url = URL.createObjectURL(b); setFoto(url); } });
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [sel]);

  const decidir = async (d: "validada" | "rechazada") => {
    if (!sel) return;
    try {
      await post(`/v1/reports/${sel.id}/review`, { decision: d });
      onMsg(d === "validada" ? "Denuncia validada." : "Denuncia rechazada: su sitio sale del mapa.");
      setSel(null); reload();
    } catch (e) { onMsg((e as Error).message); }
  };

  if (loading) return <Skeleton lines={6} />;
  if (error) return <ErrorNote error={error} retry={reload} />;
  if (!data?.length) return <Empty title="No hay denuncias pendientes">Cuando alguien reporte desde la app o la web, aparecerá aquí para que la revises.</Empty>;
  return (
    <div className="grid-2">
      <div className="list">
        {data.map((d) => (
          <button key={d.id} onClick={() => setSel(d)} className="list-item"
            style={{ textAlign: "left", background: sel?.id === d.id ? "var(--paper-2)" : "transparent", border: 0, borderBottom: "1px solid var(--charcoal-10)", borderRadius: 12, padding: 16, cursor: "pointer" }}>
            <span className="spread"><span style={{ fontWeight: 500 }}>{TIPO[d.kind] ?? d.kind}</span><span className="caption muted">{fecha(d.created_client_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span></span>
            <span className="small muted">{d.description || "Sin detalles"}{d.area_ha ? ` · ${num(d.area_ha)} ha` : ""}{d.tiene_foto ? " · con foto" : ""}</span>
          </button>
        ))}
      </div>
      {sel && (
        <div className="stack">
          <PointPicker value={{ lat: sel.lat, lon: sel.lon }} onChange={() => undefined} height={280} />
          <p className="caption muted num">Ubicación exacta {sel.lat.toFixed(5)}, {sel.lon.toFixed(5)}: solo la ven los líderes. En el mapa público se muestra la zona.</p>
          {foto && <img src={foto} alt="Foto de la denuncia (sin metadatos)" style={{ borderRadius: 20, maxHeight: 320, objectFit: "cover" }} />}
          {new Date(sel.received_at).getTime() - new Date(sel.created_client_at).getTime() > 3600_000 && (
            <p className="small muted">Hecha sin señal y sincronizada después.</p>
          )}
          <div className="row">
            <button className="btn" onClick={() => decidir("validada")}>Validar</button>
            <button className="btn btn-danger" onClick={() => decidir("rechazada")}>Rechazar</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Traducciones({ onMsg }: { onMsg: (m: string) => void }) {
  const [lang, setLang] = useState<string>("qu");
  const { data, error, loading, reload } = useApi<Trad[]>(`/v1/translations?lang=${lang}`, [lang]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  useEffect(() => setDraft({}), [lang]);

  const guardar = async (key: string) => {
    const text = draft[key]?.trim();
    if (!text) return;
    try { await api("/v1/translations", { method: "PUT", body: JSON.stringify({ key, lang, text }) }); onMsg("Traducción guardada como borrador."); reload(); }
    catch (e) { onMsg((e as Error).message); }
  };
  const audio = async (id: number, f: File | undefined) => {
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try { await post(`/v1/translations/${id}/audio`, fd); onMsg("Audio subido."); reload(); } catch (e) { onMsg((e as Error).message); }
  };
  const validar = async (id: number) => {
    try { await post(`/v1/translations/${id}/validate`, {}); onMsg("Validada: ya aparece en las fichas."); reload(); } catch (e) { onMsg((e as Error).message); }
  };

  return (
    <div className="stack">
      <div className="tabs">{LANGS.map(([k, l]) => <button key={k} className="btn btn-pill" aria-pressed={lang === k} onClick={() => setLang(k)}>{l}</button>)}</div>
      {loading ? <Skeleton lines={8} /> : error ? <ErrorNote error={error} retry={reload} /> : (
        <div className="list" style={{ maxWidth: 980 }}>
          {data?.map((t) => (
            <div key={t.key} className="list-item" style={{ gap: 10 }}>
              <div className="spread">
                <span className="caption muted">{t.key}</span>
                {t.traduccion && <span className={`tag ${t.traduccion.status === "validada" ? "" : "tag-marigold"}`}>{t.traduccion.status}{t.traduccion.audio_path ? " · con audio" : ""}</span>}
              </div>
              <p>{t.es}</p>
              <textarea className="textarea" style={{ minHeight: 56 }} aria-label={`Traducción de ${t.key}`}
                value={draft[t.key] ?? t.traduccion?.text ?? ""} onChange={(e) => setDraft((d) => ({ ...d, [t.key]: e.target.value }))}
                placeholder="Escribe la frase en tu idioma (puedes dejar {comunidad} y {peces} tal cual)" />
              <div className="row">
                <button className="btn btn-pill" onClick={() => guardar(t.key)} disabled={!draft[t.key]?.trim()}>Guardar texto</button>
                {t.traduccion && (
                  <label className="btn btn-pill" style={{ cursor: "pointer" }}>
                    Subir audio
                    <input type="file" accept="audio/*" hidden onChange={(e) => audio(t.traduccion!.id, e.target.files?.[0])} />
                  </label>
                )}
                {t.traduccion && t.traduccion.status !== "validada" && <button className="btn" onClick={() => validar(t.traduccion!.id)}>Validar</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

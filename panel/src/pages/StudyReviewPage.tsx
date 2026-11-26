import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, post, session } from "../lib/api";
import { useApi, useToast } from "../lib/hooks";
import { num } from "../lib/format";
import { PointPicker } from "../components/PointPicker";
import { ErrorNote, Skeleton, Toast } from "../components/ui";
import { ESTADO_ESTUDIO } from "./ContributePage";

interface Registro {
  id: number; status: "propuesto" | "aprobado" | "rechazado"; problems: string[]; modeled: boolean;
  fields: Record<string, unknown>; value_canonical: number | null; unit_canonical: string | null;
  lat: number | null; lon: number | null; precision_m: number | null; location_source: string | null; weight: number | null;
  measurement_id: string | null;
}
interface Detalle {
  estudio: { id: number; title: string; status: string; source_kind: string; license: string; embargo_until: string | null;
    summary: string | null; warnings: string[]; error: string | null; extraction_model: string | null };
  registros: Registro[]; cita: string;
}

type Filtro = "todos" | "mapa" | "problemas" | "aprobados";

export default function StudyReviewPage() {
  const { id } = useParams();
  const { data, error, loading, reload, setData } = useApi<Detalle>(`/v1/studies/${id}`);
  const [pdf, setPdf] = useState<string | null>(null);
  const [abierto, setAbierto] = useState<number | null>(null);
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [lic, setLic] = useState("CC-BY-4.0");
  const [embargo, setEmbargo] = useState("");
  const { toast, show } = useToast();
  const st = data?.estudio;

  // Mientras la IA lee, se consulta cada 4 s
  useEffect(() => {
    if (st?.status !== "procesando") return;
    const t = setInterval(reload, 4000);
    return () => clearInterval(t);
  }, [st?.status, reload]);

  useEffect(() => {
    if (!st || st.source_kind !== "pdf") return;
    let url: string | null = null;
    fetch(`/v1/studies/${st.id}/file`, { headers: { Authorization: `Bearer ${session.token}` } })
      .then((r) => (r.ok ? r.blob() : null)).then((b) => { if (b) { url = URL.createObjectURL(b); setPdf(url); } });
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [st?.id, st?.source_kind]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (st) { setLic(st.license); setEmbargo(st.embargo_until ?? ""); } }, [st?.license, st?.embargo_until]);   // eslint-disable-line react-hooks/exhaustive-deps

  const regs = useMemo(() => (data?.registros ?? []).filter((r) =>
    filtro === "todos" ? true : filtro === "mapa" ? r.modeled : filtro === "aprobados" ? r.status === "aprobado" : r.problems.length > 0), [data, filtro]);

  const guardar = async (r: Registro, cambios: Record<string, unknown> | null, status?: Registro["status"]) => {
    try {
      const nuevo = await api<Registro>(`/v1/studies/${id}/records/${r.id}`, { method: "PATCH", body: JSON.stringify({ fields: cambios, status }) });
      setData((d) => d && { ...d, registros: d.registros.map((x) => (x.id === r.id ? nuevo : x)) });
    } catch (e) { show((e as Error).message); }
  };

  if (loading && !data) return <div className="page"><Skeleton lines={8} /></div>;
  if (error || !data || !st) return <div className="page"><ErrorNote error={error ?? "No encontrado"} retry={reload} /></div>;

  const aprobados = data.registros.filter((r) => r.status === "aprobado").length;
  const alMapa = data.registros.filter((r) => r.status === "aprobado" && r.modeled).length;
  const publicado = st.status === "publicado" || st.status === "embargado";

  const publicar = async () => {
    try {
      const r = await post<{ estado: string; al_mapa: number; hasta?: string }>(`/v1/studies/${id}/publish`, { license: lic, embargo_until: embargo || null });
      show(r.estado === "embargado" ? `Publicado con embargo hasta ${r.hasta}.` : `Publicado: ${r.al_mapa} puntos entran al mapa. Se está recalculando.`);
      reload();
    } catch (e) { show((e as Error).message); }
  };
  const aprobarTodo = async () => {
    try { const r = await post<{ aprobados: number }>(`/v1/studies/${id}/approve-all`, {}); show(`${r.aprobados} valores aprobados.`); reload(); }
    catch (e) { show((e as Error).message); }
  };

  return (
    <div className="page review-page">
      <Link to="/aportar" className="btn btn-quiet" style={{ marginBottom: 16 }}>← Mis estudios</Link>
      <div className="page-head">
        <span className="meta">{ESTADO_ESTUDIO[st.status] ?? st.status}{st.extraction_model ? ` · leído por ${st.extraction_model}` : ""}</span>
        <h1 style={{ fontSize: 32 }}>{st.title}</h1>
        <p className="small muted">{data.cita}</p>
      </div>

      {st.status === "procesando" && (
        <div className="notice" role="status"><strong style={{ fontWeight: 500 }}>La IA está leyendo tu documento.</strong>
          <span className="small">Suele tardar entre 1 y 3 minutos. Esta página se actualiza sola.</span><div className="skeleton" style={{ height: 8, marginTop: 8 }} /></div>
      )}
      {st.status === "error" && (
        <div className="notice notice-error" role="alert"><strong style={{ fontWeight: 500 }}>No pudimos leer el documento.</strong><span className="small">{st.error}</span>
          <div><button className="btn btn-pill" onClick={async () => { await post(`/v1/studies/${id}/reextract`, {}); reload(); }}>Intentar de nuevo</button></div></div>
      )}

      {st.status !== "procesando" && st.status !== "error" && (
        <>
          {(st.summary || st.warnings.length > 0) && (
            <div className="grid-2" style={{ marginBottom: 32 }}>
              {st.summary && <div className="stack" style={{ gap: 6 }}><span className="label">Resumen</span><p className="small">{st.summary}</p></div>}
              {st.warnings.length > 0 && <div className="stack" style={{ gap: 6 }}><span className="label">La IA advierte</span>
                <ul className="small" style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 4 }}>{st.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
            </div>
          )}

          <div className="review-grid">
            {pdf && <iframe className="review-pdf" src={pdf} title="Documento original" />}
            <div className="stack" style={{ gap: 16 }}>
              <div className="spread">
                <div className="tabs" role="group" aria-label="Filtrar">
                  {([["todos", `Todos (${data.registros.length})`], ["mapa", "Entran al mapa"], ["problemas", "Con observaciones"], ["aprobados", `Aprobados (${aprobados})`]] as const).map(([k, l]) => (
                    <button key={k} className="btn btn-pill" aria-pressed={filtro === k} onClick={() => setFiltro(k)}>{l}</button>
                  ))}
                </div>
                {!publicado && <button className="btn btn-quiet" onClick={aprobarTodo}>Aprobar los que entran al mapa</button>}
              </div>
              <div className="list">
                {regs.map((r) => <Fila key={r.id} r={r} abierto={abierto === r.id} onToggle={() => setAbierto(abierto === r.id ? null : r.id)} onSave={guardar} bloqueado={!!r.measurement_id} />)}
                {regs.length === 0 && <p className="muted small">Nada con este filtro.</p>}
              </div>
            </div>
          </div>

          <section className="publish-bar">
            <div>
              <strong style={{ fontWeight: 500 }}>{aprobados} valores aprobados · {alMapa} entran al mapa</strong>
              <p className="small muted">{publicado ? "Este estudio ya es dato abierto." : "Los no aprobados no se publican. Los aprobados que no entran al mapa (cabello, suelo…) igual quedan para descarga."}</p>
            </div>
            {!publicado && (
              <div className="row">
                <select className="select" style={{ width: 170 }} value={lic} onChange={(e) => setLic(e.target.value)} aria-label="Licencia">
                  <option value="CC-BY-4.0">CC BY 4.0</option><option value="CC0-1.0">CC0</option><option value="CC-BY-SA-4.0">CC BY-SA 4.0</option>
                </select>
                <input className="input" type="date" style={{ width: 160 }} value={embargo} onChange={(e) => setEmbargo(e.target.value)} aria-label="Embargo hasta (opcional)" title="Embargo hasta (opcional)" />
                <button className="btn" onClick={publicar} disabled={!aprobados}>Publicar como dato abierto</button>
              </div>
            )}
            {publicado && <Link className="btn btn-pill" to="/datos">Ver en Datos abiertos</Link>}
          </section>
        </>
      )}
      <Toast msg={toast} />
    </div>
  );
}

const MATRICES = ["agua", "sedimento", "pez", "cabello", "sangre", "orina", "suelo", "otro"];

function Fila({ r, abierto, onToggle, onSave, bloqueado }: {
  r: Registro; abierto: boolean; onToggle: () => void; bloqueado: boolean;
  onSave: (r: Registro, cambios: Record<string, unknown> | null, status?: Registro["status"]) => void;
}) {
  const f = r.fields as Record<string, string | number | boolean | null>;
  const [ed, setEd] = useState<Record<string, string>>({});
  const [pt, setPt] = useState<{ lat: number; lon: number } | null>(r.lat !== null && r.lon !== null ? { lat: r.lat, lon: r.lon } : null);
  const v = (k: string) => (ed[k] ?? (f[k] === null || f[k] === undefined ? "" : String(f[k])));
  const cambiar = (k: string, x: string) => setEd((e) => ({ ...e, [k]: x }));
  const guardarCambios = () => {
    const c: Record<string, unknown> = {};
    for (const [k, x] of Object.entries(ed)) c[k] = ["valor", "limite_deteccion", "n", "pagina", "_precision_m"].includes(k) ? (x === "" ? null : Number(x.replace(",", "."))) : (x === "" ? null : x);
    if (pt && (pt.lat !== r.lat || pt.lon !== r.lon)) { c.lat = pt.lat; c.lon = pt.lon; }
    onSave(r, Object.keys(c).length ? c : null);
    setEd({});
  };

  return (
    <div className={`list-item rec rec-${r.status}`}>
      <div className="rec-head">
        <button className="rec-main" onClick={onToggle} aria-expanded={abierto}>
          <span className="rec-valor num">{f.bajo_ld ? "< " : ""}{String(f.valor)} {String(f.unidad ?? "")}</span>
          <span className="rec-meta">
            {String(f.matriz)}{f.subtipo ? ` · ${String(f.subtipo).replace(/_/g, " ")}` : ""}{f.estadistico && f.estadistico !== "individual" ? ` · ${String(f.estadistico)}${f.n ? ` (n=${f.n})` : ""}` : ""}
            {" · "}{String(f.lugar ?? "sin lugar")}{f.fecha ? ` · ${String(f.fecha)}` : ""}{f.pagina ? ` · pág. ${f.pagina}` : ""}
          </span>
        </button>
        <div className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
          {r.modeled ? <span className="tag tag-sky" title={`Peso en el modelo ${r.weight}`}>Al mapa</span> : <span className="tag">Solo descarga</span>}
          {!bloqueado && (
            <>
              <button className="btn btn-pill rec-btn" aria-pressed={r.status === "aprobado"} onClick={() => onSave(r, null, r.status === "aprobado" ? "propuesto" : "aprobado")} title="Aprobar">✓</button>
              <button className="btn btn-pill rec-btn" aria-pressed={r.status === "rechazado"} onClick={() => onSave(r, null, r.status === "rechazado" ? "propuesto" : "rechazado")} title="Rechazar">✕</button>
            </>
          )}
        </div>
      </div>
      {r.problems.length > 0 && <ul className="rec-problems">{r.problems.map((p, i) => <li key={i}>{p}</li>)}</ul>}
      {abierto && (
        <div className="rec-edit">
          {f.cita_textual && <blockquote className="small">«{String(f.cita_textual)}»</blockquote>}
          <div className="rec-fields">
            <label><span className="label">Matriz</span><select className="select" value={v("matriz")} onChange={(e) => cambiar("matriz", e.target.value)} disabled={bloqueado}>{MATRICES.map((m) => <option key={m}>{m}</option>)}</select></label>
            <label><span className="label">Valor</span><input className="input num" value={v("valor")} onChange={(e) => cambiar("valor", e.target.value)} disabled={bloqueado} /></label>
            <label><span className="label">Unidad</span><input className="input" value={v("unidad")} onChange={(e) => cambiar("unidad", e.target.value)} disabled={bloqueado} /></label>
            <label><span className="label">Base</span><select className="select" value={v("base")} onChange={(e) => cambiar("base", e.target.value)} disabled={bloqueado}>{["humedo", "seco", "no_aplica", "desconocido"].map((m) => <option key={m}>{m}</option>)}</select></label>
            <label><span className="label">Fecha</span><input className="input" value={v("fecha")} placeholder="AAAA-MM" onChange={(e) => cambiar("fecha", e.target.value)} disabled={bloqueado} /></label>
            <label><span className="label">Estación</span><select className="select" value={v("estacion")} onChange={(e) => cambiar("estacion", e.target.value)} disabled={bloqueado}>{["seca", "humeda", "desconocida"].map((m) => <option key={m}>{m}</option>)}</select></label>
            <label><span className="label">Lugar</span><input className="input" value={v("lugar")} onChange={(e) => cambiar("lugar", e.target.value)} disabled={bloqueado} /></label>
            {f.matriz === "pez" && <label><span className="label">Especie</span><input className="input" value={v("especie_comun") || v("especie_cientifica")} onChange={(e) => cambiar("especie_comun", e.target.value)} disabled={bloqueado} /></label>}
            <label><span className="label">Precisión de la ubicación (m)</span><input className="input num" value={v("_precision_m") || (r.precision_m ? String(r.precision_m) : "")} onChange={(e) => cambiar("_precision_m", e.target.value)} disabled={bloqueado} /></label>
          </div>
          {!bloqueado && (
            <>
              <span className="label">Ubicación {pt ? <span className="muted num" style={{ textTransform: "none", letterSpacing: 0 }}>· {pt.lat.toFixed(4)}, {pt.lon.toFixed(4)} ({r.location_source ?? "manual"}{r.precision_m ? `, ±${num(r.precision_m)} m` : ""})</span> : "· toca el mapa para marcar el sitio"}</span>
              <PointPicker value={pt} onChange={setPt} height={220} />
              <div className="row"><button className="btn" onClick={guardarCambios}>Guardar cambios</button><span className="caption muted">Al guardar se recalcula si entra al mapa.</span></div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

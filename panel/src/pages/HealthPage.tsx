import { useState } from "react";
import { post, uuid, type Comunidad } from "../lib/api";
import { useApi, useToast } from "../lib/hooks";
import { fecha, num } from "../lib/format";
import { PageHead } from "../components/Layout";
import { CommunitySearch } from "../components/CommunitySearch";
import { Empty, ErrorNote, Skeleton, Toast } from "../components/ui";

interface Item { codigo: string; texto: string; puntos?: number }
interface Protocolo { version: string; validado: boolean; sintomas: Item[]; senales_alarma: Item[]; exposicion: Item[] }
interface CasoResp { id: string; triage: "rutina" | "prioritario" | "urgente"; status: string; protocolo_validado: boolean; mensaje: string; centro_sugerido: { id: number; name: string; phone: string | null; km: number } | null }
interface Caso { id: string; comunidad: string; age_group: string; triage: string; status: string; symptoms: string[]; created_at: string }
interface Recordatorio { id: number; case_id: string; due_on: string; kind: string; comunidad: string; triage: string }
interface Campana { id: number; name: string; comunidad: string; planned_on: string; status: string; muestras: number }

const EDADES = [["0-4", "0 a 4 años"], ["5-14", "5 a 14"], ["15-49", "15 a 49"], ["50+", "50 o más"]] as const;
type Tab = "nuevo" | "casos" | "recordatorios" | "campanas";

export default function HealthPage() {
  const [tab, setTab] = useState<Tab>("nuevo");
  const { toast, show } = useToast();
  return (
    <div className="page">
      <PageHead title="Salud y seguimiento">Registra casos con consentimiento, deriva al centro de salud y sigue los controles. No guardamos nombres ni documentos.</PageHead>
      <div className="tabs" role="tablist" style={{ marginBottom: 32 }}>
        {([["nuevo", "Nuevo caso"], ["casos", "Mis casos"], ["recordatorios", "Recordatorios"], ["campanas", "Campañas de cabello"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className="btn btn-pill" aria-pressed={tab === k} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "nuevo" && <NuevoCaso onDone={(m) => show(m)} />}
      {tab === "casos" && <MisCasos onMsg={show} />}
      {tab === "recordatorios" && <Recordatorios onMsg={show} />}
      {tab === "campanas" && <Campanas onMsg={show} />}
      <Toast msg={toast} />
    </div>
  );
}

function NuevoCaso({ onDone }: { onDone: (m: string) => void }) {
  const proto = useApi<Protocolo>("/v1/health/protocol");
  const [com, setCom] = useState<Comunidad | null>(null);
  const [consent, setConsent] = useState(false);
  const [edad, setEdad] = useState<string>("");
  const [sexo, setSexo] = useState<string>("");
  const [emb, setEmb] = useState(false);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<CasoResp | null>(null);
  const toggle = (c: string) => setSel((s) => { const n = new Set(s); n.has(c) ? n.delete(c) : n.add(c); return n; });

  if (proto.loading) return <Skeleton lines={8} />;
  if (proto.error || !proto.data) return <ErrorNote error={proto.error ?? "Sin protocolo"} retry={proto.reload} />;
  const p = proto.data;
  const pick = (list: Item[]) => list.filter((x) => sel.has(x.codigo)).map((x) => x.codigo);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    if (!com) return setErr("Elige la comunidad.");
    if (!consent) return setErr("Sin consentimiento informado no se puede registrar el caso.");
    if (!edad) return setErr("Elige el grupo de edad.");
    setBusy(true);
    const now = new Date().toISOString();
    try {
      const r = await post<CasoResp>("/v1/health/cases", {
        client_uuid: uuid(), settlement_id: com.id, consent_given: true, consent_at: now, age_group: edad,
        sex: sexo || null, pregnant: emb, symptoms: pick(p.sintomas), alarm_signs: pick(p.senales_alarma),
        exposures: pick(p.exposicion), created_client_at: now,
      });
      setRes(r);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  const derivar = async () => {
    if (!res) return;
    setBusy(true);
    try {
      const r = await post<{ recordatorios: string[] }>(`/v1/health/cases/${res.id}/referrals`, { reason: `Triaje ${res.triage}` });
      onDone(`Derivado. Controles el ${r.recordatorios.map((d) => fecha(d, { day: "numeric", month: "short" })).join(", ")}.`);
      setRes(null); setSel(new Set()); setConsent(false); setEdad(""); setSexo(""); setEmb(false);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  if (res) {
    return (
      <div className="stack" style={{ maxWidth: 720 }}>
        <div className={`notice ${res.triage === "urgente" ? "notice-error" : res.triage === "prioritario" ? "notice-warn" : "notice-ok"}`} role="status">
          <span className="meta">Triaje: {res.triage}</span>
          <span style={{ fontSize: 22, fontWeight: 300 }}>{res.mensaje}</span>
          {!res.protocolo_validado && <span className="small">Guía en borrador: sigue el criterio del personal de salud.</span>}
        </div>
        {res.centro_sugerido && (
          <div className="panel-snow stack" style={{ gap: 8 }}>
            <span className="label">Centro sugerido</span>
            <span style={{ fontSize: 22, fontWeight: 300 }}>{res.centro_sugerido.name}</span>
            <span className="muted small">A {num(res.centro_sugerido.km)} km {res.centro_sugerido.phone ? `· ${res.centro_sugerido.phone}` : ""}</span>
          </div>
        )}
        {err && <p className="field-error" role="alert">{err}</p>}
        <div className="row">
          <button className="btn" onClick={derivar} disabled={busy}>Derivar y programar controles</button>
          <button className="btn btn-pill" onClick={() => { setRes(null); onDone("Caso registrado sin derivar."); }}>No derivar ahora</button>
        </div>
      </div>
    );
  }

  return (
    <form className="grid-2" onSubmit={submit} noValidate>
      <div className="form-panel">
        <div className="field-row">
          <span className="label">Comunidad</span>
          <CommunitySearch onPick={setCom} placeholder="Nombre de la comunidad" />
        </div>
        <label className="check" style={{ background: consent ? "transparent" : "#fff1c9", borderRadius: 12, padding: 12 }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span><span style={{ fontWeight: 500 }}>La persona dio su consentimiento informado.</span><br />
            <span className="small muted">Le explicaste para qué se usan los datos y que solo se publican agregados por comunidad (5 casos o más).</span></span>
        </label>
        <div className="field-row">
          <span className="label">Grupo de edad</span>
          <div className="tabs">{EDADES.map(([v, l]) => <button type="button" key={v} className="btn btn-pill" aria-pressed={edad === v} onClick={() => setEdad(v)}>{l}</button>)}</div>
        </div>
        <div className="field-row">
          <span className="label">Sexo (opcional)</span>
          <div className="tabs">{[["f", "Mujer"], ["m", "Hombre"], ["otro", "Otro"]].map(([v, l]) => <button type="button" key={v} className="btn btn-pill" aria-pressed={sexo === v} onClick={() => setSexo(sexo === v ? "" : v)}>{l}</button>)}</div>
        </div>
        {sexo === "f" && edad === "15-49" && (
          <label className="check"><input type="checkbox" checked={emb} onChange={(e) => setEmb(e.target.checked)} /><span>Está embarazada</span></label>
        )}
        {err && <p className="field-error" role="alert">{err}</p>}
        <button className="btn btn-block" disabled={busy}>{busy ? "Registrando…" : "Registrar y ver triaje"}</button>
        {!p.validado && <p className="caption muted">Guía de síntomas {p.version}: pendiente de validación por el Ministerio de Salud.</p>}
      </div>
      <div className="stack">
        <Grupo titulo="Señales de alarma (derivar hoy)" items={p.senales_alarma} sel={sel} toggle={toggle} alarma />
        <Grupo titulo="Síntomas" items={p.sintomas} sel={sel} toggle={toggle} />
        <Grupo titulo="Exposición" items={p.exposicion} sel={sel} toggle={toggle} />
      </div>
    </form>
  );
}

function Grupo({ titulo, items, sel, toggle, alarma }: { titulo: string; items: Item[]; sel: Set<string>; toggle: (c: string) => void; alarma?: boolean }) {
  return (
    <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
      <legend className="label" style={{ marginBottom: 4, color: alarma ? "var(--ember-ink)" : undefined }}>{titulo}</legend>
      {items.map((x) => (
        <label key={x.codigo} className="check"><input type="checkbox" checked={sel.has(x.codigo)} onChange={() => toggle(x.codigo)} /><span>{x.texto}</span></label>
      ))}
    </fieldset>
  );
}

function MisCasos({ onMsg }: { onMsg: (m: string) => void }) {
  const { data, error, loading, reload } = useApi<Caso[]>("/v1/health/cases");
  if (loading) return <Skeleton lines={6} />;
  if (error) return <ErrorNote error={error} retry={reload} />;
  if (!data?.length) return <Empty title="Todavía no registraste casos">Solo ves tus propios casos; nadie más puede verlos.</Empty>;
  const derivar = async (id: string) => {
    try { await post(`/v1/health/cases/${id}/referrals`, {}); onMsg("Caso derivado al centro más cercano."); reload(); }
    catch (e) { onMsg((e as Error).message); }
  };
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>Fecha</th><th>Comunidad</th><th>Edad</th><th>Triaje</th><th>Estado</th><th></th></tr></thead>
        <tbody>{data.map((c) => (
          <tr key={c.id}>
            <td>{fecha(c.created_at)}</td><td>{c.comunidad}</td><td>{c.age_group}</td>
            <td><span className={`tag ${c.triage === "urgente" ? "tag-ember" : c.triage === "prioritario" ? "tag-marigold" : ""}`}>{c.triage}</span></td>
            <td>{c.status}</td>
            <td>{c.status === "registrado" && <button className="btn btn-pill" onClick={() => derivar(c.id)}>Derivar</button>}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function Recordatorios({ onMsg }: { onMsg: (m: string) => void }) {
  const { data, error, loading, reload } = useApi<Recordatorio[]>("/v1/health/reminders?days_ahead=30");
  if (loading) return <Skeleton lines={5} />;
  if (error) return <ErrorNote error={error} retry={reload} />;
  if (!data?.length) return <Empty title="Sin controles en los próximos 30 días">Al derivar un caso se programan controles a los 7, 30 y 90 días.</Empty>;
  const hecho = async (id: number) => {
    try { await post(`/v1/health/reminders/${id}/done`, {}); onMsg("Control marcado como hecho."); reload(); } catch (e) { onMsg((e as Error).message); }
  };
  return (
    <div className="list" style={{ maxWidth: 820 }}>
      {data.map((r) => (
        <div key={r.id} className="list-item" style={{ gridTemplateColumns: "auto 1fr auto", alignItems: "center", gap: 16 }}>
          <span className="num" style={{ fontSize: 22, fontWeight: 300, minWidth: 90 }}>{fecha(r.due_on, { day: "numeric", month: "short" })}</span>
          <span>{r.comunidad} <span className="muted small">· {r.kind.replace("control_", "control a ").replace("d", " días")} · {r.triage}</span></span>
          <button className="btn btn-pill" onClick={() => hecho(r.id)}>Hecho</button>
        </div>
      ))}
    </div>
  );
}

function Campanas({ onMsg }: { onMsg: (m: string) => void }) {
  const { data, error, loading, reload } = useApi<Campana[]>("/v1/health/campaigns");
  const [com, setCom] = useState<Comunidad | null>(null);
  const [nombre, setNombre] = useState("");
  const [dia, setDia] = useState("");
  const crear = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!com || !nombre || !dia) return onMsg("Completa comunidad, nombre y fecha.");
    try { await post("/v1/health/campaigns", { name: nombre, settlement_id: com.id, planned_on: dia }); setNombre(""); setDia(""); onMsg("Campaña creada."); reload(); }
    catch (er) { onMsg((er as Error).message); }
  };
  return (
    <div className="grid-2">
      <form className="form-panel" onSubmit={crear}>
        <h3>Nueva campaña de muestreo de cabello</h3>
        <div className="field-row"><span className="label">Comunidad</span><CommunitySearch onPick={setCom} /></div>
        <div className="field-row"><label className="label" htmlFor="cn">Nombre</label><input id="cn" className="input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej.: Campaña Mayaya 2027" /></div>
        <div className="field-row"><label className="label" htmlFor="cd">Fecha</label><input id="cd" className="input" type="date" value={dia} onChange={(e) => setDia(e.target.value)} /></div>
        <button className="btn">Crear campaña</button>
      </form>
      <div className="stack">
        <h3>Campañas</h3>
        {loading ? <Skeleton lines={4} /> : error ? <ErrorNote error={error} retry={reload} /> : !data?.length ? <Empty title="Sin campañas todavía" /> : (
          <div className="list">{data.map((c) => (
            <div key={c.id} className="list-item" style={{ gridTemplateColumns: "1fr auto" }}>
              <span><span style={{ fontWeight: 500 }}>{c.name}</span><br /><span className="small muted">{c.comunidad} · {fecha(c.planned_on)}</span></span>
              <span className="small num">{c.muestras} muestras · {c.status}</span>
            </div>
          ))}</div>
        )}
        <p className="caption muted">El resumen de resultados se publica solo con 5 muestras o más.</p>
      </div>
    </div>
  );
}

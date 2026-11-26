import { useState } from "react";
import { post } from "../lib/api";
import { useApi, useToast } from "../lib/hooks";
import { fecha, hace } from "../lib/format";
import { PageHead } from "../components/Layout";
import { ErrorNote, Skeleton, Toast } from "../components/ui";

interface Version { id: number; created_at: string; triggers: { tipo: string; ref?: unknown }[]; reaches_changed: number; cells_changed: number; params_hash: string; model_info: Record<string, { n_datos?: number; n_usados?: number; recalibrado?: boolean }> | null }
const ROLES: Record<string, string> = { investigador: "Investigación", laboratorio: "Laboratorio", promotor: "Promotor", lider: "Líder", autoridad: "Autoridad", admin: "Admin" };
interface Outbox { id: number; body: string; status: string; last_error: string | null; created_at: string }

export default function AdminPage() {
  const versions = useApi<Version[]>("/v1/admin/versions?limit=15");
  const outbox = useApi<Outbox[]>("/v1/admin/outbox?limit=10");
  const pendientes = useApi<{ id: number; email: string; name: string; role: string; org: string | null; created_at: string }[]>("/v1/admin/users?pendientes=true");
  const { toast, show } = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [u, setU] = useState({ email: "", name: "", role: "laboratorio", password: "", org: "" });

  const run = async (label: string, path: string) => {
    setBusy(label);
    try { const r = await post<{ job_id: string | null }>(path, {}); show(r.job_id ? `${label}: en cola.` : `${label}: ya había uno en cola.`); setTimeout(versions.reload, 4000); }
    catch (e) { show((e as Error).message); } finally { setBusy(null); }
  };
  const crear = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await post("/v1/admin/users", { ...u, org: u.org || null }); show(`Usuario ${u.email} creado.`); setU({ email: "", name: "", role: "laboratorio", password: "", org: "" }); }
    catch (er) { show((er as Error).message); }
  };

  return (
    <div className="page">
      <PageHead title="Sistema">Versiones del mapa, tareas de actualización, avisos enviados y cuentas del equipo.</PageHead>
      <div className="row" style={{ marginBottom: 48 }}>
        <button className="btn" disabled={!!busy} onClick={() => run("Recálculo", "/v1/admin/recompute")}>Recalcular el mapa</button>
        <button className="btn btn-pill" disabled={!!busy} onClick={() => run("Amazon Mining Watch", "/v1/admin/ingest/amw")}>Actualizar minería (AMW)</button>
        <button className="btn btn-pill" disabled={!!busy} onClick={() => run("OpenStreetMap", "/v1/admin/ingest/osm")}>Actualizar poblados (OSM)</button>
      </div>

      {pendientes.data && pendientes.data.length > 0 && (
        <section className="section" style={{ marginBottom: 48 }}>
          <h2>Solicitudes de cuenta</h2>
          <div className="list">{pendientes.data.map((p) => (
            <div key={p.id} className="list-item" style={{ gridTemplateColumns: "1fr auto", alignItems: "center" }}>
              <span><span style={{ fontWeight: 500 }}>{p.name}</span> · {p.org ?? "sin institución"}<br /><span className="small muted">{p.email} · {ROLES[p.role] ?? p.role} · {hace(p.created_at)}</span></span>
              <button className="btn" onClick={async () => { try { await post(`/v1/admin/users/${p.id}/activate`, {}); show(`Cuenta de ${p.name} activada.`); pendientes.reload(); } catch (e) { show((e as Error).message); } }}>Activar</button>
            </div>
          ))}</div>
        </section>
      )}

      <section className="section">
        <h2>Versiones del mapa</h2>
        {versions.loading ? <Skeleton lines={6} /> : versions.error ? <ErrorNote error={versions.error} retry={versions.reload} /> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th className="r">Versión</th><th>Cuándo</th><th>Por qué</th><th className="r">Tramos</th><th className="r">Zonas</th><th>Datos usados</th></tr></thead>
              <tbody>{versions.data?.filter((v) => v.id > 0).map((v) => (
                <tr key={v.id}>
                  <td className="r">{v.id}</td>
                  <td title={fecha(v.created_at)}>{hace(v.created_at)}</td>
                  <td>{[...new Set(v.triggers.map((t) => t.tipo))].join(", ")}</td>
                  <td className="r">{v.reaches_changed}</td><td className="r">{v.cells_changed}</td>
                  <td className="small muted">{v.model_info ? Object.entries(v.model_info).map(([m, x]) => `${m} ${x.n_usados ?? x.n_datos ?? 0}`).join(" · ") : "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      <div className="grid-2 section">
        <div className="stack">
          <h2>Avisos a teléfonos</h2>
          {outbox.loading ? <Skeleton lines={4} /> : outbox.error ? <ErrorNote error={outbox.error} retry={outbox.reload} /> : !outbox.data?.length ? (
            <p className="muted">Aún no se generaron avisos. Se crean cuando una zona cambia de nivel y hay teléfonos suscritos.</p>
          ) : (
            <div className="list">{outbox.data.map((o) => (
              <div key={o.id} className="list-item">
                <span>{o.body}</span>
                <span className="caption muted">{o.status}{o.last_error ? ` · ${o.last_error}` : ""} · {hace(o.created_at)}</span>
              </div>
            ))}</div>
          )}
        </div>
        <form className="form-panel" onSubmit={crear}>
          <h3>Nueva cuenta</h3>
          <div className="field-row"><label className="label" htmlFor="un">Nombre</label><input id="un" className="input" required value={u.name} onChange={(e) => setU({ ...u, name: e.target.value })} /></div>
          <div className="field-row"><label className="label" htmlFor="ue">Correo</label><input id="ue" className="input" type="email" required value={u.email} onChange={(e) => setU({ ...u, email: e.target.value })} /></div>
          <div className="field-row"><label className="label" htmlFor="ur">Rol</label>
            <select id="ur" className="select" value={u.role} onChange={(e) => setU({ ...u, role: e.target.value })}>
              <option value="laboratorio">Laboratorio</option><option value="promotor">Promotor de salud</option><option value="lider">Líder comunitario</option><option value="autoridad">Autoridad</option><option value="investigador">Investigación</option><option value="admin">Administración</option>
            </select></div>
          <div className="field-row"><label className="label" htmlFor="uo">Organización (opcional)</label><input id="uo" className="input" value={u.org} onChange={(e) => setU({ ...u, org: e.target.value })} /></div>
          <div className="field-row"><label className="label" htmlFor="up">Contraseña inicial (mínimo 10)</label><input id="up" className="input" type="password" minLength={10} required value={u.password} onChange={(e) => setU({ ...u, password: e.target.value })} /></div>
          <button className="btn">Crear cuenta</button>
        </form>
      </div>
      <Toast msg={toast} />
    </div>
  );
}

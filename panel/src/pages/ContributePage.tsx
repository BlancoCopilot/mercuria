import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { fecha, int } from "../lib/format";
import { PageHead } from "../components/Layout";
import { Empty, ErrorNote, Skeleton } from "../components/ui";

interface MiEstudio {
  id: number; title: string; year: number | null; status: string; source_kind: string; license: string;
  embargo_until: string | null; created_at: string; registros: number; aprobados: number; en_mapa: number;
}

export const ESTADO_ESTUDIO: Record<string, string> = {
  procesando: "La IA está leyendo el documento…", en_revision: "Listo para revisar", publicado: "Publicado",
  embargado: "Publicado con embargo", error: "No se pudo leer", retirado: "Retirado",
};

export default function ContributePage() {
  const { user, can } = useAuth();
  return (
    <div className="page">
      <PageHead title="Aportar datos">
        Sube tu artículo, tesis o informe en PDF, o un CSV con tus mediciones. La IA propone los puntos para el mapa, tú los revisas y se publican como datos abiertos con tu nombre.
      </PageHead>
      {user && can("investigador") ? <MisEstudios /> : <Presentacion logged={!!user} />}
    </div>
  );
}

function Presentacion({ logged }: { logged: boolean }) {
  return (
    <div className="grid-2">
      <div className="stack" style={{ gap: 24 }}>
        <ol className="pasos">
          <li><strong>Sube tu investigación.</strong> PDF de un artículo, tesis o informe, o un CSV con tus mediciones (agua, sedimento, peces, cabello).</li>
          <li><strong>La IA la lee.</strong> Encuentra cada valor de mercurio con su sitio, fecha, unidad y método, y cita la página de donde salió. No inventa: lo que tu documento no dice queda vacío.</li>
          <li><strong>Tú revisas.</strong> Corriges, ubicas los sitios sin coordenadas y apruebas. Nada entra al mapa sin tu confirmación.</li>
          <li><strong>Se publica.</strong> Tus datos alimentan el mapa de riesgo y quedan para descarga libre (CC BY 4.0 por defecto) con tu cita y DOI.</li>
        </ol>
        <div className="panel">
          <h3 style={{ marginBottom: 8 }}>Para que tu dato sirva, incluye</h3>
          <p className="small">Coordenadas (o UTM con zona) · fecha o al menos mes y año · tipo de muestra (agua total o filtrada, sedimento de fondo o en suspensión, especie de pez y tejido) · valor, unidad y si es peso seco o húmedo · límite de detección · método y laboratorio · si el pez se capturó en un río o se compró en un mercado.</p>
        </div>
        <p className="small muted">¿Ya tienes cuenta? <Link to="/ingresar?volver=/aportar">Ingresa aquí</Link>. Los datos de todos ya se pueden descargar en <Link to="/datos">Datos abiertos</Link>.</p>
      </div>
      {logged ? (
        <div className="notice">
          <strong style={{ fontWeight: 500 }}>Tu cuenta no tiene el rol de investigador.</strong>
          <span className="small">Pide a la administración que te lo asigne, o crea una cuenta de investigador con otro correo.</span>
        </div>
      ) : <SolicitarCuenta />}
    </div>
  );
}

function SolicitarCuenta() {
  const [f, setF] = useState({ name: "", email: "", institution: "", password: "", motivo: "" });
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null); setBusy(true);
    try { setOk((await post<{ mensaje: string }>("/v1/auth/solicitar-cuenta", { ...f, motivo: f.motivo || null })).mensaje); }
    catch (er) { setErr((er as Error).message); } finally { setBusy(false); }
  };
  if (ok) return <div className="notice notice-ok" role="status"><strong style={{ fontWeight: 500 }}>Solicitud enviada</strong><span className="small">{ok}</span></div>;
  return (
    <form className="form-panel" onSubmit={submit}>
      <h3>Solicitar cuenta de investigador</h3>
      <p className="small muted">Para universidades, centros de investigación, ONG y laboratorios. Una persona del equipo la revisa.</p>
      {([["name", "Nombre completo", "text", "name"], ["email", "Correo institucional", "email", "email"], ["institution", "Institución", "text", "organization"]] as const).map(([k, l, t, ac]) => (
        <div key={k} className="field-row">
          <label className="label" htmlFor={`sc-${k}`}>{l}</label>
          <input id={`sc-${k}`} className="input" type={t} autoComplete={ac} required value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
        </div>
      ))}
      <div className="field-row">
        <label className="label" htmlFor="sc-pw">Contraseña (mínimo 10 caracteres)</label>
        <input id="sc-pw" className="input" type="password" autoComplete="new-password" minLength={10} required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
      </div>
      <div className="field-row">
        <label className="label" htmlFor="sc-mo">¿Qué datos aportarías? (opcional)</label>
        <textarea id="sc-mo" className="textarea" maxLength={1000} value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} />
      </div>
      {err && <p className="field-error" role="alert">{err}</p>}
      <button className="btn btn-block" disabled={busy}>{busy ? "Enviando…" : "Solicitar cuenta"}</button>
    </form>
  );
}

function MisEstudios() {
  const lista = useApi<MiEstudio[]>("/v1/studies");
  const nav = useNavigate();
  const file = useRef<HTMLInputElement>(null);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [m, setM] = useState({ title: "", authors: "", year: "", doi: "", institution: "", license: "CC-BY-4.0", embargo_until: "", pdf_open_access: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  const pick = (f?: File) => {
    setErr(null);
    if (!f) return;
    if (!/\.(pdf|csv|txt)$/i.test(f.name)) { setErr("Sube un PDF o un CSV."); return; }
    setArchivo(f);
    if (!m.title) setM((x) => ({ ...x, title: f.name.replace(/\.(pdf|csv|txt)$/i, "").replace(/[_-]+/g, " ") }));
  };

  const subir = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!archivo) { setErr("Elige el archivo."); return; }
    setBusy(true); setErr(null);
    const fd = new FormData();
    fd.append("file", archivo);
    Object.entries(m).forEach(([k, v]) => { if (v !== "" && v !== false) fd.append(k, String(v)); });
    try {
      const r = await post<{ id: number }>("/v1/studies", fd);
      nav(`/aportar/${r.id}`);
    } catch (er) { setErr((er as Error).message); setBusy(false); }
  };

  return (
    <div className="stack" style={{ gap: 48 }}>
      <form className="grid-2" onSubmit={subir}>
        <div className="drop" data-over={over} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}>
          <h3>{archivo ? archivo.name : "Suelta aquí tu PDF o CSV"}</h3>
          <p className="small muted">{archivo ? `${int(archivo.size / 1024)} KB` : "Artículo, tesis, informe técnico o tabla de mediciones. Máximo 40 MB."}</p>
          <input ref={file} type="file" accept=".pdf,.csv,.txt,application/pdf,text/csv" hidden onChange={(e) => pick(e.target.files?.[0])} />
          <button type="button" className="btn btn-pill" onClick={() => file.current?.click()}>{archivo ? "Cambiar archivo" : "Elegir archivo"}</button>
        </div>
        <div className="form-panel">
          <div className="field-row"><label className="label" htmlFor="st-t">Título</label><input id="st-t" className="input" required minLength={3} value={m.title} onChange={(e) => setM({ ...m, title: e.target.value })} /></div>
          <div className="field-row"><label className="label" htmlFor="st-a">Autores (opcional: la IA los toma del PDF)</label><input id="st-a" className="input" value={m.authors} onChange={(e) => setM({ ...m, authors: e.target.value })} /></div>
          <div className="row" style={{ gap: 20, alignItems: "end" }}>
            <div className="field-row" style={{ flex: "1 1 90px" }}><label className="label" htmlFor="st-y">Año</label><input id="st-y" className="input num" inputMode="numeric" value={m.year} onChange={(e) => setM({ ...m, year: e.target.value.replace(/\D/g, "").slice(0, 4) })} /></div>
            <div className="field-row" style={{ flex: "3 1 200px" }}><label className="label" htmlFor="st-d">DOI (opcional)</label><input id="st-d" className="input" placeholder="10.xxxx/…" value={m.doi} onChange={(e) => setM({ ...m, doi: e.target.value })} /></div>
          </div>
          <div className="field-row"><label className="label" htmlFor="st-l">Licencia de los datos</label>
            <select id="st-l" className="select" value={m.license} onChange={(e) => setM({ ...m, license: e.target.value })}>
              <option value="CC-BY-4.0">CC BY 4.0: libre uso citando la fuente (recomendada)</option>
              <option value="CC0-1.0">CC0: dominio público</option>
              <option value="CC-BY-SA-4.0">CC BY-SA 4.0: citar y compartir igual</option>
            </select></div>
          <div className="field-row"><label className="label" htmlFor="st-e">Embargo (opcional, máximo 12 meses)</label>
            <input id="st-e" className="input" type="date" value={m.embargo_until} min={new Date().toISOString().slice(0, 10)} onChange={(e) => setM({ ...m, embargo_until: e.target.value })} />
            <span className="caption muted">Si aún no publicas tu artículo: los datos se publican solos en esa fecha.</span></div>
          <label className="check"><input type="checkbox" checked={m.pdf_open_access} onChange={(e) => setM({ ...m, pdf_open_access: e.target.checked })} /><span className="small">El PDF es de acceso abierto (se puede enlazar)</span></label>
          {err && <p className="field-error" role="alert">{err}</p>}
          <button className="btn btn-block" disabled={busy || !archivo}>{busy ? "Subiendo…" : "Subir y extraer datos"}</button>
        </div>
      </form>

      <section className="section" style={{ gap: 12 }}>
        <h2>Mis estudios</h2>
        {lista.loading ? <Skeleton lines={4} /> : lista.error ? <ErrorNote error={lista.error} retry={lista.reload} /> : !lista.data?.length ? (
          <Empty title="Todavía no subiste estudios">Tu primer aporte aparece aquí mientras la IA lo lee y hasta que lo publiques.</Empty>
        ) : (
          <div className="list">
            {lista.data.map((s) => (
              <Link key={s.id} to={`/aportar/${s.id}`} className="list-item dl-row" style={{ color: "inherit", textDecoration: "none" }}>
                <div>
                  <span style={{ fontSize: 18, fontWeight: 300 }}>{s.title}</span>
                  <p className="small muted">{s.source_kind.toUpperCase()} · subido {fecha(s.created_at)} · {int(s.registros)} valores propuestos · {int(s.aprobados)} aprobados · {int(s.en_mapa)} en el mapa</p>
                </div>
                <span className={`tag ${s.status === "publicado" ? "tag-sky" : s.status === "en_revision" ? "tag-marigold" : s.status === "error" ? "tag-ember" : ""}`}>{ESTADO_ESTUDIO[s.status] ?? s.status}</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

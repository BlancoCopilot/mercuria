import { useRef, useState } from "react";
import { post } from "../lib/api";
import { useApi } from "../lib/hooks";
import { fecha, MATRIZ, num } from "../lib/format";
import { PageHead } from "../components/Layout";
import { Empty, ErrorNote, Skeleton, SyntheticTag } from "../components/ui";

interface Resultado {
  lote: string; recalculo_pendiente: boolean;
  validas: { fila: number; id: string; reach_id: number | null }[];
  en_revision: { fila: number; id: string; motivo?: string }[];
  errores: { fila: number; error: string }[];
}
interface Medicion {
  id: string; matrix: string; value: number; unit: string; value_original: number; unit_original: string; below_dl: boolean; season: string | null; source_type: string;
  weight: number; fish_species: string | null; status: string; reach_id: number | null; snap_m: number | null; sampled_on: string | null; is_synthetic: boolean;
}

const mu = (u: string) => u.replace(/^ug/i, "µg");

export default function LabPage() {
  const [over, setOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Resultado | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filtro, setFiltro] = useState<{ matrix: string; status: string }>({ matrix: "", status: "" });
  const input = useRef<HTMLInputElement>(null);
  const qs = new URLSearchParams(Object.entries(filtro).filter(([, v]) => v)).toString();
  const lista = useApi<Medicion[]>(`/v1/measurements?limit=100${qs ? `&${qs}` : ""}`, [qs]);

  const pick = (f: File | undefined) => {
    setErr(null); setRes(null);
    if (!f) return;
    if (!/\.(csv|txt)$/i.test(f.name)) { setErr("El archivo debe ser CSV (separado por comas o punto y coma)."); return; }
    if (f.size > 5 * 1024 * 1024) { setErr("El archivo supera 5 MB."); return; }
    setFile(f);
  };

  const subir = async () => {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      setRes(await post<Resultado>("/v1/measurements/csv", fd));
      setFile(null);
      lista.reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <PageHead title="Resultados de laboratorio">
        Sube un CSV con tus resultados. Cada dato se convierte a la unidad del modelo, se ubica en el río más cercano y recalcula solo los tramos que afecta.
      </PageHead>

      <div className="grid-2">
        <div
          className="drop" data-over={over}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
        >
          <h3>{file ? file.name : "Suelta aquí el archivo CSV"}</h3>
          <p className="muted small">{file ? `${num(file.size / 1024)} KB listo para subir` : "o elígelo desde tu computador. Acepta coma o punto y coma, y decimales con coma."}</p>
          <input ref={input} type="file" accept=".csv,text/csv,.txt" hidden onChange={(e) => pick(e.target.files?.[0])} />
          <div className="row">
            {!file && <button className="btn btn-pill" onClick={() => input.current?.click()}>Elegir archivo</button>}
            {file && <button className="btn" onClick={subir} disabled={busy}>{busy ? "Subiendo…" : "Subir resultados"}</button>}
            {file && <button className="btn btn-quiet" onClick={() => setFile(null)} disabled={busy}>Cancelar</button>}
          </div>
          {err && <p className="field-error" role="alert">{err}</p>}
        </div>
        <div className="stack">
          <h3>Formato</h3>
          <p className="muted small">
            Columnas obligatorias: <span className="num">matriz, valor, unidad, lat, lon</span>. Recomendadas: fecha de muestreo, tipo de fuente
            (laboratorio, kit o publicado), especie del pez, si está bajo el límite de detección, y la estación (seca o húmeda).
          </p>
          <ul className="small" style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }}>
            <li>Bajo el límite de detección: pon el límite en <span className="num">valor</span> y <span className="num">bajo_ld = si</span>.</li>
            <li>Pez sin especie conocida queda en revisión: el mercurio cambia mucho entre especies.</li>
            <li>Si el punto está en un arroyo junto a un río grande, indica <span className="num">tramo_id</span>.</li>
          </ul>
          <a className="btn btn-pill" style={{ justifySelf: "start" }} href="/v1/measurements/template.csv" download="plantilla_rastrohg.csv">Descargar plantilla</a>
        </div>
      </div>

      {res && (
        <section className="section" style={{ marginTop: 48 }} aria-live="polite">
          <h2>Resultado de la carga</h2>
          <div className="row">
            <span className="tag" style={{ background: "#dcebdc" }}>{res.validas.length} entraron al modelo</span>
            <span className="tag tag-marigold">{res.en_revision.length} en revisión</span>
            <span className="tag tag-ember">{res.errores.length} con errores</span>
          </div>
          {res.recalculo_pendiente && <p className="muted small">El mapa se está recalculando con estos datos.</p>}
          {(res.en_revision.length > 0 || res.errores.length > 0) && (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th className="r">Fila</th><th>Estado</th><th>Motivo</th></tr></thead>
                <tbody>
                  {res.errores.map((e) => <tr key={`e${e.fila}`}><td className="r">{e.fila}</td><td>Error</td><td>{e.error}</td></tr>)}
                  {res.en_revision.map((e) => <tr key={`r${e.fila}`}><td className="r">{e.fila}</td><td>En revisión</td><td>{e.motivo}</td></tr>)}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <section className="section" style={{ marginTop: 64 }}>
        <div className="spread">
          <h2>Mediciones cargadas</h2>
          <div className="row">
            <select className="select" style={{ width: 200 }} value={filtro.matrix} onChange={(e) => setFiltro((f) => ({ ...f, matrix: e.target.value }))} aria-label="Filtrar por matriz">
              <option value="">Todas las matrices</option>
              {Object.entries(MATRIZ).map(([k, v]) => <option key={k} value={k}>{v.nombre}</option>)}
            </select>
            <select className="select" style={{ width: 180 }} value={filtro.status} onChange={(e) => setFiltro((f) => ({ ...f, status: e.target.value }))} aria-label="Filtrar por estado">
              <option value="">Todos los estados</option><option value="valido">Válidas</option><option value="en_revision">En revisión</option><option value="rechazado">Rechazadas</option>
            </select>
          </div>
        </div>
        {lista.loading ? <Skeleton lines={6} /> : lista.error ? <ErrorNote error={lista.error} retry={lista.reload} /> : !lista.data?.length ? (
          <Empty title="Aún no hay mediciones con este filtro">Sube tu primer CSV arriba; puedes partir de la plantilla.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Muestreo</th><th>Matriz</th><th className="r">Valor</th><th>Original</th><th>Fuente</th><th className="r">Peso</th><th>Estado</th><th className="r">Tramo</th></tr></thead>
              <tbody>{lista.data.map((m) => (
                <tr key={m.id}>
                  <td>{fecha(m.sampled_on)}</td>
                  <td>{MATRIZ[m.matrix]?.nombre ?? m.matrix}{m.fish_species ? ` · ${m.fish_species}` : ""} <SyntheticTag show={m.is_synthetic} /></td>
                  <td className="r" title={m.below_dl ? "Bajo el límite de detección" : undefined}>{m.below_dl ? "< " : ""}{num(m.value, 3)} {mu(m.unit)}</td>
                  <td className="muted">{num(m.value_original, 3)} {mu(m.unit_original)}{m.season ? ` · ${m.season === "humeda" ? "húmeda" : "seca"}` : ""}</td>
                  <td>{m.source_type}</td>
                  <td className="r">{num(m.weight)}</td>
                  <td>{m.status === "valido" ? "Válida" : m.status === "en_revision" ? "En revisión" : "Rechazada"}</td>
                  <td className="r">{m.reach_id ?? "—"}{m.snap_m !== null && <span className="caption muted"> · {num(m.snap_m)} m</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

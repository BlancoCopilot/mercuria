import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as maplibregl from "maplibre-gl";
import { api, post } from "../lib/api";
import { useApi, useToast } from "../lib/hooks";
import { int, MATRIZ, num, pct } from "../lib/format";
import { createMap, loadBaseStyle } from "../lib/map";
import { PageHead } from "../components/Layout";
import { Empty, ErrorNote, Facts, RiskChip, Skeleton, Toast } from "../components/ui";
import { Multiples, type Serie } from "../components/Multiples";

interface Resumen {
  version_mapa: number; sitios_activos: number; sin_concesion: number; en_area_protegida: number; hg_kg_anio_p50: number | null;
  celdas_alto: number; personas_riesgo_alto: number; celdas_inciertas: number; mediciones: number; mediciones_sinteticas: number;
}
interface Prioridades {
  campanas_salud: { h3: string; risk_class: "alto" | "medio" | "bajo"; risk: number; confidence: number; poblacion: number; prioridad: number; comunidades: string | null; casos: number; accion: string }[];
  recuperacion_ecosistema: { reach_id: number; sedimento_mg_kg_p50: number; p95: number; presion_kg_anio: number; sitios: number }[];
}
interface Sugerencias {
  version: number | null; matrix: string; explicacion: string;
  sugerencias: { rank: number; reach_id: number; reduccion_pct: number; comunidad_cercana: string | null; lat: number; lon: number; p05: number | null; p50: number | null; p95: number | null; n_cercanos: number | null }[];
}

/** Quita los "(sin nombre)" de OSM y repetidos. */
const limpiar = (s: string | null) => [...new Set((s ?? "").split(",").map((x) => x.trim()).filter((x) => x && x !== "(sin nombre)"))].join(", ");

const SERIES: Serie[] = [
  { key: "minas_nuevas", titulo: "Minas nuevas", ayuda: "primera detección" },
  { key: "celdas_riesgo_alto", titulo: "Zonas en riesgo alto", ayuda: "al cierre del mes" },
  { key: "personas_alcanzadas", titulo: "Personas alcanzadas", ayuda: "fichas, audios y charlas" },
  { key: "casos_derivados", titulo: "Casos derivados", ayuda: "a centros de salud" },
  { key: "mediciones", titulo: "Mediciones cargadas", ayuda: "laboratorio, kits y publicadas" },
];

export default function DecisionPage() {
  const resumen = useApi<Resumen>("/v1/dashboard/summary");
  const prio = useApi<Prioridades>("/v1/dashboard/priorities?limit=8");
  const ind = useApi<Record<string, number | string>[]>("/v1/dashboard/indicators?months=12");

  return (
    <div className="page">
      <PageHead title="Panel de decisión" aside={resumen.data && <span className="tag">Mapa versión {resumen.data.version_mapa}</span>}>
        Dónde hacer campañas de salud, dónde muestrear primero y dónde recuperar el río.
      </PageHead>

      {resumen.loading ? <Skeleton lines={2} height={40} /> : resumen.error ? <ErrorNote error={resumen.error} retry={resumen.reload} /> : resumen.data && (
        <Facts items={[
          { label: "Personas en zonas de riesgo alto", value: int(resumen.data.personas_riesgo_alto) },
          { label: "Zonas en riesgo alto", value: int(resumen.data.celdas_alto) },
          { label: "Sitios mineros activos", value: int(resumen.data.sitios_activos) },
          { label: "Sitios en áreas protegidas", value: int(resumen.data.en_area_protegida) },
          { label: "Hg liberado estimado (kg/año, mediana)", value: num(resumen.data.hg_kg_anio_p50) },
          { label: "Zonas donde no sabemos bien", value: int(resumen.data.celdas_inciertas) },
        ]} />
      )}

      <section className="section" style={{ marginTop: 64 }}>
        <Muestreo />
      </section>

      <section className="section">
        <div className="spread"><h2>Campañas de salud</h2><span className="small muted">Riesgo × población, de mayor a menor</span></div>
        {prio.loading ? <Skeleton lines={5} /> : prio.error ? <ErrorNote error={prio.error} retry={prio.reload} /> :
          !prio.data?.campanas_salud.length ? <Empty title="Ninguna zona habitada en riesgo medio o alto">Cuando el mapa cambie, aparecerán aquí.</Empty> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Comunidades</th><th>Nivel</th><th className="r">Población</th><th className="r">Confianza</th><th className="r">Casos</th><th>Acción sugerida</th></tr></thead>
              <tbody>
                {prio.data.campanas_salud.map((r) => (
                  <tr key={r.h3}>
                    <td>{limpiar(r.comunidades) || <span className="muted">Sin poblado con nombre</span>}</td>
                    <td><RiskChip nivel={r.risk_class} palida={r.confidence < 0.6} /></td>
                    <td className="r">{int(r.poblacion)}</td>
                    <td className="r">{pct(r.confidence)}</td>
                    <td className="r">{int(r.casos)}</td>
                    <td>{r.accion.charAt(0).toUpperCase() + r.accion.slice(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section">
        <div className="spread"><h2>Recuperación del ecosistema</h2><span className="small muted">Sedimento estimado × presión minera río arriba</span></div>
        {prio.data && (prio.data.recuperacion_ecosistema.length === 0 ? <Empty title="Sin tramos priorizados" /> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Tramo</th><th className="r">Sedimento (mg/kg)</th><th className="r">Hasta (p95)</th><th className="r">Presión (kg/año)</th><th className="r">Sitios en el tramo</th></tr></thead>
              <tbody>{prio.data.recuperacion_ecosistema.map((r) => (
                <tr key={r.reach_id}>
                  <td className="num">{r.reach_id}</td><td className="r">{num(r.sedimento_mg_kg_p50)}</td><td className="r">{num(r.p95)}</td>
                  <td className="r">{num(r.presion_kg_anio)}</td><td className="r">{int(r.sitios)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>Indicadores de los últimos 12 meses</h2>
        {ind.loading ? <Skeleton lines={3} height={60} /> : ind.error ? <ErrorNote error={ind.error} retry={ind.reload} /> : ind.data && <Multiples rows={ind.data} series={SERIES} />}
      </section>
    </div>
  );
}

function Muestreo() {
  const [matriz, setMatriz] = useState("agua");
  const { data, error, loading, reload } = useApi<Sugerencias>(`/v1/sampling/suggestions?matrix=${matriz}`, [matriz]);
  const [busy, setBusy] = useState(false);
  const { toast, show } = useToast();
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    let off = false;
    loadBaseStyle().then((s) => { if (!off && el.current) map.current = createMap(el.current, s, { zoom: 7.4 }); });
    return () => { off = true; map.current?.remove(); };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !data) return;
    markers.current.forEach((x) => x.remove());
    markers.current = data.sugerencias.map((s) => {
      const d = document.createElement("div");
      d.className = "rank-pin";
      d.textContent = String(s.rank);
      return new maplibregl.Marker({ element: d }).setLngLat([s.lon, s.lat]).addTo(m);
    });
    if (data.sugerencias.length) {
      const b = new maplibregl.LngLatBounds();
      data.sugerencias.forEach((s) => b.extend([s.lon, s.lat]));
      const fit = () => m.fitBounds(b, { padding: 80, maxZoom: 10, duration: 600 });
      if (m.loaded()) fit(); else m.once("load", fit);
    }
  }, [data]);

  const recalcular = async () => {
    setBusy(true);
    try {
      const r = await post<{ job_id: string }>(`/v1/sampling/suggestions?matrix=${matriz}&k=3`, {});
      show("Calculando… se actualizará en unos segundos.");
      for (let i = 0; i < 20; i++) {
        await new Promise((res) => setTimeout(res, 1500));
        const j = await api<{ estado: string }>(`/v1/admin/jobs/${r.job_id}`).catch(() => null);
        if (!j || j.estado === "finished" || j.estado === "failed") break;
      }
      reload();
    } catch (e) {
      show((e as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <div className="grid-2">
      <div className="stack">
        <h2>Dónde tomar las próximas 3 muestras</h2>
        <p className="muted">Los puntos donde una muestra de laboratorio reduce más la incertidumbre del mapa, ponderada por la gente que vive junto a cada río.</p>
        <div className="tabs" role="group" aria-label="Tipo de muestra">
          {(["agua", "sedimento", "pez"] as const).map((m) => (
            <button key={m} className="btn btn-pill" aria-pressed={matriz === m} onClick={() => setMatriz(m)}>{MATRIZ[m].nombre}</button>
          ))}
        </div>
        {loading ? <Skeleton lines={3} /> : error ? <ErrorNote error={error} retry={reload} /> : !data?.sugerencias.length ? (
          <Empty title="Todavía no hay sugerencias para esta matriz">Calcúlalas ahora: toma unos segundos.</Empty>
        ) : (
          <ol className="list" style={{ padding: 0, margin: 0, listStyle: "none" }}>
            {data.sugerencias.map((s) => (
              <li key={s.rank} className="list-item" style={{ gridTemplateColumns: "auto 1fr auto", alignItems: "center" }}>
                <span className="rank-pin rank-static" aria-hidden="true">{s.rank}</span>
                <span>
                  <span style={{ fontWeight: 500 }}>Cerca de {s.comunidad_cercana ?? "—"}</span><br />
                  <span className="caption muted num">{s.lat.toFixed(4)}, {s.lon.toFixed(4)} · tramo {s.reach_id}</span>
                </span>
                <span className="num" title="Reducción de la incertidumbre ponderada">−{num(s.reduccion_pct)} %</span>
              </li>
            ))}
          </ol>
        )}
        <div className="row">
          <button className="btn" onClick={recalcular} disabled={busy}>{busy ? "Calculando…" : "Recalcular sugerencias"}</button>
          <Link className="btn btn-pill" to="/laboratorio">Cargar resultados</Link>
        </div>
      </div>
      <div ref={el} className="picker" style={{ height: 420 }} role="img" aria-label="Mapa de puntos de muestreo sugeridos" />
      <Toast msg={toast} />
    </div>
  );
}

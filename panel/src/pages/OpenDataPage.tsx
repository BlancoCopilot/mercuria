import { Link } from "react-router-dom";
import { useApi } from "../lib/hooks";
import { fecha, hace, int } from "../lib/format";
import { PageHead } from "../components/Layout";
import { Empty, ErrorNote, Skeleton } from "../components/ui";

interface Catalogo {
  mediciones: number; estudios: number; otros_registros: number; zonas: number; sitios: number; tramos: number;
  version_mapa: number; actualizado: string; por_matriz: { matriz: string; n: number }[];
}
interface Estudio {
  id: number; titulo: string; autores: string | null; anio: number | null; doi: string | null; url: string | null;
  institucion: string | null; licencia: string; resumen: string | null; publicado: string; pdf_abierto: boolean; mediciones_en_mapa: number;
}

const LICENCIA: Record<string, string> = { "CC-BY-4.0": "CC BY 4.0", "CC0-1.0": "CC0 (dominio público)", "CC-BY-SA-4.0": "CC BY-SA 4.0" };

export default function OpenDataPage() {
  const cat = useApi<Catalogo>("/v1/open/catalog");
  const est = useApi<Estudio[]>("/v1/open/studies");
  const n = (m: string) => cat.data?.por_matriz.find((x) => x.matriz === m)?.n ?? 0;

  const archivos = cat.data ? [
    { grupo: "Mediciones", items: [
      { t: "Todas las mediciones", d: `${int(cat.data.mediciones)} valores de agua, sedimento y peces, con su fuente, licencia y ubicación.`, f: [["CSV", "/v1/open/mediciones.csv"], ["GeoJSON", "/v1/open/mediciones.geojson"]] },
      { t: "Solo agua", d: `${int(n("agua"))} valores · µg/L de Hg total`, f: [["CSV", "/v1/open/mediciones.csv?matriz=agua"]] },
      { t: "Solo sedimento", d: `${int(n("sedimento"))} valores · mg/kg peso seco`, f: [["CSV", "/v1/open/mediciones.csv?matriz=sedimento"]] },
      { t: "Solo peces", d: `${int(n("pez"))} valores · mg/kg peso húmedo`, f: [["CSV", "/v1/open/mediciones.csv?matriz=pez"]] },
      { t: "Otros datos de los estudios", d: `${int(cat.data.otros_registros)} valores que no entran al mapa (suelo, sedimento en suspensión, sitios sin coordenadas…)`, f: [["CSV", "/v1/open/otros_registros.csv"]] },
    ] },
    { grupo: "Resultados del modelo", items: [
      { t: "Riesgo por zona", d: `${int(cat.data.zonas)} zonas H3 (~5 km²): nivel, confianza, peligro, exposición y vulnerabilidad.`, f: [["CSV", "/v1/open/zonas_riesgo.csv"]] },
      { t: "Mercurio estimado por tramo de río", d: `${int(cat.data.tramos)} tramos con mediana y rango p05–p95, por matriz.`, f: [["Agua", "/v1/open/rios.csv?matriz=agua"], ["Sedimento", "/v1/open/rios.csv?matriz=sedimento"], ["Peces", "/v1/open/rios.csv?matriz=pez"]] },
      { t: "Sitios mineros", d: `${int(cat.data.sitios)} polígonos detectados por satélite, con estado legal y Hg estimado.`, f: [["GeoJSON", "/v1/open/sitios_mineros.geojson"]] },
    ] },
    { grupo: "Fuentes", items: [
      { t: "Estudios publicados", d: `${int(cat.data.estudios)} estudios aportados por universidades e investigadores.`, f: [["CSV", "/v1/open/studies.csv"]] },
    ] },
  ] : [];

  return (
    <div className="page">
      <PageHead title="Datos abiertos" aside={cat.data && <span className="tag">Mapa versión {cat.data.version_mapa} · {hace(cat.data.actualizado)}</span>}>
        Todo lo que usa MercurIA se puede descargar, gratis y sin cuenta, en cualquier momento. Úsalo citando la fuente.
      </PageHead>

      {cat.loading ? <Skeleton lines={6} /> : cat.error ? <ErrorNote error={cat.error} retry={cat.reload} /> : (
        <div className="stack" style={{ gap: 48 }}>
          {archivos.map((g) => (
            <section key={g.grupo} className="section" style={{ gap: 12 }}>
              <h2>{g.grupo}</h2>
              <div className="list">
                {g.items.map((it) => (
                  <div key={it.t} className="list-item dl-row">
                    <div>
                      <span style={{ fontSize: 18, fontWeight: 300 }}>{it.t}</span>
                      <p className="small muted">{it.d}</p>
                    </div>
                    <div className="row" style={{ gap: 8 }}>
                      {it.f.map(([label, href]) => (
                        <a key={href} className="btn btn-pill" href={href} download>
                          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M7 1.5v8M3.5 6L7 9.5 10.5 6M2 12.5h10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                          {label}
                        </a>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <section className="section" style={{ marginTop: 64 }}>
        <div className="spread"><h2>Estudios publicados</h2><Link className="btn btn-pill" to="/aportar">Aportar mi investigación</Link></div>
        {est.loading ? <Skeleton lines={4} /> : est.error ? <ErrorNote error={est.error} retry={est.reload} /> : !est.data?.length ? (
          <Empty title="Todavía no hay estudios aportados por la plataforma">
            Las mediciones actuales vienen de una revisión de literatura. Universidades e investigadores pueden sumar las suyas en «Aportar datos».
          </Empty>
        ) : (
          <div className="list">
            {est.data.map((e) => (
              <article key={e.id} className="list-item" style={{ gap: 8 }}>
                <span className="meta">{e.institucion ?? "Investigación independiente"}{e.anio ? ` · ${e.anio}` : ""}</span>
                <span style={{ fontSize: 20, fontWeight: 300, letterSpacing: "-0.01em" }}>{e.titulo}</span>
                {e.autores && <span className="small muted">{e.autores}</span>}
                {e.resumen && <p className="small" style={{ maxWidth: "75ch" }}>{e.resumen}</p>}
                <div className="row" style={{ gap: 8 }}>
                  <span className="tag">{LICENCIA[e.licencia] ?? e.licencia}</span>
                  <span className="tag tag-sky">{int(e.mediciones_en_mapa)} puntos en el mapa</span>
                  {e.doi && <a className="small" href={`https://doi.org/${e.doi}`} target="_blank" rel="noreferrer">doi:{e.doi}</a>}
                  {!e.doi && e.url && <a className="small" href={e.url} target="_blank" rel="noreferrer">Fuente original</a>}
                  <a className="small" href={`/v1/open/mediciones.csv?estudio=${e.id}`} download>Descargar sus datos (CSV)</a>
                  <span className="caption muted">Publicado {fecha(e.publicado)}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="grid-2" style={{ marginTop: 64 }}>
        <div className="stack">
          <h2>Cómo citar</h2>
          <p className="muted">Cada fila trae su referencia y licencia; cita el estudio original. Para el conjunto:</p>
          <pre className="cite">MercurIA ({new Date().getFullYear()}). Datos abiertos de mercurio de la minería aurífera en Bolivia, versión {cat.data?.version_mapa ?? "—"}. Descargado el {fecha(new Date().toISOString())}.</pre>
        </div>
        <div className="stack">
          <h2>Qué no se publica</h2>
          <ul className="small" style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
            <li>Datos de personas: salud y cabello solo como agregados de 5 o más personas por comunidad.</li>
            <li>Ubicación exacta de denuncias: solo la zona (≈5 km²).</li>
            <li>Estudios con embargo pedido por sus autores (máximo 12 meses).</li>
            <li>Datos sintéticos de ensayo.</li>
          </ul>
          <p className="small muted">También hay una API: las mismas rutas <span className="num">/v1/open/…</span> devuelven los archivos.</p>
        </div>
      </section>
    </div>
  );
}

import { Link } from "react-router-dom";
import { PageHead } from "../components/Layout";
import { Empty } from "../components/ui";
import { LECTURAS, RECURSOS, RELATOS, embedDe, type Relato } from "../lib/informate";
import "../styles/informate.css";

// Infórmate: relatos en video de personas afectadas, textos para leer y otros materiales.
// El contenido vive en lib/informate.ts.

export default function InformatePage() {
  return (
    <div className="page">
      <PageHead title="Infórmate">
        Personas de los ríos cuentan lo que viven con el mercurio. Aquí también hay lecturas y materiales para entenderlo y cuidarte.
      </PageHead>

      <section className="section">
        <h2>Relatos</h2>
        {RELATOS.length === 0
          ? <Empty title="Pronto subiremos los relatos">Videos de pescadores, madres y promotores de salud contando lo que viven en sus comunidades.</Empty>
          : <div className="inf-videos">{RELATOS.map((r) => <VideoRelato key={r.url} r={r} />)}</div>}
      </section>

      <section className="section">
        <h2>Para leer</h2>
        {LECTURAS.length === 0
          ? <Empty title="Pronto subiremos lecturas">Notas, estudios y reportajes sobre el mercurio en Bolivia, explicados en palabras simples.</Empty>
          : (
            <div className="list">
              {LECTURAS.map((l) => (
                <a key={l.url} className="list-item inf-link" href={l.url} target="_blank" rel="noopener noreferrer">
                  <span className="inf-titulo">{l.titulo}</span>
                  <span className="small muted">{l.fuente}{l.anio ? ` · ${l.anio}` : ""}</span>
                  {l.resumen && <p className="small">{l.resumen}</p>}
                </a>
              ))}
            </div>
          )}
      </section>

      <section className="section">
        <h2>Más materiales</h2>
        {RECURSOS.length > 0 && (
          <div className="inf-cards">
            {RECURSOS.map((x) => (
              <a key={x.url} className="panel-snow inf-card" href={x.url} target="_blank" rel="noopener noreferrer">
                <span className="tag">{x.tipo}</span>
                <span className="inf-titulo">{x.titulo}</span>
                {x.resumen && <p className="small muted">{x.resumen}</p>}
              </a>
            ))}
          </div>
        )}
        <div className="inf-cards">
          <Link className="panel inf-card" to="/preguntar">
            <span className="inf-titulo">Pregúntale a Gota</span>
            <p className="small muted">Qué pescado comer, qué hacer si alguien se enferma, cómo llega el mercurio al río.</p>
          </Link>
          <Link className="panel inf-card" to="/comunidades">
            <span className="inf-titulo">Ficha de tu comunidad</span>
            <p className="small muted">El riesgo de tu zona y qué hacer, en palabras simples y con audio.</p>
          </Link>
          <Link className="panel inf-card" to="/datos">
            <span className="inf-titulo">Datos abiertos</span>
            <p className="small muted">Todas las mediciones y estudios, para descargar gratis.</p>
          </Link>
        </div>
      </section>
    </div>
  );
}

function VideoRelato({ r }: { r: Relato }) {
  const embed = embedDe(r.url);
  return (
    <article className="inf-video">
      {embed
        ? <iframe src={embed} title={`${r.titulo} — ${r.quien}`} loading="lazy" allow="encrypted-media; picture-in-picture" allowFullScreen />
        : <a className="inf-video-link" href={r.url} target="_blank" rel="noopener noreferrer">Ver el video ↗</a>}
      <div className="inf-video-txt">
        <span className="inf-titulo">{r.titulo}</span>
        <span className="small muted">{r.quien}{r.lugar ? ` · ${r.lugar}` : ""}</span>
        {r.resumen && <p className="small">{r.resumen}</p>}
      </div>
    </article>
  );
}

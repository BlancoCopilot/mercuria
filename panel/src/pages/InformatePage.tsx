import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHead } from "../components/Layout";
import { Empty } from "../components/ui";
import { CANAL_YOUTUBE, LECTURAS, RECURSOS, RELATOS, VIDEO_PROPIO, youtubeId, type Relato } from "../lib/informate";
import "../styles/informate.css";

// Infórmate: nuestro video, relatos y reportajes en video, textos para leer y otros materiales.
// El contenido vive en lib/informate.ts.

const BASE = import.meta.env.BASE_URL;

export default function InformatePage() {
  return (
    <div className="page">
      <PageHead title="Infórmate">
        Qué es el mercurio, cómo llega al río y a la mesa, y qué cuentan las personas que lo viven. En video y en palabras simples.
      </PageHead>

      <section className="section inf-destacado">
        <VideoPropio />
        <div className="inf-destacado-txt">
          <h2>{VIDEO_PROPIO.titulo}</h2>
          <p className="lead">{VIDEO_PROPIO.resumen}</p>
          <ul className="inf-puntos">
            <li>Qué es el mercurio y por qué se usa en la minería de oro</li>
            <li>Cómo pasa del río al pescado y del pescado a las personas</li>
            <li>Cómo te ayuda MercurIA: mapa de riesgo, avisos y preguntas a Gota</li>
          </ul>
          <a className="btn btn-pill" href={VIDEO_PROPIO.youtube || CANAL_YOUTUBE.url} target="_blank" rel="noopener noreferrer">
            {VIDEO_PROPIO.youtube ? "Verlo en YouTube" : "Ver nuestro canal"} ↗
          </a>
        </div>
      </section>

      <section className="section">
        <h2>Relatos y reportajes</h2>
        {RELATOS.length === 0
          ? <Empty title="Pronto subiremos los relatos">Videos de pescadores, madres y promotores de salud contando lo que viven en sus comunidades.</Empty>
          : <div className="inf-videos">{RELATOS.map((r) => <VideoYoutube key={r.url} r={r} />)}</div>}
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

      <section className="section">
        <a className="inf-canal" href={CANAL_YOUTUBE.url} target="_blank" rel="noopener noreferrer">
          <YoutubeLogo />
          <span className="inf-canal-txt">
            <span className="inf-canal-titulo">MercurIA en YouTube</span>
            <span className="inf-canal-sub">{CANAL_YOUTUBE.usuario} · Videos cortos con Gota sobre el mercurio y cómo cuidarte</span>
          </span>
          <span className="btn inf-canal-btn">Ir al canal ↗</span>
        </a>
      </section>
    </div>
  );
}

/** Nuestro video: primero una portada con su título y botón de play; al tocarla se reproduce aquí mismo. */
function VideoPropio() {
  const [play, setPlay] = useState(false);
  const v = VIDEO_PROPIO;
  return (
    <div className="inf-propio">
      {play
        ? <video src={BASE + v.src} poster={BASE + v.poster} controls autoPlay playsInline preload="auto" />
        : (
          <button className="inf-portada" onClick={() => setPlay(true)} aria-label={`Reproducir: ${v.titulo} (${v.duracion})`}>
            <img src={BASE + v.poster} alt="" loading="lazy" />
            <span className="inf-velo" />
            <PlayIcon />
            <span className="inf-duracion">{v.duracion}</span>
            <span className="inf-portada-txt">
              <span className="inf-portada-sup">Video de MercurIA</span>
              <span className="inf-portada-tit">{v.titulo}</span>
            </span>
          </button>
        )}
    </div>
  );
}

/** Video de YouTube: portada con miniatura, título y canal; al tocarla se carga el reproductor (así la página no carga YouTube de entrada). */
function VideoYoutube({ r }: { r: Relato }) {
  const [play, setPlay] = useState(false);
  const id = youtubeId(r.url);
  if (!id) {
    return (
      <article className="inf-video">
        <a className="inf-video-link" href={r.url} target="_blank" rel="noopener noreferrer">Ver el video ↗</a>
        <Pie r={r} />
      </article>
    );
  }
  return (
    <article className="inf-video">
      <div className="inf-marco">
        {play
          ? <iframe src={`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`} title={`${r.titulo} — ${r.quien}`}
              allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen />
          : (
            <button className="inf-portada" onClick={() => setPlay(true)} aria-label={`Reproducir: ${r.titulo}`}>
              <img src={`https://i.ytimg.com/vi/${id}/hqdefault.jpg`} alt="" loading="lazy" />
              <span className="inf-velo" />
              <PlayIcon />
              <span className="inf-portada-txt">
                <span className="inf-portada-sup">{r.quien}</span>
                <span className="inf-portada-tit">{r.titulo}</span>
              </span>
            </button>
          )}
      </div>
      <Pie r={r} />
    </article>
  );
}

function Pie({ r }: { r: Relato }) {
  return (
    <div className="inf-video-txt">
      <span className="small muted">{r.quien}{r.lugar ? ` · ${r.lugar}` : ""} · <a href={r.url} target="_blank" rel="noopener noreferrer">Abrir en YouTube ↗</a></span>
      {r.resumen && <p className="small">{r.resumen}</p>}
    </div>
  );
}

const PlayIcon = () => (
  <span className="inf-play" aria-hidden="true">
    <svg width="30" height="30" viewBox="0 0 30 30"><path d="M10 6.5v17l14-8.5z" fill="currentColor" /></svg>
  </span>
);

const YoutubeLogo = () => (
  <svg className="inf-yt" width="56" height="40" viewBox="0 0 56 40" aria-hidden="true">
    <rect width="56" height="40" rx="11" fill="#FF0033" />
    <path d="M22 12v16l14-8z" fill="#fff" />
  </svg>
);

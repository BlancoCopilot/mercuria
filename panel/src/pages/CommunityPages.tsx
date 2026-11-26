import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Comunidad, type Ficha, type Frase, type Pez } from "../lib/api";
import { useApi } from "../lib/hooks";
import { confianzaTexto, int, num, NIVEL_TEXTO } from "../lib/format";
import { CommunitySearch } from "../components/CommunitySearch";
import { Empty, ErrorNote, Skeleton, SyntheticTag } from "../components/ui";
import { PageHead } from "../components/Layout";

// ── Buscar comunidad ──────────────────────────────────────
export function CommunitiesPage() {
  const nav = useNavigate();
  const [cerca, setCerca] = useState<Comunidad[] | null>(null);
  const [geoErr, setGeoErr] = useState<string | null>(null);
  const top = useApi<Comunidad[]>("/v1/communities?limit=12");

  const buscarCerca = () => {
    setGeoErr(null);
    if (!navigator.geolocation) { setGeoErr("Este navegador no permite ubicar."); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => api<Comunidad[]>(`/v1/communities?lat=${p.coords.latitude}&lon=${p.coords.longitude}&limit=6`, { auth: false }).then(setCerca),
      () => setGeoErr("No pudimos obtener tu ubicación. Busca por nombre."),
      { enableHighAccuracy: false, timeout: 10000 },
    );
  };

  return (
    <div className="page">
      <PageHead title={<>Mi comunidad</>}>
        Qué pescado comer, qué hacer y adónde ir. En palabras simples, y con audio.
      </PageHead>
      <form className="marigold-bar" onSubmit={(e) => e.preventDefault()} style={{ maxWidth: 880 }}>
        <div className="field" style={{ flex: "3 1 0" }}>
          <label className="label">Comunidad</label>
          <CommunitySearch autoFocus onPick={(c) => nav(`/comunidad/${c.id}`)} />
        </div>
        <button type="button" className="btn" onClick={buscarCerca}>Cerca de mí</button>
      </form>
      {geoErr && <p className="field-error" style={{ marginTop: 12 }}>{geoErr}</p>}

      {cerca && (
        <section className="section" style={{ marginTop: 48 }}>
          <h2>Cerca de ti</h2>
          <ComunidadList items={cerca} />
        </section>
      )}
      <section className="section" style={{ marginTop: 48 }}>
        <h2>Comunidades con más población</h2>
        {top.loading ? <Skeleton lines={5} /> : top.error ? <ErrorNote error={top.error} retry={top.reload} /> : <ComunidadList items={top.data ?? []} />}
      </section>
    </div>
  );
}

function ComunidadList({ items }: { items: Comunidad[] }) {
  if (!items.length) return <Empty title="No hay comunidades cargadas todavía" />;
  return (
    <div className="list" style={{ maxWidth: 880 }}>
      {items.map((c) => (
        <Link key={c.id} to={`/comunidad/${c.id}`} className="list-item" style={{ gridTemplateColumns: "1fr auto", color: "inherit", textDecoration: "none" }}>
          <span style={{ fontSize: 18, fontWeight: 300 }}>{c.name}</span>
          <span className="muted small num">{c.km !== undefined ? `${num(c.km)} km` : c.poblacion ? `${int(c.poblacion)} hab.` : ""} →</span>
        </Link>
      ))}
    </div>
  );
}

// ── Ficha ─────────────────────────────────────────────────
const IDIOMAS = [
  { id: "es", nombre: "Castellano" }, { id: "qu", nombre: "Quechua" }, { id: "ay", nombre: "Aymara" }, { id: "gn", nombre: "Guaraní" },
];

const CONSEJO = {
  comer: { titulo: "Puede comer", nota: "Buen alimento, también para niños." },
  limitar: { titulo: "Coma poco", nota: "Máximo 1 o 2 veces por semana." },
  evitar: { titulo: "Evite si está embarazada o es niño", nota: "Concentran más mercurio." },
} as const;

export function CardPage() {
  const { id } = useParams();
  const [lang, setLang] = useState("es");
  const { data, error, loading, reload } = useApi<Ficha>(`/v1/communities/${id}/card?lang=${lang}`, [lang]);
  const [playing, setPlaying] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const queue = useRef<Frase[]>([]);

  useEffect(() => () => { audio.current?.pause(); window.speechSynthesis?.cancel(); }, []);

  const stop = () => { audio.current?.pause(); window.speechSynthesis?.cancel(); queue.current = []; setPlaying(null); };

  const play = (f: Frase, next?: () => void) => {
    audio.current?.pause(); window.speechSynthesis?.cancel();
    setPlaying(f.clave);
    const done = () => { setPlaying(null); next?.(); };
    if (f.audio_url) {
      const a = new Audio(f.audio_url);
      audio.current = a;
      a.onended = done; a.onerror = done;
      a.play().catch(done);
    } else if (lang === "es" && "speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance(f.texto);
      u.lang = "es-BO"; u.rate = 0.92;
      u.onend = done; u.onerror = done;
      window.speechSynthesis.speak(u);
    } else done();
  };

  const playAll = () => {
    if (!data) return;
    queue.current = data.frases.filter((f) => f.audio_url || lang === "es");
    const step = () => { const f = queue.current.shift(); if (f) play(f, step); };
    step();
  };

  if (loading && !data) return <div className="page"><Skeleton lines={6} height={24} /></div>;
  if (error) return <div className="page"><ErrorNote error={error} retry={reload} /></div>;
  if (!data) return null;

  const nivel = data.nivel;
  const pendientes = data.frases.some((f) => f.traduccion_pendiente);
  const grupos = (["comer", "limitar", "evitar"] as const).map((k) => ({ k, items: data.peces.filter((p) => p.consejo === k) }));
  const accion = data.frases.filter((f) => f.clave.startsWith("ficha.accion"));
  const intro = data.frases.filter((f) => f.clave.startsWith("ficha.nivel") || f.clave === "ficha.incierto");
  const centro = data.frases.find((f) => f.clave === "ficha.centro_salud");

  return (
    <div className="page">
      <div className="row" style={{ marginBottom: 24 }}>
        <Link to="/comunidades" className="btn btn-quiet">← Otra comunidad</Link>
        <div className="tabs" role="group" aria-label="Idioma de la ficha" style={{ marginLeft: "auto" }}>
          {IDIOMAS.map((i) => (
            <button key={i.id} className="btn btn-pill" aria-pressed={lang === i.id} onClick={() => { stop(); setLang(i.id); }}>{i.nombre}</button>
          ))}
        </div>
      </div>

      <div className="ficha-hero">
        <div className="stack" style={{ gap: 16 }}>
          <span className="meta">Ficha de la comunidad <SyntheticTag show={data.comunidad.sintetico} /></span>
          <h1>{data.comunidad.nombre}</h1>
          <p className="lead">
            {data.comunidad.poblacion ? `${int(data.comunidad.poblacion)} habitantes. ` : ""}
            Esto es lo que sabemos hoy sobre el mercurio en sus ríos y su pescado.
          </p>
          <div className="row">
            <button className="btn" onClick={playing ? stop : playAll} disabled={lang !== "es" && !data.frases.some((f) => f.audio_url)}>
              {playing ? "Detener" : "Escuchar la ficha"}
            </button>
            <button className="btn btn-pill" onClick={() => window.print()}>Imprimir</button>
          </div>
          {pendientes && (
            <p className="small muted">
              La traducción y el audio en este idioma están pendientes de grabación por líderes de la comunidad; se muestra el castellano.
            </p>
          )}
        </div>
        <div className="nivel-block" data-nivel={nivel}>
          <span className="meta">Riesgo por mercurio</span>
          <span className="nivel-word">{NIVEL_TEXTO[nivel]}</span>
          <span className="small">
            {data.confianza !== null ? `Confianza ${Math.round(data.confianza * 100)} %: ${confianzaTexto(data.confianza)}.` : "Todavía sin estimación."}
            {data.version_mapa !== null && <span className="muted"> Versión {data.version_mapa} del mapa.</span>}
          </span>
        </div>
      </div>

      <section className="section" style={{ marginTop: 64 }}>
        <div className="list" style={{ maxWidth: 820 }}>
          {intro.map((f) => <FraseRow key={f.clave} f={f} playing={playing} onPlay={play} lang={lang} />)}
        </div>
      </section>

      <section className="section">
        <h2>El pescado</h2>
        {data.peces.length === 0 ? <Empty title="Aún no hay estimación para el pescado de esta zona" /> : (
          <div className="peces">
            {grupos.map(({ k, items }) => (
              <div key={k} className="peces-col">
                <h3><span className="dot-big" data-consejo={k} aria-hidden="true" />{CONSEJO[k].titulo}</h3>
                <p className="small muted">{CONSEJO[k].nota}</p>
                {items.length === 0 ? <p className="small muted">Ninguna especie.</p> : items.map((p) => <PezRow key={p.codigo} p={p} />)}
              </div>
            ))}
          </div>
        )}
        <p className="caption muted" style={{ maxWidth: 760 }}>
          Comidas por semana para no pasar la ingesta tolerable de metilmercurio (porción de 150 g en adultos y 75 g en niños). Estimación orientativa, en revisión por las autoridades de salud.
        </p>
      </section>

      <section className="section">
        <h2>Qué hacer</h2>
        <div className="list" style={{ maxWidth: 820 }}>
          {accion.map((f) => <FraseRow key={f.clave} f={f} playing={playing} onPlay={play} lang={lang} />)}
        </div>
      </section>

      {data.centro_salud && (
        <section className="section">
          <h2>Centro de salud más cercano</h2>
          <div className="hero-block" style={{ maxWidth: 820, display: "grid", gap: 8 }}>
            <span style={{ fontSize: 28, fontWeight: 300, letterSpacing: "-0.02em" }}>{data.centro_salud.name}</span>
            <span className="muted">A {num(data.centro_salud.km)} km{data.centro_salud.level ? ` · ${data.centro_salud.level}` : ""}</span>
            {data.centro_salud.phone && <a href={`tel:${data.centro_salud.phone.replace(/\s/g, "")}`} className="btn" style={{ justifySelf: "start", marginTop: 8 }}>Llamar {data.centro_salud.phone}</a>}
            {centro && <span className="visually-hidden">{centro.texto}</span>}
          </div>
        </section>
      )}

      <p className="small muted" style={{ marginTop: 48, maxWidth: 760 }}>{data.aviso}</p>
    </div>
  );
}

function FraseRow({ f, playing, onPlay, lang }: { f: Frase; playing: string | null; onPlay: (f: Frase) => void; lang: string }) {
  const can = !!f.audio_url || lang === "es";
  return (
    <div className="frase">
      <button className="play" aria-pressed={playing === f.clave} disabled={!can} onClick={() => onPlay(f)}
        aria-label={can ? `Escuchar: ${f.texto}` : "Audio pendiente de grabación"} title={can ? "Escuchar" : "Audio pendiente"}>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          {playing === f.clave ? <path d="M3 2h3v10H3zM8 2h3v10H8z" fill="currentColor" /> : <path d="M3 1.5l9 5.5-9 5.5z" fill="currentColor" />}
        </svg>
      </button>
      <p>{f.texto}</p>
    </div>
  );
}

function PezRow({ p }: { p: Pez }) {
  return (
    <div className="pez">
      <span style={{ fontWeight: 500 }}>{p.nombre}</span>
      <span className="num small">{num(p.comidas_semana_nino, 2)} / {num(p.comidas_semana_adulto, 2)} por semana</span>
      <span className="caption muted">≈ {num(p.mg_kg_p50)} mg/kg (hasta {num(p.mg_kg_p95)})</span>
      <span className="caption muted" style={{ textAlign: "right" }}>niño / adulto</span>
      {p.nota && <span className="caption" style={{ gridColumn: "1 / -1" }}>{p.nota}</span>}
    </div>
  );
}

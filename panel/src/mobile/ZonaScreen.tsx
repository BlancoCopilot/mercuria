import { useEffect, useRef, useState, type ReactElement } from "react";
import { url, type Comunidad, type Ficha, type Frase, type Nivel, type Pez } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useUbicacion } from "../lib/location";
import { num } from "../lib/format";
import { CommunitySearch } from "../components/CommunitySearch";
import { Drop } from "../components/Mascot";
import { GotaImg } from "../components/GotaImg";
import { IconAltavoz, IconBuscar, IconCampana, IconCheck, IconParar, IconTelefono, IconUbicar } from "./icons";
import { abrirAjustes, callar, hablar } from "./native";
import type { useAlertas } from "./useAlertas";

type Alertas = ReturnType<typeof useAlertas>;

const IDIOMAS = [
  { id: "es", nombre: "Castellano" }, { id: "qu", nombre: "Quechua" }, { id: "ay", nombre: "Aymara" }, { id: "gn", nombre: "Guaraní" },
];

const NIVEL: Record<Nivel, string> = { alto: "Riesgo alto", medio: "Riesgo medio", bajo: "Riesgo bajo", sin_datos: "Sin datos" };

const GRUPOS = [
  { k: "comer", titulo: "Puedes comer", nota: "Buen alimento, también para niños." },
  { k: "limitar", titulo: "Come poco", nota: "1 o 2 veces por semana." },
  { k: "evitar", titulo: "Embarazadas y niños: no coman", nota: "Tienen más mercurio." },
] as const;

const K_COMUNIDAD = "mercuria.comunidad";

function leerComunidad(): { id: number; name: string } | null {
  if (import.meta.env.DEV) {   // vista previa en el navegador: ?comunidad=11&nombre=Guanay
    const q = new URLSearchParams(location.search);
    if (q.get("comunidad")) return { id: Number(q.get("comunidad")), name: q.get("nombre") ?? "Comunidad" };
  }
  try { return JSON.parse(localStorage.getItem(K_COMUNIDAD) || "null"); } catch { return null; }
}

export function ZonaScreen({ alertas, onPreguntar }: { alertas: Alertas; onPreguntar: () => void }) {
  const { estado, zona, ubicar } = useUbicacion();
  const [elegida, setElegida] = useState(leerComunidad);
  const [buscando, setBuscando] = useState(false);
  const [lang, setLang] = useState("es");

  // La comunidad que se muestra: la elegida a mano manda; si no, la más cercana a la ubicación.
  // Mientras se vuelve a ubicar se sigue mostrando la última zona (no se vacía la pantalla).
  const porGps = zona ? zona.comunidad : null;
  const comunidad = elegida ?? porGps;
  const usandoGps = !elegida && !!zona;

  const elegir = (c: Comunidad | null) => {
    const v = c ? { id: c.id, name: c.name } : null;
    try { v ? localStorage.setItem(K_COMUNIDAD, JSON.stringify(v)) : localStorage.removeItem(K_COMUNIDAD); } catch { /* */ }
    setElegida(v);
    setBuscando(false);
  };

  const empezar = async () => { if (await alertas.activar()) elegir(null); };

  // Los avisos son lo principal: mientras falte algo, van arriba, justo bajo el nivel; ya activos, al final.
  const avisosListos = alertas.activas && alertas.notificaciones && alertas.fondo;
  const sinZona = !comunidad && !zona;
  if ((sinZona && estado !== "ubicando") || buscando) {
    return (
      <Bienvenida
        buscando={buscando || estado === "denegado"} denegado={estado === "denegado"} sinSenal={estado === "sin_senal"}
        onUbicar={empezar} onBuscar={() => setBuscando(true)} onElegir={elegir}
        onCancelar={comunidad || zona ? () => setBuscando(false) : undefined}
      />
    );
  }

  return (
    <div className="m-page">
      <Cabecera lang={lang} setLang={setLang} />
      {estado === "ubicando" && !comunidad && !zona
        ? <div className="m-nivel" data-nivel="sin_datos" aria-busy="true"><p className="m-lugar">Revisando tu zona…</p><span className="skeleton" style={{ height: 56, width: "70%" }} /></div>
        : <Contenido
            comunidad={comunidad} lang={lang} usandoGps={usandoGps}
            nivelGps={usandoGps && zona ? zona.nivel : null} cercaAlto={usandoGps && !!zona?.cercaAlto} palidaGps={usandoGps && !!zona?.palida}
            onPreguntar={onPreguntar}
            avisos={avisosListos ? null : <Avisos {...alertas} />}
          />}

      {avisosListos && <Avisos {...alertas} />}

      <div className="m-lugar-acciones">
        {elegida
          ? <button className="btn btn-pill" onClick={() => { elegir(null); ubicar(); }}><IconUbicar /> Volver a mi ubicación</button>
          : <button className="btn btn-pill" onClick={() => ubicar()} disabled={estado === "ubicando"}><IconUbicar /> {estado === "ubicando" ? "Ubicando…" : "Actualizar mi zona"}</button>}
        <button className="btn btn-pill" onClick={() => setBuscando(true)}><IconBuscar /> Otra comunidad</button>
      </div>
    </div>
  );
}

function Cabecera({ lang, setLang }: { lang: string; setLang: (l: string) => void }) {
  return (
    <header className="m-head">
      <span className="m-marca"><Drop height={28} /><img src="logo-mercuria.png" alt="MercurIA" width={120} height={25} /></span>
      <label className="m-idioma">
        <span className="visually-hidden">Idioma</span>
        <select value={lang} onChange={(e) => setLang(e.target.value)}>
          {IDIOMAS.map((i) => <option key={i.id} value={i.id}>{i.nombre}</option>)}
        </select>
      </label>
    </header>
  );
}

function Contenido({ comunidad, lang, usandoGps, nivelGps, cercaAlto, palidaGps, onPreguntar, avisos }: {
  comunidad: { id: number; name: string } | null; lang: string; usandoGps: boolean;
  nivelGps: Nivel | null; cercaAlto: boolean; palidaGps: boolean; onPreguntar: () => void; avisos: ReactElement | null;
}) {
  const { data, error, loading, reload } = useApi<Ficha>(comunidad ? `/v1/communities/${comunidad.id}/card?lang=${lang}` : null, [lang]);
  // En la ubicación propia manda el nivel de la celda donde está la persona; la ficha da el resto.
  const nivel: Nivel = nivelGps ?? data?.nivel ?? "sin_datos";
  const palida = usandoGps ? palidaGps : !!data?.palida;
  const lugar = comunidad ? (usandoGps ? `Tu zona · cerca de ${comunidad.name}` : comunidad.name) : "Tu zona";

  return (
    <>
      <section className="m-nivel" data-nivel={nivel} aria-live="polite">
        <p className="m-lugar">{lugar}{data?.comunidad.sintetico && <span className="tag">Datos de prueba</span>}</p>
        <p className="m-nivel-word">{NIVEL[nivel]}</p>
        <p className="m-nivel-nota">
          {nivel === "sin_datos"
            ? "No tenemos estimación para este lugar: está fuera de los ríos que estudiamos."
            : palida ? "Hay pocos datos de esta zona: puede cambiar cuando lleguen muestras." : "Estimación con las mediciones y el satélite."}
        </p>
        {cercaAlto && nivel !== "alto" && <p className="m-nivel-nota"><strong>A menos de 3 km hay una zona de riesgo alto.</strong></p>}
        {data && <Escuchar ficha={data} nivel={nivel} lugar={lugar} lang={lang} />}
      </section>

      {avisos}

      {!comunidad && nivel !== "sin_datos" && (
        <section className="m-sec">
          <h2>Qué hacer</h2>
          <ul className="m-frases">
            <li>Embarazadas y niños: eviten los peces grandes que comen otros peces (surubí, dorado, palometa).</li>
            <li>No quemes amalgama dentro ni cerca de la casa.</li>
          </ul>
        </section>
      )}

      {loading && !data && <section className="m-sec"><span className="skeleton" style={{ height: 120 }} /></section>}
      {error && (
        <section className="m-sec m-error" role="alert">
          <p>No pudimos traer la ficha de {comunidad?.name}. Revisa tu señal.</p>
          <button className="btn btn-pill" onClick={reload}>Intentar otra vez</button>
        </section>
      )}

      {data && (
        <>
          <section className="m-sec">
            <h2>El pescado</h2>
            {data.peces.length === 0
              ? <p className="muted">Aún no hay estimación para el pescado de esta zona.</p>
              : GRUPOS.map((g) => <GrupoPeces key={g.k} titulo={g.titulo} nota={g.nota} consejo={g.k} peces={data.peces.filter((p) => p.consejo === g.k)} />)}
          </section>

          <section className="m-sec">
            <h2>Qué hacer</h2>
            <ul className="m-frases">
              {data.frases.filter((f) => f.clave.startsWith("ficha.accion")).map((f) => <li key={f.clave}>{f.texto}</li>)}
            </ul>
            <button className="btn btn-pill m-preguntar" onClick={onPreguntar}>Pregúntale a Gota</button>
          </section>

          {data.centro_salud && (
            <section className="m-sec">
              <h2>Centro de salud</h2>
              <div className="m-centro">
                <p className="m-centro-nombre">{data.centro_salud.name}</p>
                <p className="muted">{data.centro_salud.km < 1 ? "A menos de 1 km" : `A ${num(data.centro_salud.km)} km`}{data.centro_salud.level ? ` · ${data.centro_salud.level}` : ""}</p>
                {data.centro_salud.phone && (
                  <a className="btn btn-block" href={`tel:${data.centro_salud.phone.replace(/\s/g, "")}`}><IconTelefono /> Llamar {data.centro_salud.phone}</a>
                )}
              </div>
            </section>
          )}
          <p className="caption muted m-aviso">{data.aviso}</p>
        </>
      )}
    </>
  );
}

function GrupoPeces({ titulo, nota, consejo, peces }: { titulo: string; nota: string; consejo: string; peces: Pez[] }) {
  if (!peces.length) return null;
  return (
    <div className="m-peces">
      <p className="m-peces-titulo"><span className="dot-big" data-consejo={consejo} aria-hidden="true" />{titulo}</p>
      <p className="small muted">{nota}</p>
      <ul className="m-peces-lista">
        {peces.map((p) => <li key={p.codigo}><span>{p.nombre}</span>{p.nota && <span className="caption">{p.nota}</span>}</li>)}
      </ul>
    </div>
  );
}

/** Lee la ficha en voz alta: castellano con la voz del teléfono; otros idiomas, con los audios grabados. */
function Escuchar({ ficha, nivel, lugar, lang }: { ficha: Ficha; nivel: Nivel; lugar: string; lang: string }) {
  const [sonando, setSonando] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const parar = useRef(false);
  useEffect(() => () => { parar.current = true; audio.current?.pause(); callar(); }, []);

  const grabadas = ficha.frases.filter((f) => f.audio_url);
  const puede = lang === "es" || grabadas.length > 0;

  const texto = () => {
    const grupo = (k: Pez["consejo"]) => ficha.peces.filter((p) => p.consejo === k).map((p) => p.nombre).join(", ");
    const partes = [
      `${lugar.replace(" · ", ", ")}: ${NIVEL[nivel].toLowerCase()} por mercurio.`,
      grupo("comer") && `Puedes comer: ${grupo("comer")}.`,
      grupo("limitar") && `Come poco, una o dos veces por semana: ${grupo("limitar")}.`,
      grupo("evitar") && `Embarazadas y niños, no coman: ${grupo("evitar")}.`,
      ...ficha.frases.filter((f) => f.clave.startsWith("ficha.accion") || f.clave === "ficha.centro_salud").map((f) => f.texto),
    ];
    return partes.filter(Boolean).join(" ");
  };

  const tocar = (f: Frase) => new Promise<void>((ok) => {
    const a = new Audio(url(f.audio_url!));
    audio.current = a;
    a.onended = () => ok(); a.onerror = () => ok();
    a.play().catch(() => ok());
  });

  const empezar = async () => {
    parar.current = false;
    setSonando(true);
    try {
      if (lang === "es") await hablar(texto());
      else for (const f of grabadas) { if (parar.current) break; await tocar(f); }
    } finally { setSonando(false); }
  };
  const detener = () => { parar.current = true; audio.current?.pause(); callar(); setSonando(false); };

  return (
    <button className="btn m-escuchar" onClick={sonando ? detener : empezar} disabled={!puede} aria-pressed={sonando}>
      {sonando ? <IconParar /> : <IconAltavoz />}
      {sonando ? "Detener" : puede ? "Escuchar" : "Audio pendiente en este idioma"}
    </button>
  );
}

function Avisos({ activas, notificaciones, fondo, activar, desactivar, pedirSegundoPlano }: Alertas) {
  const [explicar, setExplicar] = useState(false);
  let titulo: string, texto: string, accion: ReactElement | null;
  if (!activas) {
    titulo = "Avisos apagados";
    texto = "Te avisamos cuando entres a una zona con riesgo por mercurio.";
    accion = <button className="btn btn-block" onClick={activar}>Activar avisos</button>;
  } else if (!notificaciones) {
    titulo = "Android no deja mostrar avisos";
    texto = "Permite las notificaciones de MercurIA en los ajustes del teléfono.";
    accion = <button className="btn btn-block" onClick={abrirAjustes}>Abrir ajustes</button>;
  } else if (!fondo) {
    titulo = "Te aviso solo con la app abierta";
    texto = explicar
      ? "En la siguiente pantalla toca «Ubicación» y elige «Permitir todo el tiempo»."
      : "Para avisarte también con la app cerrada necesito tu ubicación todo el tiempo. Solo uso tu zona, no tu posición exacta.";
    accion = explicar
      ? <button className="btn btn-block" onClick={async () => { await pedirSegundoPlano(); setExplicar(false); }}>Continuar</button>
      : <button className="btn btn-block" onClick={() => setExplicar(true)}>Avisarme con la app cerrada</button>;
  } else {
    titulo = "Avisos activados";
    texto = "Te avisamos si entras a una zona con riesgo, también con la app cerrada.";
    accion = <button className="btn btn-quiet" onClick={desactivar}>Apagar avisos</button>;
  }
  const listo = activas && notificaciones && fondo;
  return (
    <section className="m-avisos" data-listo={listo}>
      <span className="m-avisos-icono">{listo ? <IconCheck /> : <IconCampana />}</span>
      <div className="m-avisos-texto">
        <p className="m-avisos-titulo">{titulo}</p>
        <p className="small">{texto}</p>
      </div>
      <div className="m-avisos-accion">{accion}</div>
    </section>
  );
}

function Bienvenida({ buscando, denegado, sinSenal, onUbicar, onBuscar, onElegir, onCancelar }: {
  buscando: boolean; denegado: boolean; sinSenal: boolean; onUbicar: () => void; onBuscar: () => void;
  onElegir: (c: Comunidad) => void; onCancelar?: () => void;
}) {
  return (
    <div className="m-page m-bienvenida">
      <GotaImg size={170} mood={buscando ? "thinking" : "idle"} />
      {buscando ? (
        <>
          <h1>¿Dónde vives?</h1>
          <p className="lead">{denegado ? "No tengo permiso para ver tu ubicación. " : ""}Escribe el nombre de tu comunidad.</p>
          <div className="m-buscar"><CommunitySearch onPick={onElegir} autoFocus /></div>
          {!denegado && <button className="btn btn-quiet" onClick={onUbicar}><IconUbicar /> Mejor usar mi ubicación</button>}
          {onCancelar && <button className="btn btn-quiet" onClick={onCancelar}>Volver</button>}
        </>
      ) : (
        <>
          <h1>Hola, soy Gota</h1>
          <p className="lead">Te digo si en tu zona hay mercurio, qué pescado comer y te aviso cuando entres a una zona con riesgo.</p>
          {sinSenal && (
            <p className="notice notice-warn small" role="alert">
              No pudimos saber dónde estás. Revisa que la ubicación del teléfono esté encendida e intenta otra vez, o busca tu comunidad.
            </p>
          )}
          <button className="btn btn-block m-cta" onClick={onUbicar}><IconUbicar /> {sinSenal ? "Intentar otra vez" : "Usar mi ubicación"}</button>
          <p className="small muted">Tu ubicación exacta no sale de tu teléfono: solo consultamos la zona.</p>
          <button className="btn btn-quiet" onClick={onBuscar}><IconBuscar /> Buscar mi comunidad</button>
        </>
      )}
    </div>
  );
}

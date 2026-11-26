import { Link } from "react-router-dom";
import { useUbicacion } from "../lib/location";
import { confianzaTexto } from "../lib/format";
import { Drop } from "./Mascot";

// Franja bajo la navegación: primero pide la ubicación (con explicación), después avisa el riesgo de la zona.
export function LocationAlert() {
  const { estado, zona, ubicar, descartar, cerrarAviso, avisoCerrado } = useUbicacion();

  if (estado === "preguntar") {
    return (
      <section className="loc-bar loc-ask" aria-label="Ubicación">
        <Drop height={28} />
        <p><strong>¿Te avisamos si tu zona tiene riesgo por mercurio?</strong>{" "}
          <span className="muted">Tu ubicación exacta no sale de tu teléfono: solo consultamos la zona (unos 5 km²).</span></p>
        <div className="loc-actions">
          <button className="btn" onClick={ubicar}>Usar mi ubicación</button>
          <button className="btn btn-quiet" onClick={descartar}>Ahora no</button>
        </div>
      </section>
    );
  }
  if (estado === "ubicando") {
    return (
      <section className="loc-bar" aria-live="polite"><Drop height={28} /><p className="muted">Revisando el riesgo de tu zona…</p></section>
    );
  }
  if (estado === "denegado") {
    return null;   // el navegador ya no deja volver a preguntar; el mapa sigue teniendo "Mi ubicación"
  }
  if (estado !== "listo" || !zona || avisoCerrado) return null;

  const enRiesgo = zona.nivel === "alto" || zona.nivel === "medio";
  const lugar = zona.comunidad ? ` (cerca de ${zona.comunidad.name})` : "";
  const ficha = zona.comunidad ? `/comunidad/${zona.comunidad.id}` : null;
  const mapa = `/?celda=${zona.h3}`;

  if (enRiesgo || zona.cercaAlto) {
    const nivel = enRiesgo ? zona.nivel : "alto";
    return (
      <section className="loc-alert" data-nivel={nivel} role={nivel === "alto" ? "alert" : "status"} aria-label="Aviso de riesgo en tu zona">
        <div className="loc-alert-main">
          <span className="meta">Aviso para tu ubicación</span>
          <p className="loc-alert-title">
            {enRiesgo
              ? <>Estás en una zona con riesgo <strong>{zona.nivel === "alto" ? "ALTO" : "MEDIO"}</strong> por mercurio{lugar}.</>
              : <>A menos de 3 km de ti hay una zona con riesgo <strong>ALTO</strong> por mercurio{lugar}.</>}
          </p>
          <p className="small loc-consejo">
            Embarazadas y niños: eviten los peces grandes que comen otros peces (surubí, dorado, palometa). No quemes amalgama dentro ni cerca de la casa.
            {enRiesgo && zona.confianza !== null && <span className="muted"> Confianza {Math.round(zona.confianza * 100)} %: {confianzaTexto(zona.confianza)}.</span>}
          </p>
        </div>
        <div className="loc-actions">
          {ficha && <Link className="btn" to={ficha} onClick={cerrarAviso}>Qué hacer aquí</Link>}
          <Link className="btn btn-pill" to={mapa} onClick={cerrarAviso}>Ver en el mapa</Link>
          <button className="btn btn-quiet loc-close" onClick={cerrarAviso} aria-label="Cerrar aviso">
            <span className="hide-sm">Entendido</span><span className="show-sm" aria-hidden="true">×</span>
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="loc-bar" role="status">
      <Drop height={28} />
      <p>
        {zona.nivel === "bajo"
          ? <>Tu zona{lugar}: riesgo <strong>bajo</strong> por mercurio{zona.peorVecino === "medio" ? ", con una zona de riesgo medio cerca" : ""}.</>
          : <>No tenemos estimación para tu ubicación: está fuera de la cuenca piloto o lejos de los ríos que modelamos. Puedes verla en el mapa.</>}
      </p>
      <div className="loc-actions">
        {ficha && zona.nivel === "bajo" && <Link className="btn btn-pill" to={ficha} onClick={cerrarAviso}>Ver ficha</Link>}
        <Link className="btn btn-pill" to="/?yo=1" onClick={cerrarAviso}>Ver en el mapa</Link>
        <button className="btn btn-quiet loc-close" onClick={cerrarAviso} aria-label="Cerrar aviso">×</button>
      </div>
    </section>
  );
}

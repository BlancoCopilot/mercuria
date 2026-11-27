import { lazy, Suspense, useCallback, useEffect, useState, type ReactElement } from "react";
import { IconAvisar, IconMapa, IconPreguntar, IconZona } from "./icons";
import { CallScreen } from "../components/CallScreen";
import { alAtras } from "./native";
import { useAlertas } from "./useAlertas";
import { ZonaScreen } from "./ZonaScreen";
import { PreguntarScreen } from "./PreguntarScreen";
import { AvisarScreen } from "./AvisarScreen";

// el mapa (MapLibre) es lo más pesado: se carga la primera vez que se abre la pestaña
const MapaScreen = lazy(() => import("./MapaScreen"));

export type Tab = "zona" | "mapa" | "preguntar" | "avisar";

const TABS: { id: Tab; label: string; icon: () => ReactElement }[] = [
  { id: "zona", label: "Mi zona", icon: IconZona },
  { id: "mapa", label: "Mapa", icon: IconMapa },
  { id: "preguntar", label: "Preguntar", icon: IconPreguntar },
  { id: "avisar", label: "Avisar", icon: IconAvisar },
];

export function App() {
  const [tab, setTab] = useState<Tab>(() =>
    (import.meta.env.DEV && (new URLSearchParams(location.search).get("tab") as Tab)) || "zona");
  const alertas = useAlertas();   // vive aquí: sigue revisando la zona en cualquier pestaña

  // Botón "atrás" de Android: vuelve a Mi zona; desde Mi zona, sale de la app.
  useEffect(() => alAtras(() => {
    if (tab === "zona") return false;
    setTab("zona");
    return true;
  }), [tab]);

  const aZona = useCallback(() => setTab("zona"), []);

  return (
    <div className="m-app">
      {/* key: cada pestaña empieza arriba (si no, hereda el desplazamiento de la anterior) */}
      <main className="m-screen" data-tab={tab} key={tab}>
        {tab === "zona" && <ZonaScreen alertas={alertas} onPreguntar={() => setTab("preguntar")} />}
        {tab === "mapa" && (
          <Suspense fallback={<div className="m-mapa-cargando"><span className="skeleton" style={{ height: 120 }} /></div>}>
            <MapaScreen onFicha={aZona} />
          </Suspense>
        )}
        {tab === "preguntar" && <PreguntarScreen />}
        {tab === "avisar" && <AvisarScreen />}
      </main>
      <nav className="m-tabs" aria-label="Secciones">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} className="m-tab" aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>
            <span className="m-tab-icon"><Icon /></span>
            <span className="m-tab-label">{label}</span>
          </button>
        ))}
      </nav>
      {/* la misma pantalla de llamada que en la web: con colgar, silenciar, cronómetro y subtítulos */}
      <CallScreen />
    </div>
  );
}

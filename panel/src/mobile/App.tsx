import { useEffect, useState, type ReactElement } from "react";
import { IconAvisar, IconPreguntar, IconZona } from "./icons";
import { alAtras } from "./native";
import { useAlertas } from "./useAlertas";
import { ZonaScreen } from "./ZonaScreen";
import { PreguntarScreen } from "./PreguntarScreen";
import { AvisarScreen } from "./AvisarScreen";

export type Tab = "zona" | "preguntar" | "avisar";

const TABS: { id: Tab; label: string; icon: () => ReactElement }[] = [
  { id: "zona", label: "Mi zona", icon: IconZona },
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

  return (
    <div className="m-app">
      <main className="m-screen" data-tab={tab}>
        {tab === "zona" && <ZonaScreen alertas={alertas} onPreguntar={() => setTab("preguntar")} />}
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
    </div>
  );
}

import { useEffect } from "react";
import { MemoryRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import MapPage from "../pages/MapPage";
import { api, type Ficha } from "../lib/api";

// Mapa: el mismo de la web (riesgo, sitios mineros, centros de salud, tu ubicación y la hoja de abajo).
// La web navega con rutas; aquí corre dentro de un enrutador en memoria y "Ficha de <comunidad>"
// abre esa comunidad en la pestaña Mi zona.

export const K_COMUNIDAD = "mercuria.comunidad";

function AbrirFicha({ onFicha }: { onFicha: () => void }) {
  const { id } = useParams();
  useEffect(() => {
    let vivo = true;
    api<Ficha>(`/v1/communities/${id}/card`, { auth: false })
      .then((f) => { try { localStorage.setItem(K_COMUNIDAD, JSON.stringify({ id: f.comunidad.id, name: f.comunidad.nombre })); } catch { /* */ } })
      .catch(() => {})
      .finally(() => { if (vivo) onFicha(); });
    return () => { vivo = false; };
  }, [id, onFicha]);
  return <div className="m-mapa-cargando"><span className="skeleton" style={{ height: 120 }} /></div>;
}

export default function MapaScreen({ onFicha }: { onFicha: () => void }) {
  return (
    <div className="m-mapa">
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<MapPage app />} />
          <Route path="/comunidad/:id" element={<AbrirFicha onFicha={onFicha} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </MemoryRouter>
    </div>
  );
}

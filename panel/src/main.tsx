import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource/abril-fatface/400.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles/global.css";
import "./styles/components.css";
import { AuthProvider } from "./lib/auth";
import { ChatProvider } from "./lib/chat";
import { LocationProvider } from "./lib/location";
import { Layout } from "./components/Layout";
import { Empty, RequireRole, Skeleton } from "./components/ui";

const MapPage = lazy(() => import("./pages/MapPage"));
const CommunitiesPage = lazy(() => import("./pages/CommunityPages").then((m) => ({ default: m.CommunitiesPage })));
const CardPage = lazy(() => import("./pages/CommunityPages").then((m) => ({ default: m.CardPage })));
const ReportPage = lazy(() => import("./pages/ReportPage"));
const InformatePage = lazy(() => import("./pages/InformatePage"));
const ChatPage = lazy(() => import("./pages/ChatPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const DecisionPage = lazy(() => import("./pages/DecisionPage"));
const LabPage = lazy(() => import("./pages/LabPage"));
const HealthPage = lazy(() => import("./pages/HealthPage"));
const ValidatePage = lazy(() => import("./pages/ValidatePage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const OpenDataPage = lazy(() => import("./pages/OpenDataPage"));
const ContributePage = lazy(() => import("./pages/ContributePage"));
const StudyReviewPage = lazy(() => import("./pages/StudyReviewPage"));

// Tras un despliegue, una pestaña abierta puede pedir fragmentos que ya no existen: recargar una vez.
window.addEventListener("vite:preloadError", (e) => {
  e.preventDefault();
  try {
    if (sessionStorage.getItem("rastrohg.reloaded") === "1") return;
    sessionStorage.setItem("rastrohg.reloaded", "1");
  } catch { /* */ }
  location.reload();
});
window.addEventListener("load", () => { try { sessionStorage.removeItem("rastrohg.reloaded"); } catch { /* */ } });

const Loading = () => <div className="page"><Skeleton lines={4} height={22} /></div>;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <LocationProvider>
      <ChatProvider>
      <BrowserRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<Layout full />}>
              <Route index element={<MapPage />} />
            </Route>
            <Route element={<Layout />}>
              <Route path="comunidades" element={<CommunitiesPage />} />
              <Route path="comunidad/:id" element={<CardPage />} />
              <Route path="denunciar" element={<ReportPage />} />
              <Route path="preguntar" element={<ChatPage />} />
              <Route path="informate" element={<InformatePage />} />
              <Route path="ingresar" element={<LoginPage />} />
              <Route path="datos" element={<OpenDataPage />} />
              <Route path="aportar" element={<ContributePage />} />
              <Route path="aportar/:id" element={<RequireRole roles={["investigador"]}><StudyReviewPage /></RequireRole>} />
              <Route path="panel" element={<RequireRole roles={["autoridad"]}><DecisionPage /></RequireRole>} />
              <Route path="laboratorio" element={<RequireRole roles={["laboratorio"]}><LabPage /></RequireRole>} />
              <Route path="salud" element={<RequireRole roles={["promotor"]}><HealthPage /></RequireRole>} />
              <Route path="validar" element={<RequireRole roles={["lider"]}><ValidatePage /></RequireRole>} />
              <Route path="admin" element={<RequireRole roles={[]}><AdminPage /></RequireRole>} />
              <Route path="*" element={<div className="page"><Empty title="Esta página no existe">Vuelve al mapa desde el menú.</Empty></div>} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
      </ChatProvider>
      </LocationProvider>
    </AuthProvider>
  </StrictMode>,
);

import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { ROL_NOMBRE, useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import type { MapVersion } from "../lib/api";
import { hace } from "../lib/format";
import { Drop } from "./Mascot";
import { CallScreen } from "./CallScreen";
import { ChatWidget } from "./ChatWidget";
import { LocationAlert } from "./LocationAlert";
import { DescargarApp } from "./DescargarApp";

function Announce() {
  const { data } = useApi<MapVersion>("/v1/map/version");
  const [closedVersion, setClosedVersion] = useState<string | null>(() => {
    try { return sessionStorage.getItem("rastrohg.announce"); } catch { return null; }
  });
  if (data && closedVersion === String(data.version)) return null;
  if (!data) return <div className="announce" aria-hidden="true" />;
  const close = () => {
    setClosedVersion(String(data.version));
    try { sessionStorage.setItem("rastrohg.announce", String(data.version)); } catch { /* modo privado */ }
  };
  return (
    <div className="announce" role="status">
      <span>
        <span className="hide-sm">Mapa versión <span className="num">{data.version}</span>, actualizado {hace(data.created_at)}. Toda cifra es una estimación con su rango.</span>
        <span className="show-sm">Mapa v<span className="num">{data.version}</span> · {hace(data.created_at)}</span>
      </span>
      {/* en el celular sobra: el botón "Avisar" ya está en la barra */}
      <Link to="/denunciar" className="hide-sm">Reportar minería o peces muertos →</Link>
      <button className="btn-quiet" style={{ minHeight: 28, padding: "0 8px", border: 0, background: "transparent", cursor: "pointer" }} aria-label="Cerrar aviso" onClick={close}>×</button>
    </div>
  );
}

function Nav() {
  const { user, can, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);

  const links: { to: string; label: string; show: boolean }[] = [
    { to: "/", label: "Mapa", show: true },
    { to: "/preguntar", label: "Preguntar", show: true },
    { to: "/informate", label: "Infórmate", show: true },
    { to: "/datos", label: "Datos abiertos", show: true },
    { to: "/aportar", label: "Aportar datos", show: !user || can("investigador") },
    { to: "/panel", label: "Decisión", show: can("autoridad") },
    { to: "/laboratorio", label: "Laboratorio", show: can("laboratorio") },
    { to: "/salud", label: "Salud", show: can("promotor") },
    { to: "/validar", label: "Validar", show: can("lider") },
    { to: "/admin", label: "Sistema", show: can() },
  ];
  return (
    <header>
      <nav className="nav" aria-label="Principal">
        <Link to="/" className="wordmark brand" aria-label="MercurIA, inicio">
          <Drop height={34} />
          <img src="/logo-mercuria.png" alt="MercurIA" width={153} height={32} />
        </Link>
        <button
          className="icon-btn nav-toggle" aria-expanded={open} aria-controls="nav-links"
          aria-label={open ? "Cerrar menú" : "Abrir menú"} onClick={() => setOpen((o) => !o)}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            {open ? <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              : <path d="M2 5h14M2 9h14M2 13h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />}
          </svg>
        </button>
        <div className="nav-links" id="nav-links" data-open={open}>
          {links.filter((l) => l.show).map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to === "/"}>{l.label}</NavLink>
          ))}
          {user ? (
            <button className="btn btn-pill" onClick={logout} title={`${user.name} · ${ROL_NOMBRE[user.role]}`}>
              Salir · {ROL_NOMBRE[user.role]}
            </button>
          ) : (
            <Link className="btn btn-pill" to="/ingresar">Ingresar</Link>
          )}
          <DescargarApp />
        </div>
        {/* siempre a la vista, también en el celular (fuera del menú) */}
        <NavLink to="/denunciar" className="nav-aviso" title="Avisa de minería nueva, peces muertos o agua turbia sin dar tu nombre">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 10v4a1 1 0 0 0 1 1h3l6 4V5L7 9H4a1 1 0 0 0-1 1z" />
            <path d="M17 9a4 4 0 0 1 0 6M19.5 6.5a8 8 0 0 1 0 11" />
          </svg>
          <span className="hide-sm">Aviso anónimo</span>
          <span className="show-sm">Avisar</span>
        </NavLink>
      </nav>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="stack" style={{ gap: 8 }}>
        <span className="brand"><Drop height={26} /><img src="/logo-mercuria.png" alt="MercurIA" width={115} height={24} style={{ height: 24, width: "auto" }} /></span>
        <p className="muted">Mercurio de la minería aurífera en Bolivia: dónde está, con qué certeza y qué hacer.</p>
      </div>
      <div className="stack" style={{ gap: 8 }}>
        <span className="meta">Comunidades</span>
        <Link to="/denunciar">Reportar de forma anónima</Link>
        <Link to="/preguntar">Hacer una pregunta</Link>
      </div>
      <div className="stack" style={{ gap: 8 }}>
        <span className="meta">Equipos</span>
        <Link to="/ingresar">Laboratorios, promotores, líderes y autoridades</Link>
        <Link to="/aportar">Aportar una investigación</Link>
        <Link to="/datos">Descargar los datos</Link>
      </div>
      <p className="muted small">
        Las estimaciones combinan detección satelital, factores de emisión y mediciones publicadas. Los parámetros siguen en revisión con las autoridades de salud.
      </p>
    </footer>
  );
}

export function Layout({ full }: { full?: boolean }) {
  // full: la página (el mapa) ocupa exactamente el alto que queda bajo el aviso y la navegación
  return (
    <div className={full ? "app-full" : undefined}>
      <a href="#main" className="visually-hidden">Saltar al contenido</a>
      <Announce />
      <Nav />
      <LocationAlert />
      <main id="main">
        <Outlet />
      </main>
      {!full && <Footer />}
      <ChatWidget />
      <CallScreen />
    </div>
  );
}

export function PageHead({ title, children, aside }: { title: ReactNode; children?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="page-head">
      <div className="spread" style={{ alignItems: "end" }}>
        <h1>{title}</h1>
        {aside}
      </div>
      {children && <p className="lead">{children}</p>}
    </div>
  );
}

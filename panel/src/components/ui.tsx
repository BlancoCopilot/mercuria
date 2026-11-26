import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import type { Nivel, Rol } from "../lib/api";
import { useAuth } from "../lib/auth";
import { confianzaTexto, NIVEL_TEXTO } from "../lib/format";

export function RiskChip({ nivel, confianza, palida }: { nivel: Nivel; confianza?: number | null; palida?: boolean }) {
  return (
    <span className="chip" data-nivel={nivel} data-palida={!!palida}>
      <span className="dot" aria-hidden="true" />
      Riesgo {NIVEL_TEXTO[nivel].toLowerCase()}
      {confianza !== undefined && <span className="muted" style={{ fontWeight: 400 }}>· {confianzaTexto(confianza)}</span>}
    </span>
  );
}

export function Skeleton({ lines = 3, height = 16 }: { lines?: number; height?: number }) {
  return (
    <div className="stack" style={{ gap: 10 }} aria-busy="true" aria-label="Cargando">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton" style={{ height, width: `${92 - i * 14}%` }} />
      ))}
    </div>
  );
}

export function ErrorNote({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="notice notice-error" role="alert">
      <strong style={{ fontWeight: 500 }}>No se pudo cargar.</strong>
      <span className="small">{error}</span>
      {retry && <div><button className="btn btn-pill" onClick={retry}>Reintentar</button></div>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong style={{ fontWeight: 500 }}>{title}</strong>
      {children && <p className="muted small">{children}</p>}
    </div>
  );
}

export function Toast({ msg }: { msg: string | null }) {
  return msg ? <div className="toast" role="status">{msg}</div> : null;
}

export function RequireRole({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { user, loading, can } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="page"><Skeleton lines={4} height={22} /></div>;
  if (!user) return <Navigate to={`/ingresar?volver=${encodeURIComponent(loc.pathname)}`} replace />;
  if (!can(...roles)) {
    return (
      <div className="page">
        <Empty title="Esta sección no corresponde a tu rol">
          Pide a quien administra MercurIA que te asigne el rol adecuado.
        </Empty>
      </div>
    );
  }
  return <>{children}</>;
}

export function Facts({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="facts">
      {items.map((f) => (
        <div className="fact" key={f.label}>
          <dt className="fact-label">{f.label}</dt>
          <dd className="fact-value" style={{ margin: 0 }}>{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SyntheticTag({ show }: { show?: boolean }) {
  return show ? <span className="tag tag-sky" title="Dato inventado para ensayo">Sintético</span> : null;
}

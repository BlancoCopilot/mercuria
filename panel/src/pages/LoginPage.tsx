import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ROL_INICIO, useAuth } from "../lib/auth";

export default function LoginPage() {
  const { login, user } = useAuth();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const [params] = useSearchParams();

  if (user) return <Navigate to={params.get("volver") || ROL_INICIO[user.role]} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const me = await login(email.trim(), pw);
      nav(params.get("volver") || ROL_INICIO[me.role], { replace: true });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 980 }}>
      <div className="grid-2" style={{ alignItems: "center" }}>
        <div className="stack" style={{ gap: 16 }}>
          <h1>Ingreso de equipos</h1>
          <p className="lead">Laboratorios, promotores de salud, líderes comunitarios y autoridades. El mapa y las fichas son públicos y no necesitan cuenta.</p>
        </div>
        <form className="form-panel" onSubmit={submit}>
          <div className="field-row">
            <label className="label" htmlFor="email">Correo</label>
            <input id="email" className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field-row">
            <label className="label" htmlFor="pw">Contraseña</label>
            <input id="pw" className="input" type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} aria-invalid={!!err} />
          </div>
          {err && <p className="field-error" role="alert">{err}</p>}
          <button className="btn btn-block" disabled={busy || !email || !pw}>{busy ? "Ingresando…" : "Ingresar"}</button>
        </form>
      </div>
    </div>
  );
}

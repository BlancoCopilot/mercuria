import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, post, session, type Rol } from "./api";

export interface Usuario { id: number; email: string; name: string; role: Rol; org: string | null; lab_id: number | null; settlement_id: number | null }

interface AuthCtx {
  user: Usuario | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Usuario>;
  logout: () => void;
  can: (...roles: Rol[]) => boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [loading, setLoading] = useState(!!session.token);

  useEffect(() => {
    if (!session.token) return;
    api<Usuario>("/v1/auth/me").then(setUser).catch(() => { session.token = null; }).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await post<{ access_token: string }>("/v1/auth/login", { email, password });
    session.token = r.access_token;
    const me = await api<Usuario>("/v1/auth/me");
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(() => { session.token = null; setUser(null); }, []);
  const can = useCallback((...roles: Rol[]) => !!user && (user.role === "admin" || roles.includes(user.role)), [user]);

  return <Ctx.Provider value={{ user, loading, login, logout, can }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth fuera de AuthProvider");
  return c;
}

export const ROL_NOMBRE: Record<Rol, string> = {
  admin: "Administración", laboratorio: "Laboratorio", promotor: "Promotor de salud", lider: "Líder comunitario", autoridad: "Autoridad",
  investigador: "Investigación",
};

/** Pantalla de inicio de cada rol después del login. */
export const ROL_INICIO: Record<Rol, string> = {
  admin: "/panel", autoridad: "/panel", laboratorio: "/laboratorio", promotor: "/salud", lider: "/validar", investigador: "/aportar",
};

import { useEffect, useState } from "react";

// Botón para bajar la app de Android desde la web (solo en la barra de navegación). Pregunta al servidor (HEAD) el tamaño y la fecha
// de la APK publicada: así muestra el peso real y el enlace cambia con cada versión (Cloudflare guarda
// la APK 4 horas en caché; con ?v=<fecha> nadie baja una vieja). Si no hay APK publicada, no se muestra.
// Dentro de la propia app no tiene sentido: no aparece.

const APK = "/descargas/MercurIA.apk";
const EN_APP = import.meta.env.VITE_PLATFORM === "android";

interface Info { href: string; mb: number | null }
let cache: Promise<Info | null> | null = null;

function infoApk(): Promise<Info | null> {
  cache ??= fetch(APK, { method: "HEAD", cache: "no-store" })
    .then((r) => {
      if (!r.ok || !/android|octet-stream/.test(r.headers.get("content-type") ?? "")) return null;
      const n = Number(r.headers.get("content-length"));
      const fecha = Date.parse(r.headers.get("last-modified") ?? "");
      return { href: Number.isFinite(fecha) ? `${APK}?v=${fecha / 1000}` : APK, mb: n > 0 ? Math.round(n / 1e6) : null };
    })
    .catch(() => null);
  return cache;
}

function useApk() {
  const [info, setInfo] = useState<Info | null>(null);
  useEffect(() => { if (!EN_APP) void infoApk().then(setInfo); }, []);
  return info;
}

export const IconAndroid = ({ size = 22 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="6" y="2.5" width="12" height="19" rx="2.6" />
    <path d="M12 7.5v7M9 11.8l3 3 3-3M10.5 18.5h3" />
  </svg>
);

/** Botón de la barra de navegación: píldora en computadora; fila del menú ☰ en el celular. */
export function DescargarApp() {
  const apk = useApk();
  if (!apk) return null;
  const peso = apk.mb ? `, ${apk.mb} MB` : "";
  return (
    <a className="nav-descargar" href={apk.href} download="MercurIA.apk"
      title={`App de MercurIA para Android${peso}. Android te pedirá permitir instalar apps de este sitio.`}>
      <IconAndroid size={18} />
      <span className="nav-descargar-corto">Descargar app</span>
      <span className="nav-descargar-largo">Descargar la app (Android{peso})</span>
    </a>
  );
}

/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Servidor de la API para la app de celular (vacío en la web: mismo origen). */
  readonly VITE_API_URL?: string;
  readonly VITE_PLATFORM?: "web" | "android";
}

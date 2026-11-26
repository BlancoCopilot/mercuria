import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /v1 y /media van a la API local; en producción Caddy sirve todo en el mismo dominio.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
  worker: { format: "es" },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1200 },
});

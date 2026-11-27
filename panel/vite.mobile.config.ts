import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// App de celular (Capacitor): entrada mobile/index.html → dist-mobile/. Rutas relativas (la APK sirve
// los archivos desde el propio teléfono). VITE_API_URL dice a qué servidor hablar.
export default defineConfig({
  root: "mobile",
  base: "./",
  publicDir: "../public",
  envDir: "..",
  plugins: [react()],
  server: {
    port: 5174,
    proxy: { "/v1": "http://localhost:8000", "/media": "http://localhost:8000" },
  },
  worker: { format: "es" },
  build: { outDir: "../dist-mobile", emptyOutDir: true, chunkSizeWarningLimit: 1200 },
});

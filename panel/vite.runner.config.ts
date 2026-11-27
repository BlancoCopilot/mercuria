import { defineConfig } from "vite";

// Revisor en segundo plano: un solo archivo JS sin módulos (el motor del Background Runner no los carga),
// con h3-js adentro. Se compila después de la app, dentro de dist-mobile/runners/.
export default defineConfig({
  envDir: ".",
  publicDir: false,
  build: {
    outDir: "dist-mobile/runners",
    emptyOutDir: false,
    target: "es2020",
    lib: { entry: "src/mobile/runner/zona.ts", formats: ["iife"], name: "revisorZona", fileName: () => "zona.js" },
  },
});

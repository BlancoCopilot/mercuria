/// <reference types="@capacitor/background-runner" />
/// <reference types="@capacitor/local-notifications" />
import type { CapacitorConfig } from "@capacitor/cli";

// CAP_HTTP=1 solo para probar contra un servidor sin HTTPS (emulador → http://10.0.2.2:8090).
const http = process.env.CAP_HTTP === "1";

const config: CapacitorConfig = {
  appId: "bo.mercuria.app",
  appName: "MercurIA",
  webDir: "dist-mobile",
  server: http ? { androidScheme: "http", cleartext: true } : undefined,
  android: { backgroundColor: "#f7f0e1" },
  plugins: {
    SystemBars: { insetsHandling: "css" },
    LocalNotifications: { smallIcon: "ic_stat_gota", iconColor: "#006434" },
    BackgroundRunner: {
      label: "bo.mercuria.app.zona",      // = RUNNER_LABEL en src/mobile/alerta.ts
      src: "runners/zona.js",
      event: "revisarZona",
      repeat: true,
      interval: 15,                       // mínimo de Android; el sistema puede espaciarlo más
      autoStart: true,
    },
  },
};

export default config;

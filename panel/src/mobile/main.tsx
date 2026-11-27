import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@fontsource/abril-fatface/400.css";
import "../styles/global.css";
import "../styles/components.css";
import "./mobile.css";
import { AuthProvider } from "../lib/auth";
import { ChatProvider } from "../lib/chat";
import { LocationProvider } from "../lib/location";
import { App } from "./App";
import { iniciarNativo } from "./native";

iniciarNativo();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <LocationProvider>
        <ChatProvider>
          <App />
        </ChatProvider>
      </LocationProvider>
    </AuthProvider>
  </StrictMode>,
);

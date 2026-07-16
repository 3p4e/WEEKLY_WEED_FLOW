import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ErrorBoundary, installWatchdog } from "./SelfHeal";
import { ToastProvider } from "./components/Toast";
import "./styles/global.css";

/* SUMA theme bootstrap — apply the persisted scheme + HUD intensity to <html>
   before first paint (shared with the login theme picker via localStorage). */
(() => {
  const get = (k: string, d: string) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
  const THEMES = ["protoss", "terran", "aiur", "verdant", "zerg", "swann"];
  const HUDS = ["subtle", "medium", "heavy"];
  const theme = get("suma-theme", "protoss");
  const hud = get("suma-hud", "medium");
  document.documentElement.setAttribute("data-theme", THEMES.includes(theme) ? theme : "protoss");
  document.documentElement.setAttribute("data-hud", HUDS.includes(hud) ? hud : "medium");
})();

installWatchdog();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ErrorBoundary>
  </StrictMode>
);

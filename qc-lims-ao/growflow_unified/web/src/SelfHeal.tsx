import { Component, type ErrorInfo, type ReactNode } from "react";

/** Self-healing watchdog (ported from the GrowFlow prototype's watchdog + final
 *  bootstrap). Two layers:
 *   1. ErrorBoundary — catches a throwing render (e.g. corrupt localStorage) and
 *      shows a non-destructive "Reset & reload" bar instead of a blank screen.
 *   2. installWatchdog() — if #root is still visually empty a few seconds after
 *      load (a silent failure), surface the same recovery bar. Never auto-wipes. */

function showResetBar(message: string) {
  if (document.getElementById("gf-reset-bar")) return;
  const bar = document.createElement("div");
  bar.id = "gf-reset-bar";
  bar.style.cssText =
    "position:fixed;top:0;left:0;right:0;z-index:99999;background:#16233B;color:#fff;" +
    "font-family:'Manrope',system-ui,sans-serif;font-size:14px;font-weight:600;padding:12px 18px;" +
    "display:flex;align-items:center;gap:14px;box-shadow:0 4px 20px rgba(0,0,0,.3)";
  bar.innerHTML =
    `<span>${message}</span>` +
    `<button id="gf-reset-btn" style="margin-left:auto;background:#2F6BFF;color:#fff;border:none;` +
    `border-radius:8px;padding:8px 16px;font-weight:700;cursor:pointer;font-family:inherit">Reset &amp; reload</button>`;
  document.body.appendChild(bar);
  document.getElementById("gf-reset-btn")!.onclick = () => {
    try { localStorage.clear(); sessionStorage.clear(); } catch { /* ignore */ }
    location.reload();
  };
}

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(err: Error, info: ErrorInfo) { console.warn("GrowFlow render error", err, info); }
  componentDidUpdate() { if (this.state.failed) showResetBar("The app hit an error and could not render."); }
  render() {
    if (this.state.failed) return null; // the reset bar is the recovery UI
    return this.props.children;
  }
}

/** If the app is still visually blank ~3.5s after load, offer recovery. */
export function installWatchdog() {
  const visible = (el: Element | null) => !!el && (el as HTMLElement).offsetHeight > 4 && el.childElementCount > 0;
  let tries = 0;
  const check = () => {
    if (visible(document.getElementById("root"))) return;
    if (++tries < 8) { setTimeout(check, 450); return; }
    showResetBar("The app could not start from saved data.");
  };
  if (document.readyState === "complete") setTimeout(check, 600);
  else window.addEventListener("load", () => setTimeout(check, 600));
}

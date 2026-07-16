import { createContext, useCallback, useContext, useRef, useState, type ReactNode, type CSSProperties } from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

/* SUMA toast system — glass HUD notifications bottom-right, auto-dismiss. */
type ToastKind = "success" | "error" | "info";
interface ToastItem { id: number; kind: ToastKind; msg: string; }
interface ToastApi { toast: (msg: string, kind?: ToastKind) => void; }

const Ctx = createContext<ToastApi>({ toast: () => {} });
export const useToast = (): ToastApi => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  const toast = useCallback((msg: string, kind: ToastKind = "info") => {
    const id = ++seq.current;
    setItems((cur) => [...cur, { id, kind, msg }]);
    window.setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), 3400);
  }, []);
  const drop = (id: number) => setItems((cur) => cur.filter((t) => t.id !== id));

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div style={stack}>
        {items.map((t) => {
          const c = t.kind === "success" ? "var(--status-completed)" : t.kind === "error" ? "var(--status-stuck)" : "var(--accent)";
          const Icon = t.kind === "success" ? CheckCircle2 : t.kind === "error" ? AlertTriangle : Info;
          return (
            <div key={t.id} style={{ ...toastBox, borderLeft: `3px solid ${c}` }}>
              <Icon size={15} color={c} style={{ flexShrink: 0 }} />
              <span style={{ flex: 1, color: "var(--text)" }}>{t.msg}</span>
              <button onClick={() => drop(t.id)} style={closeBtn} aria-label="dismiss"><X size={12} /></button>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

const stack: CSSProperties = { position: "fixed", bottom: 22, right: 22, zIndex: 700, display: "flex", flexDirection: "column", gap: 10, maxWidth: "calc(100vw - 44px)" };
const toastBox: CSSProperties = {
  display: "flex", alignItems: "center", gap: 10, minWidth: 240, maxWidth: 380,
  padding: "11px 13px", background: "var(--surface-solid)", border: "1px solid var(--hairline)",
  borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-lg)", backdropFilter: "var(--blur)",
  fontSize: 13, fontWeight: 600, fontFamily: "var(--font-body)",
};
const closeBtn: CSSProperties = { background: "none", border: "none", color: "var(--text-dim)", cursor: "pointer", display: "flex", padding: 2 };

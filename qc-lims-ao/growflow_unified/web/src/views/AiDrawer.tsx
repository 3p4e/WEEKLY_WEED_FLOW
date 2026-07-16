import { useEffect, useState, type CSSProperties } from "react";
import { Sparkles, X, SendHorizontal } from "lucide-react";
import { Button, Select, Textarea } from "../components";
import { aiFunctions, aiInvoke } from "../api/planner";
import type { AiFunctions } from "../types/models";

/** AI Assistant drawer — invokes the bound stateful agents (P2). Degrades
 *  gracefully: if the Letta stack is unreachable the result says so. */
export function AiDrawer({ open, onClose, t }: { open: boolean; onClose: () => void; t: (k: string) => string }) {
  const [fns, setFns] = useState<AiFunctions | null>(null);
  const [fn, setFn] = useState("weekly_summary");
  const [input, setInput] = useState("");
  const [output, setOutput] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Task-management scope: only task/reporting capabilities are surfaced.
  const TASK_FNS = ["weekly_summary", "next_week_plan", "weekly_report", "draft_description", "executive_analytics"];
  useEffect(() => {
    if (!open || fns) return;
    (async () => {
      try {
        const f = await aiFunctions();
        setFns(f);
        const allowed = f.active.filter((k) => TASK_FNS.includes(k));
        if (allowed.length) setFn(allowed[0]);
      } catch { setFns({ catalog: {}, active: [] }); }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, fns]);

  async function ask() {
    setBusy(true); setOutput(null);
    try {
      const r = await aiInvoke(fn, input);
      setOutput(r.available ? (r.output ?? "") : `⚠︎ ${r.reason ?? "unavailable"}`);
    } catch {
      setOutput("⚠︎ error");
    } finally { setBusy(false); }
  }

  if (!open) return null;
  const options = (fns?.active ?? []).filter((k) => TASK_FNS.includes(k)).map((k) => ({ value: k, label: fns?.catalog[k] ?? k }));

  return (
    <>
      <div style={scrim} onClick={onClose} />
      <aside style={drawer}>
        <div style={head}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={16} style={{ color: "var(--color-accent, #C9A227)" }} />
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{t("ai_assistant")}</span>
          </div>
          <button style={iconBtn} onClick={onClose}><X size={15} /></button>
        </div>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, flex: 1, overflow: "auto" }}>
          {options.length > 0 ? (
            <Select label={t("ai_pick_fn")} value={fn} onChange={setFn} options={options} />
          ) : (
            <div style={muted}>{t("ai_unavailable")}</div>
          )}
          <Textarea label={t("ask_ai")} value={input} onChange={setInput} rows={3} placeholder={t("ask_ai")} />
          <Button variant="primary" icon={<SendHorizontal size={14} />} disabled={busy || !input} onClick={() => void ask()}>
            {busy ? t("ai_thinking") : t("send")}
          </Button>
          {output !== null && (
            <div style={outBox}>{output}</div>
          )}
        </div>
      </aside>
    </>
  );
}

const scrim: CSSProperties = { position: "fixed", inset: 0, background: "rgba(15,37,64,0.28)", zIndex: 40 };
const drawer: CSSProperties = { position: "fixed", top: 0, right: 0, bottom: 0, width: 380, maxWidth: "92vw", background: "var(--surface-card)", borderLeft: "1px solid var(--border-subtle)", boxShadow: "-8px 0 28px rgba(15,37,64,0.14)", zIndex: 41, display: "flex", flexDirection: "column" };
const head: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px", borderBottom: "1px solid var(--border-subtle)" };
const iconBtn: CSSProperties = { width: 28, height: 28, borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", background: "var(--surface-card)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--text-secondary)" };
const muted: CSSProperties = { fontSize: 12, color: "var(--text-tertiary)", padding: "8px 0" };
const outBox: CSSProperties = { whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.5, color: "var(--text-primary)", background: "var(--zebra)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 12 };

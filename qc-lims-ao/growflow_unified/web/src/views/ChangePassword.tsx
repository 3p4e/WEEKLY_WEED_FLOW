import { useState, type CSSProperties } from "react";
import { Button, Input } from "../components";
import { changePassword } from "../api/planner";
import type { UserOut } from "../types/models";

/** Forced first-login password change (SUMA/WWF methodology). Shown until the
 *  provisioned temp password is replaced. */
export function ChangePassword({
  t, onDone, forced,
}: { t: (k: string) => string; onDone: (u: UserOut) => void; forced: boolean }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true); setError(null);
    try {
      const u = await changePassword(current, next);
      onDone(u);
    } catch {
      setError(t("current_password") + " ✕");
    } finally { setBusy(false); }
  }

  return (
    <div style={wrap}>
      <form style={card} onSubmit={(e) => { e.preventDefault(); if (current && next.length >= 10) void submit(); }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
          {t("change_password")}
        </div>
        {forced && <div style={notice}>{t("must_change")}</div>}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 14 }}>
          <Input label={t("current_password")} value={current} onChange={setCurrent} type="password" />
          <Input label={t("new_password")} value={next} onChange={setNext} type="password" />
          {error && <div style={errBox}>{error}</div>}
          <Button variant="primary" size="lg" fullWidth disabled={busy || !current || next.length < 10}>
            {t("update_password")}
          </Button>
        </div>
      </form>
    </div>
  );
}

const wrap: CSSProperties = { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--surface-app)", padding: 24 };
const card: CSSProperties = { width: 360, background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: 24, boxShadow: "var(--shadow-md, 0 4px 20px rgba(15,37,64,0.08))" };
const notice: CSSProperties = { fontSize: 12, color: "var(--status-pending)", background: "var(--status-pending-bg)", border: "1px solid var(--status-pending-border)", borderRadius: "var(--radius-md)", padding: "8px 10px" };
const errBox: CSSProperties = { fontSize: 12, color: "var(--status-fail)", background: "var(--status-fail-bg)", border: "1px solid var(--status-fail-border)", borderRadius: "var(--radius-md)", padding: "6px 10px" };

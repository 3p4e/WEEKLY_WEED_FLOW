import { useEffect, useState, type CSSProperties } from "react";
import { Users, KeyRound, Copy, ShieldAlert } from "lucide-react";
import { Button, Select } from "../components";
import { adminListUsers, adminChangeRole, adminSetActive, adminResetPassword } from "../api/planner";
import type { AdminUser, ProvisionResult, Role, UserOut } from "../types/models";

const ALL_ROLES: Role[] = ["operator", "qa", "qp", "hod", "executive", "admin"];
const ROLE_LABEL: Record<string, string> = {
  operator: "Operator", qa: "QA Officer", qp: "Qualified Person",
  hod: "Head of Dept", executive: "Executive", admin: "Administrator",
};

/** Admin console — complete the account lifecycle beyond provisioning:
 *  role change + activate/deactivate (admin), and password reset
 *  (admin / C-level / HOD, scoped by the hierarchy). */
export function AdminConsole({ t, user }: { t: (k: string) => string; user: UserOut }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [busy, setBusy] = useState(true);
  const [otp, setOtp] = useState<ProvisionResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const isAdmin = user.role === "admin";

  async function reload() {
    setBusy(true); setErr(null);
    try { setUsers(await adminListUsers()); } catch { setErr(t("api_down")); } finally { setBusy(false); }
  }
  useEffect(() => { void reload(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function onRole(u: AdminUser, role: string) {
    try { await adminChangeRole(u.id, role); await reload(); } catch { setErr("✕"); }
  }
  async function onActive(u: AdminUser) {
    try { await adminSetActive(u.id, !u.is_active); await reload(); } catch { setErr("✕"); }
  }
  async function onReset(u: AdminUser) {
    setOtp(null);
    try { setOtp(await adminResetPassword(u.id)); } catch { setErr(t("not_permitted")); }
  }

  return (
    <div style={{ maxWidth: 1000 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <Users size={18} style={{ color: "var(--blue)" }} />
        <h2 style={{ fontSize: 18, fontWeight: 800, color: "var(--ink)", margin: 0 }}>{t("admin_console")}</h2>
      </div>
      <div style={{ fontSize: 12, color: "var(--ink-2)" }}>{t("account_lifecycle")}</div>

      {otp && (
        <div style={otpBox}>
          <KeyRound size={15} style={{ color: "var(--green-fg)" }} />
          <span style={{ fontSize: 12, color: "var(--ink-2)" }}>{t("temp_password_once")}:</span>
          <code style={otpCode}>{otp.temp_password}</code>
          <button style={copyBtn} onClick={() => navigator.clipboard?.writeText(otp.temp_password)} title="copy"><Copy size={13} /></button>
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{otp.username}</span>
        </div>
      )}
      {err && <div style={{ ...otpBox, background: "var(--status-fail-bg)", border: "1px solid var(--status-fail-border)", color: "var(--status-fail)" }}><ShieldAlert size={14} /> {err}</div>}

      <div style={panel}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>
            {[t("full_name"), t("username"), t("role"), t("department"), t("status"), ""].map((h, i) => (
              <th key={i} style={th}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {busy ? <tr><td style={td} colSpan={6}>…</td></tr> :
              users.map((u) => (
                <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.55 }}>
                  <td style={td}>
                    {u.full_name}
                    {u.cross_department && <span style={tag} title="inter-department">⇄</span>}
                    {u.must_change_password && <span style={{ ...tag, color: "var(--amber-fg)", background: "var(--amber-soft)" }} title="must change password">OTP</span>}
                  </td>
                  <td style={{ ...td, color: "var(--ink-2)", fontFamily: "var(--font-mono)", fontSize: 12 }}>{u.username}</td>
                  <td style={td}>
                    {isAdmin && u.id !== user.id ? (
                      <Select value={u.role} onChange={(r) => void onRole(u, r)}
                        options={ALL_ROLES.map((r) => ({ value: r, label: ROLE_LABEL[r] ?? r }))} />
                    ) : (ROLE_LABEL[u.role] ?? u.role)}
                  </td>
                  <td style={{ ...td, color: "var(--ink-2)" }}>{u.dept_key ?? "—"}</td>
                  <td style={td}>
                    <span style={{ ...pill, background: u.is_active ? "var(--green-soft)" : "var(--surface-3)", color: u.is_active ? "var(--green-fg)" : "var(--ink-3)" }}>
                      {u.is_active ? t("active") : t("inactive")}
                    </span>
                  </td>
                  <td style={{ ...td, textAlign: "right", whiteSpace: "nowrap" }}>
                    <Button size="sm" variant="secondary" onClick={() => void onReset(u)}>{t("reset_password")}</Button>
                    {isAdmin && u.id !== user.id && (
                      <Button size="sm" variant={u.is_active ? "danger" : "primary"} onClick={() => void onActive(u)} style={{ marginLeft: 6 }}>
                        {u.is_active ? t("deactivate") : t("activate")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const panel: CSSProperties = { background: "var(--surface-card)", border: "1px solid var(--line)", borderRadius: "var(--radius-lg)", marginTop: 14, overflow: "hidden" };
const th: CSSProperties = { textAlign: "left", padding: "8px 10px", borderBottom: "1px solid var(--line)", fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em", background: "var(--surface-2)" };
const td: CSSProperties = { padding: "8px 10px", borderBottom: "1px solid var(--line-2)", fontSize: 13, color: "var(--ink)", verticalAlign: "middle" };
const pill: CSSProperties = { fontSize: 10.5, fontWeight: 700, padding: "2px 8px", borderRadius: "var(--radius-full)", textTransform: "uppercase", letterSpacing: "0.03em" };
const tag: CSSProperties = { marginLeft: 6, fontSize: 9, fontWeight: 700, color: "var(--violet)", background: "var(--violet-soft)", borderRadius: "var(--radius-full)", padding: "1px 6px" };
const otpBox: CSSProperties = { display: "flex", alignItems: "center", gap: 8, marginTop: 12, padding: "8px 12px", background: "var(--green-soft)", border: "1px solid var(--status-pass-border)", borderRadius: "var(--radius-md)" };
const otpCode: CSSProperties = { fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700, color: "var(--ink)" };
const copyBtn: CSSProperties = { width: 26, height: 26, borderRadius: "var(--radius-md)", border: "1px solid var(--line)", background: "var(--surface-card)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--ink-2)" };

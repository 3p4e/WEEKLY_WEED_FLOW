import { useState, type CSSProperties } from "react";
import { Cpu, UserPlus, Copy, Network } from "lucide-react";
import { Button, Input, Select } from "../components";
import { provisionUser } from "../api/planner";
import { ApiError } from "../api/client";
import type { PlannerDepartment, ProvisionResult, Role, UserOut } from "../types/models";

const PROVISIONERS: Role[] = ["admin", "executive", "hod"];
const PROVIDER_KEY = "growflow_ai_provider";

const ROLE_LABEL: Record<string, string> = {
  operator: "Operator (staff)", qa: "QA Officer", qp: "Qualified Person",
  hod: "Head of Department", executive: "Executive (C-level)", admin: "Administrator",
};

/** Provisioning authority by tier (mirrors the API). */
function allowedRoles(actor: Role): Role[] {
  if (actor === "admin") return ["operator", "qa", "qp", "hod", "executive", "admin"];
  if (actor === "executive") return ["operator", "qa", "qp", "hod"];
  if (actor === "hod") return ["operator", "qa", "qp"];
  return [];
}

/** Settings — AI provider preference and account provisioning governed by the
 *  hierarchy (admin → executive → hod). */
export function SettingsView({
  t, user, departments,
}: { t: (k: string) => string; user: UserOut; departments: PlannerDepartment[] }) {
  const [provider, setProvider] = useState<string>(
    (typeof localStorage !== "undefined" && localStorage.getItem(PROVIDER_KEY)) || "letta",
  );
  const canProvision = PROVISIONERS.includes(user.role);

  function setProv(p: string) {
    setProvider(p);
    if (typeof localStorage !== "undefined") localStorage.setItem(PROVIDER_KEY, p);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 760 }}>
      <h2 style={h2}>{t("settings")}</h2>

      <section style={card}>
        <div style={cardHead}><Cpu size={15} /> {t("ai_provider")}</div>
        <div style={{ padding: 14, maxWidth: 320 }}>
          <Select label={t("ai_provider")} value={provider} onChange={setProv}
            options={[
              { value: "letta", label: "Letta (stateful agents)" },
              { value: "gateway", label: "Planner gateway" },
              { value: "off", label: "Off (manual only)" },
            ]} />
        </div>
      </section>

      {canProvision && <ProvisionCard t={t} actor={user} departments={departments} />}
    </div>
  );
}

function ProvisionCard({
  t, actor, departments,
}: { t: (k: string) => string; actor: UserOut; departments: PlannerDepartment[] }) {
  const roles = allowedRoles(actor.role);
  const deptLocked = actor.role === "hod";
  const canCross = actor.role === "admin" || actor.role === "executive";

  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<string>(roles[0] ?? "operator");
  const [email, setEmail] = useState("");
  const [deptId, setDeptId] = useState<string>(deptLocked ? (actor.dept_id ?? "") : "");
  const [cross, setCross] = useState(false);
  const [result, setResult] = useState<ProvisionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const deptOptions = departments.map((d) => ({ value: d.id, label: d.name_en }));

  async function submit() {
    setBusy(true); setErr(null); setResult(null);
    try {
      const r = await provisionUser({
        username, full_name: fullName, role, email: email || null,
        dept_id: deptId || null, cross_department: cross,
      });
      setResult(r);
      setUsername(""); setFullName(""); setEmail(""); setCross(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setErr("Not permitted by your role/scope.");
      else if (e instanceof ApiError && e.status === 409) setErr("That username already exists.");
      else setErr("Could not create the account.");
    } finally { setBusy(false); }
  }

  return (
    <section style={card}>
      <div style={cardHead}><UserPlus size={15} /> {t("provision_user")}</div>
      <div style={hierBar}>
        {t("provision_authority")}: <b style={{ color: "var(--ink)" }}>{ROLE_LABEL[actor.role] ?? actor.role}</b> →{" "}
        {roles.map((r) => ROLE_LABEL[r] ?? r).join(" · ")}
        {deptLocked && <> · {t("own_department_only")}</>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, padding: 14 }}>
        <Input label={t("username")} value={username} onChange={setUsername} />
        <Input label={t("full_name")} value={fullName} onChange={setFullName} />
        <Select label={t("role")} value={role} onChange={setRole}
          options={roles.map((r) => ({ value: r, label: ROLE_LABEL[r] ?? r }))} />
        <Select label={t("department")} value={deptId} onChange={setDeptId} disabled={deptLocked}
          options={[{ value: "", label: "—" }, ...deptOptions]} />
        <Input label={t("email")} value={email} onChange={setEmail} />
        {canCross && (
          <label style={crossRow}>
            <input type="checkbox" checked={cross} onChange={(e) => setCross(e.target.checked)} />
            <Network size={14} style={{ color: "var(--violet)" }} />
            {t("inter_department")}
          </label>
        )}
      </div>
      <div style={{ padding: "0 14px 14px", display: "flex", alignItems: "center", gap: 12 }}>
        <Button variant="primary" disabled={busy || !username || !fullName || !role} onClick={() => void submit()}>{t("create")}</Button>
        {err && <span style={{ color: "var(--status-fail)", fontSize: 12 }}>{err}</span>}
      </div>
      {result && (
        <div style={otpBox}>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 4 }}>{t("temp_password_once")}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <code style={otpCode}>{result.temp_password}</code>
            <button style={copyBtn} onClick={() => navigator.clipboard?.writeText(result.temp_password)} title="copy"><Copy size={13} /></button>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 6 }}>
            {result.username} · {ROLE_LABEL[result.role] ?? result.role} · {result.expires_hours}h
          </div>
        </div>
      )}
    </section>
  );
}

const h2: CSSProperties = { margin: 0, fontSize: 18, fontWeight: 600, color: "var(--text-primary)" };
const card: CSSProperties = { background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", overflow: "hidden" };
const cardHead: CSSProperties = { display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", borderBottom: "1px solid var(--border-subtle)", background: "var(--zebra)" };
const hierBar: CSSProperties = { fontSize: 11.5, color: "var(--ink-2)", padding: "8px 14px", background: "var(--blue-soft-2)", borderBottom: "1px solid var(--border-subtle)" };
const crossRow: CSSProperties = { display: "flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 600, color: "var(--ink-2)", alignSelf: "end", paddingBottom: 8 };
const otpBox: CSSProperties = { margin: "0 14px 14px", padding: 12, background: "var(--status-pass-bg)", border: "1px solid var(--status-pass-border)", borderRadius: "var(--radius-md)" };
const otpCode: CSSProperties = { fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700, color: "var(--text-primary)" };
const copyBtn: CSSProperties = { width: 26, height: 26, borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", background: "var(--surface-card)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--text-secondary)" };

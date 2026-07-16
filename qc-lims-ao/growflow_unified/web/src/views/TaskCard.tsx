import { useState, type CSSProperties } from "react";
import {
  ChevronDown, AlertTriangle, Plus, Wand2, GitBranch, Link2, Trash2, Pencil, ArrowRight, MessageSquarePlus,
  CheckCircle2, XCircle, Check, X, UserCheck,
} from "lucide-react";
import { addHandoff, addNote, aiRewrite, deleteTask, respondAssignment, updateTask } from "../api/planner";
import type { Lang, PlannerDepartment, PlannerTask, TaskStatus, UserOut } from "../types/models";
import { dayLabel } from "../i18n";
import { Avatar, PRIORITY_COLOR, STATUS_META, StatusPill, SumaProgress } from "../components/suma";
import { useToast } from "../components/Toast";

const CYCLE: TaskStatus[] = ["pending", "working", "review", "stuck", "postponed", "done"];
const todayDay = (): string => ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][new Date().getDay()];

function progressOf(task: PlannerTask): number {
  if (task.subtasks.length) return Math.round((task.subtasks.filter((s) => s.done).length / task.subtasks.length) * 100);
  return { done: 100, review: 75, working: 50, stuck: 25, postponed: 10, pending: 0 }[task.status] ?? 0;
}

export function TaskCard({
  task, departments, users, allTasks, lang, t, onChanged, onDeleted, onEdit, currentUser, defaultExpanded = false,
}: {
  task: PlannerTask;
  departments: PlannerDepartment[];
  users: UserOut[];
  allTasks: PlannerTask[];
  lang: Lang;
  t: (k: string) => string;
  onChanged: (u: PlannerTask) => void;
  onDeleted: (id: string) => void;
  onEdit: () => void;
  currentUser?: UserOut;
  defaultExpanded?: boolean;
}) {
  const { toast } = useToast();
  const [open, setOpen] = useState(defaultExpanded);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [sub, setSub] = useState("");
  const [declining, setDeclining] = useState(false);
  const [declineReason, setDeclineReason] = useState("");

  const assignment = task.assignment_status ?? "accepted";
  const isAssignee = !!currentUser && !!task.owner_id && currentUser.id === task.owner_id;
  const awaitingMine = isAssignee && assignment === "pending";

  const dept = departments.find((d) => d.id === task.department_id);
  const deptName = dept ? (lang === "mk" ? dept.name_mk : dept.name_en) : task.department_key ?? "";
  const meta = STATUS_META[task.status];
  const helperNames = task.helper_ids.map((id) => users.find((u) => u.id === id)?.full_name).filter(Boolean) as string[];
  const pct = progressOf(task);

  async function run(p: Promise<PlannerTask>, ok?: string) {
    setBusy(true);
    try { const u = await p; onChanged(u); if (ok) toast(ok, "success"); }
    catch { toast(t("save_failed"), "error"); }
    finally { setBusy(false); }
  }
  const cycle = () => {
    const next = CYCLE[(CYCLE.indexOf(task.status) + 1) % CYCLE.length];
    void run(updateTask(task.id, { status: next }));
  };
  const submitNote = () => { if (note.trim()) { void run(addNote(task.id, note.trim(), todayDay()), t("note_added")); setNote(""); } };
  const addSub = () => {
    if (!sub.trim()) return;
    const next = [...task.subtasks.map((s) => ({ text: s.text, done: s.done, position: s.position })),
      { text: sub.trim(), done: false, position: task.subtasks.length }];
    void run(updateTask(task.id, { subtasks: next })); setSub("");
  };
  const toggleSub = (i: number) => {
    const next = task.subtasks.map((s, idx) => ({ text: s.text, done: idx === i ? !s.done : s.done, position: s.position }));
    void run(updateTask(task.id, { subtasks: next }));
  };
  async function rewriteDesc() {
    if (!task.description?.trim()) return;
    setBusy(true);
    try {
      const r = await aiRewrite(task.description);
      if (r.available) { await run(updateTask(task.id, { description: r.text }), t("rewritten")); }
      else toast(t("ai_unavailable"), "error");
    } catch { toast(t("ai_unavailable"), "error"); } finally { setBusy(false); }
  }
  const requestHandoff = () => {
    if (!dept?.handoff_to_id) return;
    void run(addHandoff(task.id, dept.handoff_to_id), `${t("handoff_requested")} → ${handoffName}`);
  };
  const accept = () => { void run(respondAssignment(task.id, "accepted"), t("accepted_toast")); };
  const decline = () => {
    void run(respondAssignment(task.id, "declined", declineReason.trim() || undefined), t("declined_toast"));
    setDeclining(false); setDeclineReason("");
  };
  const remove = () => { setBusy(true); deleteTask(task.id).then(() => { onDeleted(task.id); toast(t("task_deleted"), "success"); }).catch(() => { toast(t("save_failed"), "error"); setBusy(false); }); };

  const handoffDept = dept?.handoff_to_id ? departments.find((d) => d.id === dept.handoff_to_id) : undefined;
  const handoffName = handoffDept ? (lang === "mk" ? handoffDept.name_mk : handoffDept.name_en) : "";
  const subDone = task.subtasks.filter((s) => s.done).length;

  return (
    <div style={{ ...card, borderLeft: `3px solid ${meta.color}` }}>
      {/* header */}
      <div style={head} onClick={() => setOpen((o) => !o)} role="button" tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter") setOpen((o) => !o); }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <ChevronDown size={14} color="var(--text-dim)" style={{ transform: open ? "none" : "rotate(-90deg)", transition: "var(--transition)", flexShrink: 0 }} />
            <span style={{ font: "var(--fw-semibold) var(--fs-base)/1.25 var(--font-body)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{task.title}</span>
          </div>
          <div style={metaRow}>
            <span style={{ color: dept?.color ?? "var(--accent)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>{deptName}</span>
            {task.days.map((d) => <span key={d} style={dayChip}>{dayLabel(d, lang)}</span>)}
            {task.subtasks.length > 0 && (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--text-dim)" }}>
                <GitBranch size={11} />{subDone}/{task.subtasks.length}
              </span>
            )}
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: PRIORITY_COLOR[task.priority], boxShadow: `0 0 6px ${PRIORITY_COLOR[task.priority]}` }} />
              <span style={{ color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{task.priority}</span>
            </span>
            {task.deps.length > 0 && <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--status-postponed)" }}><Link2 size={11} />{task.deps.length}</span>}
            {task.owner_id && assignment === "pending" && (
              <span style={asgChip("var(--status-postponed)")}><UserCheck size={10} />{t("awaiting_acceptance")}</span>
            )}
            {assignment === "declined" && (
              <span style={asgChip("var(--status-stuck)")}><XCircle size={10} />{t("assignment_declined")}</span>
            )}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}>
          <StatusPill status={task.status} label={t(task.status)} onCycle={busy ? undefined : cycle} />
          {(task.owner_name || helperNames.length > 0) && (
            <div style={{ display: "flex" }}>
              {task.owner_name && <Avatar name={task.owner_name} size={22} tone="var(--accent)" />}
              {helperNames.slice(0, 3).map((n, i) => <span key={i} style={{ marginLeft: -7 }}><Avatar name={n} size={22} /></span>)}
            </div>
          )}
        </div>
      </div>

      {/* body */}
      {open && (
        <div style={body}>
          {/* assignment acknowledgment — only the assignee can accept/decline */}
          {awaitingMine && (
            <div style={asgBanner}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--text-soft)", fontSize: "var(--fs-sm)" }}>
                <UserCheck size={14} color="var(--accent)" /> {t("assigned_to_you")}
              </span>
              {!declining ? (
                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={accept} disabled={busy} style={{ ...asgBtn, color: "var(--status-completed)" }}><Check size={13} /> {t("accept")}</button>
                  <button onClick={() => setDeclining(true)} disabled={busy} style={{ ...asgBtn, color: "var(--status-stuck)" }}><X size={13} /> {t("decline")}</button>
                </div>
              ) : (
                <div style={{ display: "flex", gap: 6, flex: 1, minWidth: 180 }}>
                  <input autoFocus value={declineReason} onChange={(e) => setDeclineReason(e.target.value)} placeholder={t("decline_reason_ph")}
                    onKeyDown={(e) => { if (e.key === "Enter") decline(); }} style={inlineInput} />
                  <button onClick={decline} disabled={busy} style={{ ...miniBtn, color: "var(--status-stuck)" }}><Check size={14} /></button>
                </div>
              )}
            </div>
          )}
          {assignment === "declined" && !awaitingMine && (
            <div style={blocker}>
              <XCircle size={13} style={{ flexShrink: 0 }} />
              <span><b>{t("assignment_declined")}</b>{task.assignment_note ? `: ${task.assignment_note}` : ""}</span>
            </div>
          )}

          {task.blocker && (
            <div style={blocker}><AlertTriangle size={13} style={{ flexShrink: 0 }} /> <span><b>{t("blocked")}:</b> {task.blocker}</span></div>
          )}
          {task.description && <p style={{ font: "var(--type-body)", fontSize: "var(--fs-sm)", color: "var(--text-muted)", margin: "0 0 10px", whiteSpace: "pre-wrap" }}>{task.description}</p>}

          {/* outcome / solution */}
          {task.outcome && (
            <div style={outcomeBox}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, font: "var(--fw-bold) var(--fs-2xs)/1 var(--font-mono)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)", color: "var(--status-completed)", marginBottom: 5 }}>
                <CheckCircle2 size={11} /> {t("outcome")}
              </div>
              <span style={{ font: "var(--type-body)", fontSize: "var(--fs-sm)", color: "var(--text-muted)", whiteSpace: "pre-wrap" }}>{task.outcome}</span>
            </div>
          )}

          {/* progress notes */}
          <SectionLabel icon={<MessageSquarePlus size={11} />}>{t("progress_notes")}</SectionLabel>
          {task.notes.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              {task.notes.map((n) => (
                <div key={n.id} style={noteRow}>
                  {n.day && <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)", fontWeight: 600, flexShrink: 0 }}>{dayLabel(n.day, lang)}</span>}
                  <span style={{ color: "var(--text-muted)" }}>{n.note}{n.author_name ? <span style={{ color: "var(--text-faint)" }}> · {n.author_name}</span> : null}</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("add_note_ph")}
              onKeyDown={(e) => { if (e.key === "Enter") submitNote(); }} style={inlineInput} />
            <button title={t("rewrite")} onClick={() => { if (note.trim()) aiRewrite(note).then((r) => r.available && setNote(r.text)).catch(() => {}); }} style={{ ...miniBtn, color: "var(--ai)" }}><Wand2 size={13} /></button>
            <button onClick={submitNote} disabled={busy || !note.trim()} style={miniBtn}><Plus size={14} /></button>
          </div>

          {/* subtasks */}
          <SectionLabel icon={<GitBranch size={11} />}>{t("subtasks")} {task.subtasks.length > 0 && <span style={{ color: "var(--text-faint)" }}>· {subDone}/{task.subtasks.length}</span>}</SectionLabel>
          {task.subtasks.map((s, i) => (
            <label key={s.id ?? i} style={subRow}>
              <input type="checkbox" checked={s.done} onChange={() => toggleSub(i)} style={{ accentColor: "var(--brand)" }} />
              <span style={{ flex: 1, color: s.done ? "var(--text-faint)" : "var(--text-muted)", textDecoration: s.done ? "line-through" : "none" }}>{s.text}</span>
            </label>
          ))}
          <div style={{ display: "flex", gap: 6, margin: "6px 0 14px" }}>
            <input value={sub} onChange={(e) => setSub(e.target.value)} placeholder={t("add_subtask_ph")}
              onKeyDown={(e) => { if (e.key === "Enter") addSub(); }} style={{ ...inlineInput, border: "1px dashed var(--hairline)", background: "transparent" }} />
            <button onClick={addSub} disabled={busy || !sub.trim()} style={miniBtn}><Plus size={14} /></button>
          </div>

          {/* dependencies */}
          {task.deps.length > 0 && (
            <>
              <SectionLabel icon={<Link2 size={11} />}>{t("dependencies")}</SectionLabel>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
                {task.deps.map((id) => {
                  const dt = allTasks.find((x) => x.id === id);
                  const met = dt?.status === "done";
                  const c = met ? "var(--status-completed)" : "var(--status-stuck)";
                  return (
                    <span key={id} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 8px", borderRadius: "var(--radius-xs)", font: "var(--fw-medium) var(--fs-2xs) var(--font-mono)", color: c, background: `color-mix(in srgb, ${c} 13%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 40%, transparent)` }}>
                      <Link2 size={10} />{(dt?.title ?? id).slice(0, 28)} · {met ? t("dep_met") : t("dep_waiting")}
                    </span>
                  );
                })}
              </div>
            </>
          )}

          {/* handoff */}
          {handoffDept && (
            <div style={handoff}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, font: "var(--fw-semibold) var(--fs-xs) var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                <span style={{ color: dept?.color ?? "var(--accent)" }}>{deptName}</span>
                <ArrowRight size={13} color="var(--text-dim)" />
                <span style={{ color: handoffDept.color ?? "var(--highlight)" }}>{handoffName}</span>
              </span>
              <button onClick={requestHandoff} disabled={busy} style={{ ...miniBtn, width: "auto", padding: "0 10px", gap: 5, color: "var(--highlight)", display: "inline-flex" }}>
                <GitBranch size={12} /> {t("request_handoff")}
              </button>
            </div>
          )}

          {/* footer actions */}
          <div style={footer}>
            <div style={{ flex: 1, minWidth: 120 }}><SumaProgress value={pct} tone={meta.color} showValue /></div>
            <button onClick={onEdit} style={actBtn}><Pencil size={12} /> {t("edit")}</button>
            {task.description && <button onClick={rewriteDesc} disabled={busy} style={{ ...actBtn, color: "var(--ai)" }}><Wand2 size={12} /> {t("rewrite")}</button>}
            <button onClick={remove} disabled={busy} style={{ ...actBtn, color: "var(--status-stuck)" }}><Trash2 size={12} /> {t("delete")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

function SectionLabel({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, font: "var(--fw-bold) var(--fs-2xs)/1 var(--font-mono)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)", color: "var(--text-dim)", marginBottom: 6 }}>
      <span style={{ color: "var(--accent)", display: "inline-flex" }}>{icon}</span>{children}
    </div>
  );
}

const card: CSSProperties = { background: "var(--surface-1)", backdropFilter: "var(--blur)", WebkitBackdropFilter: "var(--blur)", border: "var(--border)", borderRadius: "var(--radius-sm)", marginBottom: 8, boxShadow: "var(--shadow-sm)", overflow: "hidden" };
const head: CSSProperties = { display: "flex", alignItems: "flex-start", gap: 10, padding: "11px 13px", cursor: "pointer" };
const metaRow: CSSProperties = { display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginTop: 5, marginLeft: 21, font: "var(--fw-medium) var(--fs-2xs)/1 var(--font-mono)" };
const dayChip: CSSProperties = { color: "var(--text-dim)", background: "var(--glass)", padding: "2px 6px", borderRadius: "var(--radius-xs)" };
const body: CSSProperties = { padding: "10px 13px 13px", borderTop: "var(--border)" };
const blocker: CSSProperties = { display: "flex", alignItems: "center", gap: 8, padding: "8px 11px", marginBottom: 12, fontSize: "var(--fs-sm)", color: "var(--status-stuck)", background: "var(--status-stuck-dim)", border: "1px solid color-mix(in srgb, var(--status-stuck) 40%, transparent)", borderRadius: "var(--radius-sm)" };
const noteRow: CSSProperties = { display: "flex", gap: 8, padding: "5px 0", borderBottom: "1px dashed var(--hairline)", fontSize: "var(--fs-xs)", lineHeight: 1.5 };
const inlineInput: CSSProperties = { flex: 1, height: 30, padding: "0 10px", background: "var(--surface-inset)", border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", color: "var(--text)", font: "var(--type-ui)", outline: "none" };
const miniBtn: CSSProperties = { display: "grid", placeItems: "center", width: 32, height: 30, background: "var(--surface-2)", border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", color: "var(--accent)", cursor: "pointer", flexShrink: 0 };
const subRow: CSSProperties = { display: "flex", alignItems: "center", gap: 9, padding: "5px 0", fontSize: "var(--fs-sm)", cursor: "pointer" };
const handoff: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "9px 11px", marginBottom: 14, borderRadius: "var(--radius-sm)", background: "var(--surface-inset)", border: "var(--border)" };
const footer: CSSProperties = { display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, paddingTop: 12, borderTop: "var(--border)" };
const actBtn: CSSProperties = { display: "inline-flex", alignItems: "center", gap: 5, padding: "5px 9px", background: "var(--surface-inset)", border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", color: "var(--text-soft)", font: "var(--fw-semibold) var(--fs-2xs) var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer" };
const asgBanner: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8, padding: "9px 11px", marginBottom: 12, borderRadius: "var(--radius-sm)", background: "var(--surface-inset)", border: "1px solid color-mix(in srgb, var(--accent) 35%, transparent)" };
const asgBtn: CSSProperties = { display: "inline-flex", alignItems: "center", gap: 5, padding: "5px 11px", background: "var(--surface-2)", border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", font: "var(--fw-semibold) var(--fs-2xs) var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer" };
const outcomeBox: CSSProperties = { padding: "9px 11px", marginBottom: 12, borderRadius: "var(--radius-sm)", background: "var(--status-completed-dim)", border: "1px solid color-mix(in srgb, var(--status-completed) 30%, transparent)" };
const asgChip = (c: string): CSSProperties => ({ display: "inline-flex", alignItems: "center", gap: 4, color: c, padding: "1px 6px", borderRadius: "var(--radius-xs)", background: `color-mix(in srgb, ${c} 13%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 35%, transparent)` });

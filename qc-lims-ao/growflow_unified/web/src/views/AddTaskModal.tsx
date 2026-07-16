import { useState, type CSSProperties } from "react";
import { Sparkles, X } from "lucide-react";
import { Button, Input, Select, Textarea, Field } from "../components";
import { aiRewrite, createTask, deleteTask, updateTask } from "../api/planner";
import { DAYS, dayLabel } from "../i18n";
import type {
  Lang, PlannerDepartment, PlannerTask, TaskPriority, TaskStatus, UserOut,
} from "../types/models";

const STATUSES: TaskStatus[] = ["pending", "working", "review", "stuck", "postponed", "done"];
const PRIORITIES: TaskPriority[] = ["critical", "high", "medium", "low"];

export function AddTaskModal({
  task, weekStart, departments, users, defaultStatus, lang, t, onClose, onSaved,
}: {
  task: PlannerTask | null;             // null = create
  weekStart: string;
  departments: PlannerDepartment[];
  users: UserOut[];
  defaultStatus?: TaskStatus;
  lang: Lang;
  t: (k: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const editing = task !== null;
  const [title, setTitle] = useState(task?.title ?? "");
  const [departmentId, setDepartmentId] = useState(task?.department_id ?? departments[0]?.id ?? "");
  const [ownerId, setOwnerId] = useState(task?.owner_id ?? "");
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? defaultStatus ?? "pending");
  const [priority, setPriority] = useState<TaskPriority>(task?.priority ?? "medium");
  const [days, setDays] = useState<string[]>(task?.days ?? []);
  const [room, setRoom] = useState(task?.room ?? "");
  const [batch, setBatch] = useState(task?.batch ?? "");
  const [tags, setTags] = useState((task?.tags ?? []).join(", "));
  const [description, setDescription] = useState(task?.description ?? "");
  const [outcome, setOutcome] = useState(task?.outcome ?? "");
  const [blocker, setBlocker] = useState(task?.blocker ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rewriting, setRewriting] = useState(false);
  const [aiNote, setAiNote] = useState<string | null>(null);

  const deptName = (d: PlannerDepartment) => (lang === "mk" ? d.name_mk : d.name_en);

  async function rewriteDescription() {
    if (!description.trim()) return;
    setRewriting(true);
    setAiNote(null);
    try {
      const r = await aiRewrite(description);
      if (r.available) setDescription(r.text);
      else setAiNote(r.note ?? t("ai_unavailable"));
    } catch {
      setAiNote(t("ai_unavailable"));
    } finally {
      setRewriting(false);
    }
  }

  function toggleDay(d: string) {
    setDays((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]));
  }

  async function save() {
    if (!title.trim() || !departmentId) return;
    setBusy(true);
    setError(null);
    const payload = {
      department_id: departmentId,
      title: title.trim(),
      week_start: weekStart,
      owner_id: ownerId || null,
      status,
      priority,
      days,
      room: room || null,
      batch: batch || null,
      tags: tags.split(",").map((s) => s.trim()).filter(Boolean),
      description: description || null,
      outcome: outcome || null,
      blocker: blocker || null,
    };
    try {
      if (editing && task) await updateTask(task.id, payload);
      else await createTask(payload);
      onSaved();
    } catch {
      setError("Save failed — is the Core API running?");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!editing || !task) return;
    setBusy(true);
    try {
      await deleteTask(task.id);
      onSaved();
    } catch {
      setError("Delete failed");
      setBusy(false);
    }
  }

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={(e) => e.stopPropagation()}>
        <div style={headerRow}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{editing ? t("save") : t("new_task")}</div>
          <button style={closeBtn} onClick={onClose}><X size={16} /></button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12, overflowY: "auto", padding: "4px 2px" }}>
          <Input label={t("title")} value={title} onChange={setTitle} />
          <div style={grid2}>
            <Select label={t("department")} value={departmentId} onChange={setDepartmentId}
              options={departments.map((d) => ({ value: d.id, label: deptName(d) }))} />
            <Select label={t("owner")} value={ownerId} onChange={setOwnerId}
              options={[{ value: "", label: t("unassigned") }, ...users.map((u) => ({ value: u.id, label: u.full_name }))]} />
          </div>
          <div style={grid2}>
            <Select label={t("status")} value={status} onChange={(v) => setStatus(v as TaskStatus)}
              options={STATUSES.map((s) => ({ value: s, label: t(s) }))} />
            <Select label={t("priority")} value={priority} onChange={(v) => setPriority(v as TaskPriority)}
              options={PRIORITIES.map((p) => ({ value: p, label: p }))} />
          </div>

          <Field label={t("days")}>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {DAYS.map((d) => (
                <button key={d} type="button" onClick={() => toggleDay(d)}
                  style={{ ...dayToggle, ...(days.includes(d) ? dayToggleOn : {}) }}>
                  {dayLabel(d, lang)}
                </button>
              ))}
            </div>
          </Field>

          <div style={grid2}>
            <Input label={t("room")} value={room} onChange={setRoom} />
            <Input label={t("batch")} value={batch} onChange={setBatch} />
          </div>
          <Input label="Tags (comma-separated)" value={tags} onChange={setTags} />
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", letterSpacing: "0.04em", textTransform: "uppercase" }}>{t("description")}</span>
              <Button variant="ghost" size="sm" icon={<Sparkles size={13} />} onClick={rewriteDescription} disabled={rewriting || !description.trim()}>
                {rewriting ? t("drafting") : t("rewrite")}
              </Button>
            </div>
            <Textarea value={description} onChange={setDescription} rows={3} />
            {aiNote && <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>{aiNote}</div>}
          </div>
          <Textarea label={t("outcome")} value={outcome} onChange={setOutcome} rows={2} placeholder={t("outcome_ph")} />
          {status === "stuck" && <Input label={t("blocked")} value={blocker} onChange={setBlocker} />}
          {error && <div style={errBox}>{error}</div>}
        </div>

        <div style={footer}>
          {editing && <Button variant="danger" onClick={remove} disabled={busy}>{t("delete")}</Button>}
          <div style={{ flex: 1 }} />
          <Button variant="ghost" onClick={onClose} disabled={busy}>{t("cancel")}</Button>
          <Button variant="primary" onClick={save} disabled={busy || !title.trim()}>
            {editing ? t("save") : t("create_task")}
          </Button>
        </div>
      </div>
    </div>
  );
}

const overlay: CSSProperties = { position: "fixed", inset: 0, background: "rgba(15,37,64,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 24 };
const modal: CSSProperties = { width: 520, maxHeight: "88vh", display: "flex", flexDirection: "column", background: "var(--surface-card)", borderRadius: "var(--radius-lg)", padding: 18, boxShadow: "0 12px 40px rgba(15,37,64,0.25)" };
const headerRow: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 };
const closeBtn: CSSProperties = { width: 28, height: 28, borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", background: "var(--surface-card)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--text-tertiary)" };
const grid2: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 };
const footer: CSSProperties = { display: "flex", alignItems: "center", gap: 8, marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border-subtle)" };
const dayToggle: CSSProperties = { padding: "4px 9px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-strong)", background: "var(--surface-card)", fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", cursor: "pointer" };
const dayToggleOn: CSSProperties = { background: "var(--color-brand)", borderColor: "var(--color-brand)", color: "var(--text-inverse)" };
const errBox: CSSProperties = { fontSize: 12, color: "var(--status-fail)", background: "var(--status-fail-bg)", border: "1px solid var(--status-fail-border)", borderRadius: "var(--radius-md)", padding: "6px 10px" };

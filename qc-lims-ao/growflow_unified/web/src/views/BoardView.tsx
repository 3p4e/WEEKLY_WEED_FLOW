import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { Plus } from "lucide-react";
import { getTelemetry, listTasks } from "../api/planner";
import type {
  Lang, PlannerDepartment, PlannerTask, PlannerTelemetry, TaskStatus, UserOut,
} from "../types/models";
import { TaskCard } from "./TaskCard";
import { TelemetryBar } from "./TelemetryBar";
import { AddTaskModal } from "./AddTaskModal";

const COLUMNS: TaskStatus[] = ["pending", "working", "review", "stuck", "postponed", "done"];

export function BoardView({
  currentUser, departments, users, weekStart, lang, t,
}: {
  currentUser: UserOut;
  departments: PlannerDepartment[];
  users: UserOut[];
  weekStart: string;
  lang: Lang;
  t: (k: string) => string;
}) {
  const [tasks, setTasks] = useState<PlannerTask[]>([]);
  const [tele, setTele] = useState<PlannerTelemetry | null>(null);
  const [modal, setModal] = useState<{ open: boolean; task: PlannerTask | null; status?: TaskStatus }>({ open: false, task: null });

  const reload = useCallback(async () => {
    try {
      const [all, telemetry] = await Promise.all([listTasks({ weekStart }), getTelemetry(weekStart)]);
      setTasks(all);
      setTele(telemetry);
    } catch {
      setTasks([]);
      setTele(null);
    }
  }, [weekStart]);

  useEffect(() => { void reload(); }, [reload]);

  const refreshTele = useCallback(() => { getTelemetry(weekStart).then(setTele).catch(() => {}); }, [weekStart]);
  const onChanged = (u: PlannerTask) => { setTasks((cur) => cur.map((x) => (x.id === u.id ? u : x))); refreshTele(); };
  const onDeleted = (id: string) => { setTasks((cur) => cur.filter((x) => x.id !== id)); refreshTele(); };

  return (
    <div>
      <TelemetryBar tele={tele} lang={lang} t={t} />
      <div style={cols}>
        {COLUMNS.map((status) => {
          const colTasks = tasks.filter((x) => x.status === status);
          return (
            <div key={status} style={col}>
              <div style={colHead}>
                <span style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)" }}>
                  {t(status)} <span style={{ color: "var(--text-quaternary)" }}>· {colTasks.length}</span>
                </span>
                <button style={addBtn} title={t("new_task")} onClick={() => setModal({ open: true, task: null, status })}>
                  <Plus size={14} />
                </button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {colTasks.map((task) => (
                  <TaskCard key={task.id} task={task} departments={departments} users={users} allTasks={tasks} lang={lang} t={t}
                    currentUser={currentUser} onChanged={onChanged} onDeleted={onDeleted} onEdit={() => setModal({ open: true, task })} />
                ))}
                {colTasks.length === 0 && <div style={emptyCol}>—</div>}
              </div>
            </div>
          );
        })}
      </div>

      {modal.open && (
        <AddTaskModal
          task={modal.task}
          weekStart={weekStart}
          departments={departments}
          users={users}
          defaultStatus={modal.status}
          lang={lang}
          t={t}
          onClose={() => setModal({ open: false, task: null })}
          onSaved={() => { setModal({ open: false, task: null }); void reload(); }}
        />
      )}
    </div>
  );
}

const cols: CSSProperties = { display: "flex", gap: 12, overflowX: "auto", paddingBottom: 8, alignItems: "flex-start" };
const col: CSSProperties = { minWidth: 260, width: 260, flexShrink: 0, background: "var(--color-slate-100)", borderRadius: "var(--radius-lg)", padding: 10 };
const colHead: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, padding: "0 2px" };
const addBtn: CSSProperties = { width: 24, height: 24, borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", background: "var(--surface-card)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--text-tertiary)" };
const emptyCol: CSSProperties = { textAlign: "center", color: "var(--text-quaternary)", fontSize: 12, padding: "12px 0" };

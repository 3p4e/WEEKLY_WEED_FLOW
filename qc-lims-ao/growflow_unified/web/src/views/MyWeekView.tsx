import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Plus, Mic, Search, RotateCcw, ListChecks, AlertTriangle, Clock, CircleDashed, Activity } from "lucide-react";
import { Button } from "../components";
import { KpiCard, Panel, WeekStrip } from "../components/suma";
import { useToast } from "../components/Toast";
import { createTask, getTelemetry, listTasks, rolloverWeek } from "../api/planner";
import { DAYS, dayLabel } from "../i18n";
import type { Lang, PlannerDepartment, PlannerTask, PlannerTelemetry, TaskStatus, UserOut } from "../types/models";
import { TaskCard } from "./TaskCard";
import { AddTaskModal } from "./AddTaskModal";

/* Minimal Web Speech API handle (not in lib.dom types). */
interface SR { lang: string; interimResults: boolean; continuous: boolean; onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void; onend: () => void; start: () => void; stop: () => void; }
type SRCtor = new () => SR;
const speechCtor = (): SRCtor | null => {
  const w = window as unknown as { webkitSpeechRecognition?: SRCtor; SpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

const STATUSES: TaskStatus[] = ["pending", "working", "review", "stuck", "postponed", "done"];

export function MyWeekView({
  currentUser, departments, users, weekStart, lang, t,
}: {
  currentUser: UserOut; departments: PlannerDepartment[]; users: UserOut[]; weekStart: string; lang: Lang; t: (k: string) => string;
}) {
  const { toast } = useToast();
  const [tasks, setTasks] = useState<PlannerTask[]>([]);
  const [tele, setTele] = useState<PlannerTelemetry | null>(null);
  const [modal, setModal] = useState<{ open: boolean; task: PlannerTask | null }>({ open: false, task: null });
  const [activeDay, setActiveDay] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [query, setQuery] = useState("");
  const [composer, setComposer] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const recRef = useRef<SR | null>(null);

  const reload = useCallback(async () => {
    try {
      const [mine, telemetry] = await Promise.all([listTasks({ weekStart, ownerId: currentUser.id }), getTelemetry(weekStart)]);
      setTasks(mine); setTele(telemetry);
    } catch { setTasks([]); setTele(null); }
  }, [weekStart, currentUser.id]);
  useEffect(() => { void reload(); }, [reload]);

  const refreshTele = useCallback(() => { getTelemetry(weekStart).then(setTele).catch(() => {}); }, [weekStart]);
  const onChanged = (u: PlannerTask) => { setTasks((cur) => cur.map((x) => (x.id === u.id ? u : x))); refreshTele(); };
  const onDeleted = (id: string) => { setTasks((cur) => cur.filter((x) => x.id !== id)); refreshTele(); };

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    tasks.forEach((tk) => tk.days.forEach((d) => { c[d] = (c[d] ?? 0) + 1; }));
    return c;
  }, [tasks]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tasks.filter((tk) => {
      if (activeDay && !tk.days.includes(activeDay)) return false;
      if (statusFilter && tk.status !== statusFilter) return false;
      if (q && !`${tk.title} ${tk.room ?? ""} ${tk.batch ?? ""} ${tk.tags.join(" ")}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [tasks, activeDay, statusFilter, query]);

  async function quickAdd() {
    if (!composer.trim()) return;
    setBusy(true);
    try {
      await createTask({
        department_id: currentUser.dept_id ?? departments[0]?.id ?? "",
        title: composer.trim(), week_start: weekStart, owner_id: currentUser.id,
        status: "pending", priority: "medium", days: activeDay ? [activeDay] : [],
      });
      setComposer(""); toast(t("create_task") + " ✓", "success"); await reload();
    } catch { toast(t("save_failed"), "error"); } finally { setBusy(false); }
  }

  function toggleDictation() {
    if (listening) { recRef.current?.stop(); return; }
    const Ctor = speechCtor();
    if (!Ctor) { toast(t("voice_unsupported"), "error"); return; }
    const r = new Ctor();
    r.lang = lang === "mk" ? "mk-MK" : "en-US"; r.interimResults = true; r.continuous = false;
    r.onresult = (e) => { let s = ""; for (let i = 0; i < e.results.length; i++) s += e.results[i][0].transcript; setComposer(s); };
    r.onend = () => { setListening(false); recRef.current = null; };
    recRef.current = r; setListening(true); toast(t("listening"), "info"); r.start();
  }

  async function rollover() {
    setBusy(true);
    try {
      const r = await rolloverWeek(weekStart);
      toast(r.created > 0 ? t("rolled_over").replace("{n}", String(r.created)) : t("nothing_to_roll"), r.created > 0 ? "success" : "info");
      await reload();
    } catch { toast(t("save_failed"), "error"); } finally { setBusy(false); }
  }

  const completion = tele?.completion ?? 0;
  const s = tele?.by_status ?? {};
  const dayLabelFull = activeDay ? dayLabel(activeDay, lang) : (lang === "mk" ? "Сите денови" : "All days");

  return (
    <div>
      {/* Telemetry KPI row */}
      <div style={kpiRow}>
        <KpiCard value={tele?.total ?? 0} label={t("total")} tone="cyan" icon={<ListChecks size={11} />} />
        <KpiCard value={`${completion}%`} label={t("done")} tone="green" active />
        <KpiCard value={s.working ?? 0} label={t("ongoing")} tone="cyan" icon={<Activity size={11} />} />
        <KpiCard value={s.stuck ?? 0} label={t("stuck")} tone="red" icon={<AlertTriangle size={11} />} />
        <KpiCard value={s.postponed ?? 0} label={t("postponed")} tone="amber" icon={<Clock size={11} />} />
        <KpiCard value={s.pending ?? 0} label={t("pending")} tone="neutral" icon={<CircleDashed size={11} />} />
      </div>

      {/* Week strip */}
      <div style={{ margin: "16px 0" }}>
        <WeekStrip days={DAYS} counts={counts} active={activeDay ?? ""} onSelect={(d) => setActiveDay((cur) => (cur === d ? null : d))} />
      </div>

      <Panel
        label={`${t("this_day")} ${dayLabelFull}`} accent
        actions={
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={selectStyle}>
              <option value="">{t("all_statuses")}</option>
              {STATUSES.map((st) => <option key={st} value={st}>{t(st)}</option>)}
            </select>
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <Search size={12} style={{ position: "absolute", left: 8, color: "var(--text-dim)" }} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("search_placeholder")} style={{ ...selectStyle, paddingLeft: 26, width: 180 }} />
            </div>
            <Button variant="secondary" size="sm" icon={<RotateCcw size={13} />} onClick={rollover} disabled={busy}>{t("rollover")}</Button>
            <Button variant="primary" size="sm" icon={<Plus size={13} />} onClick={() => setModal({ open: true, task: null })}>{t("new_task")}</Button>
          </div>
        }
      >
        {/* Composer (quick add for the active day, with voice dictation) */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <input value={composer} onChange={(e) => setComposer(e.target.value)} placeholder={t("add_task_ph")}
            onKeyDown={(e) => { if (e.key === "Enter") void quickAdd(); }} style={composerInput} />
          <button onClick={toggleDictation} title={t("voice_task")} style={{ ...micBtn, ...(listening ? micLive : {}) }}><Mic size={15} /></button>
          <Button variant="primary" icon={<Plus size={14} />} onClick={() => void quickAdd()} disabled={busy || !composer.trim()}>{t("add_task")}</Button>
        </div>

        {visible.length === 0 ? (
          <div style={empty}>{t("no_tasks")}</div>
        ) : (
          visible.map((task) => (
            <TaskCard key={task.id} task={task} departments={departments} users={users} allTasks={tasks} lang={lang} t={t}
              currentUser={currentUser} onChanged={onChanged} onDeleted={onDeleted} onEdit={() => setModal({ open: true, task })} />
          ))
        )}
      </Panel>

      {modal.open && (
        <AddTaskModal task={modal.task} weekStart={weekStart} departments={departments} users={users} lang={lang} t={t}
          onClose={() => setModal({ open: false, task: null })}
          onSaved={() => { setModal({ open: false, task: null }); void reload(); }} />
      )}
    </div>
  );
}

const kpiRow: CSSProperties = { display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10 };
const selectStyle: CSSProperties = { appearance: "none", height: 30, padding: "0 10px", background: "var(--surface-inset)", border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", color: "var(--text)", font: "var(--type-ui)", outline: "none", cursor: "pointer" };
const composerInput: CSSProperties = { flex: 1, height: "var(--control-h)", padding: "0 12px", background: "var(--surface-inset)", border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", color: "var(--text)", font: "var(--type-ui)", outline: "none" };
const micBtn: CSSProperties = { display: "grid", placeItems: "center", width: 38, height: "var(--control-h)", background: "var(--surface-inset)", border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", color: "var(--highlight)", cursor: "pointer", flexShrink: 0 };
const micLive: CSSProperties = { color: "var(--text-on-accent)", background: "var(--highlight)", boxShadow: "var(--glow-gold)" };
const empty: CSSProperties = { padding: 40, textAlign: "center", color: "var(--text-dim)", border: "1px dashed var(--hairline)", borderRadius: "var(--radius-md)" };

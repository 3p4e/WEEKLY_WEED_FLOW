import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { ChevronLeft, ChevronRight, FileJson, FileDown, FileSpreadsheet, Sparkles, Save, Send } from "lucide-react";
import { Button, Textarea } from "../components";
import { aiDraftReport, getReport, listTasks, saveReport, submitReport } from "../api/planner";
import { dayInWindow, mondayOf, rangeLabel, weeklyWindows, type WeekWindow } from "./status";
import { dayLabel } from "../i18n";
import type { Lang, PlannerDepartment, PlannerTask, UserOut } from "../types/models";

const ROLE: Record<string, { en: string; mk: string }> = {
  operator: { en: "Operator", mk: "Оператор" },
  analyst: { en: "QC Analyst", mk: "КК Аналитичар" },
  hod: { en: "Head of Department", mk: "Раководител на оддел" },
  qa: { en: "QA Officer", mk: "ОК Службеник" },
  qp: { en: "Qualified Person", mk: "Квалификувано лице" },
  executive: { en: "Executive", mk: "Раководство" },
  admin: { en: "Administrator", mk: "Администратор" },
};

const day = (t: PlannerTask, ...fs: (keyof PlannerTask)[]) => {
  for (const f of fs) { const v = t[f]; if (typeof v === "string" && v) return v; }
  return "";
};

/* ── Status roll-up (adopted from the QC lifecycle's status summary band) ──── */
interface StatusSummary { total: number; done: number; working: number; review: number; stuck: number; postponed: number; pending: number; completion: number; }
function summarize(list: PlannerTask[]): StatusSummary {
  const s: StatusSummary = { total: list.length, done: 0, working: 0, review: 0, stuck: 0, postponed: 0, pending: 0, completion: 0 };
  for (const x of list) {
    switch (x.status) {
      case "done": s.done++; break;
      case "working": s.working++; break;
      case "review": s.review++; break;
      case "stuck": s.stuck++; break;
      case "postponed": s.postponed++; break;
      case "pending": s.pending++; break;
    }
  }
  s.completion = list.length ? Math.round((s.done / list.length) * 100) : 0;
  return s;
}

interface Submitter { name: string; position: string; department: string; }
interface SignOff { name: string; date: string; }
interface SlimTask {
  title: string; status: string; priority: string;
  department: string | null; owner: string | null;
  days: string[]; room: string | null; batch: string | null; notes: string;
  outcome: string | null;
  started_at: string | null; ended_at: string | null;
}
interface WinDoc { week: number; year: number; range: { from: string; to: string }; label: string; note: string; summary: StatusSummary; tasks: SlimTask[]; }
interface SummaryDoc {
  type: string; generated_at: string; submitter: Submitter;
  signoff: { prepared: SignOff; reviewed: SignOff; approved: SignOff };
  report: WinDoc; plan: WinDoc;
}

export function WeeklySummary({
  t, lang, user, departments,
}: {
  t: (k: string) => string; lang: Lang; user: UserOut; departments: PlannerDepartment[];
}) {
  const [offset, setOffset] = useState(0);
  const [tasks, setTasks] = useState<PlannerTask[]>([]);
  useEffect(() => { listTasks().then(setTasks).catch(() => setTasks([])); }, []);
  const { report, plan } = useMemo(() => weeklyWindows(offset), [offset]);
  const [reportNote, setReportNote] = useState("");
  const [planNote, setPlanNote] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const storeKey = mondayOf(new Date(report.from + "T00:00:00"));

  const submitter: Submitter = useMemo(() => {
    const dept = departments.find((d) => d.id === user.dept_id || d.key === user.dept_key)
      ?? departments.find((d) => d.key === "qc");
    return {
      name: user.full_name,
      position: ROLE[user.role]?.[lang] ?? user.role,
      department: dept ? (lang === "mk" ? dept.name_mk : dept.name_en) : "—",
    };
  }, [departments, user, lang]);

  // Top-level tasks only (the report/plan are about work items, not annex/step leaves).
  const topTasks = useMemo(() => tasks.filter((x) => x.node_kind === "task"), [tasks]);
  const reportTasks = useMemo(
    () => topTasks.filter((x) => dayInWindow(day(x, "completed_at", "ended_at", "updated_at", "started_at", "week_start", "created_at"), report.from, report.to)),
    [topTasks, report]);
  const planTasks = useMemo(
    () => topTasks.filter((x) => {
      const start = day(x, "started_at", "week_start", "created_at");
      return dayInWindow(start, plan.from, plan.to) || (x.status !== "done" && start && start <= plan.to && start >= report.from);
    }),
    [topTasks, plan, report]);

  const reload = useCallback(async () => {
    setStatus(null);
    try {
      const r = await getReport(storeKey);
      setReportNote(r.completed_summary ?? "");
      setPlanNote(r.next_week_plan ?? "");
    } catch { setReportNote(""); setPlanNote(""); }
  }, [storeKey]);
  useEffect(() => { void reload(); }, [reload]);

  async function onSave(submit = false) {
    setBusy(true);
    try {
      const body = { completed_summary: reportNote, progress_summary: "", next_week_plan: planNote };
      await (submit ? submitReport(storeKey, body) : saveReport(storeKey, body));
      setStatus(submit ? t("submitted") + " ✓" : t("save_draft") + " ✓");
    } catch { setStatus(t("api_down")); } finally { setBusy(false); }
  }

  async function onDraft() {
    setBusy(true);
    try {
      const r = await aiDraftReport(storeKey);
      if (r.available) {
        if (r.completed_summary) setReportNote(r.completed_summary);
        if (r.next_week_plan) setPlanNote(r.next_week_plan);
        setStatus(t("ai_draft") + " ✓");
      } else setStatus(t("ai_unavailable"));
    } catch { setStatus(t("ai_unavailable")); } finally { setBusy(false); }
  }

  function buildDoc(): SummaryDoc {
    const slim = (x: PlannerTask): SlimTask => ({
      title: x.title, status: x.status, priority: x.priority,
      department: x.department_key ?? null, owner: x.owner_name ?? null,
      days: x.days, room: x.room ?? null, batch: x.batch ?? null,
      notes: x.notes.map((n) => (n.day ? `${n.day}: ` : "") + n.note).join(" · "),
      outcome: x.outcome ?? null,
      started_at: x.started_at ?? null, ended_at: x.ended_at ?? null,
    });
    const today = new Date().toISOString().slice(0, 10);
    return {
      type: "weekly_summary", generated_at: new Date().toISOString(), submitter,
      signoff: {
        prepared: { name: submitter.name, date: today },
        reviewed: { name: "", date: "" },
        approved: { name: "", date: "" },
      },
      report: { week: report.week, year: report.year, range: { from: report.from, to: report.to }, label: rangeLabel(report.from, report.to), note: reportNote, summary: summarize(reportTasks), tasks: reportTasks.map(slim) },
      plan: { week: plan.week, year: plan.year, range: { from: plan.from, to: plan.to }, label: rangeLabel(plan.from, plan.to), note: planNote, summary: summarize(planTasks), tasks: planTasks.map(slim) },
    };
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify(buildDoc(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `weekly-summary-W${report.week}-${report.year}.json`; a.click();
    URL.revokeObjectURL(url);
  }

  function exportCSV() {
    const esc = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
    const out: string[][] = [];
    // Status-summary band, then the per-task detail rows.
    const band = (win: string, s: StatusSummary) => out.push([
      `# ${win}`, `total=${s.total}`, `done=${s.done}`, `working=${s.working}`,
      `review=${s.review}`, `stuck=${s.stuck}`, `postponed=${s.postponed}`,
      `pending=${s.pending}`, `completion=${s.completion}%`, "", "",
    ]);
    band("report", summarize(reportTasks)); band("plan", summarize(planTasks));
    out.push([]);
    const head = ["Window", "ID", "Title", "Department", "Status", "Priority", "Days", "Owner", "Room", "Batch", "Notes", "Outcome"];
    out.push(head);
    const push = (win: string, list: PlannerTask[]) => list.forEach((x) => out.push([
      win, x.id, x.title, x.department_key ?? "", x.status, x.priority, x.days.join("|"),
      x.owner_name ?? "", x.room ?? "", x.batch ?? "",
      x.notes.map((n) => `${n.day ?? ""}: ${n.note}`).join(" | "),
      x.outcome ?? "",
    ]));
    push("report", reportTasks); push("plan", planTasks);
    const csv = "﻿" + out.map((r) => r.map((c) => esc(String(c))).join(",")).join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `weekly-summary-W${report.week}-${report.year}.csv`; a.click();
    URL.revokeObjectURL(url);
  }

  async function exportPDF() {
    const [{ jsPDF }, autoTableMod] = await Promise.all([import("jspdf"), import("jspdf-autotable")]);
    const autoTable = autoTableMod.default;
    const doc = buildDoc();
    const pdf = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });
    const M = 12;                 // narrow margins
    const right = 210 - M;
    let y = M + 2;

    // Fixed labels are kept Latin-only: the standard jsPDF fonts can't render Cyrillic.
    const STAT_EN: Record<string, string> = { done: "Done", working: "Working", review: "In review", stuck: "Stuck", postponed: "Postponed", pending: "Not started" };

    pdf.setFont("helvetica", "bold"); pdf.setFontSize(15); pdf.setTextColor(22, 35, 59);
    pdf.text("GrowFlow — Weekly Summary", M, y);
    pdf.setFont("helvetica", "normal"); pdf.setFontSize(9); pdf.setTextColor(86, 104, 132);
    pdf.text(submitter.name, right, y - 1, { align: "right" });
    pdf.text(submitter.position, right, y + 3, { align: "right" });
    pdf.text(submitter.department, right, y + 7, { align: "right" });
    y += 6;
    pdf.setDrawColor(47, 107, 255); pdf.setLineWidth(0.5); pdf.line(M, y, right, y); y += 6;

    const pageBreak = (need: number) => { if (y + need > 282) { pdf.addPage(); y = M + 2; } };

    const sumLine = (s: StatusSummary) =>
      `Total ${s.total}  ·  Done ${s.done} (${s.completion}%)  ·  Working ${s.working}  ·  In review ${s.review}  ·  Stuck ${s.stuck}  ·  Postponed ${s.postponed}  ·  Not started ${s.pending}`;

    const section = (label: string, w: WinDoc) => {
      pageBreak(24);
      pdf.setFont("helvetica", "bold"); pdf.setFontSize(11); pdf.setTextColor(47, 107, 255);
      pdf.text(`${label} — Week ${w.week} · ${w.label}`, M, y); y += 5;
      pdf.setFont("helvetica", "normal"); pdf.setFontSize(7.5); pdf.setTextColor(86, 104, 132);
      pdf.text(sumLine(w.summary), M, y);
      autoTable(pdf, {
        startY: y + 2, margin: { left: M, right: M }, theme: "grid",
        head: [["Task", "Status", "Priority", "Dept", "Days", "Owner", "Notes"]],
        body: w.tasks.length
          ? w.tasks.map((x) => [x.title, STAT_EN[x.status] ?? x.status, x.priority, x.department ?? "—", x.days.join(", ") || "—", x.owner ?? "—", x.notes || "—"])
          : [["No tasks", "", "", "", "", "", ""]],
        styles: { fontSize: 7.5, cellPadding: 1.3, textColor: [22, 35, 59], overflow: "linebreak", valign: "top" },
        headStyles: { fillColor: [240, 245, 252], textColor: [86, 104, 132], fontSize: 7 },
        columnStyles: { 0: { cellWidth: 42 }, 1: { cellWidth: 18 }, 2: { cellWidth: 16 }, 3: { cellWidth: 16 }, 4: { cellWidth: 20 }, 5: { cellWidth: 26 }, 6: { cellWidth: "auto" } },
      });
      y = (pdf as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 4;
      if (w.note) {
        pageBreak(16);
        pdf.setFont("helvetica", "bold"); pdf.setFontSize(8); pdf.setTextColor(86, 104, 132);
        pdf.text("Narrative", M, y); y += 4;
        pdf.setFont("helvetica", "normal"); pdf.setFontSize(8.5); pdf.setTextColor(22, 35, 59);
        const lines = pdf.splitTextToSize(w.note, right - M) as string[];
        pdf.text(lines, M, y); y += lines.length * 4 + 4;
      }
    };
    section("Report (this week)", doc.report);
    section("Plan (next week)", doc.plan);

    // Sign-off block (GMP-style approval chain: Prepared / Reviewed / Approved).
    pageBreak(34);
    y += 2;
    pdf.setDrawColor(47, 107, 255); pdf.setLineWidth(0.4); pdf.line(M, y, right, y); y += 6;
    pdf.setFont("helvetica", "bold"); pdf.setFontSize(10); pdf.setTextColor(22, 35, 59);
    pdf.text("Signatures", M, y); y += 12;
    const colW = (right - M) / 3;
    const sigs: { label: string; sg: SignOff }[] = [
      { label: "Prepared by", sg: doc.signoff.prepared },
      { label: "Reviewed by", sg: doc.signoff.reviewed },
      { label: "Approved by", sg: doc.signoff.approved },
    ];
    sigs.forEach(({ label, sg }, i) => {
      const x = M + i * colW;
      const lineW = colW - 8;
      pdf.setDrawColor(120, 135, 160); pdf.setLineWidth(0.3); pdf.line(x, y, x + lineW, y);
      pdf.setFont("helvetica", "bold"); pdf.setFontSize(8); pdf.setTextColor(86, 104, 132);
      pdf.text(label, x, y + 4);
      pdf.setFont("helvetica", "normal"); pdf.setFontSize(8.5); pdf.setTextColor(22, 35, 59);
      pdf.text(sg.name || " ", x, y + 9);
      pdf.text(`Date: ${sg.date || "________________"}`, x, y + 14);
    });
    y += 20;

    pdf.setFontSize(7.5); pdf.setTextColor(138, 153, 176);
    pdf.text(`Generated ${doc.generated_at} · GrowFlow Unified · Purely Plant`, M, 290);
    pdf.save(`weekly-summary-W${doc.report.week}-${doc.report.year}.pdf`);
  }

  return (
    <div style={{ maxWidth: 920 }}>
      <div style={topRow}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: "var(--ink)", margin: 0 }}>{t("weekly_summary")}</h2>
          <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 2 }}>
            {submitter.name} · {submitter.position} · {submitter.department}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button style={navBtn} onClick={() => setOffset((o) => o - 1)} title={t("prev_week")}><ChevronLeft size={15} /></button>
          <button style={navBtn} onClick={() => setOffset(0)} title={t("today")}>{t("today")}</button>
          <button style={navBtn} onClick={() => setOffset((o) => o + 1)} title={t("next_week")}><ChevronRight size={15} /></button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, margin: "14px 0", flexWrap: "wrap" }}>
        <Button variant="secondary" icon={<Sparkles size={15} />} onClick={onDraft} disabled={busy}>{t("ai_draft")}</Button>
        <Button variant="ghost" icon={<Save size={15} />} onClick={() => onSave(false)} disabled={busy}>{t("save_draft")}</Button>
        <Button variant="primary" icon={<Send size={15} />} onClick={() => onSave(true)} disabled={busy}>{t("submit_report")}</Button>
        <div style={{ flex: 1 }} />
        <Button variant="secondary" icon={<FileSpreadsheet size={15} />} onClick={exportCSV}>CSV</Button>
        <Button variant="secondary" icon={<FileJson size={15} />} onClick={exportJSON}>JSON</Button>
        <Button variant="secondary" icon={<FileDown size={15} />} onClick={exportPDF}>PDF</Button>
      </div>
      {status && <div style={statusBar}>{status}</div>}

      <Section
        title={t("this_week_report")} win={report} accent="var(--green)"
        tasks={reportTasks} note={reportNote} onNote={setReportNote} t={t} lang={lang}
      />
      <Section
        title={t("next_week_plan_title")} win={plan} accent="var(--blue)"
        tasks={planTasks} note={planNote} onNote={setPlanNote} t={t} lang={lang}
      />

      <SignOffBlock t={t} preparedName={submitter.name} />
    </div>
  );
}

function Section({
  title, win, accent, tasks, note, onNote, t, lang,
}: {
  title: string; win: WeekWindow; accent: string; tasks: PlannerTask[];
  note: string; onNote: (v: string) => void; t: (k: string) => string; lang: Lang;
}) {
  const s = summarize(tasks);
  return (
    <div style={card}>
      <div style={{ ...cardHead, borderLeft: `3px solid ${accent}` }}>
        <span style={{ fontWeight: 800, color: "var(--ink)" }}>{title}</span>
        <span style={{ marginLeft: "auto", fontSize: 12, fontWeight: 700, color: "var(--ink-2)" }}>
          {t("week")} {win.week} · {rangeLabel(win.from, win.to)}
        </span>
      </div>
      <div style={{ padding: 14 }}>
        <div style={bandRow} aria-label={t("status_summary")}>
          <Stat label={t("total")} value={s.total} />
          <Stat label={t("done")} value={`${s.done} · ${s.completion}%`} tone="var(--green)" />
          <Stat label={t("working")} value={s.working} tone="var(--blue)" />
          <Stat label={t("review")} value={s.review} />
          <Stat label={t("stuck")} value={s.stuck} tone="var(--red, #e5484d)" />
          <Stat label={t("postponed")} value={s.postponed} />
          <Stat label={t("pending")} value={s.pending} />
        </div>
        {tasks.length === 0 ? <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{t("no_tasks")}</div> : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr>
              {[t("title"), t("status"), t("priority"), t("department"), t("days"), t("owner")].map((h) => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {tasks.map((x) => (
                <tr key={x.id}>
                  <td style={td}>{x.title}</td>
                  <td style={td}>{t(x.status)}</td>
                  <td style={td}>{x.priority}</td>
                  <td style={{ ...td, color: "var(--ink-2)" }}>{x.department_key ?? "—"}</td>
                  <td style={{ ...td, color: "var(--ink-2)" }}>{x.days.map((d) => dayLabel(d, lang)).join(", ") || "—"}</td>
                  <td style={{ ...td, color: "var(--ink-2)" }}>{x.owner_name ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ marginTop: 12 }}>
          <Textarea label={t("narrative")} value={note} onChange={onNote} rows={3} />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div style={statChip}>
      <span style={{ fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 800, color: tone ?? "var(--ink)" }}>{value}</span>
    </div>
  );
}

/* GMP-style approval chain rendered on-screen, mirroring the exported document. */
function SignOffBlock({ t, preparedName }: { t: (k: string) => string; preparedName: string }) {
  const today = new Date().toISOString().slice(0, 10);
  const cols: { label: string; name: string; date: string }[] = [
    { label: t("prepared_by"), name: preparedName, date: today },
    { label: t("reviewed_by"), name: "", date: "" },
    { label: t("approved_by"), name: "", date: "" },
  ];
  return (
    <div style={card}>
      <div style={{ ...cardHead, borderLeft: "3px solid var(--blue)" }}>
        <span style={{ fontWeight: 800, color: "var(--ink)" }}>{t("signatures")}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, padding: 16 }}>
        {cols.map((c) => (
          <div key={c.label}>
            <div style={{ height: 28, borderBottom: "1px solid var(--line)" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>{c.name || " "}</span>
            </div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-2)", marginTop: 4 }}>{c.label}</div>
            <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>
              {t("date_label")}: {c.date || "____________"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const topRow: CSSProperties = { display: "flex", alignItems: "flex-start", justifyContent: "space-between" };
const navBtn: CSSProperties = { padding: "6px 11px", borderRadius: "var(--radius-md)", border: "1px solid var(--line)", background: "var(--surface-card)", fontSize: 12, fontWeight: 700, color: "var(--ink-2)", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 };
const card: CSSProperties = { background: "var(--surface-card)", border: "1px solid var(--line)", borderRadius: "var(--radius-lg)", marginTop: 14, overflow: "hidden" };
const cardHead: CSSProperties = { display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", background: "var(--surface-2)", borderBottom: "1px solid var(--line)" };
const bandRow: CSSProperties = { display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 };
const statChip: CSSProperties = { display: "flex", flexDirection: "column", gap: 1, padding: "6px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--line)", background: "var(--surface-2)", minWidth: 64 };
const th: CSSProperties = { textAlign: "left", padding: "5px 6px", borderBottom: "1px solid var(--line)", fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em" };
const td: CSSProperties = { padding: "6px", borderBottom: "1px solid var(--line-2)", fontSize: 12.5, color: "var(--ink)" };
const statusBar: CSSProperties = { fontSize: 12, color: "var(--ink-2)", background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: "var(--radius-md)", padding: "7px 11px", marginBottom: 4 };

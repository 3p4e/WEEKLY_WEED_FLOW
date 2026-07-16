import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Sparkles, Users, FileCheck2, TrendingUp, AlertTriangle, Eye, ListChecks, CalendarClock } from "lucide-react";
import { Button } from "../components";
import { Eyebrow, KpiCard, Panel, SumaProgress } from "../components/suma";
import { getExecInsights, getExecTelemetry } from "../api/planner";
import type { ExecInsight, ExecTelemetry, Lang } from "../types/models";
import { dayLabel } from "../i18n";
import { weekLabel } from "./status";

export function ExecutiveDashboard({ weekStart, lang, t }: { weekStart: string; lang: Lang; t: (k: string) => string }) {
  const [tele, setTele] = useState<ExecTelemetry | null>(null);
  const [insight, setInsight] = useState<ExecInsight | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setErr(null); setInsight(null);
    try { setTele(await getExecTelemetry(weekStart)); }
    catch { setTele(null); setErr(t("api_down")); }
  }, [weekStart, t]);
  useEffect(() => { void reload(); }, [reload]);

  async function runAnalysis() {
    setAnalyzing(true);
    try { setInsight(await getExecInsights(weekStart)); }
    catch { setErr(t("api_down")); }
    finally { setAnalyzing(false); }
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Eyebrow tone="gold">OPERATIONS INTELLIGENCE</Eyebrow>
        <h2 style={{ font: "var(--type-heading)", color: "var(--text)", marginTop: 6 }}>{t("exec_overview")}</h2>
        <div style={{ font: "var(--fw-medium) var(--fs-xs) var(--font-mono)", color: "var(--text-dim)", letterSpacing: "0.08em", marginTop: 2 }}>{weekLabel(weekStart)}</div>
      </div>
      {err && <div style={warnBox}>{err}</div>}

      {tele && (
        <>
          <div style={kpiRow}>
            <KpiCard value={`${tele.completion}%`} label={t("completion")} tone="green" active />
            <KpiCard value={tele.total} label={t("total")} tone="cyan" icon={<ListChecks size={11} />} />
            <KpiCard value={tele.headcount} label={t("headcount")} tone="violet" icon={<Users size={11} />} />
            <KpiCard value={tele.by_status.stuck ?? 0} label={t("stuck")} tone="red" icon={<AlertTriangle size={11} />} />
            <KpiCard value={tele.reports_submitted} label={t("reports_in")} tone="gold" icon={<FileCheck2 size={11} />} />
            <KpiCard value={tele.busiest_day ? dayLabel(tele.busiest_day, lang) : "—"} label={t("busiest")} tone="neutral" icon={<CalendarClock size={11} />} />
          </div>

          <div style={twoCol}>
            <Panel label={t("by_department")} eyebrowIcon={<TrendingUp size={12} />} accent>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {tele.by_department.map((d) => (
                  <BarRow key={d.dept_id} label={lang === "mk" ? d.name_mk : d.name_en} pct={d.completion}
                    sub={`${d.done}/${d.total}`} stuck={d.stuck} t={t} tone={d.stuck > 0 ? "var(--status-stuck)" : "var(--brand)"} />
                ))}
                {tele.by_department.length === 0 && <Empty t={t} />}
              </div>
            </Panel>
            <Panel label={t("by_person")} eyebrowIcon={<Users size={12} />} accent>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {tele.by_user.map((u) => (
                  <BarRow key={u.user_id} label={u.user_name} pct={u.completion} sub={`${u.done}/${u.total}`} stuck={0} t={t} tone="var(--accent)" />
                ))}
                {tele.by_user.length === 0 && <Empty t={t} />}
              </div>
            </Panel>
          </div>
        </>
      )}

      <Panel label={t("ai_analysis")} eyebrowIcon={<Sparkles size={12} />} accent style={{ marginTop: 16 }}
        actions={<Button variant="primary" size="sm" icon={<Sparkles size={13} />} onClick={runAnalysis} disabled={analyzing}>{analyzing ? t("analyzing") : t("run_analysis")}</Button>}>
        {!insight && <div style={{ font: "var(--type-body)", fontSize: "var(--fs-sm)", color: "var(--text-dim)" }}>{t("no_insight_yet")}</div>}
        {insight && !insight.available && <div style={warnBox}>{insight.note}</div>}
        {insight && insight.available && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {insight.summary && <p style={{ font: "var(--type-body)", fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>{insight.summary}</p>}
            {insight.highlights.length > 0 && <InsightList icon={<TrendingUp size={13} />} title={t("highlights")} items={insight.highlights} color="var(--status-completed)" />}
            {insight.risks.length > 0 && <InsightList icon={<AlertTriangle size={13} />} title={t("risks")} items={insight.risks} color="var(--status-stuck)" />}
            {insight.foresight && (
              <div>
                <Label icon={<Eye size={13} />} text={t("foresight")} color="var(--ai)" />
                <p style={{ font: "var(--type-body)", fontSize: "var(--fs-sm)", color: "var(--text-muted)", marginTop: 4 }}>{insight.foresight}</p>
              </div>
            )}
          </div>
        )}
        {insight && insight.sources.length > 0 && (
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: "var(--border)" }}>
            <Label text={`${t("sources")} (${insight.sources.length})`} />
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 6 }}>
              {insight.sources.map((s) => <span key={s} style={sourceChip}>{s}</span>)}
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function BarRow({ label, pct, sub, stuck, t, tone }: { label: string; pct: number; sub: string; stuck: number; t: (k: string) => string; tone: string }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
        <span style={{ font: "var(--fw-semibold) var(--fs-sm) var(--font-body)", color: "var(--text)" }}>{label}</span>
        <span style={{ font: "var(--fw-medium) var(--fs-2xs) var(--font-mono)", color: "var(--text-dim)" }}>
          {sub}{stuck > 0 ? <span style={{ color: "var(--status-stuck)" }}> · {stuck} {t("stuck").toLowerCase()}</span> : null}
        </span>
      </div>
      <SumaProgress value={pct} tone={tone} showValue />
    </div>
  );
}

function InsightList({ icon, title, items, color }: { icon: ReactNode; title: string; items: string[]; color: string }) {
  return (
    <div>
      <Label icon={icon} text={title} color={color} />
      <ul style={{ margin: "5px 0 0", paddingLeft: 18 }}>
        {items.map((it, i) => <li key={i} style={{ font: "var(--type-body)", fontSize: "var(--fs-sm)", color: "var(--text-muted)", marginBottom: 3 }}>{it}</li>)}
      </ul>
    </div>
  );
}

function Label({ icon, text, color }: { icon?: ReactNode; text: string; color?: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, font: "var(--fw-bold) var(--fs-2xs) var(--font-mono)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)", color: color ?? "var(--text-dim)" }}>
      {icon}{text}
    </span>
  );
}

function Empty({ t }: { t: (k: string) => string }) {
  return <div style={{ font: "var(--type-body)", fontSize: "var(--fs-xs)", color: "var(--text-faint)" }}>{t("no_tasks")}</div>;
}

const kpiRow: CSSProperties = { display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, marginBottom: 16 };
const twoCol: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 };
const warnBox: CSSProperties = { font: "var(--type-ui)", fontSize: "var(--fs-xs)", color: "var(--status-stuck)", background: "var(--status-stuck-dim)", border: "1px solid color-mix(in srgb, var(--status-stuck) 40%, transparent)", borderRadius: "var(--radius-md)", padding: "8px 12px", marginBottom: 10 };
const sourceChip: CSSProperties = { font: "var(--fw-medium) var(--fs-2xs) var(--font-mono)", color: "var(--text-soft)", background: "var(--surface-2)", borderRadius: "var(--radius-pill)", padding: "2px 8px" };

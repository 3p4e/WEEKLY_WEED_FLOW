import type { CSSProperties } from "react";
import type { Lang, PlannerTelemetry } from "../types/models";
import { dayLabel } from "../i18n";

export function TelemetryBar({ tele, lang, t }: { tele: PlannerTelemetry | null; lang: Lang; t: (k: string) => string }) {
  if (!tele) return null;
  const s = tele.by_status;
  return (
    <div style={bar}>
      <Stat v={`${tele.completion}%`} l={t("completion")} c="var(--status-pass)" />
      <Stat v={tele.total} l={t("total")} c="var(--text-primary)" />
      <Stat v={s.working ?? 0} l={t("working")} c="var(--status-pending)" />
      <Stat v={s.stuck ?? 0} l={t("stuck")} c="var(--status-fail)" />
      <Stat v={s.postponed ?? 0} l={t("postponed")} c="var(--text-tertiary)" />
      <Stat v={s.done ?? 0} l={t("done")} c="var(--status-pass)" />
      <Stat v={tele.busiest_day ? dayLabel(tele.busiest_day, lang) : "—"} l={t("busiest")} c="var(--status-review)" />
      <div style={track}><span style={{ display: "block", height: "100%", width: `${tele.completion}%`, background: "var(--status-pass)", borderRadius: 999 }} /></div>
    </div>
  );
}

function Stat({ v, l, c }: { v: string | number; l: string; c: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 56 }}>
      <span style={{ fontSize: 18, fontWeight: 700, color: c, lineHeight: 1.1 }}>{v}</span>
      <span style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{l}</span>
    </div>
  );
}

const bar: CSSProperties = { display: "flex", alignItems: "center", gap: 18, background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: "12px 18px", marginBottom: 18, flexWrap: "wrap" };
const track: CSSProperties = { flex: 1, minWidth: 120, height: 8, background: "var(--color-slate-100)", borderRadius: 999, overflow: "hidden" };

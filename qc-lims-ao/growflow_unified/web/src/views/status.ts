/* Map planner status/priority onto the shared Badge tones, plus week helpers. */
import type { BadgeStatus } from "../components";
import type { TaskStatus, TaskPriority } from "../types/models";

export function statusBadge(status: TaskStatus): BadgeStatus {
  switch (status) {
    case "done":
      return "conforms";
    case "working":
      return "review";
    case "review":
      return "issued";
    case "stuck":
      return "oos";
    case "postponed":
      return "pending";
    case "pending":
    default:
      return "draft";
  }
}

export function priorityBadge(priority: TaskPriority): BadgeStatus {
  switch (priority) {
    case "critical":
      return "oos";
    case "high":
      return "pending";
    case "medium":
      return "review";
    case "low":
    default:
      return "na";
  }
}

/** Monday (ISO) of the week containing `d`, as YYYY-MM-DD. */
export function mondayOf(d: Date): string {
  const x = new Date(d);
  const dow = (x.getDay() + 6) % 7; // 0 = Monday
  x.setDate(x.getDate() - dow);
  x.setHours(0, 0, 0, 0);
  return toISODate(x);
}

export function addWeeks(isoMonday: string, weeks: number): string {
  const x = new Date(isoMonday + "T00:00:00");
  x.setDate(x.getDate() + weeks * 7);
  return toISODate(x);
}

export function toISODate(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** "Jun 8 – Jun 14" label for the week starting at `isoMonday`. */
export function weekLabel(isoMonday: string): string {
  const s = new Date(isoMonday + "T00:00:00");
  const e = new Date(s);
  e.setDate(s.getDate() + 6);
  return `${MONTHS[s.getMonth()]} ${s.getDate()} – ${MONTHS[e.getMonth()]} ${e.getDate()}`;
}

/* ── Friday→Thursday reporting weeks (Weekly Summary) ──────────────────────── */

/** ISO-8601 week number for a date (weeks are Thursday-anchored). */
export function isoWeek(d: Date): number {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = (date.getUTCDay() + 6) % 7;          // Mon=0
  date.setUTCDate(date.getUTCDate() - dayNum + 3);    // nearest Thursday
  const firstThu = new Date(Date.UTC(date.getUTCFullYear(), 0, 4));
  const firstThuDay = (firstThu.getUTCDay() + 6) % 7;
  firstThu.setUTCDate(firstThu.getUTCDate() - firstThuDay + 3);
  return 1 + Math.round((date.getTime() - firstThu.getTime()) / (7 * 24 * 3600 * 1000));
}

export interface WeekWindow { from: string; to: string; week: number; year: number; }

/** The report window (previous Friday → this Thursday) and the plan window
 *  (Friday → following Thursday), shifted by `offsetWeeks`. */
export function weeklyWindows(offsetWeeks = 0): { report: WeekWindow; plan: WeekWindow } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const daysSinceFri = (today.getDay() - 5 + 7) % 7;   // Friday = 5
  const friday = new Date(today);
  friday.setDate(today.getDate() - daysSinceFri + offsetWeeks * 7);
  const reportTo = new Date(friday); reportTo.setDate(friday.getDate() + 6);      // Thursday
  const planFrom = new Date(reportTo); planFrom.setDate(reportTo.getDate() + 1);   // next Friday
  const planTo = new Date(planFrom); planTo.setDate(planFrom.getDate() + 6);       // next Thursday
  const win = (from: Date, to: Date): WeekWindow => ({ from: toISODate(from), to: toISODate(to), week: isoWeek(to), year: to.getFullYear() });
  return { report: win(friday, reportTo), plan: win(planFrom, planTo) };
}

/** "Jun 26 – Jul 2, 2026" for an ISO date range. */
export function rangeLabel(fromISO: string, toISO: string): string {
  const s = new Date(fromISO + "T00:00:00"), e = new Date(toISO + "T00:00:00");
  return `${MONTHS[s.getMonth()]} ${s.getDate()} – ${MONTHS[e.getMonth()]} ${e.getDate()}, ${e.getFullYear()}`;
}

/** Is the day part of `ts` (YYYY-MM-DD…) within [from, to] inclusive? */
export function dayInWindow(ts: string | null | undefined, from: string, to: string): boolean {
  if (!ts) return false;
  const d = ts.slice(0, 10);
  return d >= from && d <= to;
}

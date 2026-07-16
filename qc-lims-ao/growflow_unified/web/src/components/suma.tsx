import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from "react";
import {
  CheckCircle2, Loader2, AlertTriangle, Clock, Circle, Eye, Shield, type LucideIcon,
} from "lucide-react";
import type { TaskStatus, TaskPriority, Role } from "../types/models";

/* ═══════════════════════════════════════════════════════════════════════════
   SUMA primitives — ported from the Purely Plant · SUMA design system.
   Dark control-room language: hex motifs, chamfered HUD panels, neon glow.
   All colours come from CSS vars (theme-reactive via [data-theme]).
   ═══════════════════════════════════════════════════════════════════════════ */

/* ── Status + role vocab (mapped onto the existing 6-status backend) ── */
export interface StatusMeta { color: string; dim: string; Icon: LucideIcon; }
export const STATUS_META: Record<TaskStatus, StatusMeta> = {
  done:      { color: "var(--status-completed)", dim: "var(--status-completed-dim)", Icon: CheckCircle2 },
  working:   { color: "var(--status-ongoing)",   dim: "var(--status-ongoing-dim)",   Icon: Loader2 },
  review:    { color: "var(--status-review)",    dim: "var(--status-review-dim)",    Icon: Eye },
  stuck:     { color: "var(--status-stuck)",     dim: "var(--status-stuck-dim)",     Icon: AlertTriangle },
  postponed: { color: "var(--status-postponed)", dim: "var(--status-postponed-dim)", Icon: Clock },
  pending:   { color: "var(--status-pending)",   dim: "var(--status-pending-dim)",   Icon: Circle },
};
export const PRIORITY_COLOR: Record<TaskPriority, string> = {
  critical: "var(--status-stuck)", high: "var(--status-postponed)", medium: "var(--highlight)", low: "var(--text-dim)",
};
const ROLE_COLOR: Record<Role, string> = {
  operator: "var(--role-staff)", qa: "var(--role-team_leader)", qp: "var(--role-team_leader)",
  hod: "var(--role-hod)", executive: "var(--role-executive)", admin: "var(--role-owner)",
};

/* ── HexBadge ── */
export function HexBadge({
  children, size = 44, tone = "gold", glow = true, style,
}: { children?: ReactNode; size?: number; tone?: "gold" | "cyan" | "brand" | "violet" | "hollow"; glow?: boolean; style?: CSSProperties }) {
  const bg = tone === "gold" ? "var(--grad-gold)" : tone === "cyan" ? "var(--grad-cyan)"
    : tone === "brand" ? "linear-gradient(160deg,var(--green-300),var(--green-500))"
    : tone === "violet" ? "linear-gradient(160deg,var(--violet-300),var(--violet-500))" : "var(--surface-2)";
  const fg = tone === "hollow" ? "var(--accent)" : tone === "violet" ? "#160c2e" : "var(--text-on-accent)";
  const sh = !glow || tone === "hollow" ? "none"
    : tone === "cyan" ? "var(--glow-cyan-sm)" : tone === "brand" ? "var(--glow-green)" : tone === "violet" ? "var(--glow-violet)" : "var(--glow-gold-sm)";
  return (
    <span style={{ display: "inline-grid", placeItems: "center", width: size, height: size, flexShrink: 0,
      clipPath: "var(--clip-hex)", background: bg, color: fg, boxShadow: sh,
      font: `var(--fw-bold) ${Math.round(size * 0.34)}px/1 var(--font-mono)`, ...style }}>
      {children}
    </span>
  );
}

/* ── Eyebrow ── */
export function Eyebrow({ children, tone = "cyan", node = true }: { children: ReactNode; tone?: "cyan" | "gold" | "brand" | "muted"; node?: boolean }) {
  const c = tone === "gold" ? "var(--highlight)" : tone === "brand" ? "var(--brand)" : tone === "muted" ? "var(--text-dim)" : "var(--accent)";
  return (
    <span style={{ font: "var(--eyebrow-font)", letterSpacing: "var(--tracking-widest)", textTransform: "uppercase", color: c, display: "inline-flex", alignItems: "center", gap: 8 }}>
      {node && <span style={{ width: 6, height: 6, borderRadius: "50%", background: c, boxShadow: "0 0 8px currentColor", flexShrink: 0 }} />}
      {children}
    </span>
  );
}

/* ── Panel (glass HUD section) ── */
export function Panel({
  label, eyebrowIcon, actions, accent = false, solid = false, children, style, bodyStyle,
}: { label?: ReactNode; eyebrowIcon?: ReactNode; actions?: ReactNode; accent?: boolean; solid?: boolean; children?: ReactNode; style?: CSSProperties; bodyStyle?: CSSProperties }) {
  return (
    <section style={{ position: "relative", background: solid ? "var(--surface-solid)" : "var(--surface-1)", backdropFilter: solid ? undefined : "var(--blur)", WebkitBackdropFilter: solid ? undefined : "var(--blur)", border: "var(--border)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-md), var(--shadow-inset)", overflow: "hidden", ...style }}>
      {accent && <span style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: "var(--grad-energy)", opacity: 0.9 }} />}
      {(label || actions) && (
        <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "0.7rem 0.9rem", borderBottom: "var(--border)" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 7, font: "var(--fw-semibold) var(--fs-xs)/1 var(--font-mono)", letterSpacing: "var(--tracking-wider)", textTransform: "uppercase", color: "var(--text-soft)" }}>
            {eyebrowIcon && <span style={{ color: "var(--accent)", display: "inline-flex" }}>{eyebrowIcon}</span>}{label}
          </span>
          {actions}
        </header>
      )}
      <div style={{ padding: "var(--space-4)", ...bodyStyle }}>{children}</div>
    </section>
  );
}

/* ── KpiCard ── */
type Tone = "cyan" | "gold" | "green" | "violet" | "red" | "amber" | "neutral";
const TONE_VAR: Record<Tone, string> = {
  cyan: "var(--accent)", gold: "var(--highlight)", green: "var(--brand-bright)", violet: "var(--ai)",
  red: "var(--status-stuck)", amber: "var(--status-postponed)", neutral: "var(--text-soft)",
};
export function KpiCard({
  value, label, sub, tone = "cyan", active = false, icon, onClick,
}: { value: ReactNode; label: string; sub?: ReactNode; tone?: Tone; active?: boolean; icon?: ReactNode; onClick?: () => void }) {
  const c = TONE_VAR[tone];
  return (
    <div onClick={onClick} role={onClick ? "button" : undefined}
      style={{ position: "relative", padding: "12px 14px 11px", cursor: onClick ? "pointer" : "default",
        clipPath: "polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 12px 100%, 0 calc(100% - 12px))",
        background: `linear-gradient(165deg, color-mix(in srgb, ${c} ${active ? 16 : 8}%, var(--surface-1)), var(--surface-inset))`,
        border: `1px solid color-mix(in srgb, ${c} ${active ? 42 : 20}%, var(--hairline))`, transition: "var(--transition)" }}>
      <span style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${c}, transparent 70%)`, opacity: 0.85 }} />
      <div style={{ fontSize: 27, fontWeight: 800, fontFamily: "var(--font-display)", color: "#eaf6ff", lineHeight: 1.05, textShadow: `0 0 12px color-mix(in srgb, ${c} 42%, transparent)` }}>{value}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, font: "var(--fw-semibold) var(--fs-2xs)/1 var(--font-mono)", letterSpacing: "var(--tracking-wider)", textTransform: "uppercase", color: "var(--text-dim)" }}>
        {icon && <span style={{ color: c, display: "inline-flex" }}>{icon}</span>}{label}
      </div>
      {sub != null && <div style={{ marginTop: 3, fontSize: 9, color: "var(--text-faint)" }}>{sub}</div>}
    </div>
  );
}

/* ── ProgressBar ── */
export function SumaProgress({ value = 0, tone = "var(--accent)", height = 8, showValue = false }: { value?: number; tone?: string; height?: number; showValue?: boolean }) {
  const pct = Math.max(0, Math.min(100, value));
  const cut = Math.min(5, Math.round(height * 0.6));
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
      <div style={{ flex: 1, position: "relative", height, overflow: "hidden",
        clipPath: `polygon(${cut}px 0,100% 0,calc(100% - ${cut}px) 100%,0 100%)`,
        background: `color-mix(in srgb, ${tone} 9%, var(--surface-inset))`, border: `1px solid color-mix(in srgb, ${tone} 22%, transparent)` }}>
        <div style={{ position: "absolute", inset: "0 auto 0 0", width: `${pct}%`, background: `linear-gradient(90deg, color-mix(in srgb, ${tone} 55%, #06121f), ${tone})`, boxShadow: `0 0 10px color-mix(in srgb, ${tone} 55%, transparent)`, transition: "width var(--dur-slow) var(--ease)" }}>
          <span style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(115deg, transparent 0 5px, rgba(0,0,0,.18) 5px 7px)" }} />
          {pct > 0 && pct < 100 && <span style={{ position: "absolute", right: 0, top: -1, bottom: -1, width: 2, background: "#eaf6ff", boxShadow: `0 0 8px #fff, 0 0 4px ${tone}` }} />}
        </div>
      </div>
      {showValue && <span style={{ font: "var(--fw-semibold) var(--fs-2xs) var(--font-mono)", color: tone, minWidth: 34, textAlign: "right", textShadow: `0 0 8px color-mix(in srgb, ${tone} 40%, transparent)` }}>{pct}%</span>}
    </div>
  );
}

/* ── Avatar (hex by default) ── */
const AV_PALETTE = ["var(--accent)", "var(--highlight)", "var(--brand-bright)", "var(--ai)", "var(--cyan-300)"];
export function Avatar({ name = "", size = 30, shape = "hex", tone }: { name?: string; size?: number; shape?: "hex" | "circle" | "rounded"; tone?: string }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
  const hash = [...name].reduce((a, ch) => a + ch.charCodeAt(0), 0);
  const c = tone ?? AV_PALETTE[hash % AV_PALETTE.length];
  const clip = shape === "hex" ? { clipPath: "var(--clip-hex)" } : shape === "circle" ? { borderRadius: "50%" } : { borderRadius: "var(--radius-sm)" };
  return (
    <span title={name} style={{ display: "inline-grid", placeItems: "center", width: size, height: size, flexShrink: 0, ...clip,
      background: `color-mix(in srgb, ${c} 18%, var(--surface-2))`, color: c,
      border: shape === "hex" ? "none" : `1px solid color-mix(in srgb, ${c} 45%, transparent)`,
      font: `var(--fw-semibold) ${Math.round(size * 0.36)}px/1 var(--font-mono)`,
      boxShadow: `0 0 0 1px color-mix(in srgb, ${c} 30%, transparent) inset` }}>
      {initials}
    </span>
  );
}

/* ── StatusPill (clickable to cycle) ── */
export function StatusPill({ status, label, onCycle, showIcon = true }: { status: TaskStatus; label: string; onCycle?: () => void; showIcon?: boolean }) {
  const m = STATUS_META[status];
  return (
    <span onClick={onCycle ? (e) => { e.stopPropagation(); onCycle(); } : undefined}
      title={onCycle ? "Cycle status" : undefined}
      style={{ display: "inline-flex", alignItems: "center", gap: "0.36rem", padding: "0.3rem 0.6rem 0.3rem 0.5rem",
        font: "var(--fw-semibold) var(--fs-2xs) var(--font-mono)", letterSpacing: "var(--tracking-wide)", textTransform: "uppercase",
        color: m.color, background: `color-mix(in srgb, ${m.color} 13%, transparent)`, border: `1px solid color-mix(in srgb, ${m.color} 45%, transparent)`,
        clipPath: "polygon(6px 0,100% 0,calc(100% - 6px) 100%,0 100%)", cursor: onCycle ? "pointer" : "default", whiteSpace: "nowrap" }}>
      {showIcon && <span style={{ width: 6, height: 6, borderRadius: "50%", background: m.color, boxShadow: `0 0 7px ${m.color}`, flexShrink: 0 }} />}
      {label}
    </span>
  );
}

/* ── RoleBadge ── */
export function RoleBadge({ role, label }: { role: Role; label: string }) {
  const c = ROLE_COLOR[role] ?? "var(--text-dim)";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", padding: "0.18rem 0.45rem", borderRadius: "var(--radius-xs)",
      font: "var(--fw-semibold) var(--fs-2xs) var(--font-mono)", letterSpacing: "var(--tracking-wide)", textTransform: "uppercase",
      color: c, background: `color-mix(in srgb, ${c} 16%, transparent)` }}>
      <Shield size={10} /> {label}
    </span>
  );
}

/* ── WeekStrip (7 day nodes with hex counts) ── */
export function WeekStrip({ days, counts, active, today, onSelect }: { days: string[]; counts: Record<string, number>; active?: string; today?: string; onSelect?: (d: string) => void }) {
  return (
    <div style={{ display: "flex", gap: "var(--space-2)" }}>
      {days.map((d) => {
        const isActive = d === active, isToday = d === today, count = counts[d] ?? 0;
        return (
          <button key={d} onClick={() => onSelect?.(d)} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "0.3rem", padding: "0.5rem 0.3rem", cursor: "pointer",
            background: isActive ? "var(--accent-dim)" : "var(--surface-1)",
            border: `1px solid ${isActive ? "var(--accent)" : isToday ? "var(--highlight)" : "var(--hairline)"}`,
            boxShadow: isActive ? "var(--glow-cyan-sm)" : "none", borderRadius: "var(--radius-md)", transition: "var(--transition)" }}>
            <span style={{ font: "var(--fw-semibold) var(--fs-2xs)/1 var(--font-mono)", letterSpacing: "var(--tracking-wide)", textTransform: "uppercase", color: isActive ? "var(--accent)" : "var(--text-dim)" }}>{d}</span>
            <span style={{ display: "grid", placeItems: "center", width: 26, height: 26, clipPath: "var(--clip-hex)",
              background: count > 0 ? (isActive ? "var(--grad-cyan)" : "var(--surface-2)") : "transparent",
              color: count > 0 ? (isActive ? "var(--text-on-accent)" : "var(--text-soft)") : "var(--text-faint)",
              font: "var(--fw-bold) var(--fs-xs)/1 var(--font-mono)" }}>{count}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Theme + HUD control (persists to localStorage, shared with login) ── */
export const SUMA_THEMES: { key: string; label: string; dot: string }[] = [
  { key: "protoss", label: "Protoss", dot: "#2ee6ff" },
  { key: "terran", label: "Terran", dot: "#38c8d2" },
  { key: "aiur", label: "Aiur", dot: "#ffcf6b" },
  { key: "verdant", label: "Verdant", dot: "#34d399" },
  { key: "zerg", label: "Zerg", dot: "#c061f0" },
  { key: "swann", label: "Swann", dot: "#ff8a2a" },
];
const HUDS = ["subtle", "medium", "heavy"] as const;

export function useSumaTheme() {
  const read = (k: string, d: string) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
  const [theme, setThemeState] = useState<string>(() => read("suma-theme", "protoss"));
  const [hud, setHudState] = useState<string>(() => read("suma-hud", "medium"));
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); try { localStorage.setItem("suma-theme", theme); } catch { /* ignore */ } }, [theme]);
  useEffect(() => { document.documentElement.setAttribute("data-hud", hud); try { localStorage.setItem("suma-hud", hud); } catch { /* ignore */ } }, [hud]);
  const setTheme = useCallback((t: string) => setThemeState(t), []);
  const setHud = useCallback((h: string) => setHudState(h), []);
  return { theme, setTheme, hud, setHud };
}

export function ThemePicker({ compact = false }: { compact?: boolean }) {
  const { theme, setTheme, hud, setHud } = useSumaTheme();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
        {SUMA_THEMES.map((th) => (
          <button key={th.key} onClick={() => setTheme(th.key)} title={th.label} aria-label={th.label} aria-pressed={theme === th.key}
            style={{ width: 20, height: 20, clipPath: "var(--clip-hex)", border: 0, padding: 0, cursor: "pointer", background: th.dot,
              boxShadow: theme === th.key ? "0 0 0 2px var(--bg-deep), 0 0 0 3px var(--text), 0 0 10px " + th.dot : "0 0 0 1px rgba(0,0,0,.35)" }} />
        ))}
      </div>
      {!compact && (
        <div style={{ display: "inline-flex", padding: 3, gap: 2, borderRadius: "var(--radius-sm)", background: "var(--surface-1)", border: "var(--border)" }}>
          {HUDS.map((h) => (
            <button key={h} onClick={() => setHud(h)} title={`HUD: ${h}`}
              style={{ padding: "3px 8px", borderRadius: "var(--radius-xs)", border: 0, cursor: "pointer", textTransform: "uppercase",
                font: "var(--fw-bold) var(--fs-2xs) var(--font-mono)", letterSpacing: ".06em",
                background: hud === h ? "var(--accent)" : "transparent", color: hud === h ? "var(--text-on-accent)" : "var(--text-dim)" }}>
              {h[0]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

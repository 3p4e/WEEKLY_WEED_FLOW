import { useState, type ReactNode, type CSSProperties } from "react";
import {
  CalendarDays, LayoutGrid, FileText, BarChart3, Settings2, GitBranch, Users,
  ChevronLeft, ChevronRight, LogOut, Globe, Sparkles, type LucideIcon,
} from "lucide-react";
import type { Lang, UserOut } from "./types/models";
import { weekLabel } from "./views/status";
import { NetworkField } from "./components/NetworkField";
import { ThemePicker } from "./components/suma";

export type ViewId = "myweek" | "board" | "tree" | "reports" | "executive" | "admin" | "settings";

interface NavItem { id: ViewId; key: string; Icon: LucideIcon; execOnly?: boolean; manage?: boolean; }

const NAV: NavItem[] = [
  { id: "myweek", key: "my_week", Icon: CalendarDays },
  { id: "board", key: "board", Icon: LayoutGrid },
  { id: "tree", key: "tree", Icon: GitBranch },
  { id: "reports", key: "weekly_summary", Icon: FileText },
  { id: "executive", key: "executive", Icon: BarChart3, execOnly: true },
  { id: "admin", key: "admin_console", Icon: Users, manage: true },
];

export interface PlannerShellProps {
  current: ViewId;
  onNavigate: (id: ViewId) => void;
  user: UserOut;
  lang: Lang;
  onToggleLang: () => void;
  t: (k: string) => string;
  weekStart: string;
  onWeekStep: (delta: number) => void;
  onToday: () => void;
  onLogout: () => void;
  onOpenAi: () => void;
  children: ReactNode;
}

export function PlannerShell(props: PlannerShellProps) {
  const { current, onNavigate, user, lang, onToggleLang, t, weekStart, onWeekStep, onToday, onLogout, onOpenAi, children } = props;
  const isExec = user.role === "executive" || user.role === "admin";
  const isManager = user.role === "admin" || user.role === "executive" || user.role === "hod";
  const items = NAV.filter((n) => (!n.execOnly || isExec) && (!n.manage || isManager));

  return (
    <>
      <NetworkField style={{ position: "fixed", inset: 0, zIndex: 0 }} density={20} />
      <nav style={sidebar}>
        <div style={logoArea}>
          <span className="pp-leaf-anim" style={{ width: 46, height: 53, flexShrink: 0 }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
            <div className="pp-brand-text" style={{ fontSize: 20, lineHeight: 1.05 }}>GrowFlow</div>
            <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", color: "var(--ink)", lineHeight: 1.1 }}>
              PURELY<span style={{ fontStyle: "italic", fontWeight: 700 }}>PLANT</span>
            </div>
            <div style={{ fontSize: 6.5, fontWeight: 600, letterSpacing: "0.2em", color: "var(--ink-3)", textTransform: "uppercase" }}>
              The Future of Cannabis
            </div>
          </div>
        </div>

        <div style={navList}>
          {items.map((item) => (
            <NavButton key={item.id} label={t(item.key)} Icon={item.Icon} active={current === item.id} onClick={() => onNavigate(item.id)} />
          ))}
        </div>

        <div style={{ padding: 8 }}>
          <NavButton label={t("settings")} Icon={Settings2} active={current === "settings"} onClick={() => onNavigate("settings")} />
        </div>

        <div style={userRow}>
          <div style={avatar}>{initials(user.full_name)}</div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 12.5, color: "var(--ink)", fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user.full_name}</div>
            <div style={{ fontSize: 11, color: "var(--ink-2)", fontWeight: 600, textTransform: "capitalize" }}>{user.role}</div>
          </div>
          <button title={t("logout")} onClick={onLogout} style={iconBtnLight}><LogOut size={14} /></button>
        </div>
      </nav>

      <header style={header}>
        <h2 style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.5px", color: "var(--ink)" }}>
          Grow<span style={{ color: "var(--orange)" }}>Flow</span>
        </h2>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: 16 }}>
          <button style={weekBtn} onClick={() => onWeekStep(-1)} title={t("prev_week")}><ChevronLeft size={15} /></button>
          <div style={{ minWidth: 150, textAlign: "center", fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>{weekLabel(weekStart)}</div>
          <button style={weekBtn} onClick={() => onWeekStep(1)} title={t("next_week")}><ChevronRight size={15} /></button>
          <button style={todayBtn} onClick={onToday}>{t("today")}</button>
        </div>
        <div style={{ flex: 1 }} />
        <ThemePicker compact />
        <button style={aiBtn} onClick={onOpenAi} title={t("ai_assistant")}>
          <Sparkles size={14} /> {t("ai_assistant")}
        </button>
        <button style={langBtn} onClick={onToggleLang} title={t("language")}>
          <Globe size={13} /> {lang === "en" ? "EN" : "МК"}
        </button>
      </header>

      <main style={content}>{children}</main>
    </>
  );
}

function NavButton({ label, Icon, active, onClick }: { label: string; Icon: LucideIcon; active: boolean; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        width: "100%", display: "flex", alignItems: "center", gap: 11, padding: "10px 12px",
        borderRadius: "var(--radius-md)", border: "none", cursor: "pointer", textAlign: "left",
        fontFamily: "var(--font-sans)", fontSize: 14, fontWeight: active ? 700 : 600,
        background: active ? "var(--blue-soft)" : hover ? "var(--surface-2)" : "transparent",
        color: active ? "var(--blue-700)" : "var(--ink-2)",
        transition: "var(--transition-ui)",
      }}
    >
      <Icon size={17} color={active ? "var(--blue)" : "var(--ink-3)"} />
      {label}
    </button>
  );
}

function initials(name: string): string {
  return name.split(/\s+/).slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "").join("");
}

const sidebar: CSSProperties = { width: "var(--sidebar-width)", flexShrink: 0, background: "var(--surface-sidebar)", backdropFilter: "var(--blur)", WebkitBackdropFilter: "var(--blur)", borderRight: "1px solid var(--hairline)", display: "flex", flexDirection: "column", height: "100vh", position: "fixed", left: 0, top: 0, zIndex: 10 };
const logoArea: CSSProperties = { padding: "18px 18px 14px", display: "flex", alignItems: "center", gap: 12 };
const navList: CSSProperties = { flex: 1, padding: 8, display: "flex", flexDirection: "column", gap: 2, overflowY: "auto" };
const userRow: CSSProperties = { display: "flex", alignItems: "center", gap: 10, padding: 12, margin: 12, marginTop: 0, borderRadius: "var(--radius-lg)", background: "var(--surface-2)" };
const avatar: CSSProperties = { width: 34, height: 34, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--blue)", color: "#fff", fontSize: 13, fontWeight: 700 };
const iconBtnLight: CSSProperties = { width: 30, height: 30, borderRadius: "var(--radius-md)", border: "1px solid var(--line)", background: "var(--surface)", color: "var(--ink-2)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" };
const header: CSSProperties = { height: "var(--header-height)", background: "rgba(6,12,28,0.78)", backdropFilter: "var(--blur)", WebkitBackdropFilter: "var(--blur)", borderBottom: "1px solid var(--hairline)", display: "flex", alignItems: "center", padding: "0 24px", gap: 4, position: "fixed", top: 0, left: "var(--sidebar-width)", right: 0, zIndex: 9 };
const weekBtn: CSSProperties = { width: 30, height: 30, borderRadius: "var(--radius-md)", border: "1px solid var(--line)", background: "var(--surface-card)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--ink-2)" };
const todayBtn: CSSProperties = { marginLeft: 6, padding: "6px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--line)", background: "var(--surface-card)", fontSize: 12, fontWeight: 700, color: "var(--ink-2)", cursor: "pointer" };
const langBtn: CSSProperties = { display: "flex", alignItems: "center", gap: 6, padding: "6px 11px", borderRadius: "var(--radius-md)", border: "1px solid var(--line)", background: "var(--surface-card)", fontSize: 12, fontWeight: 700, color: "var(--ink-2)", cursor: "pointer" };
const aiBtn: CSSProperties = { display: "flex", alignItems: "center", gap: 6, padding: "7px 13px", marginRight: 8, borderRadius: "var(--radius-md)", border: "none", background: "var(--orange)", boxShadow: "0 2px 8px rgba(255,122,26,.32)", fontSize: 12.5, fontWeight: 700, color: "#fff", cursor: "pointer" };
const content: CSSProperties = { position: "relative", zIndex: 1, marginLeft: "var(--sidebar-width)", marginTop: "var(--header-height)", minHeight: "calc(100vh - var(--header-height))", background: "transparent", padding: 24 };

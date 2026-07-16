import type { CSSProperties } from "react";

export type BadgeStatus =
  | "conforms" | "oos" | "na" | "pending" | "review"
  | "issued" | "accepted" | "pending-review" | "rejected"
  | "superseded" | "voided" | "destroyed" | "draft";

interface Tone { bg: string; border: string; fg: string; dot: string; label: string; }

const TONES: Record<BadgeStatus, Tone> = {
  conforms:        t("--status-pass", "Conforms"),
  oos:             t("--status-fail", "OOS"),
  pending:         t("--status-pending", "Pending"),
  review:          t("--status-review", "In Review"),
  na:              t("--neutral", "N/A"),
  issued:          t("--status-info", "Issued"),
  accepted:        t("--status-pass", "Accepted"),
  "pending-review":t("--status-pending", "Pending Review"),
  rejected:        t("--status-fail", "Rejected"),
  superseded:      t("--neutral", "Superseded"),
  voided:          t("--neutral", "Voided"),
  destroyed:       t("--neutral", "Destroyed"),
  draft:           t("--status-pending", "Draft"),
};

function t(base: string, label: string): Tone {
  if (base === "--neutral") return { bg: "var(--zebra)", border: "var(--border-strong)", fg: "var(--text-tertiary)", dot: "var(--text-quaternary)", label };
  return { bg: `var(${base}-bg)`, border: `var(${base}-border)`, fg: `var(${base})`, dot: `var(${base})`, label };
}

export interface BadgeProps {
  status: BadgeStatus;
  label?: string;
  size?: "sm" | "md";
  dot?: boolean;
}

export function Badge({ status, label, size = "md", dot = true }: BadgeProps) {
  const tone = TONES[status];
  const sm = size === "sm";
  /* SUMA chamfered HUD chip: mono, uppercase, tracked, glow dot. */
  const style: CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: sm ? 5 : 6,
    padding: sm ? "2px 7px 2px 6px" : "3px 9px 3px 7px",
    clipPath: "polygon(6px 0,100% 0,calc(100% - 6px) 100%,0 100%)",
    fontSize: sm ? 10 : 11, fontWeight: 600, lineHeight: 1.4, letterSpacing: "0.06em", textTransform: "uppercase",
    background: tone.bg, color: tone.fg, border: `1px solid ${tone.border}`,
    fontFamily: "var(--font-mono)", whiteSpace: "nowrap",
  };
  return (
    <span style={style}>
      {dot && <span style={{ width: sm ? 5 : 6, height: sm ? 5 : 6, borderRadius: "50%", background: tone.dot, boxShadow: `0 0 6px ${tone.dot}`, flexShrink: 0 }} />}
      {label ?? tone.label}
    </span>
  );
}

import type { CSSProperties, ReactNode } from "react";
import { FileText } from "lucide-react";
import { Badge, type BadgeStatus } from "./Badge";

export interface DocumentCardProps {
  code: string;
  title?: string;
  subtitle?: string;
  status?: BadgeStatus;
  statusLabel?: string;
  meta?: { label: string; value: string }[];
  icon?: ReactNode;
  onClick?: () => void;
}

export function DocumentCard({ code, title, subtitle, status, statusLabel, meta, icon, onClick }: DocumentCardProps) {
  return (
    <div onClick={onClick} style={{ ...card, cursor: onClick ? "pointer" : "default" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ display: "flex", gap: 10, minWidth: 0 }}>
          <div style={{ width: 34, height: 34, borderRadius: "var(--radius-md)", background: "var(--status-info-bg)", color: "var(--status-info)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            {icon ?? <FileText size={16} />}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{code}</div>
            {title && <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 1 }}>{title}</div>}
            {subtitle && <div style={{ fontSize: 11, color: "var(--text-quaternary)", marginTop: 1 }}>{subtitle}</div>}
          </div>
        </div>
        {status && <Badge status={status} size="sm" label={statusLabel} />}
      </div>
      {meta && meta.length > 0 && (
        <div style={{ display: "flex", gap: 16, marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border-subtle)" }}>
          {meta.map((m) => (
            <div key={m.label}>
              <div style={{ fontSize: 10, color: "var(--text-quaternary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{m.label}</div>
              <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 500, marginTop: 1 }}>{m.value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const card: CSSProperties = { background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: 14 };

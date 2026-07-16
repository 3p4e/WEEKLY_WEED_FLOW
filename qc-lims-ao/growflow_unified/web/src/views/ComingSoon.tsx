import type { CSSProperties } from "react";
import { Sparkles } from "lucide-react";

export function ComingSoon({ title, message }: { title: string; message: string }) {
  return (
    <div style={wrap}>
      <Sparkles size={28} style={{ color: "var(--color-accent)" }} />
      <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)" }}>{title}</div>
      <div style={{ fontSize: 13, color: "var(--text-tertiary)", maxWidth: 420, textAlign: "center" }}>{message}</div>
    </div>
  );
}

const wrap: CSSProperties = { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, minHeight: "60vh" };

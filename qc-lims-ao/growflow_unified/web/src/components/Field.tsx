import { useState, type CSSProperties, type ReactNode } from "react";

const fieldLabel: CSSProperties = { display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: 5 };
const baseControl: CSSProperties = { width: "100%", padding: "7px 10px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-strong)", background: "var(--surface-card)", fontSize: 13, color: "var(--text-primary)", fontFamily: "var(--font-sans)", outline: "none", transition: "var(--transition-ui)" };

function focusRing(focus: boolean): CSSProperties {
  return focus ? { borderColor: "var(--color-brand)", boxShadow: "0 0 0 3px rgba(27,58,92,0.12)" } : {};
}

export interface InputProps {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  prefix?: string;
  type?: string;
  disabled?: boolean;
}

export function Input({ label, value, onChange, placeholder, prefix, type = "text", disabled }: InputProps) {
  const [focus, setFocus] = useState(false);
  return (
    <label style={{ display: "block" }}>
      {label && <span style={fieldLabel}>{label}</span>}
      <span style={{ display: "flex", alignItems: "center", ...baseControl, ...focusRing(focus), padding: 0, overflow: "hidden", opacity: disabled ? 0.6 : 1 }}>
        {prefix && <span style={{ padding: "7px 0 7px 10px", color: "var(--text-quaternary)", fontFamily: "var(--font-mono)", fontSize: 13 }}>{prefix}</span>}
        <input
          type={type} value={value} disabled={disabled} placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          style={{ flex: 1, border: "none", outline: "none", background: "transparent", padding: "7px 10px", fontSize: 13, color: "var(--text-primary)", fontFamily: "var(--font-sans)", minWidth: 0 }}
        />
      </span>
    </label>
  );
}

export interface SelectProps {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
}

export function Select({ label, value, onChange, options, disabled }: SelectProps) {
  const [focus, setFocus] = useState(false);
  return (
    <label style={{ display: "block" }}>
      {label && <span style={fieldLabel}>{label}</span>}
      <select
        value={value} disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{ ...baseControl, ...focusRing(focus), cursor: "pointer", appearance: "none", opacity: disabled ? 0.6 : 1 }}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export interface TextareaProps {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}

export function Textarea({ label, value, onChange, placeholder, rows = 4 }: TextareaProps) {
  const [focus, setFocus] = useState(false);
  return (
    <label style={{ display: "block" }}>
      {label && <span style={fieldLabel}>{label}</span>}
      <textarea
        value={value} rows={rows} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{ ...baseControl, ...focusRing(focus), resize: "vertical", lineHeight: 1.5 }}
      />
    </label>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <span style={fieldLabel}>{label}</span>
      {children}
    </div>
  );
}

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useState, type CSSProperties } from "react";

/* SUMA-skinned button: chamfered HUD chrome, accent gradient body, uppercase
   mono label, neon glow + lift on hover. Prop interface is unchanged so every
   existing caller re-skins automatically. */
type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "size"> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  fullWidth?: boolean;
  children?: ReactNode;
}

const SIZES: Record<Size, CSSProperties> = {
  sm: { height: "var(--control-h-sm)", padding: "0 12px", fontSize: 10.5, gap: 6 },
  md: { height: "var(--control-h)", padding: "0 16px", fontSize: 12, gap: 7 },
  lg: { height: 44, padding: "0 22px", fontSize: 13.5, gap: 9 },
};
const ACCENT: Record<Variant, string> = {
  primary: "var(--accent)", secondary: "var(--accent)", ghost: "var(--accent)", danger: "var(--status-stuck)",
};

export function Button({ variant = "primary", size = "md", icon, fullWidth, children, disabled, style, ...rest }: ButtonProps) {
  const [hover, setHover] = useState(false);
  const c = ACCENT[variant];
  const solid = variant === "primary" || variant === "danger";
  const base: CSSProperties = {
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    ...SIZES[size], width: fullWidth ? "100%" : undefined,
    fontFamily: "var(--font-mono)", fontWeight: 700, letterSpacing: "0.13em", textTransform: "uppercase",
    cursor: disabled ? "not-allowed" : "pointer", transition: "var(--transition)",
    clipPath: "polygon(9px 0, 100% 0, 100% calc(100% - 9px), calc(100% - 9px) 100%, 0 100%, 0 9px)",
    border: "none", whiteSpace: "nowrap",
    transform: hover && !disabled ? "translateY(-2px)" : "none",
  };
  let palette: CSSProperties;
  if (disabled) {
    palette = { background: "var(--surface-2)", color: "var(--text-faint)", filter: "grayscale(0.4)", opacity: 0.55 };
  } else if (solid) {
    palette = {
      background: `linear-gradient(150deg, color-mix(in srgb, ${c} 52%, #fff), ${c} 46%, color-mix(in srgb, ${c} 72%, #04080e))`,
      color: variant === "danger" ? "#fff" : "var(--text-on-accent)",
      boxShadow: hover ? `0 0 16px color-mix(in srgb, ${c} 55%, transparent)` : `0 0 8px color-mix(in srgb, ${c} 30%, transparent)`,
    };
  } else if (variant === "secondary") {
    palette = { background: hover ? "var(--glass-hover)" : "var(--surface-inset)", color: "var(--text-soft)", boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${c} ${hover ? 45 : 26}%, var(--hairline))` };
  } else {
    palette = { background: hover ? "var(--glass-hover)" : "transparent", color: "var(--text-soft)" };
  }
  return (
    <button {...rest} disabled={disabled}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ ...base, ...palette, ...style }}>
      {icon}{children}
    </button>
  );
}

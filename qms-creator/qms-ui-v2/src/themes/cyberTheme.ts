import type { Theme } from './types'

/**
 * Cyber Glassmorphism Theme - Premium Dark Design
 * Futuristic design with glassmorphism effects and vibrant accents
 * Based on the qms-ui Premium Design System
 */
export const cyberTheme: Theme = {
  name: 'Cyber Glass',
  description: 'Futuristic glassmorphism design with vibrant neon accents',

  colors: {
    primary: '#00d9ff',           // Cyan - Primary highlights, CTAs
    secondary: '#3b82f6',         // Deep Blue - Secondary elements
    accent: '#8b5cf6',            // Purple - Accent highlights
    gray: '#94a3b8',              // Slate-400 - Body text (light on dark)
    darkBg: '#050510',            // Deep Space - Main background
    lightBg: '#16213e',           // Surface solid - Card backgrounds
    border: 'rgba(59, 130, 246, 0.2)', // Blue-tinted border
    success: '#22c55e',           // Cannabis Green
    warning: '#f59e0b',           // Amber
    error: '#ef4444',             // Red
    info: '#3b82f6',              // Blue
  },

  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    sizes: {
      xs: '12px',
      sm: '13px',
      base: '15px',
      lg: '17px',
      xl: '22px',
      '2xl': '28px',
      '3xl': '36px',
      '4xl': '48px',
    },
    weights: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },

  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px',
  },

  borderRadius: {
    none: '0px',
    sm: '6px',
    md: '12px',
    lg: '16px',
    full: '9999px',
  },

  shadows: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.3)',
    md: '0 4px 16px rgba(0, 0, 0, 0.4)',
    lg: '0 8px 32px rgba(0, 0, 0, 0.5)',
    xl: '0 0 20px rgba(0, 217, 255, 0.4)',
    none: 'none',
  },

  cssVariables: {
    '--color-primary': '#00d9ff',
    '--color-primary-dark': '#00a8cc',
    '--color-primary-light': '#5debff',
    '--color-primary-glow': 'rgba(0, 217, 255, 0.4)',
    '--color-secondary': '#3b82f6',
    '--color-secondary-dark': '#2563eb',
    '--color-accent': '#8b5cf6',
    '--color-accent-glow': 'rgba(139, 92, 246, 0.3)',
    '--color-gray': '#94a3b8',
    '--color-dark-bg': '#050510',
    '--color-bg-soft': '#0a0a1a',
    '--color-surface': 'rgba(22, 33, 62, 0.6)',
    '--color-surface-solid': '#16213e',
    '--color-light-bg': '#16213e',
    '--color-card-bg': 'rgba(30, 41, 59, 0.5)',
    '--color-border': 'rgba(59, 130, 246, 0.2)',
    '--color-border-glow': 'rgba(0, 217, 255, 0.3)',
    '--color-success': '#22c55e',
    '--color-cannabis-green': '#22c55e',
    '--color-cannabis-glow': 'rgba(34, 197, 94, 0.25)',
    '--color-warning': '#f59e0b',
    '--color-error': '#ef4444',
    '--color-info': '#3b82f6',
    '--color-text': '#f8fafc',
    '--color-text-muted': '#94a3b8',
    '--color-text-dim': '#64748b',
    '--font-family': '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    '--spacing-xs': '4px',
    '--spacing-sm': '8px',
    '--spacing-md': '16px',
    '--spacing-lg': '24px',
    '--spacing-xl': '32px',
    '--border-radius-sm': '6px',
    '--border-radius-md': '12px',
    '--border-radius-lg': '16px',
    '--shadow-md': '0 4px 16px rgba(0, 0, 0, 0.4)',
    '--shadow-glow': '0 0 20px rgba(0, 217, 255, 0.4)',
    '--backdrop-blur': 'blur(16px) saturate(180%)',
  },
}

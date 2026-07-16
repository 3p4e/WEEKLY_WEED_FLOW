import type { Theme } from './types'

/**
 * PP SOP Platform - Default Theme
 * Pharmaceutical-grade design system based on PP brand identity
 * Color scheme: PP_BLUE (#1F4E79), PP_GREEN (#538135), PP_GRAY (#404040)
 */
export const ppSopTheme: Theme = {
  name: 'PP SOP',
  description: 'Pharmaceutical-grade design system with PP brand identity',
  
  colors: {
    primary: '#1F4E79',          // PP_BLUE - Primary headings, CTAs, trusted authority
    secondary: '#538135',         // PP_GREEN - Accents, success states, plant/growth theme
    accent: '#538135',            // PP_GREEN - Same as secondary
    gray: '#404040',              // PP_GRAY - Body text, subtle elements
    darkBg: '#0F172A',            // slate-950 - Main background (darker than primary)
    lightBg: '#F5F7FA',           // Clean light background for contrast
    border: '#E2E8F0',            // slate-200 - Subtle borders
    success: '#16A34A',           // green-600 - Success indicators
    warning: '#EA8C55',           // amber-600 - Warnings
    error: '#DC2626',             // red-600 - Error states
    info: '#0EA5E9',              // sky-500 - Informational
  },

  typography: {
    fontFamily: '"Arial Narrow", "Arial", sans-serif',
    sizes: {
      xs: '11px',
      sm: '12px',
      base: '14px',
      lg: '16px',
      xl: '20px',
      '2xl': '28px',
      '3xl': '32px',
      '4xl': '40px',
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
    sm: '4px',
    md: '6px',
    lg: '12px',
    full: '9999px',
  },

  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
    none: 'none',
  },

  cssVariables: {
    '--color-primary': '#1F4E79',
    '--color-secondary': '#538135',
    '--color-accent': '#538135',
    '--color-gray': '#404040',
    '--color-dark-bg': '#0F172A',
    '--color-light-bg': '#F5F7FA',
    '--color-border': '#E2E8F0',
    '--color-success': '#16A34A',
    '--color-warning': '#EA8C55',
    '--color-error': '#DC2626',
    '--color-info': '#0EA5E9',
    '--font-family': '"Arial Narrow", "Arial", sans-serif',
    '--spacing-xs': '4px',
    '--spacing-sm': '8px',
    '--spacing-md': '16px',
    '--spacing-lg': '24px',
    '--spacing-xl': '32px',
    '--border-radius-sm': '4px',
    '--border-radius-md': '6px',
    '--border-radius-lg': '12px',
    '--shadow-md': '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  },
}

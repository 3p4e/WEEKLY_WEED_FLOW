import type { Theme } from './types'

/**
 * Modern Clean Theme - Alternative design system
 * Contemporary design with fresh color palette
 * Suitable for users who prefer a lighter, more minimal aesthetic
 */
export const modernTheme: Theme = {
  name: 'Modern Clean',
  description: 'Contemporary design with fresh, minimal aesthetic',
  
  colors: {
    primary: '#2563EB',           // blue-600 - Modern blue
    secondary: '#7C3AED',         // violet-600 - Purple accent
    accent: '#7C3AED',            // violet-600
    gray: '#1F2937',              // gray-800 - Dark text
    darkBg: '#FFFFFF',            // White - Clean background
    lightBg: '#F3F4F6',           // gray-100 - Subtle contrast
    border: '#D1D5DB',            // gray-300 - Light borders
    success: '#10B981',           // emerald-500
    warning: '#F59E0B',           // amber-500
    error: '#EF4444',             // red-500
    info: '#06B6D4',              // cyan-500
  },

  typography: {
    fontFamily: '"Segoe UI", "Helvetica Neue", sans-serif',
    sizes: {
      xs: '12px',
      sm: '13px',
      base: '15px',
      lg: '17px',
      xl: '22px',
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
    md: '8px',
    lg: '12px',
    full: '9999px',
  },

  shadows: {
    sm: '0 1px 3px 0 rgba(0, 0, 0, 0.08)',
    md: '0 4px 12px 0 rgba(0, 0, 0, 0.12)',
    lg: '0 12px 24px 0 rgba(0, 0, 0, 0.15)',
    xl: '0 20px 40px 0 rgba(0, 0, 0, 0.2)',
    none: 'none',
  },

  cssVariables: {
    '--color-primary': '#2563EB',
    '--color-secondary': '#7C3AED',
    '--color-accent': '#7C3AED',
    '--color-gray': '#1F2937',
    '--color-dark-bg': '#FFFFFF',
    '--color-light-bg': '#F3F4F6',
    '--color-border': '#D1D5DB',
    '--color-success': '#10B981',
    '--color-warning': '#F59E0B',
    '--color-error': '#EF4444',
    '--color-info': '#06B6D4',
    '--font-family': '"Segoe UI", "Helvetica Neue", sans-serif',
    '--spacing-xs': '4px',
    '--spacing-sm': '8px',
    '--spacing-md': '16px',
    '--spacing-lg': '24px',
    '--spacing-xl': '32px',
    '--border-radius-sm': '4px',
    '--border-radius-md': '8px',
    '--border-radius-lg': '12px',
    '--shadow-md': '0 4px 12px 0 rgba(0, 0, 0, 0.12)',
  },
}

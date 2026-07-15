import type { Theme } from './types'

/**
 * Cannabis Professional Theme - Nature-Inspired Design
 * Earthy green tones with warm accents for cannabis industry focus
 * Professional yet organic aesthetic
 */
export const cannabisTheme: Theme = {
  name: 'Cannabis Pro',
  description: 'Nature-inspired professional theme with earthy cannabis tones',

  colors: {
    primary: '#16a34a',           // Green-600 - Primary cannabis green
    secondary: '#854d0e',         // Yellow-800 - Earthy brown accent
    accent: '#65a30d',            // Lime-600 - Lighter green accent
    gray: '#44403c',              // Stone-700 - Warm gray text
    darkBg: '#1c1917',            // Stone-900 - Dark earthy background
    lightBg: '#fafaf9',           // Stone-50 - Light cream background
    border: '#d6d3d1',            // Stone-300 - Warm border
    success: '#22c55e',           // Green-500 - Success
    warning: '#d97706',           // Amber-600 - Warning
    error: '#dc2626',             // Red-600 - Error
    info: '#0891b2',              // Cyan-600 - Info
  },

  typography: {
    fontFamily: '"Source Sans Pro", "Nunito Sans", -apple-system, sans-serif',
    sizes: {
      xs: '11px',
      sm: '13px',
      base: '15px',
      lg: '17px',
      xl: '21px',
      '2xl': '26px',
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
    sm: '0 1px 3px 0 rgba(28, 25, 23, 0.1)',
    md: '0 4px 6px -1px rgba(28, 25, 23, 0.1)',
    lg: '0 10px 15px -3px rgba(28, 25, 23, 0.1)',
    xl: '0 20px 25px -5px rgba(28, 25, 23, 0.1)',
    none: 'none',
  },

  cssVariables: {
    '--color-primary': '#16a34a',
    '--color-primary-dark': '#15803d',
    '--color-primary-light': '#22c55e',
    '--color-secondary': '#854d0e',
    '--color-accent': '#65a30d',
    '--color-gray': '#44403c',
    '--color-dark-bg': '#1c1917',
    '--color-light-bg': '#fafaf9',
    '--color-border': '#d6d3d1',
    '--color-success': '#22c55e',
    '--color-warning': '#d97706',
    '--color-error': '#dc2626',
    '--color-info': '#0891b2',
    '--font-family': '"Source Sans Pro", "Nunito Sans", -apple-system, sans-serif',
    '--spacing-xs': '4px',
    '--spacing-sm': '8px',
    '--spacing-md': '16px',
    '--spacing-lg': '24px',
    '--spacing-xl': '32px',
    '--border-radius-sm': '4px',
    '--border-radius-md': '8px',
    '--border-radius-lg': '12px',
    '--shadow-md': '0 4px 6px -1px rgba(28, 25, 23, 0.1)',
  },
}

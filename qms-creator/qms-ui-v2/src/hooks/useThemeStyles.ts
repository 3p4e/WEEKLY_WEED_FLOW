import { useCurrentTheme } from '../context/ThemeContext'
import type { Theme } from '../themes/types'
import type { CSSProperties } from 'react'

/**
 * Common style combinations using theme colors
 */
export function useThemeStyles() {
  const theme = useCurrentTheme()

  const styles = {
    // Cards and containers
    card: {
      backgroundColor: theme.colors.lightBg,
      borderColor: theme.colors.border,
    } as CSSProperties,

    cardDark: {
      backgroundColor: theme.colors.darkBg,
      borderColor: theme.colors.border,
    } as CSSProperties,

    // Headers
    heading1: {
      color: theme.colors.primary,
      fontWeight: 'bold',
    } as CSSProperties,

    heading2: {
      color: theme.colors.secondary,
      fontWeight: 'bold',
    } as CSSProperties,

    heading3: {
      color: theme.colors.gray,
      fontWeight: 'bold',
    } as CSSProperties,

    // Body text
    body: {
      color: theme.colors.gray,
    } as CSSProperties,

    bodyLight: {
      color: theme.colors.lightBg,
    } as CSSProperties,

    // Buttons
    buttonPrimary: {
      backgroundColor: theme.colors.primary,
      color: 'white',
    } as CSSProperties,

    buttonSecondary: {
      backgroundColor: theme.colors.secondary,
      color: 'white',
    } as CSSProperties,

    buttonSuccess: {
      backgroundColor: theme.colors.success,
      color: 'white',
    } as CSSProperties,

    buttonWarning: {
      backgroundColor: theme.colors.warning,
      color: 'white',
    } as CSSProperties,

    buttonError: {
      backgroundColor: theme.colors.error,
      color: 'white',
    } as CSSProperties,

    // Status badges
    badgeSuccess: {
      backgroundColor: `${theme.colors.success}20`,
      color: theme.colors.success,
    } as CSSProperties,

    badgeWarning: {
      backgroundColor: `${theme.colors.warning}20`,
      color: theme.colors.warning,
    } as CSSProperties,

    badgeError: {
      backgroundColor: `${theme.colors.error}20`,
      color: theme.colors.error,
    } as CSSProperties,

    badgeInfo: {
      backgroundColor: `${theme.colors.info}20`,
      color: theme.colors.info,
    } as CSSProperties,

    // Inputs
    input: {
      backgroundColor: theme.colors.lightBg,
      borderColor: theme.colors.border,
      color: theme.colors.gray,
    } as CSSProperties,

    // Dividers
    divider: {
      borderColor: theme.colors.border,
    } as CSSProperties,

    // Backgrounds
    bgLight: {
      backgroundColor: theme.colors.lightBg,
    } as CSSProperties,

    bgDark: {
      backgroundColor: theme.colors.darkBg,
    } as CSSProperties,

    // Hover states
    hoverLight: {
      backgroundColor: `${theme.colors.primary}10`,
    } as CSSProperties,

    hoverDark: {
      backgroundColor: `${theme.colors.primary}20`,
    } as CSSProperties,
  }

  return { theme, styles }
}

/**
 * Helper to create theme-aware hover styles
 */
export function getHoverStyles(baseColor: string, isDark = false) {
  const alpha = isDark ? '30' : '15'
  return {
    backgroundColor: `${baseColor}${alpha}`,
  } as CSSProperties
}

/**
 * Helper to create theme-aware gradient
 */
export function getGradient(fromColor: string, toColor: string) {
  return {
    background: `linear-gradient(135deg, ${fromColor} 0%, ${toColor} 100%)`,
  } as CSSProperties
}

/**
 * Helper to create status-specific styling
 */
export function getStatusStyles(status: 'success' | 'warning' | 'error' | 'info', theme: Theme) {
  const statusMap = {
    success: { bg: theme.colors.success, bgLight: `${theme.colors.success}20` },
    warning: { bg: theme.colors.warning, bgLight: `${theme.colors.warning}20` },
    error: { bg: theme.colors.error, bgLight: `${theme.colors.error}20` },
    info: { bg: theme.colors.info, bgLight: `${theme.colors.info}20` },
  }

  return {
    color: statusMap[status].bg,
    backgroundColor: statusMap[status].bgLight,
  } as CSSProperties
}

export { ppSopTheme } from './ppSopTheme'
export { modernTheme } from './modernTheme'
export { cyberTheme } from './cyberTheme'
export { cannabisTheme } from './cannabisTheme'
export type { Theme, ThemeContextType, ColorPalette, TypographyTokens } from './types'

import type { Theme } from './types'
import { ppSopTheme } from './ppSopTheme'
import { modernTheme } from './modernTheme'
import { cyberTheme } from './cyberTheme'
import { cannabisTheme } from './cannabisTheme'

/**
 * Default theme registry
 * All themes available for user selection
 */
export const themeRegistry: Record<string, Theme> = {
  'cyber': cyberTheme,           // Futuristic glassmorphism (default)
  'pp-sop': ppSopTheme,          // Pharmaceutical blue/green
  'modern': modernTheme,          // Clean light theme
  'cannabis': cannabisTheme,      // Nature-inspired green
}

/**
 * Get default theme - Cyber Glass is the new default
 */
export const getDefaultTheme = (): Theme => cyberTheme

/**
 * Get theme by name
 */
export const getThemeByName = (name: string): Theme | null => {
  return themeRegistry[name] || null
}

/**
 * Get all available theme names
 */
export const getAvailableThemeNames = (): string[] => {
  return Object.keys(themeRegistry)
}

/**
 * Get all available themes
 */
export const getAvailableThemes = (): Theme[] => {
  return Object.values(themeRegistry)
}

/**
 * Get theme with metadata for display
 */
export const getThemesWithMetadata = () => {
  return [
    { key: 'cyber', theme: cyberTheme, icon: '🌐', label: 'Cyber Glass', description: 'Futuristic dark theme with neon accents' },
    { key: 'pp-sop', theme: ppSopTheme, icon: '💊', label: 'PP SOP', description: 'Pharmaceutical professional blue/green' },
    { key: 'modern', theme: modernTheme, icon: '✨', label: 'Modern Clean', description: 'Light minimal contemporary design' },
    { key: 'cannabis', theme: cannabisTheme, icon: '🌿', label: 'Cannabis Pro', description: 'Nature-inspired earthy green tones' },
  ]
}

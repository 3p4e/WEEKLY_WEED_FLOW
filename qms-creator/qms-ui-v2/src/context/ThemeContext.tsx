import React, { createContext, useContext } from 'react'
import { useThemeStore } from '../stores/useThemeStore'
import type { Theme, ThemeContextType } from '../themes/types'
import { getAvailableThemeNames } from '../themes'

/**
 * ThemeContext - Provides theme data throughout the app
 * Primarily integrates with useThemeStore (Zustand) for state management
 */
const ThemeContext = createContext<ThemeContextType | null>(null)

interface ThemeProviderProps {
  children: React.ReactNode
}

/**
 * ThemeProvider - Wraps the app and makes theme accessible via context
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const store = useThemeStore()

  const value: ThemeContextType = {
    theme: store.currentTheme,
    themeName: store.currentThemeName,
    availableThemes: getAvailableThemeNames(),
    switchTheme: store.switchTheme,
    registerTheme: store.registerTheme,
    resetToDefault: store.resetToDefault,
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

/**
 * useTheme - Hook to access theme context
 * Use this in components that need theme data
 */
// eslint-disable-next-line react-refresh/only-export-components -- context hooks live alongside the provider by design
export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}

/**
 * useCurrentTheme - Hook to access only the current theme object
 */
// eslint-disable-next-line react-refresh/only-export-components -- context hooks live alongside the provider by design
export function useCurrentTheme(): Theme {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useCurrentTheme must be used within ThemeProvider')
  }
  return context.theme
}

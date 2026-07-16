import { create } from 'zustand'
import type { Theme } from '../themes/types'
import { themeRegistry, getDefaultTheme, getThemeByName } from '../themes'

interface ThemeStore {
  currentThemeName: string
  currentTheme: Theme
  previousThemeName: string
  previousTheme: Theme | null
  defaultThemeName: string
  
  // Actions
  switchTheme: (themeName: string) => boolean
  registerTheme: (name: string, theme: Theme) => void
  resetToDefault: () => void
  revertToPrevious: () => void
  applyThemeToDom: (theme: Theme) => void
}

const STORAGE_KEY = 'qms-theme'
const DEFAULT_THEME_NAME = 'cyber'

// Load theme from localStorage or use default
const loadInitialTheme = (): string => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && themeRegistry[stored]) {
      return stored
    }
  } catch {
    // Fallback if localStorage is not available
  }
  return DEFAULT_THEME_NAME
}

/**
 * Apply theme to DOM via CSS variables
 */
const applyThemeToDom = (theme: Theme) => {
  const root = document.documentElement
  Object.entries(theme.cssVariables).forEach(([key, value]) => {
    root.style.setProperty(key, value)
  })
}

/**
 * Initialize theme on app load
 */
const initialThemeName = loadInitialTheme()
const initialTheme = getThemeByName(initialThemeName) || getDefaultTheme()
applyThemeToDom(initialTheme)

/**
 * Theme store - manages theme switching with persistence
 */
export const useThemeStore = create<ThemeStore>((set, get) => ({
  currentThemeName: initialThemeName,
  currentTheme: initialTheme,
  previousThemeName: initialThemeName,
  previousTheme: null,
  defaultThemeName: DEFAULT_THEME_NAME,

  switchTheme: (themeName: string) => {
    const theme = getThemeByName(themeName)
    
    if (!theme) {
      console.warn(`Theme "${themeName}" not found in registry`)
      return false
    }

    const state = get()
    
    set({
      previousThemeName: state.currentThemeName,
      previousTheme: state.currentTheme,
      currentThemeName: themeName,
      currentTheme: theme,
    })

    // Apply to DOM
    applyThemeToDom(theme)

    // Persist to localStorage
    try {
      localStorage.setItem(STORAGE_KEY, themeName)
    } catch {
      console.warn('Failed to persist theme preference to localStorage')
    }

    return true
  },

  registerTheme: (name: string, theme: Theme) => {
    // Register in the global registry
    themeRegistry[name] = theme
    console.log(`Theme "${name}" registered successfully`)
  },

  resetToDefault: () => {
    const { switchTheme, defaultThemeName } = get()
    switchTheme(defaultThemeName)
  },

  revertToPrevious: () => {
    const { previousThemeName, switchTheme } = get()
    if (previousThemeName) {
      switchTheme(previousThemeName)
    }
  },

  applyThemeToDom,
}))

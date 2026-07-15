/**
 * Design Tokens - Color Palette
 */
export interface ColorPalette {
  primary: string
  secondary: string
  accent: string
  gray: string
  darkBg: string
  lightBg: string
  border: string
  success: string
  warning: string
  error: string
  info: string
}

/**
 * Design Tokens - Typography
 */
export interface TypographyTokens {
  fontFamily: string
  sizes: {
    xs: string
    sm: string
    base: string
    lg: string
    xl: string
    '2xl': string
    '3xl': string
    '4xl': string
  }
  weights: {
    normal: number
    medium: number
    semibold: number
    bold: number
  }
}

/**
 * Design Tokens - Spacing
 */
export interface SpacingTokens {
  xs: string
  sm: string
  md: string
  lg: string
  xl: string
  '2xl': string
  '3xl': string
}

/**
 * Design Tokens - Border Radius
 */
export interface BorderRadiusTokens {
  none: string
  sm: string
  md: string
  lg: string
  full: string
}

/**
 * Design Tokens - Shadows
 */
export interface ShadowTokens {
  sm: string
  md: string
  lg: string
  xl: string
  none: string
}

/**
 * Complete Theme Object
 */
export interface Theme {
  name: string
  description: string
  colors: ColorPalette
  typography: TypographyTokens
  spacing: SpacingTokens
  borderRadius: BorderRadiusTokens
  shadows: ShadowTokens
  
  // CSS Variable mapping for Tailwind/direct CSS usage
  cssVariables: {
    [key: string]: string
  }
}

/**
 * Theme Context Type
 */
export interface ThemeContextType {
  theme: Theme
  themeName: string
  availableThemes: string[]
  switchTheme: (themeName: string) => void
  registerTheme: (name: string, theme: Theme) => void
  resetToDefault: () => void
}

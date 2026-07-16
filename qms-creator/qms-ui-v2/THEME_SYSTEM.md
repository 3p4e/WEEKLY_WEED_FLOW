# Theme System Documentation

## Overview

The PP SOP Platform features a fully pluggable, runtime-switchable theme system. Users can switch between predefined themes (like "PP SOP" and "Modern Clean") and revert to previous selections at any time. Administrators can also create and register custom themes programmatically.

## Architecture

### Components

1. **Theme Types** (`src/themes/types.ts`)
   - Defines the `Theme` interface with all required design tokens
   - Type-safe color palettes, typography, spacing, and shadow definitions

2. **Theme Definitions** (`src/themes/ppSopTheme.ts`, `src/themes/modernTheme.ts`)
   - Pre-defined theme implementations
   - Each theme contains complete design system specifications

3. **Theme Registry** (`src/themes/index.ts`)
   - Central registry of all available themes
   - Utility functions to query and manage themes

4. **Theme Store** (`src/stores/useThemeStore.ts`)
   - Zustand-based state management
   - Handles theme switching with localStorage persistence
   - Tracks previous theme for revert functionality
   - Applies themes to DOM via CSS variables

5. **Theme Context** (`src/context/ThemeContext.tsx`)
   - React Context for app-wide theme access
   - Custom hooks: `useTheme()` and `useCurrentTheme()`

6. **Theme Switcher UI** (`src/components/ThemeSwitcher.tsx`)
   - Dropdown, inline, and compact UI variants
   - One-click theme switching and revert functionality
   - Integrated into TopBar by default

## Usage Guide

### Using Themes in Components

#### Option 1: Using the Context Hook (Recommended)

```tsx
import { useCurrentTheme } from '../context/ThemeContext'

export function MyComponent() {
  const theme = useCurrentTheme()

  return (
    <div style={{ backgroundColor: theme.colors.primary }}>
      <h1 style={{ color: theme.colors.lightBg }}>
        Hello World
      </h1>
    </div>
  )
}
```

#### Option 2: Using the Theme Store Directly

```tsx
import { useThemeStore } from '../stores/useThemeStore'

export function MyComponent() {
  const theme = useThemeStore((state) => state.currentTheme)

  return (
    <div style={{ backgroundColor: theme.colors.primary }}>
      Content
    </div>
  )
}
```

#### Option 3: Using Theme Styles Hook

```tsx
import { useThemeStyles } from '../hooks/useThemeStyles'

export function MyComponent() {
  const { theme, styles } = useThemeStyles()

  return (
    <div style={styles.card}>
      <h1 style={styles.heading1}>Title</h1>
      <p style={styles.body}>Body text</p>
    </div>
  )
}
```

### Accessing Theme Values

All theme objects have the following structure:

```typescript
theme = {
  name: string                           // Theme identifier
  description: string                    // User-friendly description
  colors: {
    primary: string                      // Main brand color
    secondary: string                    // Accent color
    accent: string                       // Additional accent
    gray: string                         // Text color
    darkBg: string                       // Background color
    lightBg: string                      // Light background
    border: string                       // Border color
    success: string                      // Success status
    warning: string                      // Warning status
    error: string                        // Error status
    info: string                         // Information status
  }
  typography: {
    fontFamily: string
    sizes: { xs, sm, base, lg, xl, '2xl', '3xl', '4xl' }
    weights: { normal, medium, semibold, bold }
  }
  spacing: {
    xs, sm, md, lg, xl, '2xl', '3xl'
  }
  borderRadius: {
    none, sm, md, lg, full
  }
  shadows: {
    sm, md, lg, xl, none
  }
  cssVariables: Record<string, string>   // CSS variable map
}
```

## Switching Themes

### User-Facing Theme Switching

Users can switch themes using the `ThemeSwitcher` component (appears in the TopBar by default):

```tsx
import { ThemeSwitcher } from '../components/ThemeSwitcher'

<ThemeSwitcher variant="dropdown" />    // Default dropdown
<ThemeSwitcher variant="inline" />      // Inline buttons
<ThemeSwitcher variant="compact" />     // Compact select
```

### Programmatic Theme Switching

```tsx
import { useTheme } from '../context/ThemeContext'
import { useThemeStore } from '../stores/useThemeStore'

export function MyComponent() {
  const { switchTheme, resetToDefault } = useTheme()
  const store = useThemeStore()

  return (
    <div>
      <button onClick={() => switchTheme('modern')}>
        Switch to Modern
      </button>
      <button onClick={() => store.revertToPrevious()}>
        Revert to Previous
      </button>
      <button onClick={() => resetToDefault()}>
        Reset to Default (PP SOP)
      </button>
    </div>
  )
}
```

## Creating Custom Themes

### Step 1: Define the Theme

Create a new file in `src/themes/`, e.g., `src/themes/customTheme.ts`:

```typescript
import { Theme } from './types'

export const customTheme: Theme = {
  name: 'Custom Theme',
  description: 'My custom design system',
  
  colors: {
    primary: '#1E40AF',
    secondary: '#7C3AED',
    accent: '#7C3AED',
    gray: '#1F2937',
    darkBg: '#FFFFFF',
    lightBg: '#F3F4F6',
    border: '#D1D5DB',
    success: '#10B981',
    warning: '#F59E0B',
    error: '#EF4444',
    info: '#06B6D4',
  },

  typography: {
    fontFamily: '"Segoe UI", sans-serif',
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
    '--color-primary': '#1E40AF',
    '--color-secondary': '#7C3AED',
    // ... map all colors and design tokens
  },
}
```

### Step 2: Register the Theme

Add to `src/themes/index.ts`:

```typescript
import { customTheme } from './customTheme'

export const themeRegistry: Record<string, Theme> = {
  'pp-sop': ppSopTheme,
  'modern': modernTheme,
  'custom': customTheme,  // ← Add here
}
```

### Step 3: Use the Theme

It's now automatically available to switch to:

```typescript
const { switchTheme } = useTheme()
switchTheme('custom')
```

## Persistence

Theme selection is automatically persisted to localStorage under the key `pp-sop-theme`. When users return to the app, their previously selected theme is restored.

To disable persistence or customize the storage key, edit `src/stores/useThemeStore.ts`:

```typescript
const STORAGE_KEY = 'pp-sop-theme'  // Change this value
```

## CSS Variables

All themes export CSS variables that can be used directly in your CSS:

```css
.my-element {
  background-color: var(--color-primary);
  color: var(--color-light-bg);
  padding: var(--spacing-md);
  border-radius: var(--border-radius-md);
  box-shadow: var(--shadow-md);
}
```

## Dynamic Styling

For conditional styling based on theme:

```tsx
function MyComponent() {
  const theme = useCurrentTheme()

  const buttonStyle = {
    backgroundColor: isActive ? theme.colors.primary : theme.colors.lightBg,
    color: isActive ? 'white' : theme.colors.gray,
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.md,
  }

  return <button style={buttonStyle}>Click me</button>
}
```

## Migration Guide

### Converting Existing Components

Before (hardcoded colors):
```tsx
<div className="bg-slate-950 text-slate-100">
  <h1 className="text-blue-600">Title</h1>
</div>
```

After (theme-aware):
```tsx
const theme = useCurrentTheme()
<div style={{ backgroundColor: theme.colors.darkBg, color: theme.colors.lightBg }}>
  <h1 style={{ color: theme.colors.primary }}>Title</h1>
</div>
```

## Best Practices

1. **Always use theme colors** - Never hardcode hex values in component styles
2. **Use useCurrentTheme()** - Prefer context hook over store for simpler components
3. **Create theme-aware utilities** - Extract common style patterns to `useThemeStyles()`
4. **Test theme switching** - Ensure components render correctly with all available themes
5. **Document custom themes** - Add descriptions to help users choose appropriate themes
6. **Avoid alpha transparency** - If needed, append hex alpha values (e.g., `${color}80` for 50% opacity)

## Troubleshooting

### Theme doesn't update in component
- Ensure component is wrapped by `ThemeProvider` in the app
- Use `useCurrentTheme()` or `useThemeStore()` hook
- Check that component is re-rendering (verify with React DevTools)

### CSS variables not working
- Ensure `ThemeProvider` is at app root
- Verify CSS variable names in theme object
- Check browser console for CSS errors

### Theme resets on page reload
- Verify localStorage is not disabled in browser
- Check STORAGE_KEY is correctly set
- Verify no other code is clearing localStorage

### Styles not applying
- Verify inline styles have correct syntax
- Check theme object has all required color values
- Use browser inspector to verify computed styles

## Advanced

### Creating a theme programmatically at runtime

```typescript
import { useThemeStore } from '../stores/useThemeStore'
import { Theme } from '../themes/types'

export function useDynamicTheme() {
  const store = useThemeStore()

  const createAndApplyTheme = (customColors: Record<string, string>) => {
    const newTheme: Theme = {
      name: 'Dynamic Theme',
      description: 'Runtime-generated theme',
      colors: { ...defaultColors, ...customColors },
      // ... rest of theme object
    }

    store.registerTheme('dynamic', newTheme)
    store.switchTheme('dynamic')
  }

  return { createAndApplyTheme }
}
```

## API Reference

### useTheme()

```typescript
const { theme, themeName, availableThemes, switchTheme, registerTheme, resetToDefault } = useTheme()
```

- `theme: Theme` - Current theme object
- `themeName: string` - Name of current theme
- `availableThemes: string[]` - List of available theme names
- `switchTheme(name: string): void` - Switch to theme by name
- `registerTheme(name: string, theme: Theme): void` - Register new theme
- `resetToDefault(): void` - Reset to default PP SOP theme

### useCurrentTheme()

```typescript
const theme = useCurrentTheme()
```

- Returns only the current `Theme` object (lighter-weight than useTheme)

### useThemeStore()

```typescript
const store = useThemeStore()
```

- `currentTheme: Theme` - Current theme
- `currentThemeName: string` - Current theme name
- `previousTheme: Theme | null` - Previous theme
- `previousThemeName: string` - Previous theme name
- `defaultThemeName: string` - Default theme identifier
- `switchTheme(name: string): boolean` - Switch theme (returns success)
- `registerTheme(name: string, theme: Theme): void` - Register theme
- `resetToDefault(): void` - Reset to default
- `revertToPrevious(): void` - Revert to previous theme
- `applyThemeToDom(theme: Theme): void` - Apply theme CSS variables to DOM

---

**Last Updated:** January 2026
**Maintained By:** Fusion AI Assistant

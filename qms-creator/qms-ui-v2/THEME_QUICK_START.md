# Theme System - Quick Start Guide

## 1️⃣ Use Theme Colors in Components

```tsx
import { useCurrentTheme } from '../context/ThemeContext'

export function MyComponent() {
  const theme = useCurrentTheme()
  
  return (
    <div style={{ backgroundColor: theme.colors.lightBg }}>
      <h1 style={{ color: theme.colors.primary }}>Hello</h1>
      <p style={{ color: theme.colors.gray }}>Content</p>
    </div>
  )
}
```

## 2️⃣ Available Theme Colors

```typescript
theme.colors.primary        // #1F4E79 (PP Blue) - Main brand
theme.colors.secondary      // #538135 (PP Green) - Accents
theme.colors.accent         // #538135 - Same as secondary
theme.colors.gray           // #404040 - Body text
theme.colors.darkBg         // #0F172A - Background
theme.colors.lightBg        // #F5F7FA - Light background
theme.colors.border         // #E2E8F0 - Borders
theme.colors.success        // #16A34A - Success state
theme.colors.warning        // #EA8C55 - Warning state
theme.colors.error          // #DC2626 - Error state
theme.colors.info           // #0EA5E9 - Info state
```

## 3️⃣ Switch Themes Programmatically

```tsx
import { useTheme } from '../context/ThemeContext'

export function ThemeButton() {
  const { switchTheme } = useTheme()
  
  return (
    <button onClick={() => switchTheme('modern')}>
      Switch to Modern
    </button>
  )
}
```

## 4️⃣ Access Store Directly

```tsx
import { useThemeStore } from '../stores/useThemeStore'

export function MyComponent() {
  const store = useThemeStore()
  
  // Current theme
  const theme = store.currentTheme
  const name = store.currentThemeName
  
  // Actions
  store.switchTheme('pp-sop')       // Switch to theme
  store.revertToPrevious()          // Go back to previous
  store.resetToDefault()            // Reset to PP SOP
}
```

## 5️⃣ Using Pre-configured Styles

```tsx
import { useThemeStyles } from '../hooks/useThemeStyles'

export function MyComponent() {
  const { styles } = useThemeStyles()
  
  return (
    <div style={styles.card}>
      <h1 style={styles.heading1}>Title</h1>
      <p style={styles.body}>Content</p>
      <button style={styles.buttonPrimary}>Click</button>
    </div>
  )
}
```

## 6️⃣ Theme Switcher Component

```tsx
import { ThemeSwitcher } from '../components/ThemeSwitcher'

// In TopBar/Header
<ThemeSwitcher variant="compact" />    // Compact select

// In Settings page
<ThemeSwitcher variant="dropdown" />   // Full dropdown

// Inline theme options
<ThemeSwitcher variant="inline" />     // Button options
```

## 7️⃣ Create Custom Theme

**File:** `src/themes/myTheme.ts`

```typescript
import { Theme } from './types'

export const myTheme: Theme = {
  name: 'My Custom',
  description: 'My custom theme',
  colors: {
    primary: '#0066FF',
    secondary: '#FF6B00',
    // ... all 11 colors
  },
  typography: {
    fontFamily: '"Segoe UI", sans-serif',
    sizes: { xs: '12px', sm: '13px', /* ... */ },
    weights: { normal: 400, /* ... */ },
  },
  spacing: {
    xs: '4px', sm: '8px', /* ... */
  },
  borderRadius: {
    none: '0px', sm: '4px', /* ... */
  },
  shadows: {
    sm: '0 1px 2px rgba(0,0,0,0.05)', /* ... */
  },
  cssVariables: {
    '--color-primary': '#0066FF',
    // ... map all tokens
  },
}
```

**File:** `src/themes/index.ts`

```typescript
import { myTheme } from './myTheme'

export const themeRegistry = {
  'pp-sop': ppSopTheme,
  'modern': modernTheme,
  'my-custom': myTheme,  // ← Add here
}
```

Now use it: `switchTheme('my-custom')`

## 8️⃣ Common Patterns

### Card with theme styling
```tsx
const theme = useCurrentTheme()
<div
  style={{
    backgroundColor: theme.colors.lightBg,
    borderColor: theme.colors.border,
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.md,
  }}
  className="border rounded-lg"
>
  Content
</div>
```

### Button with theme
```tsx
<button
  style={{
    backgroundColor: theme.colors.primary,
    color: 'white',
    padding: `${theme.spacing.sm} ${theme.spacing.md}`,
    borderRadius: theme.borderRadius.md,
  }}
>
  Click me
</button>
```

### Text with status colors
```tsx
<span style={{ color: theme.colors.success }}>Success</span>
<span style={{ color: theme.colors.warning }}>Warning</span>
<span style={{ color: theme.colors.error }}>Error</span>
<span style={{ color: theme.colors.info }}>Info</span>
```

## 9️⃣ Typography System

```typescript
// Font family (available in all themes)
theme.typography.fontFamily  // "Arial Narrow" or "Segoe UI"

// Font sizes
theme.typography.sizes.xs    // 11px / 12px
theme.typography.sizes.sm    // 12px / 13px
theme.typography.sizes.base  // 14px / 15px
theme.typography.sizes.lg    // 16px / 17px
theme.typography.sizes.xl    // 20px / 22px
theme.typography.sizes['2xl'] // 28px
theme.typography.sizes['3xl'] // 32px
theme.typography.sizes['4xl'] // 40px

// Font weights
theme.typography.weights.normal    // 400
theme.typography.weights.medium    // 500
theme.typography.weights.semibold  // 600
theme.typography.weights.bold      // 700
```

## 🔟 Spacing System

```typescript
theme.spacing.xs   // 4px
theme.spacing.sm   // 8px
theme.spacing.md   // 16px
theme.spacing.lg   // 24px
theme.spacing.xl   // 32px
theme.spacing['2xl'] // 48px
theme.spacing['3xl'] // 64px
```

## 1️⃣1️⃣ Workflow Components

### Question Card
```tsx
import { QuestionCard } from '../components/questionnaire/QuestionCard'

<QuestionCard
  questionNumber={1}
  title="Which scope applies?"
  options={[
    {
      id: '1',
      label: 'All phases',
      description: 'Full lifecycle coverage',
      sources: ['EudraLex Vol 4', 'ICH Q10'],
    },
  ]}
  onSelect={(id) => console.log(id)}
/>
```

### Agent Pipeline
```tsx
import { AgentPipelineStatus } from '../components/workflow/AgentPipelineStatus'

<AgentPipelineStatus
  agents={[
    { id: '1', name: 'Metadata Orchestrator', status: 'completed' },
    { id: '2', name: 'Introduction Architect', status: 'active', progress: 45 },
    { id: '3', name: 'Procedure Engineer', status: 'pending' },
  ]}
  estimatedTimeRemaining={180}
/>
```

### Quality Review
```tsx
import { QualityReview } from '../components/workflow/QualityReview'

<QualityReview
  score={94}
  checklist={[
    { id: '1', category: 'Compliance', title: 'All mandatory sections', status: 'pass', message: '✓ Complete' },
  ]}
  recommendations={[
    { id: '1', priority: 'medium', title: 'Add inspection frequency', description: '...' },
  ]}
  onApprove={() => console.log('Approved')}
/>
```

### Wizard Progress
```tsx
import { WizardProgress } from '../components/workflow/WizardProgress'

<WizardProgress
  steps={[
    { id: '1', title: 'Metadata', completed: true, current: false },
    { id: '2', title: 'Questions', completed: false, current: true },
    { id: '3', title: 'Review', completed: false, current: false },
  ]}
  currentStep={1}
/>
```

## 💾 Persistence

Theme is automatically saved to localStorage:
- **Key:** `pp-sop-theme`
- **Value:** Theme name (e.g., `"modern"`)
- **Persistence:** Automatic on switch
- **Load:** On app startup

Clear theme history:
```javascript
localStorage.removeItem('pp-sop-theme')
```

## 🎨 Current Themes

| Name | File | Primary | Secondary | Best For |
|------|------|---------|-----------|----------|
| **PP SOP** | `ppSopTheme.ts` | #1F4E79 | #538135 | Professional, pharma |
| **Modern** | `modernTheme.ts` | #2563EB | #7C3AED | Contemporary, light |

## ❓ FAQ

**Q: How do I access colors outside components?**
A: You can't directly; use hooks. Colors are tied to React components.

**Q: Can users customize colors?**
A: Yes, create a custom theme and register it (see section 7️⃣).

**Q: Does changing theme reload the app?**
A: No, it's instant with CSS variables.

**Q: What happens if a theme is missing?**
A: App defaults to PP SOP theme.

**Q: Can themes be loaded from an API?**
A: Yes, register themes dynamically: `store.registerTheme('name', themeObject)`

**Q: Are CSS variables updated on theme switch?**
A: Yes, automatically via `applyThemeToDom()`

**Q: How do I use Tailwind with themes?**
A: Prefer inline styles. Or export Tailwind config with CSS variables.

---

**Version:** 1.0  
**Last Updated:** January 29, 2026  
**Quick Reference for Developers**

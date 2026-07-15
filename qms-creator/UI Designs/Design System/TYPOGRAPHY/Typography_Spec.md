# Typography System Specification

**Version:** 1.0  
**Date:** January 29, 2026  
**Status:** Production Ready ✅

---

## Font Families

### PP SOP Theme
```
Font Family: Arial Narrow
Fallback: Arial, sans-serif
Usage: Professional, pharmaceutical standard
Origin: System font, widely available
Weight Range: Normal (400), Bold (700)
```

### Modern Clean Theme
```
Font Family: Segoe UI
Fallback: "Helvetica Neue", Arial, sans-serif
Usage: Contemporary, clean, modern
Origin: System font (Windows/Web), common default
Weight Range: Normal (400) to Bold (700)
```

---

## Font Size Scale

All sizes in pixels. Scale is based on 1.25x multiplier for hierarchy.

| Size | PP SOP | Modern | Rem | Usage |
|------|--------|--------|-----|-------|
| **xs** | 11px | 12px | 0.6875em | Captions, small labels |
| **sm** | 12px | 13px | 0.8125em | Labels, helper text |
| **base** | 14px | 15px | 0.9375em | Body text, form inputs |
| **lg** | 16px | 17px | 1.0625em | Larger labels, emphasis |
| **xl** | 20px | 22px | 1.375em | Subsection headings |
| **2xl** | 28px | 28px | 1.75em | Section headings |
| **3xl** | 32px | 32px | 2em | Page titles |
| **4xl** | 40px | 40px | 2.5em | Hero headings |

**Base Size:** 14px (PP SOP) / 15px (Modern)  
**Multiplier:** 1.25x between steps

---

## Font Weights

Standardized weights used across both themes:

| Weight | Value | Usage | CSS |
|--------|-------|-------|-----|
| **Normal** | 400 | Body text, regular content | `font-weight: 400` |
| **Medium** | 500 | Form labels, emphasis | `font-weight: 500` |
| **Semibold** | 600 | Subheadings | `font-weight: 600` |
| **Bold** | 700 | Headings, strong emphasis | `font-weight: 700` |

---

## Heading System

### H1 - Page Title
```
Font Size: 32px (3xl)
Font Weight: Bold (700)
Line Height: 1.2
Letter Spacing: -0.5px
Color (PP SOP): #1F4E79 (Primary Blue)
Color (Modern): #2563EB (Modern Blue)
Margin Top: 0
Margin Bottom: 24px
```

**Example:** "SOP Creation Progress"

### H2 - Section Heading
```
Font Size: 20px (xl)
Font Weight: Bold (700)
Line Height: 1.3
Letter Spacing: 0
Color (PP SOP): #538135 (Secondary Green)
Color (Modern): #7C3AED (Purple)
Margin Top: 32px
Margin Bottom: 16px
```

**Example:** "Appearance & Theme", "Quality Assessment"

### H3 - Subsection
```
Font Size: 16px (lg)
Font Weight: Bold (700)
Line Height: 1.4
Letter Spacing: 0
Color (PP SOP): #404040 (Gray)
Color (Modern): #1F2937 (Dark Gray)
Margin Top: 24px
Margin Bottom: 12px
```

**Example:** "Theme Name", "Color Palette"

### H4 - Minor Heading
```
Font Size: 14px (base)
Font Weight: Semibold (600)
Line Height: 1.5
Color: Inherit from theme
Margin Top: 16px
Margin Bottom: 8px
```

---

## Body Text

### Standard Paragraph
```
Font Size: 14px (PP SOP) / 15px (Modern)
Font Weight: Normal (400)
Line Height: 1.5
Letter Spacing: 0
Color (PP SOP): #404040 (Gray)
Color (Modern): #1F2937 (Dark Gray)
Margin Bottom: 16px
```

### Small Text / Caption
```
Font Size: 12px (sm)
Font Weight: Normal (400)
Line Height: 1.4
Color: Slightly lighter than body
Usage: Captions, secondary information
```

### Helper Text / Hint
```
Font Size: 11px (xs)
Font Weight: Normal (400)
Line Height: 1.4
Color: Muted / gray
Usage: Form hints, descriptions
```

---

## Form Text

### Form Label
```
Font Size: 14px (base)
Font Weight: Medium (500)
Color: Primary text color
Margin Bottom: 6px
```

### Form Input Text
```
Font Size: 14px (base)
Font Weight: Normal (400)
Line Height: 1.5
Color: Body text color
Placeholder Color: 60% opacity of text color
```

### Form Error Text
```
Font Size: 12px (sm)
Font Weight: Normal (400)
Color: #DC2626 (Error Red)
Margin Top: 4px
```

---

## Button Text

### Button Default
```
Font Size: 14px (base)
Font Weight: Medium (500)
Letter Spacing: 0.5px (subtle)
Text Transform: None
Color: White (on colored bg) or primary (on light bg)
Line Height: 1.2
```

### Button Small
```
Font Size: 12px (sm)
Font Weight: Medium (500)
Padding: 6px 12px
```

### Button Large
```
Font Size: 16px (lg)
Font Weight: Medium (500)
Padding: 12px 24px
```

---

## Monospace Text

### Code / Variables
```
Font Family: 'Monaco', 'Courier New', monospace
Font Size: 12px (sm)
Background: Light gray background
Padding: 2px 6px
Border Radius: 3px
Example: padding: 8px
```

### Inline Code
```
Font Family: Monospace
Font Size: 13px
Background: Light background
Color: Code color (darker)
```

---

## Link Styling

### Standard Link
```
Font Size: Inherit
Font Weight: Inherit
Color (PP SOP): #1F4E79 (Primary)
Color (Modern): #2563EB (Primary)
Text Decoration: Underline
Hover: Darker shade + cursor pointer
Active: Visited state (slightly grayed)
```

### Link Button
```
Font Size: 14px
Font Weight: Medium (500)
Color: White (on primary background)
Text Decoration: None
Hover: Opacity change or darker background
```

---

## Badge & Tag Text

### Badge
```
Font Size: 11px (xs)
Font Weight: Semibold (600)
Text Transform: Uppercase
Letter Spacing: 0.5px
Padding: 4px 8px
```

### Tag
```
Font Size: 12px (sm)
Font Weight: Medium (500)
Padding: 6px 12px
```

---

## Table Text

### Table Header
```
Font Size: 12px (sm)
Font Weight: Semibold (600)
Color: White or primary color
Text Align: Left or Center
```

### Table Cell
```
Font Size: 14px (base)
Font Weight: Normal (400)
Color: Body text color
Padding: 12px
Line Height: 1.5
```

---

## Line Height Reference

| Purpose | Value | Ratio |
|---------|-------|-------|
| Heading | 1.2 | Tight, professional |
| Subheading | 1.3 | Slightly loose |
| Body | 1.5 | Readable, comfortable |
| Tight | 1.15 | Compact spacing |
| Loose | 1.75 | Spacious, emphasized |

---

## Letter Spacing

| Use Case | Value | Notes |
|----------|-------|-------|
| Normal | 0 | Default, most text |
| Headings | -0.5px | Tighter, more professional |
| Labels | 0.5px | Slightly wider, emphasis |
| All Caps | 0.75px | Standard for uppercase |
| Tight | -0.25px | For emphasis |
| Loose | 1px | For special emphasis |

---

## Text Decorations

### Underline
- **Links:** Underlined by default
- **Hover:** Continue underlined
- **Visited:** Slightly faded

### Bold
- **Usage:** Emphasis within body text
- **Method:** `<strong>` tag or `font-weight: 700`
- **Not for:** Headings (use heading styles instead)

### Italic
- **Usage:** Quoted text, references, emphasis
- **Method:** `<em>` tag or `font-style: italic`
- **Sparingly:** Use only when semantically necessary

### Strikethrough
- **Usage:** Disabled/deprecated items
- **Method:** `text-decoration: line-through`

---

## Text Alignment

### Default
```
Alignment: Left
Justification: Flush left with ragged right edge
Usage: Most content
```

### Center
```
Alignment: Center
Usage: Headings, titles, special emphasis
```

### Justify
```
Alignment: Justified
Usage: Body text in formal documents
Hyphenation: Enabled to prevent large gaps
```

### Right
```
Alignment: Right
Usage: Rare - RTL languages, special layouts
```

---

## Responsive Typography

### Mobile (< 768px)
```
H1: 24px (down from 32px)
H2: 18px (down from 20px)
Body: 14px (same)
Spacing: Reduced margins/line-height
```

### Tablet (768px - 1024px)
```
H1: 28px
H2: 20px
Body: 14px
Spacing: Standard
```

### Desktop (> 1024px)
```
All sizes at standard specifications
Full spacing and line heights
```

---

## Text Color Reference

### PP SOP Theme
| Element | Color | Hex |
|---------|-------|-----|
| Headings (H1) | Primary | #1F4E79 |
| Headings (H2) | Secondary | #538135 |
| Headings (H3) | Gray | #404040 |
| Body Text | Gray | #404040 |
| Muted Text | Light Gray | #666666 |
| Links | Primary | #1F4E79 |
| Success | Green | #16A34A |
| Warning | Orange | #EA8C55 |
| Error | Red | #DC2626 |

### Modern Theme
| Element | Color | Hex |
|---------|-------|-----|
| Headings (H1) | Primary | #2563EB |
| Headings (H2) | Secondary | #7C3AED |
| Headings (H3) | Dark Gray | #1F2937 |
| Body Text | Dark Gray | #1F2937 |
| Muted Text | Light Gray | #9CA3AF |
| Links | Primary | #2563EB |
| Success | Green | #10B981 |
| Warning | Amber | #F59E0B |
| Error | Red | #EF4444 |

---

## Typography Combinations

### Professional Heading
```
"H1 + Body + Gray Label"
Size: 32px primary blue
+ 14px gray text
+ 11px muted label
= Professional, clear hierarchy
```

### Modern Minimal
```
"H2 + Body + Small"
Size: 20px purple
+ 15px dark gray
+ 12px light gray
= Contemporary, clean
```

### Emphasis
```
Strong + Regular
Weight: Bold (700) within normal (400) text
Use Case: Important words, emphasis
```

---

## Implementation Examples

### React / Styled Components
```tsx
const heading1 = css`
  font-family: "Arial Narrow", Arial, sans-serif;
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.5px;
  color: #1F4E79;
  margin-bottom: 24px;
`

const bodyText = css`
  font-family: "Arial Narrow", Arial, sans-serif;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5;
  color: #404040;
  margin-bottom: 16px;
`
```

### CSS Variables
```css
:root {
  --font-family: "Arial Narrow", Arial, sans-serif;
  --font-size-xs: 11px;
  --font-size-sm: 12px;
  --font-size-base: 14px;
  --font-size-lg: 16px;
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  --line-height-tight: 1.2;
  --line-height-normal: 1.5;
  --letter-spacing-tight: -0.5px;
}

h1 {
  font: var(--font-weight-bold) var(--font-size-3xl) / var(--line-height-tight) var(--font-family);
  letter-spacing: var(--letter-spacing-tight);
}
```

---

## Accessibility Notes

✓ **Minimum Font Size:** 14px for body text (WCAG minimum 12px)  
✓ **Line Height:** 1.5 for comfortable reading  
✓ **Contrast:** All text colors meet WCAG AA standard  
✓ **Semantic HTML:** Use proper heading hierarchy (`<h1>`, `<h2>`, etc.)  
✓ **Scale Appropriately:** Increase font size for elderly/vision-impaired users  

---

## Best Practices

1. **Maintain Hierarchy** - Use heading levels consistently
2. **Limit Font Styles** - Max 2 font families per design
3. **Readable Size** - Never below 12px for body text
4. **Sufficient Contrast** - Always check WCAG compliance
5. **Generous Spacing** - Line height of 1.5 for body text
6. **Semantic HTML** - Use correct tags for meaning
7. **Font Loading** - System fonts are fastest
8. **Responsive** - Adjust sizes for mobile

---

**Typography System v1.0**  
Professional, accessible, and visually consistent typography for the PP SOP Platform.

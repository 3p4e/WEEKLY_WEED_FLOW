# PP SOP Platform - UI Design System

**Version:** 1.0  
**Date:** January 29, 2026  
**Status:** Complete ✅

Welcome to the UI Design System documentation for the PP SOP Platform. This folder contains all design specifications, color palettes, typography guides, and component examples.

---

## 📁 Folder Structure

```
UI_Designs/
├── README.md                      (This file - Overview & Index)
├── COLORS/                        (Color palettes & specifications)
│   ├── PP_SOP_Palette.json
│   ├── Modern_Palette.json
│   ├── Color_Specifications.md
│   └── Color_Swatches.html        (Visual reference)
├── TYPOGRAPHY/                    (Font systems & scales)
│   ├── Typography_Spec.md
│   └── Font_Scale.json
├── SPACING/                       (Spacing system & grid)
│   ├── Spacing_System.md
│   └── Spacing_Tokens.json
├── COMPONENTS/                    (UI component designs)
│   ├── Component_Library.md
│   ├── Button_Variants.md
│   ├── Form_Inputs.md
│   ├── Cards.md
│   └── Examples/
│       ├── QuestionCard_Design.md
│       ├── AgentPipeline_Design.md
│       ├── QualityReview_Design.md
│       └── WizardProgress_Design.md
├── THEMES/                        (Theme definitions)
│   ├── PP_SOP_Theme.json
│   ├── Modern_Clean_Theme.json
│   └── Theme_Switching_Guide.md
├── WORKFLOWS/                     (User flows & wireframes)
│   ├── SOP_Creation_Flow.md
│   ├── Theme_Switching_Flow.md
│   └── Questionnaire_Flow.md
├── TOKENS/                        (Design tokens for tools)
│   ├── Design_Tokens.json
│   ├── CSS_Variables.css
│   └── Tailwind_Config.json
└── ASSETS/                        (Visual assets & exports)
    ├── Color_Palette_Card.md
    ├── Accessibility_Report.md
    └── Export_for_Figma.json
```

---

## 🎨 Quick Access

### Colors
- **PP SOP Theme Colors:** [COLORS/PP_SOP_Palette.json](./COLORS/PP_SOP_Palette.json)
- **Modern Theme Colors:** [COLORS/Modern_Palette.json](./COLORS/Modern_Palette.json)
- **Visual Color Reference:** [COLORS/Color_Swatches.html](./COLORS/Color_Swatches.html)
- **Detailed Specifications:** [COLORS/Color_Specifications.md](./COLORS/Color_Specifications.md)

### Typography
- **Font System Guide:** [TYPOGRAPHY/Typography_Spec.md](./TYPOGRAPHY/Typography_Spec.md)
- **Typography Tokens:** [TYPOGRAPHY/Font_Scale.json](./TYPOGRAPHY/Font_Scale.json)

### Spacing
- **Spacing Guide:** [SPACING/Spacing_System.md](./SPACING/Spacing_System.md)
- **Spacing Values:** [SPACING/Spacing_Tokens.json](./SPACING/Spacing_Tokens.json)

### Components
- **Full Component Library:** [COMPONENTS/Component_Library.md](./COMPONENTS/Component_Library.md)
- **Workflow Components:**
  - [Question Card Design](./COMPONENTS/Examples/QuestionCard_Design.md)
  - [Agent Pipeline Design](./COMPONENTS/Examples/AgentPipeline_Design.md)
  - [Quality Review Design](./COMPONENTS/Examples/QualityReview_Design.md)
  - [Wizard Progress Design](./COMPONENTS/Examples/WizardProgress_Design.md)

### Themes
- **PP SOP Theme Definition:** [THEMES/PP_SOP_Theme.json](./THEMES/PP_SOP_Theme.json)
- **Modern Theme Definition:** [THEMES/Modern_Clean_Theme.json](./THEMES/Modern_Clean_Theme.json)
- **Theme Switching:** [THEMES/Theme_Switching_Guide.md](./THEMES/Theme_Switching_Guide.md)

### Tokens & Exports
- **All Design Tokens:** [TOKENS/Design_Tokens.json](./TOKENS/Design_Tokens.json)
- **CSS Variables:** [TOKENS/CSS_Variables.css](./TOKENS/CSS_Variables.css)
- **Figma Export:** [TOKENS/Export_for_Figma.json](./TOKENS/Export_for_Figma.json)

---

## 🎯 What's Inside

### Color Palettes (COLORS/)
Complete color specifications for both themes with:
- Hex codes
- RGB values
- HSL values
- Usage guidelines
- Accessibility information
- Contrast ratios
- Visual swatches

### Typography System (TYPOGRAPHY/)
Font system specifications including:
- Font family (Arial Narrow, Segoe UI)
- Size scales (xs, sm, base, lg, xl, 2xl, 3xl, 4xl)
- Font weights (normal, medium, semibold, bold)
- Line heights
- Letter spacing

### Spacing System (SPACING/)
Standardized spacing values:
- xs: 4px
- sm: 8px
- md: 16px
- lg: 24px
- xl: 32px
- 2xl: 48px
- 3xl: 64px

### Components (COMPONENTS/)
UI component specifications:
- Button variants (primary, secondary, success, warning, error)
- Form inputs (text, select, checkbox, radio)
- Cards with theme variants
- Workflow components (Question Card, Agent Pipeline, Quality Review, Wizard Progress)
- Complete examples with usage

### Themes (THEMES/)
Complete theme definitions:
- PP SOP Theme (pharmaceutical-grade)
- Modern Clean Theme (contemporary)
- How to switch themes
- How to create custom themes

### Design Tokens (TOKENS/)
Machine-readable design tokens:
- JSON format for programmatic usage
- CSS variables for CSS-in-JS
- Figma-compatible exports
- Design tool integrations

---

## 📖 How to Use This Documentation

### For Designers
1. Start with [Color_Specifications.md](./COLORS/Color_Specifications.md)
2. Review [Typography_Spec.md](./TYPOGRAPHY/Typography_Spec.md)
3. Check [Component_Library.md](./COMPONENTS/Component_Library.md)
4. Use [Color_Swatches.html](./COLORS/Color_Swatches.html) for visual reference

### For Developers
1. Check [Design_Tokens.json](./TOKENS/Design_Tokens.json)
2. Review [CSS_Variables.css](./TOKENS/CSS_Variables.css)
3. Use [THEMES/PP_SOP_Theme.json](./THEMES/PP_SOP_Theme.json) for theme structure
4. Reference [Typography_Spec.md](./TYPOGRAPHY/Typography_Spec.md) for font system

### For Design Tool Integration (Figma)
1. Export [Export_for_Figma.json](./TOKENS/Export_for_Figma.json)
2. Import into Figma via design tokens plugin
3. Components match specifications in [Component_Library.md](./COMPONENTS/Component_Library.md)

### For Product Managers
1. Review [SOP_Creation_Flow.md](./WORKFLOWS/SOP_Creation_Flow.md)
2. Check [Questionnaire_Flow.md](./WORKFLOWS/Questionnaire_Flow.md)
3. See [Component_Library.md](./COMPONENTS/Component_Library.md) for feature UX

---

## 🎨 Theme Overview

### PP SOP Theme
- **Purpose:** Professional, pharmaceutical-grade, EU GMP compliant
- **Primary Color:** #1F4E79 (Blue)
- **Secondary Color:** #538135 (Green)
- **Best for:** Corporate, regulated, professional contexts
- **Typography:** Arial Narrow

**Use Case:** Default theme for the platform, emphasizing trust and compliance

### Modern Clean Theme
- **Purpose:** Contemporary, minimal, light
- **Primary Color:** #2563EB (Modern Blue)
- **Secondary Color:** #7C3AED (Purple)
- **Best for:** Modern interfaces, forward-thinking organizations
- **Typography:** Segoe UI

**Use Case:** Alternative for users preferring contemporary aesthetics

---

## 🔄 Theme Switching

Users can switch between themes instantly in the Settings page:

**Settings → Appearance & Theme → Select Theme**

The system:
- ✅ Switches instantly (no reload)
- ✅ Saves selection to localStorage
- ✅ Allows reverting to previous theme
- ✅ Can reset to default theme

See [Theme_Switching_Guide.md](./THEMES/Theme_Switching_Guide.md) for technical details.

---

## 📐 Design Specifications

### Colors
- **11 semantic colors** per theme
- **WCAG AA compliant** contrast ratios
- **Status indicators:** Success, Warning, Error, Info

### Typography
- **8 font sizes** (xs to 4xl)
- **4 font weights** (normal, medium, semibold, bold)
- **Consistent line heights** (1.15, 1.5)

### Spacing
- **8-based scale** (4px, 8px, 16px, 24px, 32px, 48px, 64px)
- **Consistent padding/margins**
- **Predictable layouts**

### Borders & Shadows
- **5 border radius values** (none, sm, md, lg, full)
- **4 shadow elevations** (sm, md, lg, xl)

---

## 📋 Component Categories

### Basic Components
- Buttons (multiple variants)
- Form Inputs (text, select, etc.)
- Cards (default, dark, highlighted)
- Badges & Tags
- Dividers

### Workflow Components
- **Question Card** - For agent questionnaires
- **Agent Pipeline Status** - Visual workflow progress
- **Quality Review** - Assessment & recommendations
- **Wizard Progress** - Multi-step process indicator

### Complex Components
- Navigation/Sidebar
- Top Bar/Header
- Modals & Dialogs
- Tables

---

## 🚀 Getting Started

1. **Understand the Design System**
   - Read this README
   - Review color palette
   - Check typography system

2. **Choose Your Workflow**
   - **Designer:** Use Figma export or visual references
   - **Developer:** Import JSON tokens or CSS variables
   - **Product:** Review component library and flows

3. **Implement**
   - Follow component specifications
   - Use design tokens consistently
   - Test theme switching

4. **Reference**
   - Keep this folder accessible
   - Bookmark key files
   - Share with team members

---

## 📞 Support & Questions

### For Design Questions
→ See [COMPONENTS/Component_Library.md](./COMPONENTS/Component_Library.md)

### For Color Questions
→ See [COLORS/Color_Specifications.md](./COLORS/Color_Specifications.md)

### For Development Questions
→ See [TOKENS/Design_Tokens.json](./TOKENS/Design_Tokens.json)

### For Theme Questions
→ See [THEMES/Theme_Switching_Guide.md](./THEMES/Theme_Switching_Guide.md)

### For Accessibility Questions
→ See [ASSETS/Accessibility_Report.md](./ASSETS/Accessibility_Report.md)

---

## 📊 Design System Statistics

| Metric | Value |
|--------|-------|
| **Themes Available** | 2 (PP SOP, Modern) |
| **Primary Colors** | 4 per theme |
| **Status Colors** | 4 per theme |
| **Typography Sizes** | 8 levels |
| **Font Weights** | 4 options |
| **Spacing Values** | 7 scale units |
| **Border Radius Values** | 5 options |
| **Shadow Elevations** | 4 levels |
| **Component Types** | 15+ |
| **Workflow Components** | 4 specialized |
| **WCAG Compliance** | AA ✓ |

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 29, 2026 | Initial release with PP SOP and Modern themes |

---

## 📝 Maintainers

- **Design System Owner:** Fusion AI Assistant
- **Last Updated:** January 29, 2026
- **Status:** Production Ready ✅

---

## 📚 Related Documentation

- **Main Theme System:** `/qms-ui-v2/THEME_SYSTEM.md`
- **Quick Start Guide:** `/qms-ui-v2/THEME_QUICK_START.md`
- **Color Reference:** `/qms-ui-v2/THEME_COLOR_REFERENCE.md`
- **Implementation Summary:** `/qms-ui-v2/IMPLEMENTATION_SUMMARY.md`

---

**PP SOP Platform Design System**  
Built with attention to pharmaceutical industry standards, regulatory compliance, and user experience excellence.

🎨 Design-driven. 👨‍💻 Developer-friendly. ♿ Accessible.

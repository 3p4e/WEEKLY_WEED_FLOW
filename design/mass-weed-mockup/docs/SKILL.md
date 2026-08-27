---
name: growflow-design
description: Use this skill to generate well-branded interfaces and assets for GrowFlow (Weekly Weed Flow), the operations task tracker by Purely Plant GmbH — for production or throwaway prototypes/mocks. Contains essential design guidelines, colors, type, fonts, brand assets, and a UI-kit component library for prototyping. Green-hero system with light + dark "control-room" themes and bilingual EN/МК support.
user-invocable: true
---

Read the `readme.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and
create static HTML files for the user to view. If working on production code, you can copy assets
and read the rules here to become an expert in designing with this brand.

Key facts:
- **Brand:** Purely Plant green is the hero (`--primary #15A86B`). Leaf mark + "GrowFlow"
  wordmark (green "Flow") are bitmaps in `assets/` — never redraw them.
- **Tokens:** link `styles.css` for all CSS custom properties (colors, type, spacing, radius,
  elevation). Dark theme via `[data-theme="dark"]`.
- **Type:** Manrope (app), Outfit (brand), Geist Mono (ids/codes). **Icons:** Lucide (CDN).
- **Bilingual:** every string exists in English + Macedonian; МК runs ~30% longer — never
  truncate. Tone is serious, calm, precise, trustworthy (regulated facility).
- **Components:** compiled to `window.GrowFlowDesignSystem_7accb1` via `_ds_bundle.js`. See
  `components/*/*.prompt.md` for usage. The task card is the signature component; see
  `ui_kits/growflow/` for a full interactive app recreation.

If the user invokes this skill without any other guidance, ask them what they want to build or
design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_
production code, depending on the need.

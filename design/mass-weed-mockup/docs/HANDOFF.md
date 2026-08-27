# GrowFlow Design System — Handoff Document

**Project:** GrowFlow (internal name **WWF** — "Weekly Weed Flow")
**Company:** Purely Plant GmbH — licensed medical-cannabis production, North Macedonia
**Design system namespace:** `GrowFlowDesignSystem_7accb1`
**Prepared:** 2026-07-05
**Live reference app:** https://wwf.srv1231216.hstgr.cloud

---

## 1. What this project is

This is a **design system** (compiled library of tokens + components) with a **full interactive app recreation** layered on top. It exists to let designers and developers produce well-branded GrowFlow interfaces — production code or throwaway prototypes — that match the real product.

Two things live here:

1. **A component library** — 29 React components, 176 design tokens, a dark "control-room" theme, and 21 specimen cards that populate the Design System tab.
2. **A hi-fi, interactive recreation** of the real WWF task-tracker app (`ui_kits/growflow/`), rebuilt from the actual source (`3p4e/WEEKLY_WEED_FLOW`), not screenshots.

The goal of the redesign: **a substantially better-looking, more polished, more usable interface** while keeping the same information architecture, feature set, brand, and EN/МК bilingual support.

---

## 2. Sources used (for whoever picks this up)

Everything here was derived from client-provided materials. If you have access, explore them to go deeper:

- **GitHub — the live app source (ground truth):** [`3p4e/WEEKLY_WEED_FLOW`](https://github.com/3p4e/WEEKLY_WEED_FLOW) — vanilla single-file app in `web/gf/*` (`data.js`, `core.js`, `views.js`, `app.css`, `brand.css`), plus `docs/SPEC.md`, `docs/SCOPE.md`, `docs/STATUS.md`.
- **Codebase handover archive:** `WWF_DES/WWF-UI-Design-Handover/` — design brief, design-system doc, screen breakdown, EN/МК copy deck, domain/roles/workflows, `design-tokens.json`, and screenshots.
- **Uploaded brand assets:** `uploads/PP_Leaf.svg`, `uploads/PP_TEXT_2.svg`, `uploads/PP_Leaf_T2s.svg`.

> **Reading tip:** the repo is the ground truth. When something differs from what a screenshot suggested, the repo won. All component values (paddings, radii, colors) were lifted from `web/gf/*`.

---

## 3. Repository map

```
/                         design-system root (compiler reads this)
├── styles.css            @import-only entry point (consumers link this)
├── brand.css             Purely Plant logo lockups + 3D leaf CSS
├── tokens/               colors.css · typography.css · layout.css · base.css
├── components/           30 components in 7 groups (see §5)
│   ├── brand/  core/  forms/  data/  nav/  task/  feedback/
├── guidelines/           16 foundation specimen cards (Design System tab)
├── ui_kits/growflow/     the interactive app recreation (see §6)
│   ├── index.html        thin shell — loads the 3 script files below
│   ├── data.js           org model, roles, i18n, seed tasks
│   ├── screens.js        11 secondary screens
│   ├── app.js            app shell, task cards, modals, composition
│   ├── tweaks-panel.js   expressive tweak controls
│   └── font-specimen.html
├── templates/growflow/   reusable app-shell Design Component + ds-base.js
├── assets/               logos, leaf PNGs
├── readme.md             the design guide + manifest
├── SKILL.md              Agent-Skills-compatible entry point
├── HANDOFF.md            this document
└── GrowFlow App.html     standalone offline export of the app
```

**Compiler-generated — never edit by hand:** `_ds_bundle.js`, `_ds_manifest.json`, `_adherence.oxlintrc.json`.

---

## 4. Design foundations (quick reference)

**Color.** Green-hero. `--primary` = `#15A86B`, brightened to `#22C07E` in dark. Leaf gradient `#5BBA47 → #8DC73F`. Full neutral ramp, 6 status colors (pending/working/review/stuck/postponed/done), 4 priority accents. Tokens carry a light default and a `[data-theme="dark"]` scope.

**Type.**
- **Saira** — body & UI (`--font-app`)
- **Orbitron** — display & titles (`--font-display`)
- **Rajdhani** — all-caps metadata / micro-labels (`--font-label`)

All three are Google Fonts. ⚠️ These are **substitutions** — see Caveats.

**Spacing / shape.** 4px-based spacing scale; radii `--r-sm 8 · --r-md 12 · --r-lg 14 · --r-xl 18` (exact values from source — not snapped to a grid). Soft layered shadows (`--sh-*`).

**Brand mark & aesthetic.** A real 3D leaf — the uploaded solid mesh (`assets/pp-leaf-3d.obj`, ~5k verts) rendered in **WebGL / Three.js** with a plasma-green material; on the splash it spin-bursts before handing off to login (auto-falls back to a CSS extruded stack if WebGL is unavailable). Click interactions: consecutive clicks escalate spin speed; 3+ rapid clicks trigger a wormhole implosion → re-emergence. Random idle movements cycle automatically. The `GrowFlowLockup` component defaults to `onDark=true` (white text on dark backgrounds). The system wears a **Romulan-console ("Tal Shiar") reskin**: plasma-green on hull-black, angular `--clip-bevel` / `--clip-chevron` corner geometry, `--scanlines` / `--plasma-grid` textures.

**176 tokens total.** See the Design System tab and `guidelines/*.html` specimen cards for the full picture.

---

## 5. Component library (29 components, 7 groups)

| Group | Components |
|---|---|
| **brand** | `Leaf`, `GrowFlowLockup` |
| **core** | `Button`, `IconButton`, `Avatar`, `AvatarStack`, `Badge`, `Chip` |
| **forms** | `Input`, `Textarea`, `Select`, `Checkbox`, `Switch`, `Segmented`, `Field` |
| **task** | `StatusPill`, `PriorityTag`, `TaskCard` |
| **data** | `KpiTile`, `BarRow` |
| **nav** | `NavItem`, `DeptRow` |
| **feedback** | `Modal`, `Toast` |

Each directory has `<Name>.jsx` + `<Name>.d.ts` (props contract) + `<Name>.prompt.md` (usage) + one `@dsCard` HTML specimen. Consume via `const { Button } = window.GrowFlowDesignSystem_7accb1` after loading `_ds_bundle.js`.

> The inventory mirrors the source app's component families — nothing invented beyond it. There are no `Tabs`/`Tooltip`/`Radio` etc. because the source doesn't define them.

---

## 6. The interactive app (`ui_kits/growflow/`)

A genuinely clickable recreation. **Login flow:** splash (click the leaf) → login → app.

**15 routed views, no dead nav:** My Week, Board (drag-and-drop), Timeline, Coordination, Dashboard, Team, AI Report/Plan, Analytics, Audit, Import, Access, Governance, Planning, QC Lab, Settings.

**Domain model:** 11 departments, 8 roles + permission gating (deny toasts), 8 task types, RACI ownership, 6-status lifecycle, EN/МК throughout, light + dark theme.

**Working interactions:**
- Status cycling, drag-and-drop board, checkbox completion
- Add / edit / delete tasks — full form (owner + helpers multi-select, weekday chips, est. hours, recurrence, due, ref, tags)
- **Multi-week data** — 3 weeks (26/27/28); global week stepper filters My Week, Board, Timeline, Dashboard, Report
- Search + department filter (with clearable chip)
- Team CRUD + **Set active user** (switches acting identity → drives permissions)
- Voice-capture flow (record → AI parse → confirm)
- Assistant (ask + draft-with-tone)
- Plan/Report toggle with draft → submit
- Export: JSON / CSV / Markdown
- Keyboard shortcuts: ⌘/Ctrl+K search, `n` new task, Esc blur

**Architecture:** `index.html` is a thin shell that loads `data.js` → `screens.js` → `app.js` as `text/babel`. Load order matters: `data.js` exposes `window.GF_*` globals; `screens.js` and `app.js` rebind them at the top of their IIFEs so each file is self-sufficient. These `.js` files are **not** swept into the DS bundle (loaded via babel-src, confirmed).

---

## 7. How to use this system

**Preview components/foundations:** open the **Design System tab** — 21 cards across Brand, Colors, Type, Spacing, Components, GrowFlow App.

**Start a new screen:** the **Templates** picker offers `templates/growflow/` (the app shell as a Design Component). In a consuming project, point `ds-base.js`'s `base` at the bound `_ds/<folder>`.

**Build a static artifact / prototype:** copy the assets you need out of `assets/`, link `styles.css` for tokens, load `_ds_bundle.js` for components, and read `readme.md` + `SKILL.md` to design like the brand.

**Offline demo:** `GrowFlow App.html` is a fully self-contained (2.7 MB) export — opens anywhere, no network.

---

## 8. Caveats & known limitations

- **Fonts.** The brand logotype uses **Poppins** (Google Fonts), with **Comfortaa** self-hosted as legacy fallback. Display/label type (Orbitron / Rajdhani) and body (Saira) are deliberate choices for the Romulan-console feel.
- **Icons** are **Lucide** (CDN) standing in for the source app's hand-authored 20×20 stroke icon set — matched on stroke weight, not identical.
- **Single-instance seed state.** Everything is client-side mock data; nothing persists across reload except theme + identity. New team members don't propagate onto pre-computed task cards (identity switching works).
- **Some screens exceed the source** (QC Lab, Governance are richer interpretations, good for demos but not 1:1 recreations).
- **Deliberately excluded** — per the repo's own `SCOPE.md` (WWF is a non-GMP planning tool): PDF export with GMP sign-off, electronic signatures, MFA, backend/RLS concerns. Recreating these would invent beyond the source.

---

## 9. Suggested next steps (highest value first)

1. **Provide real brand fonts + icon set** → swap out the substitutions (biggest fidelity win).
2. **Live data propagation** — make new members/tasks flow into all precomputed views.
3. **Persistence** — wire seed state to localStorage so demos survive reload.
4. **Add starting points** — none are marked yet; tag the app shell + key components so consuming projects can seed from them.
5. **Confirm the 6-status + 8-role labels** against current production copy (EN + МК).

---

## 10. Open asks for the client

> **Please help us make this perfect:**
> 1. Send the **real logotype/brand font files** (currently Poppins) and the **product typefaces** (currently Saira/Orbitron/Rajdhani).
> 2. Confirm whether the **Lucide icon substitution** is acceptable, or provide the original icon assets.
> 3. Tell us which of the **richer screens** (QC Lab, Governance) should be trimmed to match production vs. kept as forward-looking proposals.
> 4. Flag any **color or terminology** that's drifted from the current live app.

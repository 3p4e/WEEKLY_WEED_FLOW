# GrowFlow Design System

A green-hero design system for **GrowFlow** (internal name **WWF — Weekly Weed Flow**), the weekly, department-based operations task tracker built by **Purely Plant GmbH**, a licensed medical-cannabis production facility in North Macedonia.

This system is a **redesign foundation**: it keeps GrowFlow's information architecture, feature set, brand, and bilingual (English / Македонски) support, and rebuilds the *visual* language into one confident, premium, calm operations product with the **Purely Plant green as the hero** and a real **dark "control-room" theme**.

> Live app (reference): https://wwf.srv1231216.hstgr.cloud

---

## Sources used to build this

Everything here was derived from the materials the client provided. If you have access, explore them to design with higher fidelity:

- **UI design handover archive** (mounted codebase): `WWF_DES/WWF-UI-Design-Handover/`
  - `docs/01-DESIGN-BRIEF.md` … `docs/07-API-DATA-MODEL.md` — product, IA, current design system, screens, roles, bilingual copy, data model.
  - `design-tokens.json` — the current (light-only) tokens, used as the baseline.
  - `current-frontend/web/` — the live vanilla HTML/CSS/JS app (`gf/app.css`, `brand.css`, `core.js`, `data.js`) — the ground-truth for exact values, the icon set, and the animated leaf.
  - `screenshots/` — live renders of the running app.
- **GitHub repo:** https://github.com/3p4e/WEEKLY_WEED_FLOW — the app source; browse it for deeper fidelity when building real screens.
- **Brand assets:** `assets/PP_Leaf_3D.glb` (3D leaf model), `assets/pp-leaf-3d.obj` (OBJ mesh), `assets/pp-leaf.svg`, `assets/pp-wordmark.png`, plus uploaded variants (Borg, Romulan, Discovery surface textures).

---

## What this redesign changes (vs. the current app)

- **One system, green as hero.** The old app had two competing identities (blue/orange chrome + green brand). Here the Purely Plant green is the primary action/brand color; blue/orange/red/amber/violet are demoted to disciplined *functional* accents (status, priority).
- **A crafted task card** — the single most important component, redesigned to scan status, priority, owner, department, due date, and time at a glance and expand in place.
- **A real dark control-room theme** (`[data-theme="dark"]`) in addition to light.
- **Normalized spacing** on a 4px scale (the old app was hand-tuned: 7/9/11/13/14px).
- **Raised muted-text contrast** and a consistent green focus ring for accessibility.

---

## Content fundamentals (voice & copy)

- **Bilingual, always.** Every visible string exists in **English and Macedonian (Cyrillic)**. Macedonian runs **\~15–30% longer** — layouts, buttons, chips, and nav must flex and **never truncate** role/department names. Components accept a `lang` prop where labels differ.
- **Register: serious, calm, precise, trustworthy.** This is a regulated (GMP-adjacent) facility tool, not a consumer app. Copy is plain and operational: "Add a task — or speak it", "Request handoff", "View only", "No tasks here yet." Never playful, never cutesy.
- **Casing.** Sentence case for actions and body ("New task", "Log work"). UPPERCASE only for small eyebrow labels (11px, tracked +0.04em): "PROGRESS NOTES", "OWNER", "DEPENDENCIES".
- **Person / voice.** Neutral and direct — the UI addresses tasks and the facility, not "you"/"I". Section labels are nouns ("Blockers", "Workload").
- **Numbers & codes** are shown in mono (Geist Mono): task ids (`T-4KZ9`), document reference codes (`PP-QC-012`), dates, hours, counts.
- **Emoji:** effectively **not used** in chrome. The one idiomatic exception carried from the source is a celebratory "None 🎉" on an all-clear blockers state — optional. Prefer the Lucide icon set instead.
- **Domain vocabulary:** departments, RACI (Accountable owner + Responsible helpers), the 6-status lifecycle (Not started → Working on it → In review → Stuck → Postponed → Done), task types (CAPA/SOP/Validation/Document/Lab/Meeting/Admin/Other), work-session classes (regular/overtime/night/weekend). "Administrator" is a system role and **never** appears in a role picker.

---

## Visual foundations

- **Color.** Green-hero. `--primary` = `#15A86B` (`--green-500`), brightened to `#22C07E` in dark. Leaf art gradient `#5BBA47 → #8DC73F`; the "Flow" wordmark gradient `#5BBA47 → #15A86B`. Neutrals are a **cool navy** family (`--ink #16233B` … muted `--ink-3`), surfaces are clean cool-whites (`--surface #FFF`, canvas `--bg #EEF2F7`). Functional accents: blue (review), orange (working / voice CTA), red (stuck/overdue), amber (postponed), violet (task type). Every accent has a `-soft` tint for backgrounds and a `-700` for text-on-tint.
- **Type.** App font **Saira** (400–800, body/UI); display font **Orbitron** (headings/titles); label font **Rajdhani** (small all-caps metadata); brand font **Poppins** (the GrowFlow wordmark + PURELYPLANT sub-caps); mono **Geist Mono** (ids, codes, dates). Comfortaa is self-hosted as a legacy fallback. Base 15px.
- **Spacing & layout.** 4px scale (`--sp-1`…`--sp-10`). Header 64px, sidebar 250px, content padding 24px, mobile breakpoint 880px.
- **Radius.** Tags 6px, buttons/inputs 8px, fields/nested 12px, task card 14px, panels 18px, modals 22px, pills/avatars full. Cards are **soft-cornered, lightly bordered, low-shadow** — never heavy.
- **Elevation.** A restrained 3-step navy-tinted shadow ramp (`--sh-1` rest → `--sh-2` hover → `--sh-3` modals) plus a green `--sh-brand` glow reserved for the primary button. Dark theme swaps to deeper black shadows.
- **Backgrounds.** Flat calm surfaces — **no decorative gradients** in chrome. The one sanctioned gradient moment is the **login/splash hero** (a dark radial with a green cast) and the brand leaf's aura. The cross-department **handoff banner** uses a subtle blue→orange tint.
- **Borders & focus.** 1px `--line` borders; status is expressed as a **4px colored left-bar** on the task card. Focus = green ring (`--sh-focus`, `0 0 0 3px` soft green).
- **Hover / press.** Hover darkens/tints subtly (buttons → `-hover`/`-700`, ghost/rows → `--surface-2`). Press = slight scale on buttons; no bounce. Motion is restrained and honors `prefers-reduced-motion`.
- **Motion.** Micro (0.12s), UI (0.18s), panel/drawer (0.28s), eased with `--ease-out`. The **animated leaf** (aura pulse + float/breathe + masked light-sweep shimmer) is the one signature brand flourish — reserve it for hero moments (login, splash) and disable under reduced motion.
- **Imagery vibe.** Warm, living-green plant photography would sit well against the cool-navy neutrals; keep it calm and premium, not clinical or stock-y. (No generic imagery ships in this kit — add real facility photography as needed.)

---

## Iconography

- The current app ships a **custom inline-SVG icon set** (`core.js` `GF.ICONS`) — 20×20 viewBox, **1.8px stroke**, round caps/joins, feather/Lucide-flavored (search, bell, plus, mic, leaf, grid, timeline, chat, settings, sun, drop, box, shield, wrench, flask, sparkle, calendar, trend, trash, etc.).
- **This system uses [Lucide](https://lucide.dev) (CDN) as its icon set** — the closest match to the source's stroke weight and geometry. Components accept icons as **React nodes**, so pass any Lucide (or inline-SVG) glyph: `icon={<Plus/>}`. Cards load `https://unpkg.com/lucide@0.460.0`.
  - **⚠️ Substitution flagged:** Lucide stands in for the app's hand-authored `GF.ICONS`. If you want pixel-exact parity, lift the paths from `WWF_DES/.../gf/core.js` instead. Please confirm whether Lucide is acceptable or provide the icon font/sprite you want standardized.
- **Brand marks** use the **3D animated leaf** (WebGL/Three.js from `assets/pp-leaf-3d.obj`) and the PURELYPLANT wordmark PNG. The `<Leaf>` component renders the extruded CSS fallback; the app's `LeafMark` renders the real 3D mesh with plasma-green material. The old bitmap `.pp-logo` classes have been removed — use the `<GrowFlowLockup>` React component instead.

---

## Components

Reusable primitives (compiled to `window.GrowFlowDesignSystem_7accb1`). The set mirrors the source app's component inventory — nothing invented beyond it.

**Brand** (`components/brand/`)

- **Leaf** — Purely Plant leaf mark, static or the signature animated 3D version (WebGL/Three.js).
- **GrowFlowLockup** — "GrowFlow" wordmark (green "Flow") + Purely Plant sub-caps. Defaults to `onDark=true` (white text) for the dark theme.
- **Warbird** — heraldic imperial crest (swept double-chevron raptor + plasma core); `solid` / `line` / `ghost` variants. Legacy decorative mark from the Romulan-console reskin.

**Core** (`components/core/`)

- **Button** — primary (green hero), orange (New/Voice CTAs), secondary, ghost, danger.
- **IconButton** — square icon-only action with optional count badge.
- **Avatar** / **AvatarStack** — initials avatars + overlapping RACI stack.
- **Badge** / **Chip** — semantic pill labels + selectable option chips.

**Forms** (`components/forms/`)

- **Field**, **Input**, **Textarea**, **Select** — labeled controls with the green focus ring.
- **Checkbox**, **Switch**, **Segmented** — toggles + the EN|МК segmented control.

**Task** (`components/task/`)

- **StatusPill**, **PriorityTag**, **DueBadge**, **TypeChip**, **RefCode** — the task meta vocabulary (exports `STATUS` with EN+МК labels/colors).
- **TaskCard** — the crafted, expandable task card (the heart of My Week).

**Data** (`components/data/`)

- **KpiTile**, **BarRow** — calm dashboard data-viz.

**Nav** (`components/nav/`)

- **NavItem**, **DeptRow**, **DayPill** — sidebar nav, department rows, week-strip pills.

**Feedback** (`components/feedback/`)

- **Modal** (with a dark voice-capture variant), **Toast**.

Each component directory has a `<Name>.jsx`, `<Name>.d.ts` (props contract), `<Name>.prompt.md` (usage), and a `*.card.html` specimen shown in the Design System tab.

---

## UI kit

- **`ui_kits/growflow/`** — a fully interactive recreation of the GrowFlow app on the real 11-department / 8-role model: **login (+ forgot-password) → My Week (permission-gated task cards with handoff row + Edit/Advance/Delete) → Board (drag-and-drop kanban) → Dashboard → Timeline → Coordination → Team (→ user modal) → Report/Plan → Audit → Import → Settings (role switcher + permissions grid)**, plus **Add/Edit**, **Worklog** and **voice-capture** modals, an **Assistant** slide-over, a live **EN ⇄ МК** toggle and a **light / dark** theme switch. Everything is inlined in `ui_kits/growflow/index.html` (React + Babel; a Tweaks panel drives Softness / Brand accent / Tempo).
- **`templates/growflow/`** — a Design Component (`GrowFlow.dc.html`) that packages the app shell (sidebar + header + My Week) from the design-system components as a reusable **template** starting point for consuming projects.

---

## Foundations (Design System tab cards)

`guidelines/` holds specimen cards grouped as **Colors** (brand ramp, leaf gradient, neutrals, status, priority/accents, dark theme), **Type** (scale, families, labels), **Spacing** (scale, radius & elevation), and **Brand** (lockups).

---

## Files at a glance

- `styles.css` — global entry (import list only).
- `tokens/` — `colors.css`, `typography.css`, `layout.css` (spacing/radius/elevation/motion), `base.css`.
- `brand.css` — leaf/wordmark/lockup assets + the animated leaf.
- `assets/` — brand bitmaps + PWA icons.
- `components/` — reusable primitives (see above).
- `ui_kits/growflow/` — the interactive app recreation (all screens inlined in `index.html`).
- `templates/growflow/` — reusable app-shell template (`GrowFlow.dc.html` + `ds-base.js`).
- `guidelines/` — foundation specimen cards.
- `SKILL.md` — makes this usable as a downloadable Agent Skill.

## Caveats / open questions

- **Icons:** Lucide is substituted for the app's custom `GF.ICONS` set (flagged above).
- **Fonts** load from Google Fonts (Saira, Orbitron, Rajdhani, Poppins, Geist Mono). **Poppins substitutes for the real PURELYPLANT logotype font** (nearest geometric-sans match — flag for the user; supply the real font file for production). Self-host all families for CSP/offline if the production PWA requires it.
- The GrowFlow UI kit is a **fully interactive** recreation on the real 11-department / 8-role model: login (+ forgot-password), My Week (permission-gated task cards with handoff row + Edit/Advance/Delete actions), Board (drag-and-drop), Dashboard, Timeline, Coordination, Team (→ user modal), Report/Plan (status band + activity band + dept breakdown + AI insights), Audit trail, Import, Settings (role switcher + permissions grid), plus Add/Edit, Worklog and Voice modals and an Assistant slide-over. A `templates/growflow/` DC packages the app shell as a reusable starting point.y.

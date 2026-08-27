# WWF — Project Handoff (for a new chat)

**Prepared:** 2026-07-21 · **Project:** WWF · **Environment:** this is a *design-system* project (a `_ds_manifest.json` lives at the root and a compiler regenerates `_ds_bundle.js` / `_ds_manifest.json` / `_adherence.oxlintrc.json` every turn — **never hand-edit those three**).

> **Paste this whole file into the new chat.** It is self-contained: it tells the next agent what the product is, what has been built, where every file lives, the exact MASS WEED token map, the decisions locked so far, and the environment rules that keep the design system valid.

---

## 0. TL;DR — read this first

- The product is **WEEKLY_WEED_FLOW** (internal: **WWF**; app brand **GrowFlow**; sometimes **SUMA**): a **weekly, department-based task-tracking & reporting** web app for **Purely Plant GmbH**, a licensed medical-cannabis producer in **North Macedonia**.
- It is **bilingual — English + Macedonian (Cyrillic), always** — and ships **light + dark** themes.
- **Scope rule (hard):** WWF is an *informational planning/management* tool — it produces **no GMP/QMS records**. Never design certificates, batch records, or official QMS forms. Weekly exports carry a bilingual "not a GMP/QMS record" disclaimer.
- **Two visual systems coexist in this project for the same app.** The **active thread** is **MASS WEED** — a *Mass Effect*-inspired sci-fi HUD reskin. The earlier **GrowFlow green-hero** system is the compiled DS at the project root and is still valid, just not what we're actively iterating.
- **The MASS WEED deliverable is a drop-in reskin** that keeps the real repo's exact CSS token names and only changes their **values**, so it reskins the whole app with zero markup changes.

---

## 1. The real app (ground truth)

- **GitHub:** https://github.com/3p4e/WEEKLY_WEED_FLOW (branch `main`). Newer front-end lives under **`web-next/src/design/`** (token files: `tokens/colors.css`, `tokens/typography.css`, `tokens/layout.css`, `base.css`, `brand.css`, entry `styles.css`). An older vanilla build lives under `web/gf/*`.
- **Live reference:** https://wwf.srv1231216.hstgr.cloud
- **Authoritative brief in-project:** `docs/UI-DESIGN-BRIEF-2026-07.md` (also pasted into the history) + `docs/SPEC.md`. Read the brief before designing any new surface — it defines component anatomy (task card, chips, pills, nav), the 5 "new surfaces," and the CSP/bilingual/theme constraints.

### 1.1 Information architecture

**7 departments** (code → EN / МК · abbr · icon). MASS WEED retunes each dept hue to sit against the cyan HUD:

| code | EN / МК | abbr | MASS WEED `--dept-*` |
|---|---|---|---|
| cultivation | Cultivation / Одгледување | CU | `#2be8a0` |
| production | Production / Производство | PR | `#2fd9d9` |
| qc | Quality Control / Контрола на квалитет | QC | `#a07bf0` |
| quality_assurance | Quality Assurance / Обезбедување квалитет | QA | `#f0803e` |
| logistics | Warehouse / Магацин | WH | `#35b6e0` |
| security | Security / Обезбедување | SE | `#8296b4` |
| tooling | Maintenance / Одржување | MU | `#9fb0c8` |

Cross-department **handoff pipeline:** cultivation → production → qc → quality_assurance → logistics.

*(Note: the older green-hero UI kit was built against an expanded **11-department / 8-role** interpretation. The brief and MASS WEED use the canonical **7**. If asked to reconcile, the brief's 7 wins.)*

- **Roles:** OWNER / CEO / COO (org-wide overview + full drill-down), QP (org-wide read, certifies), department managers (`*_MGR` — own board, compile+lock their weekly doc), USER (own week — fast, mobile-first), ADMIN (provisioning; not a design target — never appears in a role picker).
- **6-status lifecycle:** pending → working → review → stuck → postponed → done.
- **Task types:** Routine / Project / Incident (brief); older kit also used CAPA/SOP/Validation/Document/Lab/Meeting/Admin/Other.
- **Task attributes** (per-dept metadata → shown as card chips): room, strain, plant_count, batch_ref, sample_ref, equipment_ref, area, …
- **Subtasks:** **unlimited nesting** (theme → document → version → …). This was an explicit user directive — do **not** cap the depth.

---

## 2. What's been built (two systems)

### A. GrowFlow green-hero design system — project root (compiled DS)

The original redesign. Green (`--primary #15A86B`, brightened `#22C07E` in dark) as hero, cool-navy neutrals. This is the **compiled component library** — namespace **`GrowFlowDesignSystem_7accb1`**.

- `styles.css` (import-only entry) → `tokens/` (`colors.css`, `typography.css`, `layout.css`, `base.css`) · `brand.css`
- `components/` — 29 React components in 7 groups (brand / core / forms / task / data / nav / feedback); each dir has `<Name>.jsx` + `.d.ts` + `.prompt.md` + a `@dsCard` specimen.
- `guidelines/` — foundation specimen cards (Colors / Type / Spacing / Brand).
- `ui_kits/growflow/` — a **fully interactive** app recreation (login → My Week → Board → Dashboard → Timeline → Coordination → Team → Report → Settings, etc.; React+Babel, EN⇄МК, light/dark, Tweaks panel).
- `templates/growflow/` — a reusable app-shell Design Component (`GrowFlow.dc.html` + `ds-base.js`).
- Docs: **`readme.md`** (the design guide — recently **user-edited**, do not revert), **`HANDOFF.md`** (green-hero handoff), `SKILL.md`.
- **Brand:** the Purely Plant **3D leaf** (`assets/PP_Leaf_3D.glb` / `assets/pp-leaf-3d.obj`) rendered in WebGL/Three.js with a plasma-green material — spin-burst on splash, escalating spin on repeated clicks, 3+ rapid clicks → wormhole implode/re-emerge, random idle motion. CSS extruded-leaf fallback when WebGL is unavailable. Standalone leaf demos: `Leaf 3D Showcase.html`, `Leaf 3D Interactive.html`.
- **Note:** the root DS still carries a **"Tal Shiar" (Romulan-console)** reskin lineage in its layout/effects tokens (angular clips, scanlines). MASS WEED supersedes that direction.

### B. MASS WEED (Mass Effect HUD) reskin — **the active work**

A galaxy-map command-console identity: **Omni-cyan hero**, hull-blue gunmetal surfaces, warning-brass + sentinel-red accents, chamfered corners, scanline/HUD-grid textures, edge-sweep/plasma-pulse motion. Two folders:

**`wwf-mass-weed/` — the drop-in deliverable + the canvas**
- `design/` **mirrors the repo's `web-next/src/design/` file-for-file.** Install = `cp -r design/* web-next/src/design/`. Files: `styles.css` (entry), `tokens/colors.css`, `tokens/typography.css`, `tokens/layout.css`, `base.css`, `brand.css`, plus `mass-weed-components.css` (a `.mw-*` HUD component layer for NEW surfaces). It keeps **every real token name** (`--primary`, `--surface`, `--st-*`, `--dept-*`, `--av-*`) and brand class (`.pp-leaf`, `.gf-wordmark`) — only values change.
- `wwf-skin.css` — the single-file predecessor of the `design/` folder (token map + `.mw-*` layer). The canvas links this one.
- `design/README.md` — install + per-file "what changed" notes.
- **`design-system.html`** — a **pannable canvas** (`<meta name="design_doc_mode" content="canvas">`) presenting the whole system with a fixed **Dark/Light + EN|МК** control bar. See §4 for the frame inventory.

**`mass-weed/` — the original standalone ME kit** (~40 hand-built HTML screens + `mass-weed.css` + helper JS `mw-leaf.js`, `mw-i18n.js`, `nav.js`, `cmdk.js`, `data.js`). Screens include: `login`, `splash`, `board`, `board-tree`, `my-day`, `depthome`, `execreport`, `dashboard`, `reports`, `report-standalone`, `task-detail`, `af-modal`, `team`, `settings`, `workload`, `calendar`, `orders`, `order-detail`, `notifications`, `search`, `analytics`, `approvals`, `automations`, `rule-builder`, `ui-elements`, plus cultivation-flavored extras (`batch`, `cure`, `harvest`, `genetics`, `environment`, `nutrients`, `packaging`, `facility`, `sop`, `compliance`, `decrypt`). Treat these as the richer design reference; `wwf-mass-weed/` is the clean, repo-aligned source of truth for tokens.

---

## 3. MASS WEED token map (exact values)

`:root` = command deck (dark-primary). `[data-theme="dark"]` deepens surfaces; `[data-theme="light"]` = "Cool-Mist Glass" daylight. Token **names are the repo's** — only values differ.

**Hero (Omni-cyan, remaps the green ramp):** `--green-500 #5ec8f0` = `--primary`; `--primary-hover #8fe3ff` (dark `#a8e4fb`); `--accent-rgb 94,200,240`; leaf gradient `--leaf-from #8fe3ff → --leaf-to #1c6ca3`, highlight `--leaf-lime #a8e4fb`.

**Surfaces (`:root`):** `--bg #0c1a2e` · `--surface #14283f` · `--surface-2 #1a3252` · `--surface-3 #22456b`. **`[data-theme="dark"]` deepens to:** `--bg #0a1626` · `--surface #122336` · `--surface-2 #182d49` · `--surface-3 #204060`.
> ⚠️ **Recent user directive (done):** the dark background was lightened from near-black `#050b18` to the mid gunmetal `#0c1a2e` / `#0a1626` above. Don't take it back toward black.

**Ink:** `--ink #eaf6ff` · `--ink-2 #9dc0d8` · `--ink-3 #6a8aa4` · `--ink-4 #47657c`. Aliases: `--text-strong/-body/-muted/-faint`, `--text-on-brand #041018`.

**Semantic accents:** `--blue #5ec8f0` · `--orange #f0b95e` (warning brass) · `--red #ef4d4d` (sentinel) · `--amber #ecec4a` · `--violet #c89bf0` (biotic) · `--teal #6cf05a`. Each has `-700` + `-soft`.

**Status:** working→orange, review→blue, stuck→red, postponed→amber, done→teal, pending→ink-3 (each `--st-*` + `--st-*-soft`). **Priority:** critical→red, high→orange, medium→blue, low→ink-3.

**Borders/glass:** `--line rgba(94,200,240,.16)` · `--border-strong rgba(94,200,240,.34)` (dark `.4`) · `--glass-bg rgba(9,28,52,.72)` · `--focus-ring rgba(accent,.5)`.

**Light theme** swaps hero to `--primary #1a86c4` (`--accent-rgb 26,134,196`), surfaces to cool whites (`--bg #e8f2f8` · `--surface #f6fbfe`), ink to `#0a2740`…`#8aa6ba`, and darkens every accent for AA on light.

**Type (`typography.css`):** Titillium Web (body/UI) · Saira Condensed (display/titles) · Orbitron (numeric telemetry, sparingly) · Geist Mono (codes/ids/dates/hours). Google Fonts; Comfortaa self-hosted for the Cyrillic brand fallback. **Verify Cyrillic coverage on any new face.**

**Layout (`layout.css`):** chamfered corner clips (`--clip-panel` / `--clip-bevel` / `--clip-chevron`), Omni-glow elevation ramp, scanline + HUD-grid textures. Header 64px, sidebar 252px.

---

## 4. The canvas — `wwf-mass-weed/design-system.html`

Pannable (host provides pan/zoom). Fixed control bar toggles theme + language for the whole page. Three bands:

- **Band A · Design System:** A1 Cover · A2 Color System (surfaces/ink, primary/accents, status, priority) · A3 Typography · A4 Effects/primitives (panels, wells, elevation, radius).
- **Band B · Components:** B1 Buttons/Segmented/Toggle · B2 Task-card atom + meta chips · B3 Inputs/fields · B4 Dialog + menu + alerts · B5 Departments.
- **Band C · Screen Gallery (real SUMA views in ME skin):** C1 Login/Splash · C2 My Week (full shell) · C3 Board (kanban) · C4 Department Home (Cultivation-branded) · C5 Executive Report · C6 Dashboard/Exec Overview · C7 Documents Workbench · **C8 New Task modal** · **C9 Log Progress popup**.

**C8/C9 are the most recently refined frames** and encode a key rule (see §5): **no native `<select>` dropdowns** — every choice (department, type, priority, status, day, progress, hours) is a **multi-choice chamfered chip/button group**. C8 has a 7-dept picker that live-swaps the modal accent and re-renders per-dept field blocks (CU/PR/QC + a generic fallback) with a live attribute-chip preview, an **unlimited-nesting** subtask tree with dept-colored rails, a handoff pipeline, tags, and a Cancel / Save draft / Create footer. C9 (Log Progress) reveals a red blocker field when "Stuck" is chosen and has quick-set progress (25/50/75/100) + hours quick-add. The chips are wired with a small vanilla JS delegator at the bottom of the file — extend that pattern, don't add inline handlers.

---

## 5. Decisions locked in this thread (honor these)

1. **MASS WEED must genuinely read as Mass Effect** — angular chamfers, cyan HUD glow, scanlines, telemetry numerals. A flat/rounded pass was rejected.
2. **Drop-in, not a rewrite:** keep the repo's exact token names + brand classes; change only values; mirror `web-next/src/design/` file-for-file.
3. **Dark background lightened** to gunmetal `#0c1a2e` / `#0a1626` (never back to near-black).
4. **No native dropdowns anywhere** — replace every `<select>` with themed multi-choice button/chip popups covering all feasible choices.
5. **Unlimited subtask nesting** — never fix the depth.
6. **Task-creation + progress-logging UI matters** — full New Task modal + Log Progress popup exist on the canvas (C8/C9); keep them as the interaction model.
7. **Bilingual everywhere**, both themes always, and the **non-GMP** scope disclaimer on reports.
8. On text-color rule carried from earlier: text is white on dark; only in **light theme** may surfaces be light, and then annotated text is dark/black.

---

## 6. Environment rules the next agent MUST follow

This is a **design-system project**, so the tooling is specific:

- **Never write** `_ds_bundle.js`, `_ds_manifest.json`, `_adherence.oxlintrc.json` — the compiler owns them. After any change, run **`check_design_system`** and fix what it reports until clean.
- **Global CSS** the compiler reads = root `styles.css` + its `@import` closure. Components = any `<Name>.d.ts` with a sibling `.jsx`/`.tsx`. `@dsCard` HTML comments (first line of a file) populate the **Design System tab**; `@template` comments under `templates/<slug>/` populate the **Templates** picker.
- **Reusable templates/decks must be Design Components** (`.dc.html` via **`dc_write`**), not plain HTML — a DC body is click-editable markup that can `<x-import>` this DS's compiled components. Put template files under `templates/<slug>/` with `<Slug>.dc.html` (PascalCase) and `<!-- @template … -->` as line 1; a sibling `ds-base.js` loads the bundle.
- **Design-component styling is inline only** (no class stylesheets inside a DC); `<helmet>` at the top for fonts/@font-face/@keyframes/scripts.
- **`thumbnail.html`** at the root is the homepage tile (renders ~72×48) — brand mark on the primary color + a value-ordered swatch strip; do **not** load the bundle there. It's already written (GrowFlow wordmark, green). If MASS WEED becomes the primary identity, update it to the cyan palette.
- The MASS WEED canvas is **plain HTML with `design_doc_mode=canvas`**, linking `wwf-skin.css` directly — it is *not* a compiled part of the DS (it's a reference artifact), which is fine.
- **CSP for production drop-in:** `default-src 'self'`; styles/scripts self+inline; images self + `data:`/`blob:`; fonts self + Google Fonts only. No CDN icons, no remote images. Icons are an inline SVG set. The standalone report (brief §3.4) must be **zero-JS** (`<details>/<summary>` only) and use a **system font stack** (no webfont fetch).

---

## 7. Open questions / likely next steps

- **Which system is canonical going forward?** If MASS WEED wins, decide whether to (a) keep both, (b) fold MASS WEED values into the root compiled DS so `GrowFlowDesignSystem_7accb1` ships the ME look, and update `thumbnail.html` + `readme.md`/`HANDOFF.md` accordingly.
- **The 5 brief surfaces** (Department Home, dept fields + attribute chips, Executive Report, standalone zero-JS HTML report, board tree rows): C4/C5/C7 + C8 exist on the canvas as ME frames; the **standalone offline report** (§3.4) still needs a dedicated zero-JS, system-font, print-safe artifact.
- **Fonts/icons are substitutions** — get the real PURELYPLANT logotype font + the app's hand-authored icon set for pixel parity; self-host all faces for the PWA/CSP.
- **Reconcile 7 vs 11 departments** and confirm current EN/МК labels + 6-status/role copy against production.
- **Integrate the drop-in** into the repo (`web-next/src/design/`) and smoke-test both themes + Cyrillic strings (МК runs ~20–30% longer — nothing may truncate).

---

## 8. Fast file map

```
/                          GrowFlow green-hero DS (compiled) — namespace GrowFlowDesignSystem_7accb1
├── styles.css  brand.css  tokens/  components/  guidelines/
├── ui_kits/growflow/      interactive app recreation
├── templates/growflow/    app-shell Design Component
├── readme.md HANDOFF.md SKILL.md   (green-hero docs; readme user-edited)
├── thumbnail.html         homepage tile
├── assets/                3D leaf (glb/obj), logos, PWA icons
├── Leaf 3D Showcase.html · Leaf 3D Interactive.html   leaf demos
│
├── mass-weed/             ★ standalone MASS WEED kit — ~40 HTML screens + mass-weed.css + helper JS
│
├── wwf-mass-weed/         ★ MASS WEED drop-in + canvas  (ACTIVE)
│   ├── design/            mirrors repo web-next/src/design/ (styles.css, tokens/*, base.css, brand.css, mass-weed-components.css)
│   ├── design/README.md   install + per-file change notes
│   ├── wwf-skin.css        single-file token map + .mw-* layer (canvas links this)
│   └── design-system.html  pannable canvas: spec + components + screen gallery (C8/C9 = task create + log progress)
│
├── docs/                  UI-DESIGN-BRIEF-2026-07.md, SPEC.md (product ground truth)
├── design_handoff_growflow/   earlier handoff bundle
└── _ds_bundle.js _ds_manifest.json _adherence.oxlintrc.json   ← compiler-owned, never edit
```

**Repo to mirror:** https://github.com/3p4e/WEEKLY_WEED_FLOW → `web-next/src/design/`.

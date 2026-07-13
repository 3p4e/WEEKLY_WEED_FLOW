# GrowFlow / WEEKLY_WEED_FLOW — UI Design Brief

**Audience:** a designer (human or AI) producing beautiful, production-ready
HTML/CSS mockups for five new surfaces, plus optional polish of existing ones.
**This document is self-contained** — everything needed (product context,
design tokens, component anatomy, constraints, deliverable format) is here.

---

## 1. Product one-pager

**GrowFlow** is the web UI of WEEKLY_WEED_FLOW: a weekly task-planning and
reporting tool for **Purely Plant**, a licensed medical-cannabis producer in
North Macedonia. Teams plan tasks per ISO week, log work sessions and progress
notes, hand off work across departments, and compile weekly **Plan** and
**Report** documents that roll up to the owner.

**Important scope rule:** the app produces **no GMP/QMS records** — real
quality records are hard-copy. Everything here is *informational* planning and
management reporting. Weekly report exports carry a bilingual disclaimer to
that effect. Don't design anything that looks like a certificate, batch
record, or official QMS form.

**Bilingual, always:** every label exists in **English and Macedonian
(Cyrillic)** — `EN | МК` toggle in the header. Designs must tolerate Cyrillic
strings ~20–30% longer than English. Buttons, chips, and column headers must
not truncate Macedonian labels.

**Personas / roles:**

| Persona | Role codes | What they need |
|---|---|---|
| Owner + executives | OWNER, CEO, COO | Org-wide overview; the weekly report with drill-down to any task, note, and logged hour ("100% of the data upon his own wish") |
| Qualified Person | QP | Org-wide read, certifies across departments |
| Department managers | CU/PR/QC/QA/WH/SE/MU_MGR | Their department's board, compile + lock their department's weekly document |
| Operators (staff) | USER | Their own week: tasks, notes, work logging — fast, mobile-friendly |
| System admin | ADMIN | Provisioning; not a design target |

**The 7 departments** (code → EN / МК, brand color, abbreviation, icon):

| code | EN | МК | color | abbr | icon |
|---|---|---|---|---|---|
| cultivation | Cultivation | Одгледување | `#2BE8A0` | CU | leaf |
| production | Production | Производство | `#2FD9D9` | PR | box |
| qc | Quality Control | Контрола на квалитет | `#7A5BE0` | QC | flask |
| quality_assurance | Quality Assurance | Обезбедување квалитет | `#C2410C` | QA | shield |
| logistics | Warehouse | Магацин | `#0891B2` | WH | box |
| security | Security | Обезбедување | `#566884` | SE | shield |
| tooling | Maintenance | Одржување | `#5A6B82` | MU | wrench |

Cross-department handoff pipeline (a task can "hand off" to the next dept):
cultivation → production → qc → quality_assurance → logistics.

---

## 2. The design system as implemented (do not reinvent — extend)

The shell is a **dark glass-morphism** system ("plasma green on green-charcoal
glass"), with a complete light-theme override ("Cool Mist Glass") switched via
`<html data-theme="light">`. All styling reads CSS custom properties, so a new
surface that uses the tokens below is automatically theme-correct.

### 2.1 Core tokens (dark default)

```css
/* Surfaces (green-charcoal, elevated glass) */
--bg:#0E1F17; --surface:#163025; --surface-2:#1E3B2D; --surface-3:#274A38;
--overlay:rgba(7,18,13,.74);

/* Ink */
--ink:#E9F6EF; --ink-2:#A2C4B5; --ink-3:#6E9384; --ink-4:#557568;

/* Primary accent: plasma green. --accent-rgb recolours the whole shell. */
--accent-rgb:43,232,160; --primary:#2BE8A0; --primary-hover:#4CF2B3;
--primary-soft:rgba(var(--accent-rgb),.13); --text-on-primary:#03130C;

/* Secondary accents */
--blue:#2FD9D9 (plasma teal)  --orange:#E0A73E (bronze)
--red:#FF4D5E  --amber:#C79A54  --violet:#9B7BE8  --teal:#2FD9D9
/* each with a -soft rgba(…,.15–.18) tint for chip/badge backgrounds */

/* Glass */
--glass-bg:rgba(11,25,19,.72); --glass-border:rgba(var(--accent-rgb),.12);
--glass-blur:blur(18px);

/* Borders */ --line:rgba(var(--accent-rgb),.16); --border-strong:#2F5A44;

/* Elevation (dark, glowy) */
--sh-1 … --sh-3 (rising drop shadows + inset accent hairline)
--sh-brand:0 0 26px rgba(var(--accent-rgb),.5), 0 2px 8px rgba(0,0,0,.6);
--focus-ring:rgba(var(--accent-rgb),.42);

/* Texture */ --scanlines: subtle repeating 1px horizontal darkening

/* Radii */ --r-sm:8px --r-md:12px --r-lg:14px --r-xl:18px
/* Spacing */ 4/8/12/16/20/24/32/40 (--sp-1…--sp-10)
/* Type scale */ 10/12/14/15/17/20/24/32 (--fs-xs…--fs-3xl)
/* Layout */ --header-h:64px --sidebar-w:252px
```

### 2.2 Typography

- `--font: 'Saira'` — body/UI.
- `--font-display: 'Orbitron'` — display numerals, hero stats, telemetry
  values (sci-fi flavor; use sparingly).
- `--font-brand: 'Poppins'/'Comfortaa'` — brand lockups only.
- `--mono: 'Geist Mono'` — codes, IDs, hours, dates.
- Loaded from Google Fonts (CSP explicitly allows `fonts.googleapis.com` +
  `fonts.gstatic.com`); Comfortaa is self-hosted woff2 with Cyrillic subsets.
  **Cyrillic coverage matters** — Saira covers Cyrillic; verify any new face.

### 2.3 Brand

Purely Plant leaf + wordmark assets (`.pp-leaf`, `.pp-wordmark`, sizes sm–xl).
The animated leaf `.pp-leaf-anim` (plasma aura, float, shimmer — with
`prefers-reduced-motion` fallback) is the hero on login/splash. Brand
gradient text `.pp-brand-text`: `linear-gradient(135deg,#2BE8A0,#2FD9D9,#E0A73E)`.
GrowFlow wordmark styling: "Grow" in ink, "Flow" in plasma green.

### 2.4 Shell anatomy

- **Header (64px):** brand, global search, language toggle `EN|МК`, theme
  toggle, voice-capture button, "New task" (permission-gated), user avatar.
- **Sidebar (252px):** nav items (icon + label + optional count badge);
  executives get an extra "Overview" item on top; below, the department list
  (color dot + bilingual name + weekly count); user card at bottom.
- **Week strip:** ‹ › week navigation, "Week N" + date-range label,
  "This week" badge, avatars of people active this week.
- **Day pills:** All / Mon–Fri with per-day counts.
- **Telemetry band (My Week only):** collapsible stat bar — completion %,
  totals, working/stuck/postponed counts — expanding to progress track +
  stat cards. Values use `--font-display`.
- **Panels:** current week + collapsible next-week panel, each a glass card
  (`--surface`, `--glass-border`, `--r-lg`) with a head row (title, count,
  actions) and a body of task cards, ending in a ghost "+ Add task" row.

### 2.5 Task card anatomy (the atom of the whole UI)

Collapsed row: status checkbox → title + meta line (dept abbr in dept color,
task id, reference code chip, type chip, due badge (red when overdue),
subtask progress `n/m`, logged hours, `#tag` chips) → right side: day tags,
avatar stack, status pill, priority tag, chevron.
Expanded: blocker banner (if stuck), description, **notes timeline**
(day label + text; notes by OWNER get a gold "owner" treatment, CEO/COO a
lighter executive accent — directives must never drown in ordinary notes),
note input with mic + AI paraphrase, handoff visual (dept badge → dept badge),
action row (Log work · Add subtask · Edit · AI paraphrase · progress track ·
Archive).

Status colors: done=green, working=orange, review=blue, stuck=red,
postponed=amber (`.pill.s-*`). Priority tags: low/normal/high/critical.
Avatars: initials on deterministic per-user color, 2px dark ring.

### 2.6 Existing views (for context; not to redesign)

My Week (panels above) · Board (kanban by status) · Timeline · Coordination
(handoffs) · Dashboard · Team · Executive Overview (execs only) · Weekly
Report view · **Documents workbench** (compile → per-section edit/approve →
lock → PDF export of weekly Plan/Report; sections: Cultivation Status,
Production Overview, Quality & GMP, Technical Status, Inventory & Logistics,
Site Security + org-wide Transition Plan and Production Forecast) · AI Intake
· Audit log · Settings modal. AI-generated content is always visibly labeled
with a disclaimer wrapper.

---

## 3. What to design — five new surfaces

These are being built now. Wireframe-level requirements below; you own the
visual design. Reuse the tokens/components; propose refinements freely, but
the task card, chips, pills, and nav must stay recognizably the same system.

### 3.1 Department Home screens (`depthome`)

A department-branded landing view for staff and managers — the first thing an
operator sees. Week strip stays visible (it is week-scoped).

- Header: department icon + bilingual name, tinted with the dept color
  (e.g., a soft `--primary-soft`-style wash of the dept color),週 context.
- A row of **preset chips** — one-tap task suggestions for that department's
  routine work (e.g. Cultivation: "Watering GR-2", "Defoliation", "IPM check").
- **Panels per department**, populated from that week's tasks:
  - Cultivation: tasks grouped **by room** + a "ready for handoff" rail
  - QC: lab/inspections **due** + **in review**
  - Maintenance: grouped **by equipment** + a "stuck/blocked" rail
  - Warehouse: **in / out** flow columns
  - Production: grouped **by batch**
  - QA: CAPA / SOP / document groups + review queue
  - Security: patrols / incidents
- Groups derive from new per-task **attributes** (room, strain, plant_count,
  sample_ref, equipment_ref, batch_ref, area, …). Cards inside groups are the
  standard task card (compact).
- Design a **generic fallback** layout (status columns) for a department
  without a template.
- Must look great **empty** (first Monday of a week): friendly bilingual
  empty state + the preset chips as the call to action.

### 3.2 Department fields in the Add/Edit task modal + attribute chips

- The Add-task modal gains a **department fields block** under the department
  select: 2–4 small labeled inputs (text / number / select) defined per
  department, bilingual labels (e.g. Room/Просторија, Strain/Сорта,
  Plant count/Број растенија). Re-renders when the department changes.
  Keep it visually light — these are optional metadata, not a form wall.
- Task cards then show **attribute chips** in the meta line: small
  `key: value` chips (e.g. `GR-2`, `Kalorist`, `120 pl`), styled like the
  existing tag chips but visually distinct (attribute = filled soft chip with
  mono value; tag = `#hash` outline chip). One dept accent per card max —
  don't rainbow the meta line.

### 3.3 Executive Report view (`execreport`) — the owner's cockpit

Read-only consumption surface over the weekly documents (managers author
elsewhere). Full-page view (no week strip; it has its own week/kind picker).

1. **Submission status board** — 7 department chips + 1 org-wide chip:
   `missing` (red) / `draft` (amber) / `locked` (green) with dept color
   accents; click focuses that department's section. This is the owner's
   at-a-glance "who has reported".
2. **Org KPI band** — on-time %, overdue count, total hours, complexity;
   large `--font-display` numerals, glass stat cards (mirror telemetry).
3. **Per-department sections** — collapsible (collapsed by default), header =
   dept badge + status + updated-at. Inside: the section's metric grid
   (read-only), bilingual narrative (EN/МК toggle honors the global language),
   AI-generated passages inside the standard AI-disclaimer wrapper.
4. **Task drill-down rows** — expandable rows inside a section: status pill,
   bilingual title, assignee avatars; expanded → progress notes **with author
   names**, per-task logged hours; owner/exec notes keep their gold treatment.
5. **Deep links** — every task row offers "Open in board" (jumps to that week
   + expands the card) and "Worklog" (raw sessions). Design the affordance
   (icon buttons on the row).
6. **Export actions** — "PDF" and "Interactive HTML" buttons in the view
   header.
   Handle gracefully: missing dept documents (ghost section with "not
   submitted" state), AI unbound (sections render without AI passages).

### 3.4 Standalone interactive HTML report (offline artifact)

A **single self-contained HTML file** the owner downloads and opens anywhere
(train, phone, no network, months later). **Zero JavaScript, zero network
fetches** — interactivity via `<details>/<summary>` only; all styles inline.

- Same information architecture as 3.3: title block (kind, week, org),
  KPI band, per-department `<details>` sections → per-task `<details>` →
  notes with authors; per-task effort ribbon (inline SVG, provided).
- Print-quality typography; **dark mode via `prefers-color-scheme`** (design
  both). Fonts: system stack only (it must not fetch webfonts) — pick
  elegant fallbacks that echo Saira's voice.
- Bilingual: EN and МК titles side by side (this artifact is not toggleable —
  both languages visible, EN primary, МК secondary styling).
- Prominent but tasteful bilingual disclaimer banner: *"Weekly informational
  summary for management — not a GMP/QMS record."*
- It should still look intentional when printed to paper (no glass effects —
  use borders and weight instead of blur/glow).

### 3.5 Board tree rows (theme → document → version)

Task cards can now have **children** (a "theme" of work contains documents,
documents contain versions/reworks). On the board:

- The subtask counter on a parent card becomes an **expand toggle**
  ("▸ 12 documents" / "▾"). Expanding reveals **indented child rows** under
  the card — compact single-line task rows (status dot, title, own date
  range, hour count, chevron to expand one more level for versions).
- Children may span other weeks than the parent — each child row shows its
  own `start → end` date range in `--mono`; make that scannable.
- Two indent levels max (theme → document → version). Use the dept color as
  a 2px left rail on the indent to tie children to the parent.
- Keep it calm: children are secondary information — lower contrast than
  full cards, no avatars unless different from parent.

---

## 4. Constraints (hard)

1. **CSP:** `default-src 'self'`; styles/scripts self + inline; images self +
   `data:`/`blob:`; fonts only self/Google Fonts. **No other external assets,
   no CDN icons, no remote images.** Icons are an inline SVG set (`GF.icon`)
   — new icons must be added to that set, not loaded remotely.
2. **No new inline event-handler patterns** beyond the existing codebase
   style; no `<script>` in mockups for the standalone report (3.4 is zero-JS).
3. **Vanilla JS + string templates** render everything — design components
   as HTML/CSS that can be produced by template literals (no framework
   assumptions, no CSS-in-JS).
4. **Both themes:** every design must work with the dark tokens and the light
   (`data-theme="light"`) overrides. Don't hardcode hexes where a token
   exists.
5. **Responsive:** sidebar collapses on mobile (existing `mobile.css`
   breakpoints); dept home and exec report must degrade to single column;
   the standalone report is fluid down to 360px.
6. **Accessibility:** WCAG AA contrast on ink/surface and chip fg/bg pairs
   (the light theme is already contrast-checked — keep it that way);
   `prefers-reduced-motion` honored for any animation; focus-visible rings
   via `--focus-ring`; `<details>/<summary>` keyboards for free in 3.4.
7. **Bilingual:** never design a component that only fits the English string.
8. **PWA:** the app is installable with a service-worker shell; avoid
   viewport-height tricks that break standalone mode.

---

## 5. Deliverable format

For each of the five surfaces, return:

1. A **static HTML file** (one per surface) using the token vocabulary from
   §2.1 (declare the `:root` block or link a shared `tokens.css` copy) with
   realistic bilingual content — use the departments, names and statuses from
   this brief (fictional people are fine; use `[TEST]`-style names).
2. Dark **and** light theme (`data-theme` attribute switch).
3. A short **design notes** block per file (as an HTML comment): what you
   changed/extended in the system, any new tokens you propose (name + value +
   rationale), interaction states covered (hover/focus/active/empty/error).
4. New CSS classes namespaced per surface (`.dh-*` dept home, `.xr-*` exec
   report, `.tree-*` board tree, `.af-*` attribute fields, standalone report
   scoped by its own file).

We will lift your markup/CSS into the codebase's template-literal renderers
— the closer your class structure is to the anatomy described in §2, the
faster it ships.

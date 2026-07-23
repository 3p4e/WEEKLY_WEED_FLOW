# GrowFlow — Frontend / UI Design Handover

**A complete, self-contained brief for redesigning the GrowFlow web application UI.**
Hand this document to Claude Design (or any UI/UX designer) as the single source of
truth. It covers every module, every screen, every data field, every state, the design
system, the bilingual requirement, and the GxP guardrails that constrain how records may
be presented. No access to the codebase is required to design from this document.

- **Document owner:** Purely Plant GmbH — engineering
- **Date:** 2026‑07‑23
- **App codename:** GrowFlow (a.k.a. Weekly Weed Flow / WWF)
- **Current shell version:** `wwf-shell-v3.71.0`
- **Platform:** installable PWA, vanilla‑JS (no framework, no build step), bilingual **English / Македонски**

---

## 0. How to use this document

1. **Read §1–§8 first.** They are global: product context, zones, roles, navigation,
   the design system, bilingual rules, and GxP UI guardrails. They apply to *every*
   screen and are not repeated per module.
2. **§9 is the module catalog.** Each module has a fixed sub‑structure:
   *Purpose · GxP zone · Personas · Screens & layout · Data fields · Actions · States ·
   Human IDs & lifecycle.* Design each module against its section.
3. **§10–§13 are references:** global UI patterns, the state catalog, the component
   library, and the human‑ID / enum reference tables.
4. Anything marked **🔒 GxP** is a regulatory constraint on presentation. It is not
   negotiable for aesthetic reasons — see §8 for why.
5. The app is **already fully built and functional** on this exact data model and API.
   This is a *re‑skin / redesign* brief, not a greenfield spec. Preserve behavior and
   information; you have latitude on layout, hierarchy, motion, and polish.

---

## 1. Product overview

GrowFlow is the operations + quality platform for **Purely Plant GmbH**, a licensed
**medical‑cannabis cultivation and production facility in North Macedonia** operating
under **EU‑GMP / MK‑GMP** expectations. One application serves three very different kinds
of work under one login:

1. **Operational task management** — the weekly rhythm of running a grow + production
   facility across departments (cultivation, production, QC, QA, warehouse, security,
   maintenance). This is the original heart of the app.
2. **QMS document authoring** — an AI‑assisted engine ("Document Studio") that drafts,
   formats and versions controlled SOPs and quality documents in house style.
3. **QC LIMS** — a full quality‑control laboratory information system: specifications,
   samples, certificates of analysis, out‑of‑specification investigations, chain of
   custody, stability, water and transport testing — the GMP records layer.

**Design tension to resolve:** these three worlds have very different tones. Operations
should feel fast, fluid, and encouraging. QC LIMS must feel exact, controlled, and
serious — a record you could hand to an inspector. The design system (Mass Weed HUD,
§6) already spans both; your job is to keep operations *inviting* without making the
regulated records feel *casual*. §8 governs the regulated side.

### Users, scale, languages

- Small org: ~25 named users, one facility, one organization tenant.
- Every human‑facing string ships in **both English and Macedonian (Cyrillic)**. The
  user toggles language live; the whole UI re‑renders. See §7.
- Primarily **desktop/laptop** in offices and the lab, with meaningful **tablet/phone**
  use on the floor (installable PWA, offline shell). Design responsive, touch‑friendly.

---

## 2. Architecture the UI runs on (what a designer needs to know)

You do not need backend detail, but three facts shape the UI:

- **Single‑page app, template‑string rendering.** Views are rendered by writing HTML
  into containers. There is a global design‑token CSS layer (§6) that every component
  reads, so a re‑skin is mostly *token + component CSS*, not per‑screen rewrites.
- **Two independent data domains** (people/accounts vs. tasks/quality). The UI merges
  them; a designer just needs to know a "person" (name, role, avatar color, department)
  and a "record" (task, sample, certificate…) are separate objects joined by id.
- **Everything is organization‑scoped and permission‑gated.** The same screen shows
  different controls to different roles. Every module section below lists who sees/does
  what. Never design a control that all roles can see if only some can use it — hide or
  clearly disable, and show the reason (§8, §11).

---

## 3. The three zones (this is the top‑level mental model)

Every screen belongs to exactly one **zone**, and the zone dictates tone, chrome, and
guardrails. Make the zone legible at a glance (e.g. via the nav group it sits in and
subtle chrome cues) — a user must always know whether they are editing *live operational
work* or a *controlled GMP record*.

| Zone | What it is | Tone | Records are… | Guardrails |
|------|-----------|------|--------------|-----------|
| **A · Operations** (non‑GMP) | Weekly task management, coordination, dashboards, facility board | Fast, fluid, encouraging | Editable, low‑ceremony | Light. Planning aids, not controlled records. |
| **B · QMS Studio** | AI‑assisted authoring of controlled SOPs/quality docs; document registry + knowledge search | Deliberate, guided | Draft → reviewed → issued documents | Medium. Versioned; issued = locked. |
| **C · QC LIMS** (GMP records) | Specifications, samples, CoA/certificates, OOS, custody, stability/water/transport | Exact, controlled, inspectable | **Controlled GMP records** | **Heavy — see §8.** Immutable once issued; e‑signed; second‑person review; QP release. |

### 🔒 Mandatory scope disclaimer (Zone A)

The operations zone is **explicitly NOT a GMP‑controlled records system**. Its exports
and reports (weekly plan, weekly report, audit‑prep readiness) are **planning aids**.
Wherever an operations artifact could be mistaken for a controlled record — the weekly
Plan/Report documents, the Audit‑Prep readiness view, any PDF export — the UI must carry
a quiet but unmistakable disclaimer, e.g.:

> *"Planning aid — not a GMP‑controlled record. Controlled records live in QC LIMS /
> Document Studio."* (EN)
> *"Помошно средство за планирање — не е GMP‑контролиран запис."* (МК)

This is a real regulatory boundary, not boilerplate. Do not bury it, and do not let a
polished PDF read as an official certificate.

---

## 4. Personas & roles

There are **13 roles** in a strict tier order. Labels are bilingual. The role a user
holds changes what nav groups, buttons, and screens they see, and — in the QC zone —
what lifecycle transitions they may perform.

| Tier | Role code | EN label | МК label | Notes |
|------|-----------|----------|----------|-------|
| System | `ADMIN` | Administrator | Администратор | Seeded in DB only; never shown in a role picker. Org‑scoped (not a superuser). |
| Executive | `OWNER` | Owner | Сопственик | Business owner. Cross‑department read. |
| Executive | `CEO` | CEO | Извршен директор | |
| Executive | `COO` | COO | Оперативен директор | |
| Manager | `QA_MGR` | QA Manager | Менаџер за КО | Quality Assurance |
| Manager | `QC_MGR` | QC Manager | Менаџер за КК | Quality Control — primary QC‑LIMS writer |
| Manager | `PR_MGR` | Production Manager | Менаџер за производство | |
| Manager | `WH_MGR` | Warehouse Manager | Менаџер за магацин | |
| Manager | `SE_MGR` | Security Manager | Менаџер за обезбедување | |
| Manager | `CU_MGR` | Cultivation Manager | Менаџер за одгледување | |
| Manager | `MU_MGR` | Maintenance Manager | Менаџер за одржување | |
| Manager | `QP` | Qualified Person | Квалификувано лице | Certifies/releases batches across all departments (Annex 16). |
| Staff | `USER` | Operator | Оператор | Base staff. Own‑tasks only. No management/QMS/QC nav. |

### Role groupings that drive the UI

- **Executives** = OWNER, CEO, COO (+ ADMIN can preview). Get the **Executive Overview**
  and cross‑department metrics; can hide departments from their own overview.
- **Managers** = the seven `*_MGR` + QP. Full task capabilities. Dept‑scoped managers
  (all managers **except QP**) only see their own department's tasks; QP and executives
  are org‑wide.
- **Elevated** = everything except `USER` (org‑wide task read, audit access, QMS Studio
  group visible).
- **QC writers** = ADMIN, executives, `QC_MGR`, `QP` may write QC records. Within QC,
  finer gates apply (below).
- **QC sign‑off roles:** `QP` (release/certify — Annex 16), `QC_MGR` (CoQ compile,
  reviewer). **Second‑person rule:** reviewer ≠ analyst, approver ≠ submitter — enforced
  by comparing *people*, not roles (see §8).

### Persona → primary screens (design priority per persona)

| Persona | Lands on | Lives in |
|---------|----------|----------|
| Operator (`USER`) | **My Week** | My Week, Board, Calendar, My Day, Inbox |
| Department manager | **Department Home** | Dept Home, Board, Coordination, Team, Workload, Approvals |
| QC Manager | Department Home | All QC‑LIMS views (Specs, Samples, CoA, OOS, Custody, Leaves), Analytics |
| Qualified Person (QP) | Approvals / QC | Certificates (release), OOS disposition, CoQ, Approvals |
| QA Manager | Audit Prep | Audit Prep, Document Studio, Approvals, Analytics |
| Executive | **Executive Overview** | Exec Overview, Analytics, Dashboard, Facility |
| Admin | (previews all) | Settings, Team, everything for support |

---

## 5. Information architecture & navigation

### Global chrome

- **Top header (64px):** brand/logo (left), global command/search entry, language
  toggle (EN ⇄ МК), theme/skin picker (palette icon), notifications bell (with unread
  badge), the logged‑in user's avatar (opens Settings → Account).
- **Left sidebar (252px):** the primary nav rail, grouped (below), plus a **Departments
  filter list** with per‑department color dots and live task counts. Collapsible on
  smaller screens; becomes a drawer / bottom nav on phones.
- **Main content region:** the active view.

### The grouped nav rail (exact groups & items)

Groups only organize; they never override per‑role visibility. Order matters.

**Operations** (Операции)
- *Department Home* (`depthome`) — only if the user's role has a department home
- *My Week* (`mywork`) — the default landing for operators
- *Board* (`board`)
- *Timeline* (`timeline`)
- *Calendar* (`calendar`)

**Management** (Менаџмент)
- *Executive Overview* (`exec`) — executives/admin only
- *Coordination* (`coord`) — badge = count of pending cross‑department handoffs this week
- *Dashboard* (`dash`)
- *Team* (`team`)
- *Workload* (`workload`) — managers/execs only

**QMS Studio** (QMS Студио) — only for roles above `USER`
- *Document Studio* (creation wizard)
- *Registry* (document register)
- *Knowledge* (knowledge search)
- *(QC‑LIMS views register themselves into this zone — see §9.)*

**System** (Систем)
- *Inbox / Notifications* (`inbox`) — badge = unread count

> Full‑page modules (QC LIMS, Facility, Approvals, Audit Prep, Analytics, Intake,
> Import, Audit) insert themselves into the correct group via anchor markers. Treat the
> rail as **extensible**: design the group headers and item rows so an arbitrary number
> of QC/QMS items can live under the "QMS Studio" group without visual overflow (it can
> get long — plan for scroll and/or collapsible groups).

### Complete view inventory (every screen the app has)

Design tokens for each are in §9. Grouped by zone:

**Zone A — Operations & Management**
`depthome` (Department Home) · `mywork` (My Week) · `board` (Board) · `timeline`
(Timeline) · `calendar` (Calendar) · `coord` (Coordination) · `dash` (Dashboard) ·
`exec` (Executive Overview) · `team` (Team) · `workload` (Workload) · `myday` (My Day) ·
`facility` (Facility board) · `approvals` (Approvals) · `analytics` (Analytics) ·
`auditprep` (Audit Prep readiness) · `report` (Weekly Plan/Report document) · `execreport`
(Executive report) · `intake` (AI Intake) · `import` (Bulk Import) · `inbox`
(Notifications) · `audit` (Audit trail).

**Zone B — QMS Studio**
`qmsstudio` (Document creation wizard) · `qmsregistry` (Document registry) · `qmsknow`
(Knowledge search).

**Zone C — QC LIMS**
`qcspec` (Specifications) · `qclab` (Lab dashboard) · `qcregister` (Certificate register) ·
`qcsample` (Samples) · `qcgenealogy` (Batch genealogy) · `qccoa` (Certificates / CoA) ·
`qcecoa` (eCoA intake) · `qcoos` (OOS / CAPA) · `qccustody` (Sampling requests / field
records / chain of custody) · `qcleaves` (Water · Stability · Transport).

**Global**
Settings modal · Command palette (⌘K) · Login/splash entry · Demo mode.

---

## 6. Design system

The app ships a mature, token‑driven design system. **Re‑skinning = re‑authoring tokens
and component CSS; markup stays.** The default look is the **"Mass Weed" HUD** (a Mass
Effect‑inspired command‑deck aesthetic). There are **35 total skins** the user can pick
from, all driven by the same token contract.

### 6.1 The token contract (the heart of it)

Every visual is expressed through CSS custom properties. A skin restates the tokens; all
components recolor with no markup change. The single most important token is
`--accent-rgb` (a raw `r,g,b` triple): nav tint, glass borders, glows, and focus rings
are all `rgba(var(--accent-rgb), α)`, so one triple re‑hues the whole shell.

**Core token families** (default dark = Mass Weed):

```
Surfaces:   --bg  --surface  --surface-2  --surface-3  --overlay
Ink/text:   --ink  --ink-2  --ink-3  --ink-4
Borders:    --line  --line-2  --border-strong
Primary:    --accent-rgb (triple)  --primary  --primary-hover  --primary-soft
            --primary-fg  --text-on-primary
Semantic:   --green  --blue  --teal  --orange  --amber  --red  --violet
            (+ each has -soft / -fg variants for chips)
Data‑viz:   --ch-a  --ch-b   (CVD‑safe chart pair, per theme)
Glass:      --glass-bg  --glass-border  --glass-blur
Elevation:  --sh-1  --sh-2  --sh-3  --sh-brand  --focus-ring  --glow-cyan
Texture:    --scanlines  --clip-panel  --clip-notch  --chamfer  --chamfer-sm
Type:       --font  --font-display  --font-brand  --font-num  --mono
            --ls-label  --ls-wide (letter-spacing)
Layout:     --r-sm/md/lg/xl (radii)  --header-h(64)  --sidebar-w(252)
Spacing:    --sp-1..--sp-10 (4→40px)
Type scale: --fs-xs(10)..--fs-3xl(32)
```

**Reference — the default "Mass Weed" dark skin** (command deck):
```
--bg:#14273f  --surface:#1c3350  --surface-2:#234064  --surface-3:#2c4e79
--ink:#eaf6ff  --ink-2:#9dc0d8  --ink-3:#6a8aa4
--accent-rgb:94,200,240   --primary:#5ec8f0 (HUD cyan)   --primary-hover:#8fe3ff
--green:#6cf05a  --orange:#f0b95e  --red:#ef4d4d  --amber:#ecec4a  --violet:#c89bf0
--font:'Titillium Web'  --font-display:'Saira Condensed'  --font-num:'Orbitron'
--r-sm:3px --r-md:4px --r-lg:5px  --chamfer:14px   (corners are CUT, not rounded)
```

**Reference — the "Plasma" dark skin** (the original GrowFlow look, still selectable):
```
--bg:#0E1F17 (green‑charcoal)  --surface:#163025  --ink:#E9F6EF
--accent-rgb:43,232,160  --primary:#2BE8A0 (plasma green)
--font:'Saira'  --font-display:'Orbitron'  --font-brand:'Poppins'
--r-sm:8px..--r-xl:18px   (soft rounded corners)
```

### 6.2 The Mass Weed HUD aesthetic (default identity)

The default skin is a sci‑fi **command‑deck HUD**. Its signature moves — design *with*
these, or deliberately evolve them:

- **Chamfered panels, not rounded.** Cards/modals/sidebar use clipped corners
  (`--clip-panel`, `--chamfer:14px`) — angular, cut hardware, not soft cards.
- **Cyan edge‑glow** on primary/active elements (`--glow-cyan`) and a **plasma‑glow
  elevation** model (`--sh-2` uses inset glow, not soft drop shadow).
- **Scanline texture** faintly overlaid on cards/modals/sidebar (`--scanlines`).
- **Deep‑space canvas** — a radial navy gradient + faint starfield behind the whole shell.
- **HUD corner reticles / frames** (`.hud-frame`) on hero panels.
- **Condensed, tracked, uppercase labels** (`--font-display` = Saira Condensed,
  `--ls-label:.14em`), **Orbitron for numerics** (counts, metrics, IDs), Titillium Web
  for body. Cyrillic (МК) gracefully falls back to Saira (always loaded).

There is a light variant ("Cool Mist Glass", `mass-weed-light`) — frosted white glass,
same cyan‑blue accent — for daylight/office use.

### 6.3 The 35‑skin system

Users pick a skin from a palette picker (grouped Dark / Light). Skins are:

- **5 core skins** (define their own derived tokens): `mass-weed` (default),
  `mass-weed-light`, `dark` ("Plasma"), `light` ("Cool Mist"), `suma` ("Protoss").
- **~30 "Carbon" skins** (token‑only overrides on a shared derived layer), dark and
  light, e.g. *Blurple Chat, Code Forge, Digital Rain, Ebony Amber, Forest, Nord,
  Nordic, Nightfang (Dracula), Mocha (Catppuccin), Vapor Deck, Aurora, Jade Mint,
  Kawaii, Retro 98, Miami Neon, Steel Mist, Winter Blush…*

**Design implications:**
- Never hard‑code a color. Every component must read tokens so all 35 skins work.
- The **Mass Weed HUD chrome** (chamfers, scanlines, starfield, reticles) applies only
  to the two mass‑weed variants; Carbon/Plasma skins use rounded radii + soft shadows.
  Your component CSS must degrade cleanly between "HUD" and "flat glass" modes.
- **Self‑heal:** unknown/retired skins snap back to `mass-weed`. The login/splash
  showcases a *random* skin per load without overwriting the user's saved choice.

### 6.4 Department identity colors

Each department has a fixed identity color + icon + abbreviation, used on cards, chips,
dept dots, facility, and charts. Keep them recognizable across skins (they may be tuned
per skin, but the hue family should hold).

| Dept code | Abbr | EN / МК | Color (default) | Icon |
|-----------|------|---------|-----------------|------|
| `cultivation` | CU | Cultivation / Одгледување | `#2BE8A0` | leaf |
| `production` | PR | Production / Производство | `#2FD9D9` | box |
| `quality_control` / `qc` | QC | Quality Control / Контрола на квалитет | `#7A5BE0` | flask |
| `quality_assurance` | QA | QA / QP · ОК / КвЛ | `#C2410C` | shield |
| `logistics` | WH | Warehouse / Магацин | `#0891B2` | box |
| `security` | SE | Security / Обезбедување | `#566884` | shield |
| `tooling` | MU | Maintenance / Одржување | `#5A6B82` | wrench |

*(An extended operational taxonomy also splits cultivation into Cloning & Nursery,
Vegetation, Flowering, Irrigation, and warehouse into In/Out — with their own greens,
gold, teal, magenta.)*

### 6.5 Iconography

Custom inline SVG icon set, 20×20 viewBox, stroke paths (not filled), single‑color
(inherits `currentColor`). ~50 glyphs: search, bell, plus, mic, chevrons, check, clock,
user/users, flag, leaf, grid, timeline, chat, link, settings, sun/moon, hexagon, palette,
drop/droplet, box, shield, wrench, flask, sparkle, arrow, trash, menu, trend, calendar,
at (@mentions), forward, x, play, info, eye/eyeOff, layers, award, git‑branch, file,
file‑input, alert‑triangle. Keep this stroke‑icon language; extend in the same style.

### 6.6 Typography

- **Body/UI:** Titillium Web (Mass Weed) / Saira (Plasma). Clean, technical sans.
- **Display/headers:** Saira Condensed / Orbitron — condensed, uppercase, tracked.
- **Numerics/IDs/metrics:** Orbitron ("HUD counter" feel).
- **Mono:** Geist Mono (codes, hashes, audit).
- **Brand:** Poppins / Comfortaa (Comfortaa is self‑hosted with Cyrillic subset incl.
  U+2116 №).
- **Cyrillic must always render** — every font stack falls back to Saira (loaded).

---

## 7. Bilingual / i18n requirements 🔒

**Every user‑facing string is bilingual EN/МК.** This is non‑negotiable — the workforce
is Macedonian; regulators and some staff read English.

- A single language state drives the whole app; the header toggle flips it live and
  everything re‑renders. There is no page reload.
- The codebase pattern is a helper `AL(en, mk)` returning the active language's string,
  plus dictionaries for statuses, roles, priorities, days. **Design must accommodate
  text expansion:** Macedonian strings are frequently 20–40% longer; Cyrillic is wider.
  Never design a control whose label only fits in English. Test every button, chip, tab,
  and empty state in МК.
- **Data can be bilingual too:** many records carry `name_en` / `name_mk` (departments,
  spec materials, test names). Show the active language, fall back to the other.
- **Dates:** day abbreviations are localized (Mon→Пон, Tue→Вто…). Numbers/units are not
  translated. The numero sign **№ (U+2116)** is used, not "No." (see §8).
- **The letter is never dropped:** if a translation is missing, fall back to English
  rather than showing a blank or a key.

**Standing typographic directive:** wherever a document/record shows a "number of"
label, use **№** (U+2116), e.g. "Sample №", "Certificate №". This is a house convention
across all controlled documents.

---

## 8. GxP UI guardrails 🔒 (the rules the regulated zone imposes on design)

These come from EU‑GMP / MK‑GMP, EU‑GMP Annex 11 (computerized systems) and Annex 16
(QP certification), ALCOA+ data‑integrity principles, and the facility's approved SOPs.
They constrain how QC‑LIMS (Zone C) and, to a lesser degree, QMS Studio (Zone B) may be
presented. **Violating these can invalidate a record.** Design for them explicitly.

1. **Never fabricate data — blank is a value.** If a quantity is unknown/unmeasured, the
   UI shows it **blank / `—`**, never a zero, guess, placeholder number, or "N/A" that
   reads as a result. Acceptance limits, results, verdicts left unmeasured stay empty
   for a human. Design empty cells that clearly read as *"not yet entered"* vs. *"entered
   as blank"* — they are different and must look different.

2. **Issued records are immutable — correct by revision, never edit.** Once a
   certificate/spec is APPROVED/RELEASED (or a document is issued), its content is
   frozen at the database level. You do not "edit" it — you **create a new revision**
   (new revision number; the prior becomes **SUPERSEDED**). The UI must:
   - Render issued records with unmistakable **read‑only / locked chrome** (a lock
     affordance, muted edit controls, a "SUPERSEDED / current revision" banner).
   - Offer **"Create revision"** instead of "Edit" once locked.
   - Show the **supersession chain** (this revision ← superseded ← …) so history is
     visible and traceable.

3. **Second‑person review (segregation of duties).** Reviewer ≠ analyst; approver ≠
   submitter. Enforced by comparing the actual people. The UI must:
   - **Disable** the Review action for the person who performed the test, with a clear
     reason ("You entered these results — review requires a second person").
   - **Disable** Approve/Release for the submitter.
   - Never present a control that will 403 without explaining why.

4. **QP‑gated release (Annex 16).** Only the **Qualified Person** may release a batch /
   certify a CoQ. Release/certify actions must be visibly QP‑only (locked with a "QP
   release" label for everyone else), and gated on data completeness — a certificate can
   only be released if every result complies (a FAIL/unmeasured value blocks it).

5. **Annex 11 electronic signatures.** QC approvals capture an e‑signature: the signer
   **re‑authenticates with their password at the moment of signing**, and the signature
   (who, when, meaning) is bound to the record. Design a **signing modal**: statement of
   meaning ("I approve/release this…"), password field, explicit confirm; show the
   resulting signature block (name, role, timestamp, meaning) on the record.

6. **Tamper‑evident audit trail.** Every create/update/delete of a record is written to
   a hash‑chained, append‑only audit log. There is an **Audit** view (§9) and a
   **verify** action that reports chain integrity. Design audit rows as immutable
   history (who · what · when · before→after), and a clear "chain verified / N breaks"
   status.

7. **eCoA review checklist gate (QCT‑018).** An external certificate cannot be promoted
   into the system until a defined **review checklist** is completed and ACCEPTED. If any
   item is REJECTED, the document goes to REJECTED. Design the checklist as an explicit
   gate, not an optional side panel.

8. **Deviation logging (§6.16).** Actions taken outside the normal path get a logged
   reason. Where the UI lets a user override/deviate, require and capture a reason
   (min‑length enforced) — surface it as a required field, not a silent allow.

9. **Provenance is shown, not hidden.** Certificate results carry where they came from
   (source document code, institution, date). eCoA‑ingested values show their source. The
   verify loop reconciles a promoted certificate against its source and surfaces
   **VERIFIED / DISCREPANCY** — never silently "fixes" a mismatch; it *reports* it.

10. **Grounded AI only.** AI features (knowledge Q&A, CoA Q&A) must return **cited**
    passages from real sources, never a fabricated synthesis. "No match" → show an honest
    empty grounded state, not an invented answer.

**Chrome vocabulary to design once and reuse (Zone C):** a *locked/immutable* record
treatment; a *revision / supersession* banner + chain; a *second‑person blocked* control
state with reason; a *QP‑only* release control; the *e‑signature* modal + signature
block; a *provenance* line; a *verify verdict* chip (VERIFIED / DISCREPANCY); a *blank vs.
zero* cell distinction; the *deviation reason* required field.

---

## 9. Module catalog

Each module below follows: **Purpose · Zone · Personas · Screens & layout · Data fields ·
Actions · States · Human IDs & lifecycle.** "States" always means the empty / loading /
error / permission‑denied variants you must design (see also §11).

---

### 9.1 My Week (`mywork`) — Zone A

- **Purpose.** The operator's home: this week's tasks, quick capture, quick status.
- **Personas.** Everyone; the default landing for `USER`.
- **Screens & layout.** A week‑scoped list of the user's tasks with a prominent
  **quick‑add** ("Add a task — or speak it", incl. voice dictation via mic). Tasks are
  expandable rows/cards showing detail. Sidebar week selector (prev/this/next + more),
  day filter, department filter, search, tag filter.
- **Data fields (task).** Title (bilingual), department (color/abbr chip), owner
  (Accountable — one person), helpers (Responsible — many), status (6‑state), priority
  (4‑level), due date, day‑of‑week, week, task type, progress notes (append log),
  dependencies/links, cross‑department handoff target, completion %, external reference,
  custom department attributes (jsonb templated per department).
- **Actions.** Create (typed or dictated), edit (own/any per role), change status
  (cycle or explicit picker), set priority/due/assignees (via the **chooser** popup, §10),
  add progress note, roll a task over to next week, delete (managers), AI‑rewrite a title.
- **States.** Empty: "No tasks here yet." Loading skeleton rows. Error toast on failed
  fetch (per‑resource, never blanks the whole UI). Permission: operators can only change
  status/edit on tasks they own.
- **Human IDs & lifecycle.** Status enum (with МК): `pending` Not started / Не започнато ·
  `working` Working on it / Во тек · `review` In review / На преглед · `stuck` Stuck /
  Блокирано · `postponed` Postponed / Одложено · `done` Done / Завршено. Priority:
  `critical / high / medium / low` (Критичен/Висок/Среден/Низок).

### 9.2 Board (`board`) — Zone A

- **Purpose.** Kanban/column view of the week's tasks by status (and/or department).
- **Personas.** All; managers see their department scope, execs org‑wide.
- **Layout.** Columns per status (6), cards colored by department, drag to change status
  (respect permission gates), collapsible department swimlanes. Also renders a **tree
  depth** view for parent/subtask families and, for the document board, theme → document →
  version rows.
- **States.** Empty column placeholders; per‑card skeleton; disabled drag for operators
  on others' tasks (with reason).

### 9.3 Timeline (`timeline`) — Zone A

- **Purpose.** Time‑ordered / Gantt‑like view of tasks across the week and dependencies.
- **Layout.** Horizontal lanes by day/department; dependency links drawn between tasks;
  overdue markers. Handoff pipeline visualized (cultivation → production → QC → QA →
  logistics).

### 9.4 Calendar (`calendar`) — Zone A

- **Purpose.** Month/week calendar of tasks by due date.
- **Layout.** Standard calendar grid, tasks as chips colored by department, localized day
  names, click a day to filter My Week to it. 14‑week window (4 back → 9 forward).

### 9.5 Coordination (`coord`) — Zone A

- **Purpose.** Cross‑department handoffs — where work passes between departments.
- **Personas.** Managers/execs. Nav badge = count of pending handoffs this week.
- **Layout.** The handoff pipeline (from‑dept → to‑dept), tasks awaiting handoff, @mentions,
  a coordination chat/thread affordance. Show the fixed pipeline: CU→PR→QC→QA→WH.
- **States.** Empty ("No pending handoffs"). Badge disappears at zero.

### 9.6 Dashboard (`dash`) — Zone A

- **Purpose.** At‑a‑glance operational metrics for the current scope.
- **Layout.** Stat cards (done/total/completion %, busiest day, status distribution),
  small charts. Reads the whole week (ignores day/tag filters).

### 9.7 Executive Overview (`exec`) — Zone A (Management)

- **Purpose.** Cross‑department executive read: metrics per department, dependency/batch
  flow, week‑over‑week trend.
- **Personas.** OWNER/CEO/COO (+ ADMIN preview) only.
- **Layout.** Department cards/strips with completion + trend sparklines, a
  **department‑visibility toggle** (execs can hide departments from their own overview,
  persisted per browser; "reset" restores all), CEO/COO summary strips, WoW sparkline.
- **States.** Hidden‑department chips; "show all" reset.

### 9.8 Team (`team`) — Zone A (Management)

- **Purpose.** People management: roster, roles, add/edit person.
- **Personas.** ADMIN + managers (a manager may create only `USER` staff, only in their
  own department).
- **Layout.** People cards grouped by department, avatar (colored initials), role chip
  (bilingual). Add/Edit person modal: full name, role (filtered picker — never offers
  ADMIN), department, avatar color, active toggle, reset password, change password.
- **States.** Permission: role picker options depend on the creator's role; deactivated
  users shown muted.

### 9.9 Workload (`workload`) — Zone A (Management)

- **Purpose.** Balance work across people — who is over/under‑loaded.
- **Personas.** Managers/execs.
- **Layout.** Per‑person load bars/heat, by department, with re‑assignment affordances.
  Feeds the AI workload‑balancing suggestions.

### 9.10 My Day (`myday`) — Zone A

- **Purpose.** A focused "today" list — the subset of My Week due/scheduled today, plus
  approvals awaiting the user.
- **Layout.** A simple prioritized day list; quick status changes; "what needs me today".
- **Note.** Its data fetch has a known slow path — design a graceful loading/timeout
  state (skeleton + "still loading…", not a hang).

### 9.11 Department Home (`depthome`) — Zone A

- **Purpose.** A department‑tailored landing page (per‑department layout, presets, and
  field templates) for managers/staff of that department.
- **Layout.** Department‑branded header (dept color/icon), department KPIs, quick‑add with
  the department's custom field template, department‑scoped task list.

### 9.12 Facility (`facility`) — Zone A

- **Purpose.** The physical facility board: **rooms** and **plant batches** (strain,
  plant count, growth phase) across the grow.
- **Personas.** Execs + department managers.
- **Layout.** Rooms as tiles/zones, each showing occupancy and current batches; a batch
  card shows strain, count, phase (clone/veg/flower/harvest), room. Cultivation‑forward
  visual (greens). This is operational (Zone A), **not** the GMP batch‑genealogy record
  (that's QC, §9.24).
- **States.** Empty rooms, unassigned batches.

### 9.13 Approvals (`approvals`) — Zone A/B bridge

- **Purpose.** A unified queue of things awaiting the current user's sign‑off (task
  sign‑offs, document approvals, QC review/approve/release items surfaced here).
- **Personas.** Managers, QP, QA, execs.
- **Layout.** A prioritized approval inbox: each row = what, who submitted, when, the
  action (approve/reject/release), and a link to the record. Second‑person and QP gates
  apply (§8). Known slow fetch — design a robust loading state.
- **States.** Empty ("Nothing awaits your approval"). Per‑item permission reason when the
  user can't act (e.g. they submitted it).

### 9.14 Analytics (`analytics`) — Zone A (Management)

- **Purpose.** Deeper operational analytics: weekly trends, department snapshot, task‑type
  mix, outcome traceability.
- **Layout.** SVG charts using the CVD‑safe `--ch-a`/`--ch-b` pair; trend lines, stacked
  bars, distributions. Elevated roles only, dept‑scoped for managers.
- **States.** Empty‑data chart placeholders; loading shimmer.

### 9.15 Audit Prep (`auditprep`) — Zone A (Management) 🔒 disclaimer

- **Purpose.** GMP **audit‑readiness** rollup: per‑programme (MK‑GMP / EU‑GMP /
  SOP‑writing) completion, due‑date milestone timeline with overdue flags, status
  distribution, busiest day, outcome traceability.
- **Personas.** Elevated (esp. QA), dept‑scoped.
- **Layout.** Programme cards with completion %, a milestone timeline, telemetry panels.
- **🔒 GxP.** This is a **planning aid, not a controlled record** — carry the §3
  disclaimer prominently.

### 9.16 Weekly Plan / Report document (`report`) — Zone A/B

- **Purpose.** Compile a weekly **Plan** (forward) or **Report** (retrospective) document
  per department, review it, lock it, export PDF.
- **Personas.** Managers/execs; QA for review/lock.
- **Layout.** A document composer: sections (per template registry), bilingual AI‑drafted
  content, a status strip (draft → in review → locked), section‑level approve, a server
  ribbon/header, export to PDF. Pick any week or a custom date range.
- **🔒.** Once **locked**, content is immutable (edit is blocked at DB level → the UI must
  show locked chrome and offer a new version, not an edit). Carry the planning‑aid
  disclaimer. Min‑length reason on revise.
- **States.** Draft (editable), In review, Locked (read‑only + "create version").

### 9.17 Executive Report (`execreport`) — Zone A

- **Purpose.** A cross‑department executive report document (roll‑up of the weekly
  reports) with CEO/COO strips and WoW sparkline.
- **Layout.** Similar composer to §9.16 but org‑wide; a board tree of theme → document →
  version.

### 9.18 AI Intake (`intake`) — Zone A

- **Purpose.** Paste free‑text (meeting notes, messages) → AI extracts **task candidates**
  → review → adopt into real tasks.
- **Layout.** A paste box → "Extract" → a review list of proposed tasks (each editable:
  title, dept, assignee, due) → per‑item adopt/discard → bulk adopt. Input length‑capped.
- **States.** Empty paste; extracting (loading); no candidates found; AI unavailable
  (graceful "no binding" degrade).

### 9.19 Bulk Import (`import`) — Zone A

- **Purpose.** Structured bulk import of tasks (e.g. from a capture prompt / external
  system) via a paste/upload of a defined format.
- **Layout.** Input area → validate → preview rows → import; shows accepted/rejected with
  reasons. Content size‑capped.
- **States.** Validation errors inline per row; duplicate detection (409 → "already
  exists").

### 9.20 Notifications / Inbox (`inbox`) — Zone A (System)

- **Purpose.** The user's notification feed: task assignments, @mentions, handoffs,
  approvals, automation alerts (e.g. CAPA‑stuck, validation‑stuck, workflow sign‑off),
  QC OOS notifications.
- **Layout.** A feed list, unread badge on the bell + nav item, filter by reason/type,
  mark‑read, acknowledge (some notifications require an explicit ack, capturing who/when).
- **States.** Empty ("You're all caught up"), unread emphasis, filter chips.

### 9.21 Audit trail (`audit`) — Zone A/C 🔒

- **Purpose.** View the tamper‑evident audit log and verify chain integrity.
- **Personas.** Elevated / audit roles.
- **Layout.** Immutable history rows: actor, action (create/update/delete), entity, when,
  before→after diff. A **"Verify chain"** action reporting integrity: hash breaks / link
  breaks / head breaks — designed as a clear "Verified ✓" or "N breaks found" status.
- **🔒.** Rows are read‑only history; never editable. Mono font for hashes/ids.

### 9.21b QMS Studio — Document Studio (`qmsstudio`) — Zone B

- **Purpose.** The AI‑assisted **controlled‑document creation wizard**: questionnaire →
  section‑by‑section AI drafting with per‑section regulatory checks → assembly → bilingual
  house‑style formatting → verify (hard PASS gate) → DOCX/PDF.
- **Personas.** Authoring = QP / QA_MGR / ADMIN; read = above `USER`.
- **Screens & layout (wizard):**
  1. **Questionnaire** — structured intake (document type, scope, regulatory basis…).
  2. **Progress** — live generation status per section (polling; show a stepper/section
     checklist with per‑section state: queued → drafting → checking → done).
  3. **Regulatory‑check report** — cited findings from real regulatory sources per section
     (grounded; §8.10).
  4. **Verify report** — the house‑style formatter's hard **RESULT: PASS/FAIL** gate; a
     FAIL never produces a document.
  5. **Download** — DOCX + PDF (house style: navy header, bilingual MK|EN, 6pt floor).
- **🔒.** Never ship a document on FAIL. Never fabricate regulatory content — cite. House
  style is fixed (navy #2B547E, Calibri, bilingual).
- **States.** Each wizard step has queued/running/done/failed; the reg‑check step shows
  "no citation found" honestly; DocEngine unreachable → clean 503 degrade.

### 9.22 QMS Registry (`qmsregistry`) & Knowledge (`qmsknow`) — Zone B

- **Registry.** The controlled‑document register: list of issued documents with number,
  title, version/revision, status, effective date, department, links to DOCX/PDF. Read‑only
  history; supersession chains.
- **Knowledge.** Grounded search over the real regulatory + document knowledge sources —
  returns **cited** passages, never invented answers. A search box → ranked cited results
  with source labels.
- **States.** If the legacy registry service is retired/unavailable, show an honest panel
  ("retired — use Document Studio"), not a broken screen.

---

### QC LIMS (Zone C) 🔒 — the regulated records module

All QC views share the §8 guardrails. Common chrome: human‑ID headers with **№**, locked/
revision treatment on issued records, second‑person + QP gates on lifecycle buttons,
e‑signature modal, provenance lines, blank‑not‑zero cells, deviation reasons.

**QC human‑ID formats (per‑entity, per‑year sequences):**
`PP-SPEC-YYYY-NNNN` (spec) · `PP-SMP-YYYY-NNNN` (sample) · `PP-OOS-YYYY-NNNN` (OOS) ·
`PP-ECOA-YYYY-NNNN` (ingested eCoA doc) · `PP-RQS-YYYY-NNNN` (sampling request) ·
`PP-SFR-YYYY-NNNN` (sample field record) · `PP-WT-YYYY-NNNN` (water test) ·
`PP-STB-YYYY-NNNN` (stability study) · `PP-TRN-YYYY-NNNN` (sample transport).
**Certificate numbers are per‑type, per‑year:** `iCoA-PP-YYYY-NNNN` (internal CoA),
`eCoA-PP-YYYY-NNNN` (external), `CoQ-PP-YYYY-NNNN` (Certificate of Quality),
`WCoA-PP-YYYY-NNNN` (water CoA), `CoA-PP-YYYY-NNNN` (generic).

### 9.23 Specifications (`qcspec`) — Zone C

- **Purpose.** Master data: material specifications and their test parameters + acceptance
  limits. Everything else references a spec.
- **Personas.** Read = elevated; write = ADMIN/exec/`QC_MGR`/`QP`.
- **Layout.** A spec **registry** (list: spec №, material code, material name EN/МК,
  version, status, THC grade, effective date, approved‑by) → a spec **detail** with a
  **parameter table** (test name EN/МК, method, spec type, lower/upper limit, unit,
  pharmacopoeia reference, sort order).
- **Data rules 🔒.** Exactly **one ACTIVE spec per (material, version scope)**. Limits left
  unknown stay **blank** (never 0). Computed helpers: total THC / total CBD.
- **Actions.** Create spec, add parameters, drive lifecycle transitions (guarded), create
  a new version (supersede). Approve = an elevated act.
- **Lifecycle (8 stages).** DRAFT → … → ACTIVE (one active) → SUPERSEDED/RETIRED, with
  guarded transitions. Only ACTIVE specs may be cited by new certificates.
- **States.** No specs yet; a spec with no parameters ("add the first parameter"); locked
  ACTIVE spec (read‑only + "new version"); blank vs. entered limits.

### 9.24 Samples & genealogy (`qcsample`, `qcgenealogy`) — Zone C

- **Purpose.** Register and track QC samples through their lifecycle; view **batch
  genealogy** (parent/child ancestry, incl. blending → many‑to‑many).
- **Layout.** Sample **registry/board** (sample №, batch id, material, sample type,
  status, retention flag, sampling plan) → sample **detail** (genealogy chain, QR string,
  linked certificate, custody). A **genealogy** view drawing the ancestry graph
  (git‑branch icon vocabulary).
- **Lifecycle (state machine, guarded PATCH with actor/role checks):**
  COLLECTED → [IN_TRANSIT → RECEIVED] → IN_TEST → TESTED → [REVIEWED] → APPROVED →
  RELEASED, plus REJECTED and QUARANTINE. **A failing/out‑of‑spec result auto‑flags the
  sample to QUARANTINE.** Second‑person: TESTED→REVIEWED requires a different person than
  who tested; release is QP‑gated.
- **🔒.** Show who performed each transition + when. Blank sample‑type/retention are real
  states. Sample kind taxonomy + non‑conformance fields per SOP.
- **States.** Empty registry; a quarantined sample must be visually unmistakable (red);
  disabled transitions with reasons (second‑person / QP).

### 9.25 Certificates / CoA (`qccoa`, `qcregister`, `qclab`) — Zone C

- **Purpose.** Certificates of Analysis / Quality: the result record for a batch against a
  spec, driven through review → approval → **QP release**, then rendered to a controlled
  **CoQ** document via the DocEngine.
- **Personas.** Analyst enters results; a *second* person reviews; QP approves/releases.
- **Layout.**
  - **Certificate register** (`qcregister`) — all certificates: cert № (per‑type), batch,
    spec, type, status, decision (PASS/FAIL), analyst/reviewer/approver, dates, retention.
  - **Lab dashboard** (`qclab`) — the QC workbench overview (in‑test, awaiting review,
    awaiting release, OOS open).
  - **Certificate detail** (`qccoa`) — header (cert №, batch, spec, lab verdict), a
    **results grid** (per parameter: result value/numeric, limits from the spec,
    `complies` verdict auto‑evaluated, status, provenance: source document/institution/
    date), the second‑person signature block, and the release/CoQ actions.
- **Actions & lifecycle.** DRAFT → REVIEWED → APPROVED → RELEASED (+ VOIDED). Add result
  (auto‑evaluates complies vs. spec limits; validates the parameter belongs to the cert's
  spec). Review (≠ analyst). Approve/Release (**QP only**, blocked if any result doesn't
  comply → the CoQ can't be fabricated over a FAIL). **Generate CoQ** (`.docx`, bilingual
  house style, hard PASS gate) once RELEASED. Revise (new revision; prior SUPERSEDED),
  with a min‑length reason. Void with reason.
- **🔒.** Immutable once APPROVED/RELEASED (revision, not edit). Honest signature block
  (only real signers shown). Every result carries provenance. CoQ mandatory‑field manifest
  (WHO TRS 1010 / Annex 16). A CoA number is assigned per type per year.
- **States.** Empty results grid; a result pending (blank, not 0); a FAIL result (red +
  blocks release); "release requires QP"; "review requires a second person"; RELEASED =
  locked chrome + CoQ download.

### 9.26 eCoA intake (`qcecoa`) — Zone C

- **Purpose.** Ingest an external supplier/lab CoA (PDF/eCoA), transcribe/extract its
  values, auto‑map them to spec parameters, discover unknown fields, review, and **promote**
  into an internal DRAFT certificate — with a verify loop back to source.
- **Layout.**
  - **eCoA register** (doc №, institution, status: UPLOADED → EXTRACTED → REVIEWED →
    PROMOTED / REJECTED, review deadline).
  - **Extraction workbench** — raw extracted rows; each auto‑mapped to a spec parameter
    (by prior human mapping, then by name) with a server‑graded `complies`; **unmapped/
    unknown labels queue as placeholders** for a human to MAP (future CoAs then auto‑map)
    or IGNORE.
  - **Review checklist (QCT‑018)** 🔒 — the gate that must be ACCEPTED before promote;
    REJECT → document REJECTED.
  - **Promote** → creates a DRAFT certificate + one result per mapped extraction, carrying
    provenance; unmapped values are **never fabricated**, they're left for a human.
  - **Verify vs source** — reconciles the promoted certificate against the eCoA per
    parameter → **VERIFIED / DISCREPANCY** (with per‑line detail); history preserved.
  - **CoA Q&A (RAG)** — grounded Q&A over the ingested CoA text; returns **cited** passages
    `[doc#idx]`, or an honest empty when nothing matches.
- **🔒.** 5‑working‑day review clock (§6.3.1). Adaptive placeholder discovery. Never
  auto‑correct a discrepancy — report it. PDF original custody + SHA‑256 hash retained.
- **States.** Upload pending; extracting; placeholders awaiting resolution; checklist
  incomplete (promote disabled with reason); discrepancy verdict; Q&A no‑match empty.

### 9.27 OOS / CAPA (`qcoos`) — Zone C

- **Purpose.** Out‑of‑Specification investigation (two‑phase) + append‑only OOS register +
  CAPA (corrective/preventive action, derived).
- **Layout.** OOS **register** (OOS №, sample/cert, phase, disposition, status) → OOS
  **detail** (Phase I lab investigation, Phase II full investigation, disposition, CAPA
  view). Recipients/notifications on raise.
- **Lifecycle.** OPEN → PHASE_I → PHASE_II → CLOSED (with a **disposition** decision).
  **Closing/disposition is QP‑gated** (e.g. QC_MGR cannot close/reject disposition; QP
  can). CAPA is rendered as a read‑time view over the OOS record + its transitions.
- **🔒.** The register is **append‑only** — every transition is logged, nothing overwritten.
  A CLOSED OOS's disposition is frozen. Deviation/reason capture.
- **States.** Open OOS emphasized; phase progress; disposition awaiting QP; append‑only log.

### 9.28 Custody cluster (`qccustody`) — Zone C

- **Purpose.** Field‑to‑lab traceability (ALCOA++): sampling requests (RQS), sample field
  records (SFR), and the chain of custody per sample.
- **Layout.** Three tabs/sections:
  - **RQS** (sampling requests): RQS №, status OPEN → REGISTERED → IN_PROGRESS →
    COMPLETED/CANCELLED, a **24‑hour QC registration window** (deadline + "window met"
    flag per SOP‑017), request fields (§6.1.4), produces a sample. **RQS must exist before
    sampling** (§6.1.1) — enforce the ordering in the UI.
  - **SFR** (field records): SFR №, field location/GPS, barrel numbers (list), destination,
    transport times, receipt condition; CREATED → IN_FIELD → COMPLETED/CANCELLED.
  - **Chain of custody** (per sample): an append‑only handoff log — from/to person +
    location, reason, transfer type (FIELD_TO_LAB / LAB_INTERNAL / LAB_TO_DISPOSAL /
    STABILITY_TRANSFER), condition.
- **🔒.** Custody log is append‑only and continuous. Control № on RQS. Registration‑window
  result is stamped, not editable after.
- **States.** RQS awaiting registration (countdown to the 24h deadline — design a clear
  "X h left / window met/missed" indicator); empty custody chain; guarded transitions.

### 9.29 Water · Stability · Transport leaves (`qcleaves`) — Zone C

- **Purpose.** Three standalone JSONB‑backed QC record types with no cross‑table deps.
- **Layout.** Tabs:
  - **Water tests** (`PP-WT`): grade (TW/BW/TR/RO), parameters (list of measurements),
    passed/out‑of‑expectation flag.
  - **Stability studies** (`PP-STB`, id shown as *study №*): type (LT/ACC/INT), batches
    (list), IN_PROGRESS → CLOSED (with shelf‑life on close).
  - **Sample transports** (`PP-TRN`): free‑text refs, tests (list), draft → in_transit →
    received, annex forms (SAR / MOIA / TMCOC / COO / FIN — shown under `forms.*` flags).
- **🔒.** Parameters unmeasured stay blank. Guarded transitions (bad enum → rejected).
- **States.** Empty per tab; in‑progress vs. closed; annex‑form checklist.

---

### 9.30 Settings (modal) — global

- **Purpose.** Account + app settings.
- **Layout.** A tabbed modal: **Account** (profile, change password), **Appearance**
  (theme/skin picker — grouped Dark/Light, live preview), **Language**, **AI** (per‑user/
  org AI binding management for admins), and admin utilities. Opened from the header
  avatar, the gear, or the sidebar user card.
- **States.** Password change requires current password; AI‑binding absent → features
  degrade gracefully.

### 9.31 Login / splash entry — global

- **Purpose.** Authentication + brand moment.
- **Layout.** A 3D animated leaf splash (self‑hosted three.js + mesh), a login form
  (username/password, remember device), bilingual. Showcases a **random skin per load**
  (without changing the user's saved skin). "Try the demo" entry (below).
- **🔒/UX.** Login screen must be bilingual. Failed‑login rate limiting exists (design a
  clear "too many attempts" state). Token expiry → return to splash gracefully.

### 9.32 Demo mode — global

- **Purpose.** A "Try the demo" path that logs into a **real, isolated demo organization**
  with seeded data, wiped on start/exit. Not a mock — the real app on a sandbox org.
- **Layout.** A demo **banner** ("sample data · cast & skin rotate each start · changes
  are not saved · not the production database"), a floating demo control, exit button.
  Rotates a random skin + a "cast" theme each start.
- **States.** Demo active (banner + demo chrome), exiting (wipe), demo disabled (button
  absent / graceful fail).

---

## 10. Global UI patterns (design once, reuse everywhere)

- **Chooser popup (`GF.chooser`).** The app deliberately replaced native `<select>`
  dropdowns with a custom popup chooser for assignees, departments, status, priority,
  dates, spec params, etc. Design one excellent chooser: searchable, keyboard‑navigable,
  avatars/color dots/icons per option, bilingual labels. It's used *pervasively* — it is
  arguably the most important interactive component after the card.
- **Command palette (⌘K, `cmdk`).** Global fuzzy launcher: jump to any view, run actions,
  search tasks/records. Bilingual. Design it as a first‑class navigation accelerator.
- **Modals.** Consistent modal shell (header, body, footer actions), focus trap + **focus
  restore** on close, Esc to close, backdrop `--overlay`. The **e‑signature modal** (§8) is
  a specialized variant.
- **Toasts.** Transient feedback (success/error/info), bilingual, non‑blocking; errors are
  per‑resource so one failure never blanks the UI.
- **Status chips.** A single status‑chip component reading `GF.statusLabel` + status color,
  reused across tasks, docs, samples, certs, OOS — but note each domain has its *own* status
  vocabulary (§13). Design a chip system flexible enough for all of them while staying
  visually coherent.
- **Stat cards, gauges, steppers, feeds, accordions, tabs, pagers, breadcrumbs, spinners,
  skeletons, striped tables** — the Mass Weed system already defines these; keep the full
  kit and make each token‑driven + skin‑safe.
- **Cards with a department accent** (`--dept-acc`): the workhorse task/record card carries
  a left accent in the department color.
- **HUD frame / reticle** (`.hud-frame`): the hero‑panel treatment on mass‑weed skins.

---

## 11. State catalog (design these for every data surface)

For each list, grid, chart, and detail, design all of:

1. **Empty** — a purposeful empty state with the right bilingual copy and, where relevant,
   the primary "create the first X" action. Distinguish "nothing here" from "no results
   for this filter."
2. **Loading** — skeletons (rows/cards/chart shimmer), never a blank flash; long fetches
   (My Day, Approvals) get a "still loading…" affordance, not a hang.
3. **Error** — a per‑resource error surface (toast + inline retry), never a whole‑screen
   crash. Show the message, keep the rest of the UI alive.
4. **Permission‑denied / gated** — a control the user can't use is **hidden or clearly
   disabled with a reason** (role, second‑person, QP, locked record). Never silently 403.
5. **🔒 Blank vs. zero** (Zone C) — an unmeasured value (`—`) must look different from an
   entered zero.
6. **🔒 Locked / immutable** (Zone B/C) — issued records get read‑only chrome + "create
   revision," never a live edit field.
7. **Offline (PWA)** — the app shell works offline; live data shows an offline notice; API
   writes queue/fail gracefully.

---

## 12. Component & layout reference (what already exists to reuse)

- **Shell:** header (64px) + collapsible sidebar (252px) + main; responsive to drawer/bottom
  nav on phone.
- **Nav rail:** grouped (Operations / Management / QMS Studio / System) with per‑item badges;
  extensible anchors for full‑page modules.
- **Departments filter list:** color dots + live counts + "add department" (admin).
- **Cards:** task card, record card, stat card, KPI card, room/batch tile — all with dept
  accent option.
- **Tables/grids:** results grid (QC), registers (specs/certs/OOS/eCoA/RQS/SFR), striped +
  sortable + status‑chipped.
- **Charts:** SVG line/bar/distribution using `--ch-a/--ch-b`, CVD‑safe, skin‑aware.
- **Wizard/stepper:** the Document Studio creation flow + QC checklists.
- **Signature block + e‑sign modal:** Zone C.
- **Audit rows + verify status:** tamper‑evident history.
- **Chooser, ⌘K palette, modal, toast, banner (demo/scope), 3D leaf splash.**

---

## 13. Reference tables

### Task status (Zone A) — enum · EN · МК · suggested color token
| code | EN | МК | color |
|------|----|----|-------|
| `pending` | Not started | Не започнато | ink‑3 (neutral) |
| `working` | Working on it | Во тек | blue |
| `review` | In review | На преглед | violet |
| `stuck` | Stuck | Блокирано | red |
| `postponed` | Postponed | Одложено | amber |
| `done` | Done | Завршено | green |

### Priority (Zone A)
`critical` Критичен (red) · `high` Висок (orange) · `medium` Среден (amber) · `low` Низок (ink‑3).

### QC lifecycle vocabularies (Zone C) — design status chips for each
- **Spec:** DRAFT → (review stages) → ACTIVE → SUPERSEDED / RETIRED (8 stages; one ACTIVE).
- **Sample:** COLLECTED → IN_TRANSIT → RECEIVED → IN_TEST → TESTED → REVIEWED → APPROVED →
  RELEASED; + REJECTED, QUARANTINE.
- **Certificate:** DRAFT → REVIEWED → APPROVED → RELEASED; + VOIDED; decision PASS/FAIL.
- **eCoA document:** UPLOADED → EXTRACTED → REVIEWED → PROMOTED / REJECTED.
- **eCoA extraction map:** mapped / unmapped (→ placeholder MAP or IGNORE).
- **Verify verdict:** VERIFIED / DISCREPANCY.
- **OOS:** OPEN → PHASE_I → PHASE_II → CLOSED (+ disposition).
- **RQS:** OPEN → REGISTERED → IN_PROGRESS → COMPLETED / CANCELLED (+ 24h window met/missed).
- **SFR:** CREATED → IN_FIELD → COMPLETED / CANCELLED.
- **Custody transfer type:** FIELD_TO_LAB / LAB_INTERNAL / LAB_TO_DISPOSAL / STABILITY_TRANSFER.
- **Stability:** IN_PROGRESS → CLOSED (type LT/ACC/INT).
- **Transport:** draft → in_transit → received (annex forms SAR/MOIA/TMCOC/COO/FIN).
- **Water grade:** TW / BW / TR / RO.

### Human‑ID formats (see §9 QC for full list)
Tasks: internal. Documents: controlled register numbers. QC: `PP-<TYPE>-YYYY-NNNN`
(SPEC/SMP/OOS/ECOA/RQS/SFR/WT/STB/TRN). Certificates per‑type‑per‑year:
`iCoA-PP` / `eCoA-PP` / `CoQ-PP` / `WCoA-PP` / `CoA-PP` `-YYYY-NNNN`. Always render the
"number of" label as **№**.

### Skins (35)
Core: mass‑weed (default), mass‑weed‑light, dark (Plasma), light (Cool Mist), suma
(Protoss). Carbon dark (~19): Blurple Chat, Blush Slate, Code Forge, Digital Rain, Ebony
Amber, Forest, Heart of Darkness, Indigo Turquoise, Lambda Core, Mocha (Catppuccin),
Nightfang (Dracula), Nord, Nordic, Solo Night, Tropical Midnight, Vapor Classic, Vapor
Deck. Carbon light (~13): Amber Glow, Aurora, Azure Silence, Blush Slate, Console Horizon,
Jade Matrix, Jade Mint, Kawaii, Miami Neon, Playlist Mint, Retro 98, Steel Mist, Winter
Blush.

---

## 14. Non‑negotiable checklist for the designer

- [ ] Every string designed in **both EN and МК**; layouts survive Cyrillic + longer МК.
- [ ] Every component reads **design tokens** — all 35 skins work; nothing hard‑coded.
- [ ] The **Mass Weed HUD** identity is honored (chamfers, cyan glow, scanlines, HUD type)
      as the default, while flat/rounded Carbon skins degrade cleanly.
- [ ] The **three zones** are legible; a user always knows if they're in operations vs. a
      controlled record.
- [ ] **🔒 GxP chrome** designed once and reused: locked/immutable, revision+supersession,
      second‑person‑blocked, QP‑only, e‑signature modal + block, provenance, verify verdict,
      blank‑vs‑zero, deviation reason, **№**.
- [ ] The **scope disclaimer** appears on every operations artifact that could be mistaken
      for a controlled record.
- [ ] Every data surface has **empty / loading / error / permission‑denied** states.
- [ ] The **chooser**, **⌘K palette**, **modals** (focus‑restore), **toasts**, **status
      chips**, and **cards** are first‑class, reusable, token‑driven.
- [ ] Responsive: desktop‑first but genuinely usable on tablet/phone; installable PWA with
      an offline shell.

---

*End of handover. This document describes the application as it exists at shell version
`wwf-shell-v3.71.0`. Design freely on top of this information model, tone, and the GxP
guardrails — those guardrails are the one thing that cannot bend.*

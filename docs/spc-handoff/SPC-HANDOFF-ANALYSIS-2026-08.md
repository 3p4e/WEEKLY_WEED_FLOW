# SP-COA-COQ handoff analysis — what the archives say and what the WWF app must do

Analyzed 2026-08-14 from the owner's two archives:
`SP-COA-COQ_FINAL_DOCS.zip` (6.5 MB — `Final_Docs/` curated deliverables + the
ImB_SPC / ImG_SPEC HANDOFFs) and `SP-COA-COQ_ALL_PROJECT.zip` (31 MB — the full
design-system project: root `HANDOFF.md`/`readme.md`/`SKILL.md`/`CLAUDE.md`,
`documents/` masters, `PROD_SPEC/` masters, `uploads/` source data, tokens/
components/guidelines). Everything below is read from those files, not inferred.

Machine-readable extracts committed alongside this file:
- **`imb_grade_ladders.json`** — all 257 per-strain-per-grade potency rows parsed
  from `Final_Docs/ImB_SPC/{BASE_SPCs,NEWs,RENs}` (71 strains: tier, grade,
  product code, nominal, range_min/max). This is the seed data for
  `qc_potency_specs` / `qc_potency_spec_ranges`.
- **`portfolio_master.json`** — all 78 batch rows of
  `BCP_PRODUCT_MASTER_FINAL.xlsx · 01_Portfolio_Master` (tranche, batch,
  original strain, renamed "Neu" strain, brand STEADY/CAYN, final label, THC%,
  commercial THC-bracket, volume kg).

---

## 1. The two document families (both are in scope for the app)

**Family 1 — certificates & acceptance specs** (`documents/` masters):
CoA (accepts outsourced eCoA; bronze stamp; lab cross-ref) · **iCoA** (all
in-house, never cites external labs, Method-Validation column, **3-tier
signoff**) · **CoQ** (aggregates eCoAs vs spec; keeps lab cross-ref; release
disposition; **2 signatories, no QP**) · Spec_IMB (strain-agnostic,
`QCSP-IMB-001`) · IMG (incoming-materials/packaging, `QCSP-RMI-P0005-v1`).

**Family 2 — ImB per-strain per-grade Product Specifications**
(`PROD_SPEC/` + `Final_Docs/ImB_SPC/`): one cultivar × one potency grade = one
A4 doc, code `QCSP 001_<ACR>-<ROMAN>_v.01` (template `QCSP 001 v.03`).
Anatomy: navy header → Orbitron strain-name block → gold-tag classification
(Phenotype INDICA/SATIVA/HYBRID+ratio · Chemotype **THC·CBD only** ·
Processing **Machine Trimmed only**) → §01 potency table (Grade / Product Code
`<ACR>_THC<nominal>:CBD1` / Nominal ±half-width / Range / CBD ≤1.0%) → 4-cell
info grid (Primary Packaging = the Triplex Alu Bag · Form&Type "Dry Cannabis
Flower · Intermediate Bulk (InB)" · Storage 15–25 °C, 30–60 %rH · Shelf Life) →
§02 the 12-parameter Ph. Eur. 3028 panel → 2 signatories → navy footer.

## 2. THE GRADE MODEL — three systems coexist; per-strain stored data wins

This is the most important finding for the app:

1. **Family-1 fixed 5-tier** (strain-agnostic Spec_IMB / iCoA / CoQ):
   exactly 5 grades, **I=THC27 · II=THC23 · III=THC19 · IV=THC15 · V=THC9,
   each ±2.0 % w/w** — "never 6". (P060052 = Grade IV, AC 13.0–17.0 ✓.)
   Note these tiers do NOT tile: gaps exist (e.g. 11–13 between V and IV).
2. **ImB per-strain ladders with batch history** (Grape Pie, Jokerz 31, OPM,
   Clemosa…): each strain's own authored ladder — GP I 26–30 / II 22–26 /
   III 18–22 / IV 13.83–18; J31 two tiers 23.5–30 / 16.5–23.5; CLE five tiers
   down to 5.00–10.00. **Contiguous** (tiers meet). 40 of 71 strains.
3. **ImB standard bracket** (strains without history, incl. NEWs/GG4 and most
   RENs): **I 27.00–30.00 · II 23.00–26.90 · III 16.00–22.90 · IV 5.00–15.90**
   — **0.10-pp gaps between tiers**. 31 of 71 strains.

The ImB HANDOFF's own rule: *"Always read the strain's own potency table —
never assume the standard split."* That is exactly the app's deployed model
(stored, approved `qc_potency_specs` per cultivar) — with **one defect**: our
`_validate_ladder` requires adjacent tiers to MEET, so the 31 bracket-style
strains (and the family-1 5-tier table) would be rejected at authoring.

**App change №1 (backend, small): relax ladder validation** to accept authored
gaps between adjacent tiers (contiguous OR bracket-style; validation should
require ordering + no overlap, not exact meeting; keep Spec I top = 30 and
bottom = floor). `disposition_for` ("largest range_min ≤ v") already handles
gap values correctly (26.95 → Grade II, since it fails to reach 27.00).

**App change №2 (seed): load `imb_grade_ladders.json`** into
`qc_potency_specs`/`qc_potency_spec_ranges` (DRAFT, versioned per source
family; approval stays a human act — segregation of duties already enforced).

## 3. Batch-level renames — a concept the app does not have

`01_Portfolio_Master` maps **each batch** (not each strain) to a commercial
identity: Original → **Neu** name + **Brand** (STEADY/CAYN) + **Finales Label**
+ commercial THC-bracket (7–10/10–13/13–16/16–19/19–22/22–25/≥25 %). The same
original strain maps to *different* Neu names per batch (Cap Junkie →
Cookie Kush on CJ052501/01 but → OG Banana's on CJ062501/2; GG4 → GG4 or
Cherry Chocolate; Sleepy Joe → Sleepy Joe or Calmino). 78 batches, 3 tranches.

**App implication:** cultivars alone can't express this. A future
`batch_commercial_identity` (batch → neu_cultivar/brand/label/bracket) table —
or at minimum surfacing Portfolio-Master data on the batch — is needed before
the app can generate T*/T*_rename-style deliverables. The HANDOFF also warns
T1 (original identity) grades from **retest** THC while T1_rename grades from
**intake** THC — deliberately different sources; never reconcile.

## 4. Locked design rules the app's documents must match (both families)

- **№** never "No." (already enforced in the app's CoQ test) ✓
- **"MK GMP Certified Facility"**, never "EU GMP" ✓ (already)
- Palette navy `#1B3A5C` + gold `#A67C2E`/`#C9A227`; bronze `#8C6B3F` only for
  CoA/iCoA "Issued" stamp; Montserrat + Roboto Mono (+ Orbitron for ImB strain
  display + doc codes). ("Decoration bleeds; text does not" — 0.3in safe frame.)
- **Signatories:** Spec/IMG/CoQ = exactly 2 — QC **Blagoj Nikolov** + QA
  **Jovana Romevska Cvetkovski**, no QP. **iCoA = 3-tier**: Analyst
  **Stojanka Pavlova** (PP-QCL-04) → Senior Analyst **Marija Trajkovska**
  (PP-QCL-02) → Head of QC **Blagoj Nikolov**. The app currently captures
  Annex-11 e-signatures generically; the iCoA flow should model the 3-tier
  chain (analyst ≠ senior ≠ HoQC) — our M5 segregation logic extends naturally.
- **Doc numbering** `CoQ-PP-YYYY-NNNN` / `iCoA-PP-YYYY-NNNN` /
  `eCoA-PP-YYYY-NNNN`, monotonic per type per year — the app's per-org minting
  (M7) matches the shape; verify the exact prefixes the app emits.
- **One A4 page per document**, type floor 6pt, tables middle-left.
- 12-parameter Ph. Eur. 3028 panel numbering (canonical): 1 Macroscopic ·
  2 Microscopic · 3 HPTLC · 4 Total Δ9-THC · 5 Total CBD · 6 Total CBN ·
  7 Foreign Matter · 8 LoD (≤12.0%, 40 °C/24 h/15–25 mbar) · 9 Micro (4 sub) ·
  10 Mycotoxins · 11 Heavy Metals · 12 Pesticides. Family wording nuance: ImB
  says **"Microbiological Purity"**; family-1 canon says "Microbiological
  Quality" — keep per-family wording, don't unify.
- Family-2 constants: Chemotype THC·CBD only; Processing Machine-Trimmed only;
  CBD column ≤1.0%; storage/shelf-life strings as in the HANDOFF; **CBN factor
  0.876** on the ImB panel (vs 0.877 for THC/CBD) — as authored.

## 5. IMG / packaging facts (owner-settled)

Spec code **QCSP-RMI-P0005-v1**, template **QCSP 002 v.01** (the
`QCSP-IMG-PRI-00x` codes are wrong — never use). Material PET 12 µm + ALU 7 µm
+ PE 80 µm = 103 µm ±5 %, 300×500 mm, blank, shelf life **1 year**, per
supplier certificate № 25044/ТЉ-01. Material Master keeps exactly 4 cells
(CAS № / Intended Use / Storage / Shelf Life). The ImB spec's Primary-Packaging
cell cites this bag verbatim (net 400.0 g ±3%). Open QA items: seal strength
≥15 N/15 mm, approval hierarchy, Al purity, OTR/WVTR.

## 6. The iCoA single-parameter series (family-1 active queue)

Series batch **P060052** (Apples & Bananas, Grade IV, THC 15:CBD 1, lab sample
PP-QCL-26-042, spec QCSP-IMB-001 v.02, linked CoQ-PP-2026-0005). Built:
0001 (§1–2), 0002 (§3), 0003 (§4–6). Queued 0004–0009 (§7–§12) pending owner
confirmation of grouping. Verified results to keep consistent: THC 16.93 %,
CBD 0.07 %, CBN N.D., LoD 6.77 %, FM 0.12 %, micro <10 CFU/g, aflatoxins
<2 µg/kg, metals <LOQ, pesticides ≤LOQ. If the app is to render iCoAs, this
is the layout + fixture set to match.

## 7. Concrete WWF work plan derived from all of the above

| # | Change | Where | Status (2026-08-14) |
|---|--------|-------|------|
| 1 | Relax ladder validation: ordered + non-overlapping (0.10-gap brackets legal, overlap 422) | `potency.py` `_validate_ladder` | **DONE** — commit "bracket-style tiers" |
| 2 | Seed the 71-strain catalogue as DRAFT (auto-create cultivars, idempotent, dry-run) | `POST /qc/potency-specs/import` + `app/data/imb_grade_ladders.json` | **DONE** |
| 3 | Batch commercial identity — full table + API + Portfolio-Master import + CoQ-detail surfacing | migration **0059** + `qc/commercial.py` | **DONE** (owner: full table) |
| 4 | iCoA 3-tier chain: **HoQC-only** approval (QP 403 on ICOA), analyst≠reviewer≠approver, signature dedup | `certificates.py` + migration **0060** | **DONE** (owner: no QP — breaking) |
| 5 | Doc-number prefixes already conform; fixed the **UTC-year** defect — numbers now carry the facility year (`SITE_YEAR_SQL`, 13 mint sites, new static guard) | `worktime.py` + qc modules | **DONE** |
| 6 | Faithful A4 HTML documents: ImB per-strain spec (owner's own archive template, tokenized) + single-parameter iCoA (design-system shell) | `qc/spec_html.py` + `app/data/imb_spec_template.html` | **DONE** (owner: HTML via FastAPI) |
| 7 | IMG packaging facts as reference (QCSP-RMI-P0005-v1, 4-cell material master) | §5 of this document | **DONE** (documented here) |

Frontend shipped with them: the `qcpotency` view (registry/approve/supersede/
import/A4 links), the CoQ compile cultivar picker (ladder freezing was
unreachable from the UI before), the commercial-identity row on the CoQ
detail, and ICOA-vs-QP button gating.

Still open (unchanged, needs owner/QA decisions): the eCoA *document* series
`PP-ECOA-` vs `eCoA-PP-`; the legacy global Engine-B sequences; signatures on
`qc_coq` rows (aggregation CoQs still render the honest no-signature block).
The archives remain the layout source of truth — masters in `documents/` and
`PROD_SPEC/`, curated copies in `Final_Docs/` (never edit curated copies).

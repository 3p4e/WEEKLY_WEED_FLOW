# The facility layout — reading the as-built ground-floor plan

Source: **`Layout Full.pdf`** — "Medical Cannabis Facility, Purely Plant, Municipality of
Petrovec, Rep. N. Macedonia. Conceptual layout, Ground floor / architectural design.
Scale 1:100. 03/2021. STRUCTURE-DOOEL, Tetovo." One A0 sheet (3370 × 2384 pt),
drawn in Archicad, supplied by the owner on 2026-09-05.

The register it produced lives at **`backend/app/data/facility_layout.json`** —
191 rooms, each with its code, both printed names, its stamped area and perimeter,
a functional zone, a regime (GACP / GMP / support) and a normalised anchor point on
the drawing.

## How the register was extracted

The drawing stamps every room with three things: a **red room code** in a box
(`C180`, `F104`, `T160`), a **blue bilingual name** (Macedonian over English), and a
black **`P:` / `A:` box** giving perimeter in metres and area in square metres. All
three are real text in the PDF, not raster, so they were read as vector text with
their coordinates rather than by looking at pixels:

1. Every character was pulled with its bounding box and regrouped into runs,
   handling the rotated (90°) labels as well as the horizontal ones.
2. Each run was classified by the colour of its ink in a 2× render — red, blue,
   black or green. Red runs matching `^(C|E|F|M|T|W)\d{1,3}[A-Za-z]?$` are the room
   codes; blue runs are names; black runs matching `P:` / `A:` are the stamps.
3. Codes printed side by side in one run (`C181 C182 C183 C184 C185`) were split
   and their x positions interpolated by character offset.
4. Areas and perimeters were taken from the stamp directly beneath each code;
   names from the nearest blue run.
5. Every room was then cross-checked by eye against magnified crops of the sheet,
   and the ambiguous ones (crowded stamps, overprinted digits) were corrected by
   hand. Those corrections are the `O` table in the build script.
6. Finally the anchors were plotted back onto the drawing and confirmed to land on
   their own room stamps.

The prefix letter is the wing: **C** cultivation, **F** flower processing,
**E** extraction and finished dosage form, **M** main entrance and personnel,
**T** technical, **W** the laundry suite.

## What the plan actually says about classification

The owner asked whether the classification is carried in colour. **It is not.**
The sheet has no cleanliness legend and virtually every room is drawn unfilled
white. The only colour legend on the sheet is a four-box waste key — chemical
waste, cultivation waste (cannabis stems), discarded materials, municipal waste —
plus a note that hydrogen peroxide is recommended.

Colour on this drawing means:

| Colour | What it marks |
|---|---|
| Red boxes and text | Room codes; also dashed fire-compartment lines |
| Blue text | Room names |
| Green linework | Benches, racking, joinery, door types `tip 1`–`tip 4` |
| Magenta blocks | `PW` pass-windows between adjoining rooms |
| Red dashed boxes | Pass boxes, tagged `Pas boks POS 1A`–`POS 6A` |
| Solid mid-grey | The protected fire-escape shafts (`PPZ` exits) |
| Pale periwinkle | `E46` quarantine for final product 2 |
| Rose/pink band | `F130` quarantine for final product 1 |
| Pale orange | The external generator compound |
| Grey with ochre diagonals | Outside the envelope — canopy at +5.40, aprons, ramps |

So the zoning has to be read from the **architecture**, not the palette, and the
architecture states it clearly: every regime change is made through an air lock
(`ТАМПОН ЗОНА` / `TAMPON ZONA`) with a paired set of doors, and every material
transfer that does not move people goes through a pass box or a `PW` pass-window.

## The zoning as built

| Zone | Rooms | Area | What it is |
|---|---:|---:|---|
| cultivation | 13 | 3 964 m² | Flowering 1.1–1.6, vegetation 1–2, mother plants, two clone rooms, seeds, sick-plant quarantine |
| technical | 18 | 2 436 m² | Seven AHU plant rooms, machine room, water treatment, substation, electrical, nitrogen, compressed air, CO₂ |
| circulation | 24 | 1 088 m² | Corridors, stairs, lifts |
| post_harvest | 9 | 668 m² | De-bucking, trimming 1–2, drying 1A/1B/1C and 2, curing 1–2 |
| personnel | 35 | 526 m² | Wardrobes, toilets, canteen, security, offices, BMS/EMS control room |
| warehouse | 17 | 502 m² | Incoming materials, dry-flower store and its quarantine, finished-product stores, packaging material |
| production | 10 | 395 m² | Extraction, purification, grinding and decarboxylation, FDF 1–3, primary and secondary packaging |
| utility | 25 | 370 m² | Stores, washing rooms, clean-equipment rooms, laundry |
| airlock | 17 | 133 m² | The regime boundaries themselves |
| quality | 9 | 78 m² | Three in-process control laboratories, sampling premises |
| waste | 5 | 63 m² | Four separate garbage exits |
| egress | 8 | 58 m² | `PPZ` fire escapes, rated 60 or 90 minutes |

### The GACP → GMP boundary

The owner already stated the operational rule: *"harvest, cure and defoliating end
of GACP → start of GMP process."* The building agrees with it. Live plants live in
the C wing; the first room that handles cut material is the de-bucking premise
`C153`, and everything downstream of it — trimming, drying, curing, extraction,
packaging, warehousing — sits in the F and E wings behind an air lock.

The crossing point on the drawing is the staircase `C144` and air lock `F102`:
west of it the codes are `C`, east of it they are `F`.

The register therefore marks each room with a `regime`:

- **GACP** — 31 rooms: the cultivation wing and its own corridors, stores, locks
  and sampling rooms.
- **GMP** — 69 rooms: post-harvest, production, quality, warehousing and the locks
  and washing rooms serving them.
- **SUPPORT** — 90 rooms: plant rooms, personnel areas, circulation, waste and
  fire escapes, which sit under neither regime.

### The clean-side / dirty-side discipline the plan encodes

Four patterns repeat across the building and are worth naming, because they are
what a cleanliness classification would formalise:

1. **Changing cascades.** `F124 → F125 → F126 → F127` off hall `F123`, then
   `F121` / `F122` beyond; `F93` / `F94` behind air lock `F91`; `E21` / `E22`,
   `E50` / `E51`, `E75` / `E76`, `C15` / `C16`. Male and female cells are paired at
   every step, so the gowning sequence is graded, not single-stage.
2. **Wash / clean-equipment couples.** `F116` clean equipment beside `F117` washing
   room; `E42` beside `E43`. Dirty in one side, clean out the other.
3. **Pass-through transfer.** Magenta `PW` pass-windows at `F97`, `F119` into
   laboratory `F120`, `E82` into the grinding and decarboxylation room `E83`, `E43`
   and `F130`; red-dashed pass boxes `POS 1A`–`POS 6A` set into the walls of the
   main hall `M11`, the laundry `W18`, curing `F108` and secondary packaging `F129`.
4. **Mirrored dispatch trains.** `F130 → F131 → F132` and `E46 → E47 → E48`:
   quarantine, then warehouse, then a final-product exit lock through the east wall.
   Both quarantine slots are the only two rooms on the sheet given a solid colour.

### Cleanliness grades — not on the drawing

No grade (A/B/C/D, ISO class, or "CNC") appears anywhere on the sheet. Assigning
them is a QA decision, not something that can be read out of the architecture, so
the register deliberately does **not** invent one. What the register carries is the
`regime` and the `zone`; a `grade` column can be added once QA states the
classification, and the air-lock topology above is the evidence base for it.

**[NEEDS INPUT]** Which classification scheme does the site's validation master plan
use, and what grade is assigned to each of: cultivation rooms, drying and curing,
trimming and de-bucking, extraction and FDF production, packaging, the in-process
control laboratories, and the finished-product warehouses?

## Cultivation capacity, as drawn

Each grow room is stamped twice: the gross room area and, below it, a smaller net
figure — the cultivation area.

| Room | Name | Gross | Net |
|---|---|---:|---:|
| C180 | Flowering premise 1.1 | 501.38 m² | 416.00 m² |
| C181 | Flowering premise 1.2 | 501.38 m² | 416.00 m² |
| C182 | Flowering premise 1.3 | 501.38 m² | 416.00 m² |
| C183 | Flowering premise 1.4 | 501.38 m² | 416.00 m² |
| C184 | Flowering premise 1.5 | 508.36 m² | 416.00 m² |
| C185 | Flowering premise 1.6 | 501.38 m² | 416.00 m² |
| C178 | Vegetation premise 1 | 249.99 m² | 198.00 m² |
| C179 | Vegetation premise 2 | 249.93 m² | 198.00 m² |
| C171 | Mother plants premise | 317.86 m² | 245.44 m² |
| C176 | Clones premise 1 | 54.24 m² | — |
| C177 | Clones premise | 54.30 m² | — |

Six flowering rooms of equal net area confirms the owner's phase plan: flowering
runs 6–9 weeks *"in one of the 6 available flowering rooms"*. There are **two**
clone rooms, not one, and **two** vegetation rooms.

Post-harvest capacity is likewise doubled: drying rooms `F104` / `F105` / `F106`
(98 m² each) plus `E81` (41 m²), curing `F108` (73 m²) and `E90` (24 m²), trimming
`F96` (96 m²) and `E80` (92 m²).

## Known gaps in the register

- **`E34`** (44.00 m² / 29.88 m) has no name that could be attributed with
  confidence. It sits in the purification row and contains vacuum filtration, a
  magnetic stirrer and a short-path distillation unit.
- **`C88`** (seeds premise) has a legible perimeter of 11.29 m but its area digits
  are overprinted by the code box, so the area is left null rather than guessed.
- **`E35` / `E36` / `E37`** map to purification, FDF 1 and FDF 2 by column position;
  the drawing also names an **FDF 3** production premise whose code could not be
  separated from its neighbours. The `E38` = primary packaging 2 reading is likewise
  positional.
- Two wardrobe cells near the laundry show only the numerals `29` and `30` in their
  code boxes (4.91 m² / 10.49 m each) and are not in the register.
- The English on the sheet carries the draughtsman's own spellings —
  `TECHICAL ROOM FOR AHU`, `MATHER PLANTS PREMISE`, `LABARATORIJA`,
  `PREMISE FOR CLEAN EQUIPMNT`, `WARDEROBE`. The register normalises these to
  `TECHNICAL`, `MOTHER PLANTS`, `IN PROCESS CONTROL LABORATORY`,
  `PREMISE FOR CLEAN EQUIPMENT`, `WARDROBE`; the raw forms are in this note.

## Fire compartmentation

The plan marks fire-rated doors along the corridors as `PPZ 60min` and the escape
shafts as `PPZ 90min`, with red dashed lines showing the compartment boundaries
running across the flowering halls and the drying rooms. Four separate waste exits
and eight `PPZ` escapes discharge directly to the outside. This is recorded here
because it constrains where a batch can physically move, but it is not modelled in
the register yet.

## How the app carries it

**`facility_rooms`** (migration tasks 0068) holds the register: code, both names,
wing, zone, regime, grade, area, net area, perimeter, the plan anchor, the
department that runs the room, and a note. It is deliberately not `rooms`:
`rooms` is the short list of places the app schedules a batch into, keyed by a
lowercase slug; `facility_rooms` is the whole building, keyed by the architect's
code. `rooms.facility_room_id` links one to the other, and either can exist
without the other.

**`/facility/layout`** (`backend/app/api/facility_layout.py`):

| Route | Who | What |
|---|---|---|
| `GET /facility/layout` | every role above base USER | the register, filterable by zone, wing, regime or a text query, with per-zone room counts and areas |
| `GET /facility/layout/{id}` | same | one room, plus the batches currently in the operational room it is linked to |
| `PATCH /facility/layout/{id}` | ADMIN, executives, QA | the judgement columns only: regime, grade, zone, department, the room link, a note |
| `POST /facility/layout/import` | ADMIN, executives | loads the packaged register; idempotent on the room code, and it never overwrites a classification somebody made |

The code, name, area, perimeter and anchor are not editable through the API.
They are what the sheet says, and a correction belongs in the register, not in a
per-room edit that would leave the app quietly disagreeing with the drawing.

**The board.** The Facility view has two tabs: *Rooms*, the live occupancy board
that was already there, and *Floor plan*. The plan tab renders
`web/assets/facility-ground-floor.png` — the sheet itself, cropped to exactly
the bounds the anchors were normalised against — with one pin per room placed at
`plan_x` / `plan_y` in percent. Because both sides use the same bounds, the pins
and the drawing stay aligned at every zoom with no arithmetic in the view. Pins
are coloured by zone, the legend doubles as a zone filter with room counts and
areas, a search narrows both pins and roster, and clicking a pin opens the room:
its two names, the stamped areas and perimeter, the zone and regime, the
cleanliness grade (or "not classified"), the department, and whatever is growing
in it right now.

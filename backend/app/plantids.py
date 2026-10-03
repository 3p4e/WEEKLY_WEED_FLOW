"""Identity strings the facility prints on things — composed here, nowhere else.

Pure functions, no database, so the conventions the owner stated on 2026-09-05
live in one place and every caller (the catalogue import, the mother bank, the
plant fill, the A4 product page) composes the same string the same way.

PRODUCT (the ImB Product Specification, one page per product):
    <ABBR>_THC<nominal>:CBD1          GP_THC26:CBD1
  window = nominal ± 10 % relative, printed to two decimals as
  nominal × 0.90 … nominal × 1.10 − 0.01 (26 → 23.40 – 28.59 %; 8 → 7.20 – 8.79 %).

MOTHER PLANT:
    <ABBR><grade>_S<campaign>M<mother_no>-<generation>_<stock_no>
    GP26_S1M03-2_020
  GP26 = strain abbreviation + potency grade (the product's nominal); S1 = the
  selection campaign, numbered facility-wide; M03 = mother plant number 03 of
  that campaign; -2 = the mother's own generation (second-generation clone from
  the initial mother); _020 = mother-plant clone number 20 in stock.

CLONE (a plant cut from a known mother):
    <mother>-<cutting>.<clone>       GP26_S1M03-2_020-03.147
  03 = the third cutting event from that mother; 147 = the 147th clone of that
  cutting. A mother is cut 6–9+ times, 200–300 clones each, so the clone number
  is per cutting (001–999) and the cutting number tells them apart (01–99).

LEGACY PLANT (no known mother — imported clones, seed):
    <clone-date>_<batch code>_<seq>   20260706_GP072501_0001
  The middle segment is the BATCH CODE, not the cultivar: the batch code is
  unique per org and already starts with the cultivar abbreviation, so two
  batches of one cultivar cloned on the same day (the normal plan — one
  cultivar per flowering room) get distinct ids by construction. Until the
  2026-09-27 review the segment was the cultivar, and the second batch's fill
  collided on plants_org_id_plant_code_key at its first chunk (CS-02).
"""
import re
from datetime import date

PRODUCT_CODE_RE = re.compile(r"^([A-Z][A-Z0-9]{1,11})_THC(\d+(?:\.\d+)?):CBD(\d+(?:\.\d+)?)$")


def window_for(nominal: float) -> tuple[float, float]:
    """REFERENCE ONLY — the window the issued ImB pages (QCSP 001 v.03) print:
    nominal ± 10 % relative, two decimals, upper bound nominal × 1.10 − 0.01.

    Owner decision 2026-09-18: the flat ±10 % rule is retired as a grading
    method — "the fitted approach is applicable everywhere". Nothing in the
    app derives a product window from a nominal any more: POST /qc/products,
    /qc/products/ladder and both importers store the window they are given,
    and ±10 % survives only as the CEILING a window may not exceed
    (products._TOLERANCE_CEILING). This function describes what the v.03
    pages say, for tests and provenance; it must not be used to create one."""
    n = float(nominal)
    return round(n * 0.9, 2), round(round(n * 1.1, 2) - 0.01, 2)


def grade_str(grade) -> str:
    """26 → '26', 28.5 → '28.5' — the potency grade as the ID prints it."""
    g = float(grade)
    return str(int(g)) if g == int(g) else f"{g:g}"


def product_code(acronym: str, grade, cbd=1) -> str:
    return f"{acronym}_THC{grade_str(grade)}:CBD{grade_str(cbd)}"


def acronym_of(code: str) -> str | None:
    m = PRODUCT_CODE_RE.match(code or "")
    return m.group(1) if m else None


def mother_code(acronym: str, grade, campaign_seq: int, mother_no: int,
                generation: int, stock_no: int) -> str:
    return (f"{acronym}{grade_str(grade)}_S{int(campaign_seq)}M{int(mother_no):02d}"
            f"-{int(generation)}_{int(stock_no):03d}")


def clone_code(mother: str, cutting_no: int, clone_no: int) -> str:
    return f"{mother}-{int(cutting_no):02d}.{int(clone_no):03d}"


def legacy_plant_code(day: date, batch_code: str, seq: int) -> str:
    """<clone-date>_<batch code>_<seq>. The batch code, not the cultivar, is
    what makes this unique across two batches cloned the same day."""
    return f"{day.strftime('%Y%m%d')}_{batch_code}_{int(seq):04d}"


# Sequence caps the facility's conventions impose. Every check that refuses a
# number past one of these reads the cap from here, so the message, the
# suggestion and the schema CHECK cannot drift apart.
MAX_BATCH_SEQ = 99        # GP092699 is the last batch of GP in 09/26
MAX_MOTHER_NO = 99        # M99 (mother_plants_mother_no_check)
MAX_STOCK_NO = 999        # _999 (mother_plants_stock_no_check)
MAX_GENERATION = 9        # -9 — one bound for typed and parent-derived generations
MAX_CUTTING_NO = 99       # -99. (clone_run_mothers_cutting_no_check); see CS-11
MAX_CLONE_NO = 999        # .999 (plants_clone_no_check)

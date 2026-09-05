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
    <clone-date>_<ABBR>_<seq>         20260706_GP_0001   (migration 0045)
"""
import re
from datetime import date

PRODUCT_CODE_RE = re.compile(r"^([A-Z][A-Z0-9]{1,11})_THC(\d+(?:\.\d+)?):CBD(\d+(?:\.\d+)?)$")


def window_for(nominal: float) -> tuple[float, float]:
    """The printed acceptance window of a product: nominal ± 10 % relative."""
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


def legacy_plant_code(day: date, cultivar_code: str, seq: int) -> str:
    return f"{day.strftime('%Y%m%d')}_{cultivar_code}_{int(seq):04d}"

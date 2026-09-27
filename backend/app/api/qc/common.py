from app.deps import uuid_or_404
from app.roles import ADMIN, EXECUTIVE_ROLES
from app.worktime import SITE_YEAR_SQL
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import APIRouter, HTTPException
import re
import uuid


router = APIRouter(prefix="/qc", tags=["qc"])


_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "QC_MGR", "QP")


_QP_ROLES = (ADMIN, "QP")


_COQ_ROLES = (ADMIN, "QC_MGR")


def _uuid_or_404(value, what: str = "Resource") -> None:
    """A malformed {id} path segment must be a clean 404, not a 500 from asyncpg
    trying to cast it to a uuid inside the lookup query (mirrors auth._require_uuid)."""
    uuid_or_404(value, f"{what} not found")


def _uuid_or_422(value, field: str) -> None:
    """A user-supplied uuid BODY field (cross-DB actor refs have no FK to catch a
    bad value) must 422 on a malformed id rather than 500 on the insert."""
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(422, f"{field} must be a valid id")


_HOQC = (ADMIN, "QC_MGR", "QP")


def _dec(value) -> Decimal | None:
    """Exact Decimal form of a measurement or a limit, whatever the caller
    holds it as. A float goes through `str()` first: `Decimal(23.4)` is the
    binary expansion 23.39999999999999857…, which is exactly the comparison
    bug this exists to remove, while `Decimal("23.4")` is the number the lab
    wrote. A DB `numeric` arrives as Decimal already and passes through."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        # A `numeric` column that a float was bound into carries the float's
        # full binary expansion (asyncpg encodes 23.4 as 23.399999999999998578…),
        # so a row written before values were bound as Decimal reads back with
        # a 50-digit tail — and a value of exactly 23.4 then fails an upper
        # limit "23.4". No laboratory reports more than 15 significant digits;
        # a longer tail is that artefact and is read back through the float
        # it came from, which is the number that was meant.
        if len(value.as_tuple().digits) > 15:
            return Decimal(repr(float(value)))
        return value
    if isinstance(value, float):
        d = Decimal(repr(value))
        # 10.0 is the number 10: keep an integral float integral, so a limit
        # of 10 stores and prints as "10", as it did when asyncpg encoded the
        # float itself, not as "10.0".
        return d.to_integral_value() if d == d.to_integral_value() else d
    return Decimal(str(value))


def _evaluate(value, lo, hi):
    """Return (complies, status). Unknown when there's no numeric value to
    judge — GxP: we never invent a verdict for a missing measurement.

    Compared as Decimal (review 2026-09-27 QC-05). The limits of a
    specification parameter are `numeric` columns and arrive as Decimal; the
    value arrives as a float from the request or as Decimal from a `numeric`
    column depending on the path. Python compares float and Decimal EXACTLY,
    so `23.4 >= Decimal("23.4")` is False and a lab reporting exactly the
    limit — the ordinary case for LOQ-style limits — was graded FAIL on the
    eCoA path while the iCoA path (which cast the limits to float first)
    graded the same value PASS. Every path now grades the same way."""
    v = _dec(value)
    if v is None:
        return None, "unknown"
    lo_d, hi_d = _dec(lo), _dec(hi)
    ok = (lo_d is None or v >= lo_d) and (hi_d is None or v <= hi_d)
    return ok, ("pass" if ok else "fail")


# Ph. Eur. 3028: total = neutral + 0.877 × acid. The 0.877 factor is the molar
# mass ratio THC/THCA (314.5 / 358.5). Held as a Decimal so the sum is exact.
ACID_FACTOR = Decimal("0.877")


_TOTAL_PLACES = Decimal("0.01")


def derived_total(neutral, acid) -> Decimal:
    """THE Total Δ9-THC / Total CBD computation (review 2026-09-27 QC-10,
    QC-20) — one function, used by every path that derives a total.

    total = neutral + 0.877 × acid, computed in Decimal and rounded HALF-UP to
    two places, which is how the pharmacopoeial figure is reported. Python's
    `round()` on a binary float resolved ties on the binary representation
    instead: 1.47 + 0.877 × 25.00 = 23.395 exactly, which `round(…, 2)` gave
    as 23.39 — below the 23.40 window minimum the catalogue prints — and
    0.04 + 0.877 × 15.00 = 13.195 came out 13.19, inside a 13.19 maximum the
    correct 13.20 is outside of. Two of the three grading paths rounded that
    way and the third certified whatever the lab had transcribed."""
    a, b = _dec(neutral), _dec(acid)
    if a is None or b is None:
        raise ValueError("derived_total needs both component values")
    return (a + ACID_FACTOR * b).quantize(_TOTAL_PLACES, rounding=ROUND_HALF_UP)


_NUM_TOKEN = re.compile(r"^[+-]?[0-9][0-9 .,  ']*$")


def parse_lab_number(raw, decimal_separator: str = ".") -> Decimal | None:
    """Read the number a laboratory printed, under THAT laboratory's decimal
    convention (review 2026-09-27 QC-03).

    Returns the Decimal for a plain point value, None for text that is not a
    number at all ("Complies", "< LOQ", "n.d." — no measurement to grade), and
    raises ValueError for text that LOOKS numeric but is not well-formed under
    the given separator: "0,6" read by a "." laboratory has a comma that can
    be neither the decimal mark nor a thousands group. The client used to
    `parseFloat("0,6")` that to 0 and the server believed it, so a lead result
    of 0,6 mg/kg against a ≤ 0.5 limit was graded as conforming and printed
    as "0,6" under "Conforms to Specification". Guessing is worse than
    refusing: an ambiguous figure is sent back to the transcriber.

    Accepted shapes (sep = ","): "22,61" · "1.234,5" · "1 234,5" · "22" ·
    "22,61 %" (a trailing unit is ignored). A leading comparator ("< 0,5")
    is a bound, not a point value, and reads as None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if decimal_separator not in (".", ","):
        raise ValueError("decimal_separator must be '.' or ','")
    # strip a trailing unit ("22,61 %", "0.6 mg/kg") — anything after the
    # numeric token; a leading comparator/qualifier means "not a point value".
    m = re.match(r"^([+-]?[0-9][0-9 .,  ']*?)\s*(?:[%‰a-zA-Zµμ°/].*)?$", s)
    if not m:
        return None
    tok = m.group(1).strip()
    if not _NUM_TOKEN.match(tok):
        return None
    group = "." if decimal_separator == "," else ","
    esc_group, esc_dec = re.escape(group), re.escape(decimal_separator)
    # digits, optionally grouped in threes by the OTHER separator / a space,
    # then an optional decimal part under THIS separator.
    grouped = rf"^[+-]?\d{{1,3}}(?:(?:{esc_group}|[   '])\d{{3}})+(?:{esc_dec}\d+)?$"
    plain = rf"^[+-]?\d+(?:{esc_dec}\d+)?$"
    if not (re.match(plain, tok) or re.match(grouped, tok)):
        raise ValueError(
            f"'{s}' is not a number under the laboratory's decimal separator"
            f" '{decimal_separator}' — check the laboratory's separator setting or the"
            " transcribed value")
    cleaned = re.sub(r"[   ']", "", tok).replace(group, "")
    if decimal_separator == ",":
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:   # pragma: no cover — the regexes above exclude it
        raise ValueError(f"'{s}' is not a number")


def reconcile_numeric(raw_value, numeric_value, decimal_separator: str = ".",
                      field: str = "numeric_value"):
    """The numeric of record for a transcribed line: derived from the raw text
    on the server, never taken on the client's word (QC-03).

    - raw parses → its value is authoritative; a supplied numeric must agree
      (to 1e-9) or the request is refused with 422.
    - raw is non-numeric text ("< LOQ") → no point value exists; a supplied
      numeric would be an invented measurement → 422.
    - no raw text → the supplied numeric (if any) stands.
    - raw malformed under the separator → 422 (see parse_lab_number).
    Returns a Decimal or None. Decimal, never float: asyncpg binds a float
    into a `numeric` column as its binary expansion (1.47 becomes
    1.469999999999999973…), which is how a Ph. Eur. total of exactly 23.395
    came out as 23.39 even after the rounding was fixed (QC-20)."""
    try:
        parsed = parse_lab_number(raw_value, decimal_separator)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if parsed is None:
        if numeric_value is not None and raw_value is not None and str(raw_value).strip():
            raise HTTPException(
                422, f"{field} {numeric_value} was supplied but the transcribed text"
                     f" '{str(raw_value).strip()}' is not a point value — a number cannot be"
                     " graded that the source certificate does not state")
        return _dec(numeric_value)
    if numeric_value is not None and abs(_dec(numeric_value) - parsed) > Decimal("1e-9"):
        raise HTTPException(
            422, f"{field} {numeric_value} disagrees with the transcribed text"
                 f" '{str(raw_value).strip()}' (reads as {parsed} under the laboratory's"
                 f" '{decimal_separator}' decimal separator)")
    return parsed


def norm_batch(value):
    """Batch identifiers are compared as free text by every OOS and CoQ gate
    (review 2026-09-27 QC-27). An OOS filed as 'p050022' did not block a CoQ
    for 'P050022'. Written upper-cased and trimmed so equality is equality;
    the gates additionally compare case-insensitively for rows that predate
    this rule."""
    if value is None:
        return None
    return " ".join(str(value).split()).upper()


async def mint_series_number(c, org_id, table: str, column: str, prefix: str,
                             width: int = 4) -> str:
    """Advisory-locked per-(org, year) sequential document number, reset to
    0001 each 1 January — gap-free within the lock, never reused. This is the
    M7 pattern that _mint_oos_number / _mint_doc_number / _mint_cert_number
    established; review 2026-09-27 QC-28 found the remaining series (PP-SPEC,
    PP-SMP, PP-SPL, PP-LAB, PP-SFR, PP-WT, PP-STB, PP-TRN) still drawn from
    global `nextval()` sequences shared across every tenant that never reset
    and burned a number on every rolled-back insert. `table`/`column`/`prefix`
    are module constants at every call site, never request input."""
    yr = await c.fetchval(f"SELECT {SITE_YEAR_SQL}")  # facility year, not UTC  # nosec B608
    await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"{prefix}:{org_id}:{yr}")
    seq = await c.fetchval(
        f"SELECT coalesce(max((regexp_match({column}, '-([0-9]+)$'))[1]::int), 0) + 1"  # nosec B608 — identifiers are module constants
        f" FROM {table} WHERE org_id=$1 AND {column} LIKE $2 || '-' || $3 || '-%'",
        org_id, prefix, yr)
    return f"{prefix}-{yr}-{seq:0{width}d}"


def _norm_unit(u) -> str:
    return " ".join((u or "").split()).lower()


def check_derived_total_units(p: dict, ra: dict, rb: dict) -> None:
    """Ph. Eur. 3028 derives total = neutral + 0.877 × acid. The 0.877 factor is a
    molar-mass ratio (THC/THCA), NOT a unit conversion, so the sum is only
    meaningful when both component results share ONE unit — % + % or mg/g + mg/g,
    never % + mg/g. A total summed across mixed units is a scientifically
    meaningless number that would be certified as conformance, so refuse it rather
    than emit it. The derived value is reported in the computed parameter's declared
    unit, so that must agree with the components too. Raises 409 on any mismatch."""
    ua, ub, up = _norm_unit(ra.get("unit")), _norm_unit(rb.get("unit")), _norm_unit(p.get("unit"))
    name = p.get("test_name_en") or p.get("test_name_mk") or "computed total"
    if ua != ub:
        raise HTTPException(
            409, f"'{name}' cannot be derived: its components are recorded in different"
                 f" units ({ra.get('unit') or '—'} vs {rb.get('unit') or '—'}) — Ph. Eur. 3028"
                 " sums them directly, so both must be expressed in the same unit")
    if up and ua and up != ua:
        raise HTTPException(
            409, f"'{name}' is declared in {p.get('unit')} but its components are recorded in"
                 f" {ra.get('unit')} — the derived total must be reported in its components' unit")


def _lab_verdict_bool(v: str | None) -> bool | None:
    """Best-effort reading of the lab's stated verdict for the reconciliation
    flag. Deliberately conservative: anything ambiguous returns None and no
    mismatch is computed — the flag must never manufacture a disagreement."""
    if not v:
        return None
    t = v.strip().lower()
    # "Not applicable" / "not tested" / "n/a" assert NO verdict at all — they
    # contain the substring "not" and would otherwise fall into the fail
    # branch below and normalize to an explicit lab FAIL, which could
    # manufacture a false reconciliation mismatch. Must be excluded first.
    if any(p in t for p in ("not applicable", "not tested", "not performed", "n/a")):
        return None
    if t in ("no", "не") or any(n in t for n in ("not", "non", "fail", "oos", "не ")):
        return False
    if any(p in t for p in ("pass", "conform", "compl", "задоволува", "соодветств")):
        return True
    return None


_SAMPLE_KINDS = ("PC", "MB", "EXT", "RET", "STAB", "RT", "CC")


# custody.py's registrar gate is the same Head-of-QC role set as every other
# _HOQC gate in this package — alias, never a second literal tuple, so a
# future role-model change to one can't silently leave the other behind.
_QC_REGISTRAR = _HOQC


def splice_stamps(fields: list[str], args: list, extra_sql: list[str], extra_args: list):
    """Append actor-stamp fragments to a positional-parameter UPDATE.

    `extra_sql` fragments carry the literal token PLACEHOLDER where a `$n`
    belongs; `n` is only knowable once the fragment's value has been appended to
    `args`, which is why this cannot just be built inline with the rest.
    Fragments WITHOUT the token (e.g. "phase_ii_completed_at=now()") consume no
    argument and pass through untouched.

    Factored out of certificates.py and oos.py, which had grown two copies.
    They were not equivalent: certificates.py used
    `zip(extra_sql, extra_args)`, which is only correct while every fragment
    happens to carry a placeholder — adding one no-placeholder fragment there
    would have silently mis-paired every value after it against the wrong
    column, with no error. oos.py's token-checking form is the correct one and
    is what this keeps. Mutates `fields`/`args` in place, as both call sites do
    throughout.
    """
    pending = list(extra_args)
    for frag in extra_sql:
        if "PLACEHOLDER" in frag:
            args.append(pending.pop(0))
            fields.append(frag.replace("PLACEHOLDER", str(len(args))))
        else:
            fields.append(frag)
    if pending:
        raise ValueError(
            f"splice_stamps: {len(pending)} stamp value(s) had no PLACEHOLDER fragment"
        )

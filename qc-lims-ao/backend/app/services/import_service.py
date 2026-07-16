"""
Import service — XLSX catalog parser ported from CoA_TRACK.

Parses 'List of COAs.xlsx' using stdlib zipfile + xml.etree only — no openpyxl.
Expected Excel structure (row 3 = header):
  A: Customer (E, B, A, or blank)
  B: Row number
  C: Strain name
  D: Batch code (e.g., CJ1024 - R&D)
  E: Quantity (kg)
  F: THC (%) — text like "THC - 23%"
  G: Batch number / Production batch
  H: COAs status (YES or blank)

AC-08: parse_xlsx() returns list of dicts on valid XLSX, raises FileNotFoundError
on missing file, raises ValueError on corrupt file.
"""
import os
import re
import zipfile
import xml.etree.ElementTree as ET

_NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_letter(ref: str) -> str:
    """Extract column letter from cell ref like 'A4' → 'A'."""
    return re.match(r"([A-Z]+)", ref).group(1) if ref else ""


def _parse_thc(raw: str) -> float | None:
    """Parse THC from 'THC - 23%' or 'THC - 21.80%' → float."""
    m = re.search(r"([\d.]+)\s*%?", raw)
    return float(m.group(1)) if m else None


def _parse_qty(raw: str) -> float | None:
    """Parse quantity — skip '-' or blanks."""
    raw = raw.strip()
    if not raw or raw == "-" or raw.startswith("-"):
        return None
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def parse_xlsx(path: str) -> list[dict]:
    """
    Parse the XLSX catalog file using stdlib only.

    Returns list of dicts with keys:
      customer, strain_name, batch_code, quantity_kg, thc_percent,
      production_batch, coa_status

    AC-08: Raises FileNotFoundError if file missing, ValueError if corrupt.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Catalog not found: {path}")

    z = zipfile.ZipFile(path)

    # Read shared strings
    ss_xml = z.read("xl/sharedStrings.xml")
    ss_root = ET.fromstring(ss_xml)
    strings = []
    for si in ss_root.findall(".//s:si", _NS):
        parts = [t.text or "" for t in si.findall(".//s:t", _NS)]
        strings.append("".join(parts))

    # Read sheet1
    sheet_xml = z.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet_xml)
    rows = root.findall(".//s:sheetData/s:row", _NS)

    results: list[dict] = []

    # Data starts at row 4 (index 3), header at row 3
    for row in rows:
        row_num = int(row.get("r", "0"))
        if row_num < 4:  # skip title + header rows
            continue

        cells: dict[str, str] = {}
        for c in row.findall("s:c", _NS):
            ref = c.get("r", "")
            typ = c.get("t", "")
            val_el = c.find("s:v", _NS)
            val = val_el.text if val_el is not None else ""
            if typ == "s" and val.isdigit():
                idx = int(val)
                val = strings[idx] if idx < len(strings) else val
            cells[_col_letter(ref)] = val.strip() if val else ""

        strain_name = cells.get("C", "").strip()
        if not strain_name:
            continue  # skip empty rows

        batch_code = cells.get("D", "").strip()
        production_batch = cells.get("G", "").strip()
        coa_raw = cells.get("H", "").strip().upper()

        results.append({
            "customer": cells.get("A", "").strip() or None,
            "strain_name": strain_name,
            "batch_code": batch_code,
            "quantity_kg": _parse_qty(cells.get("E", "")),
            "thc_percent": _parse_thc(cells.get("F", "")),
            "production_batch": production_batch if production_batch and production_batch != "0" else None,
            "coa_status": "YES" if coa_raw == "YES" else "pending",
        })

    z.close()
    return results

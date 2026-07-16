"""
Specification DOCX Ingestion Service (P1).

Parses approved specification DOCX files (QCSP-FP-001, QCSP-IMB-001, etc.)
and creates Specification + SpecParameter records in the LIMS database.

Idempotent: skips if spec_number already exists.
Per QCSOP 010 §6.6: QCSP-[TYPE]-[NNN]-v[VV] numbering.
"""

import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.specification import (
    Specification,
    SpecParameter,
    SpecStatus,
    SpecParameterType,
    TestLocation,
)
from app.services.spec_numbering_service import get_next_spec_number_async


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_SPEC_DOCX_DIR = Path("/a0/usr/uploads")

# Default operational limit factor: 90% of release range (tightened inward)
# For bounded: op_min = rel_min + 10% of range, op_max = rel_max - 10% of range
# For max-only: op_max = rel_max * 0.9
# For min-only: op_min = rel_min * 1.1
DEFAULT_OP_FACTOR = 0.1  # 10% inward from release limits

# Regex to extract QCSP number from filename or document header
# Matches QCSP-FP-001, QCSPFP001, QCSP-IMB-001, QCSPIMB001
QCSP_NUMBER_RE = re.compile(r"(QCSP[-]?[A-Z]{0,3}[-]?\d{3,})", re.IGNORECASE)

# Known spec files and their metadata
KNOWN_SPECS = [
    {
        "filename": "QCSPFP001_Product_Specification.docx",
        "material_code": "FP-001",
        "material_name_en": "Dried Cannabis Flower",
        "material_name_mk": "Сушен цвет од канабис",
        "spec_type_code": "FP",  # Finished Product
    },
    {
        "filename": "QCSPIMB001_Product_Specification.docx",
        "material_code": "IMB-001",
        "material_name_en": "Incoming Material B",
        "material_name_mk": "Влезен материјал Б",
        "spec_type_code": "IMB",  # Incoming Material B
    },
]


# ── DOCX Parsing ──────────────────────────────────────────────────────────────

class SpecTableParser:
    """Parse specification parameter tables from DOCX."""

    def __init__(self, doc: Document):
        self.doc = doc
        self.params: list[dict] = []

    def parse(self) -> list[dict]:
        """Extract all parameter tables from the document."""
        for table in self.doc.tables:
            self._parse_table(table)
        return self.params

    def _parse_table(self, table: Table) -> None:
        """Parse a single table looking for parameter rows."""
        if len(table.rows) < 2:
            return

        # Detect header row
        header_row = table.rows[0]
        headers = [cell.text.strip().lower() for cell in header_row.cells]

        # Map known header patterns
        col_map = self._map_columns(headers)
        if not col_map:
            return  # Not a parameter table

        for row in table.rows[1:]:
            cells = [cell.text.strip() for cell in row.cells]
            if len(cells) < 3:
                continue

            param = self._extract_param(cells, col_map)
            if param and param.get("test_name_en"):
                self.params.append(param)

    def _map_columns(self, headers: list[str]) -> dict[str, int]:
        """Map column names to indices based on header text."""
        mapping = {}
        for i, h in enumerate(headers):
            if any(k in h for k in ("test", "parameter", "analysis")):
                mapping["test_name"] = i
            elif any(k in h for k in ("method", "reference")):
                mapping["method"] = i
            elif any(k in h for k in ("limit", "specification", "spec")):
                if "min" in h or "lower" in h:
                    mapping["limit_min"] = i
                elif "max" in h or "upper" in h:
                    mapping["limit_max"] = i
                else:
                    mapping["limits"] = i
            elif any(k in h for k in ("unit", "measure")):
                mapping["unit"] = i
            elif any(k in h for k in ("pharmacopoeia", "ph.")):
                mapping["pharmacopoeia"] = i

        # Need at least test name and some limit info
        if "test_name" not in mapping:
            return {}
        return mapping

    def _extract_param(self, cells: list[str], col_map: dict) -> dict | None:
        """Extract a single parameter from table cells."""
        test_name = cells[col_map.get("test_name", 0)]
        if not test_name or test_name.lower() in ("test", "parameter", "analysis"):
            return None

        method = cells[col_map.get("method", 1)] if "method" in col_map else ""
        unit = cells[col_map.get("unit", 2)] if "unit" in col_map else ""
        pharmacopoeia = cells[col_map.get("pharmacopoeia", -1)] if "pharmacopoeia" in col_map else ""

        # Parse limits
        limit_min = None
        limit_max = None

        if "limits" in col_map:
            limit_text = cells[col_map["limits"]]
            limit_min, limit_max = self._parse_limit_text(limit_text)
        else:
            if "limit_min" in col_map:
                limit_min = self._parse_number(cells[col_map["limit_min"]])
            if "limit_max" in col_map:
                limit_max = self._parse_number(cells[col_map["limit_max"]])

        # Default operational limits: 90% inward from release limits
        op_min, op_max = None, None
        if limit_min is not None and limit_max is not None:
            range_val = limit_max - limit_min
            op_min = limit_min + (range_val * DEFAULT_OP_FACTOR)
            op_max = limit_max - (range_val * DEFAULT_OP_FACTOR)
        elif limit_max is not None:
            op_max = limit_max * (1 - DEFAULT_OP_FACTOR)
        elif limit_min is not None:
            op_min = limit_min * (1 + DEFAULT_OP_FACTOR)

        return {
            "test_name_en": test_name,
            "test_name_mk": test_name,  # Will be translated if bilingual table found
            "test_method": method or "Ph. Eur.",
            "spec_type": self._infer_spec_type(limit_min, limit_max),
            "lower_limit": limit_min,
            "upper_limit": limit_max,
            "unit": unit or "% w/w",
            "pharmacopoeia_ref": pharmacopoeia or "",
            "release_limit_min": limit_min,
            "release_limit_max": limit_max,
            "operational_limit_min": op_min,
            "operational_limit_max": op_max,
            "test_location": TestLocation.IN_HOUSE.value,
            "compendial": True,
            "sorting_order": len(self.params),
        }

    def _parse_limit_text(self, text: str) -> tuple[Optional[float], Optional[float]]:
        """Parse limit text like '≤ 10.0' or '5.0 – 15.0' or 'NMT 0.2'."""
        text = text.strip().replace("–", "-").replace("—", "-")

        # Range pattern: "5.0 - 15.0" or "5.0–15.0"
        range_match = re.search(r"([0-9]+\.?[0-9]*)\s*[-–]\s*([0-9]+\.?[0-9]*)", text)
        if range_match:
            return float(range_match.group(1)), float(range_match.group(2))

        # Max only: "≤ 10.0", "NMT 10.0", "max 10.0"
        max_match = re.search(r"(?:≤|nmt|max|not more than)\s*([0-9]+\.?[0-9]*)", text, re.IGNORECASE)
        if max_match:
            return None, float(max_match.group(1))

        # Min only: "≥ 5.0", "NLT 5.0"
        min_match = re.search(r"(?:≥|nlt|min|not less than)\s*([0-9]+\.?[0-9]*)", text, re.IGNORECASE)
        if min_match:
            return float(min_match.group(1)), None

        # Plain number
        plain_match = re.search(r"([0-9]+\.?[0-9]*)", text)
        if plain_match:
            val = float(plain_match.group(1))
            return val, val

        return None, None

    def _parse_number(self, text: str) -> Optional[float]:
        """Extract a float from text."""
        match = re.search(r"([0-9]+\.?[0-9]*)", text.strip())
        return float(match.group(1)) if match else None

    def _infer_spec_type(self, min_val: Optional[float], max_val: Optional[float]) -> str:
        """Infer parameter type from limits."""
        if min_val is not None and max_val is not None:
            return SpecParameterType.NUMERIC_BOUNDED.value
        elif max_val is not None:
            return SpecParameterType.NUMERIC_MAX.value
        elif min_val is not None:
            return SpecParameterType.NUMERIC_MIN.value
        return SpecParameterType.TEXT.value


def extract_qcsp_number_from_docx(doc: Document) -> Optional[str]:
    """Extract QCSP number from document header or first paragraphs."""
    # Check first 10 paragraphs
    for para in doc.paragraphs[:10]:
        text = para.text.strip()
        match = QCSP_NUMBER_RE.search(text)
        if match:
            return match.group(1).upper()
    return None


# ── Ingestion Service ─────────────────────────────────────────────────────────

async def ingest_specification_docx(
    db: AsyncSession,
    file_path: Path,
    material_code: str,
    material_name_en: str,
    material_name_mk: str,
    spec_type_code: str,
    effective_date: date | None = None,
) -> Specification | None:
    """
    Ingest a specification DOCX file into the LIMS database.

    Idempotent: returns existing specification if spec_number already exists.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Specification DOCX not found: {file_path}")

    doc = Document(str(file_path))

    # Extract QCSP number from document
    doc_qcsp = extract_qcsp_number_from_docx(doc)
    spec_number = doc_qcsp or f"QCSP{spec_type_code}001"

    # Check idempotency
    existing = await db.execute(
        select(Specification).where(Specification.spec_id == spec_number)
    )
    if existing.scalar_one_or_none():
        return None  # Already ingested

    # Parse parameters
    parser = SpecTableParser(doc)
    params_data = parser.parse()

    # Fallback: if no params parsed from tables, use seed data for known specs
    if not params_data:
        params_data = _get_seed_params(material_code)

    # Create specification
    spec = Specification(
        spec_id=spec_number,
        material_code=material_code,
        material_name_en=material_name_en,
        material_name_mk=material_name_mk,
        version=1,
        effective_date=effective_date or date.today(),
        status=SpecStatus.ACTIVE.value,
    )
    db.add(spec)
    await db.flush()
    await db.refresh(spec)

    # Create parameters
    for pd in params_data:
        param = SpecParameter(
            spec_id=spec.id,
            test_name_en=pd["test_name_en"],
            test_name_mk=pd.get("test_name_mk", pd["test_name_en"]),
            test_method=pd["test_method"],
            spec_type=pd["spec_type"],
            lower_limit=pd.get("lower_limit"),
            upper_limit=pd.get("upper_limit"),
            unit=pd["unit"],
            pharmacopoeia_ref=pd.get("pharmacopoeia_ref"),
            test_location=pd.get("test_location", TestLocation.IN_HOUSE.value),
            compendial=pd.get("compendial", True),
            operational_limit_min=pd.get("operational_limit_min"),
            operational_limit_max=pd.get("operational_limit_max"),
            release_limit_min=pd.get("release_limit_min"),
            release_limit_max=pd.get("release_limit_max"),
            sorting_order=pd.get("sorting_order", 0),
        )
        db.add(param)

    await db.flush()
    return spec


async def ingest_all_approved_specs(db: AsyncSession) -> list[Specification]:
    """
    Ingest all known approved specifications.
    Returns list of newly created specifications (skips existing).
    """
    created = []
    for spec_meta in KNOWN_SPECS:
        file_path = SPEC_DOCX_DIR / spec_meta["filename"]
        spec = await ingest_specification_docx(
            db=db,
            file_path=file_path,
            material_code=spec_meta["material_code"],
            material_name_en=spec_meta["material_name_en"],
            material_name_mk=spec_meta["material_name_mk"],
            spec_type_code=spec_meta["spec_type_code"],
        )
        if spec:
            created.append(spec)

    return created


# ── Seed Data Fallback ────────────────────────────────────────────────────────

def _get_seed_params(material_code: str) -> list[dict]:
    """
    Fallback seed parameters for known specs when DOCX parsing yields nothing.
    Based on QCSP-FP-001 and QCSP-IMB-001 extracted data.
    """
    if material_code == "FP-001":
        return [
            {"test_name_en": "Identity", "test_name_mk": "Идентитет", "test_method": "TLC / HPLC-DAD", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "pass/fail", "release_limit_min": None, "release_limit_max": None, "sorting_order": 0},
            {"test_name_en": "Loss on Drying", "test_name_mk": "Губење при сушење", "test_method": "Ph. Eur. 2.02.12", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 10.0, "sorting_order": 1},
            {"test_name_en": "Water Activity", "test_name_mk": "Активност на вода", "test_method": "ISO 21807", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "aw", "release_limit_max": 0.65, "sorting_order": 2},
            {"test_name_en": "THC Content", "test_name_mk": "Содржина на ТХЦ", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 1.0, "sorting_order": 3},
            {"test_name_en": "CBD Content", "test_name_mk": "Содржина на ЦБД", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_BOUNDED.value, "unit": "% w/w", "release_limit_min": 5.0, "release_limit_max": 15.0, "sorting_order": 4},
            {"test_name_en": "Total Cannabinoids", "test_name_mk": "Вкупно канабиноиди", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_BOUNDED.value, "unit": "% w/w", "release_limit_min": 8.0, "release_limit_max": 20.0, "sorting_order": 5},
            {"test_name_en": "CBG Content", "test_name_mk": "Содржина на ЦБГ", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 1.0, "sorting_order": 6},
            {"test_name_en": "CBC Content", "test_name_mk": "Содржина на ЦБЦ", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 1.0, "sorting_order": 7},
            {"test_name_en": "CBN Content", "test_name_mk": "Содржина на ЦБН", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 0.2, "sorting_order": 8},
            {"test_name_en": "THCV Content", "test_name_mk": "Содржина на ТХЦВ", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 1.0, "sorting_order": 9},
            {"test_name_en": "TAMC", "test_name_mk": "ТАМЦ", "test_method": "Ph. Eur. 2.06.13", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "CFU/g", "release_limit_max": 100000.0, "sorting_order": 10},
            {"test_name_en": "TYMC", "test_name_mk": "ТИМЦ", "test_method": "Ph. Eur. 2.06.13", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "CFU/g", "release_limit_max": 10000.0, "sorting_order": 11},
            {"test_name_en": "S. aureus", "test_name_mk": "С. ауреус", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 12},
            {"test_name_en": "P. aeruginosa", "test_name_mk": "П. аеругиноза", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 13},
            {"test_name_en": "E. coli", "test_name_mk": "Е. коли", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 14},
            {"test_name_en": "Salmonella", "test_name_mk": "Салмонела", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/10g", "sorting_order": 15},
            {"test_name_en": "B. cepacia", "test_name_mk": "Б. цепација", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 16},
            {"test_name_en": "C. albicans", "test_name_mk": "Ц. албиканс", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 17},
            {"test_name_en": "Aflatoxins (B1, B2, G1, G2)", "test_name_mk": "Афлатоксини (Б1, Б2, Г1, Г2)", "test_method": "Ph. Eur. 2.08.13", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "µg/kg", "release_limit_max": 4.0, "sorting_order": 18},
            {"test_name_en": "Ochratoxin A", "test_name_mk": "Охратоксин А", "test_method": "Ph. Eur. 2.08.13", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "µg/kg", "release_limit_max": 2.0, "sorting_order": 19},
        ]

    elif material_code == "IMB-001":
        # Seed data for IMB-001 — similar structure, fewer parameters
        return [
            {"test_name_en": "Identity", "test_name_mk": "Идентитет", "test_method": "TLC / HPLC-DAD", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "pass/fail", "sorting_order": 0},
            {"test_name_en": "Loss on Drying", "test_name_mk": "Губење при сушење", "test_method": "Ph. Eur. 2.02.12", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 12.0, "sorting_order": 1},
            {"test_name_en": "THC Content", "test_name_mk": "Содржина на ТХЦ", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "% w/w", "release_limit_max": 0.3, "sorting_order": 2},
            {"test_name_en": "CBD Content", "test_name_mk": "Содржина на ЦБД", "test_method": "Ph. Eur. 2.08.10", "spec_type": SpecParameterType.NUMERIC_MIN.value, "unit": "% w/w", "release_limit_min": 3.0, "sorting_order": 3},
            {"test_name_en": "TAMC", "test_name_mk": "ТАМЦ", "test_method": "Ph. Eur. 2.06.13", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "CFU/g", "release_limit_max": 100000.0, "sorting_order": 4},
            {"test_name_en": "TYMC", "test_name_mk": "ТИМЦ", "test_method": "Ph. Eur. 2.06.13", "spec_type": SpecParameterType.NUMERIC_MAX.value, "unit": "CFU/g", "release_limit_max": 10000.0, "sorting_order": 5},
            {"test_name_en": "S. aureus", "test_name_mk": "С. ауреус", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 6},
            {"test_name_en": "P. aeruginosa", "test_name_mk": "П. аеругиноза", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 7},
            {"test_name_en": "E. coli", "test_name_mk": "Е. коли", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/1g", "sorting_order": 8},
            {"test_name_en": "Salmonella", "test_name_mk": "Салмонела", "test_method": "Ph. Eur. 2.06.14", "spec_type": SpecParameterType.CATEGORICAL.value, "unit": "absent/10g", "sorting_order": 9},
        ]

    return []


# ── P1-E2: Finished Product Analytical Preset ─────────────────────────────────

def get_finished_product_preset() -> list[dict]:
    """
    Return 11-parameter analytical preset for finished product specifications.
    
    Per P1-E2: Standard 11 analytical parameters with Ph.Eur method references,
    limit types, and bilingual names.
    
    Returns:
        List of 11 parameter dictionaries ready for SpecParameter creation.
    """
    return [
        {
            "test_name_en": "Loss on Drying",
            "test_name_mk": "Губење при сушење",
            "test_method": "Ph.Eur. 2.2.32",
            "spec_type": "NUMERIC_MAX",
            "unit": "% w/w",
            "release_limit_max": 10.0,
            "sorting_order": 0,
        },
        {
            "test_name_en": "Foreign Matter",
            "test_name_mk": "Странска материја",
            "test_method": "Ph.Eur. 2.8.2",
            "spec_type": "NUMERIC_MAX",
            "unit": "% w/w",
            "release_limit_max": 2.0,
            "sorting_order": 1,
        },
        {
            "test_name_en": "Total CBN",
            "test_name_mk": "Вкупно ЦБН",
            "test_method": "Ph.Eur. 2.8.10",
            "spec_type": "NUMERIC_MAX",
            "unit": "% w/w",
            "release_limit_max": 0.2,
            "sorting_order": 2,
        },
        {
            "test_name_en": "Heavy Metals",
            "test_name_mk": "Тешки метали",
            "test_method": "Ph.Eur. 2.4.27",
            "spec_type": "NUMERIC_MAX",
            "unit": "mg/kg",
            "release_limit_max": 10.0,
            "sorting_order": 3,
        },
        {
            "test_name_en": "Aflatoxins (B1, B2, G1, G2)",
            "test_name_mk": "Афлатоксини (Б1, Б2, Г1, Г2)",
            "test_method": "Ph.Eur. 2.8.13",
            "spec_type": "NUMERIC_MAX",
            "unit": "µg/kg",
            "release_limit_max": 4.0,
            "sorting_order": 4,
        },
        {
            "test_name_en": "Ochratoxin A",
            "test_name_mk": "Охратоксин А",
            "test_method": "Ph.Eur. 2.8.13",
            "spec_type": "NUMERIC_MAX",
            "unit": "µg/kg",
            "release_limit_max": 2.0,
            "sorting_order": 5,
        },
        {
            "test_name_en": "Pesticide Residues",
            "test_name_mk": "Остатоци од пестициди",
            "test_method": "Ph.Eur. 2.8.18",
            "spec_type": "NUMERIC_MAX",
            "unit": "mg/kg",
            "release_limit_max": 0.01,
            "sorting_order": 6,
        },
        {
            "test_name_en": "Total Aerobic Microbial Count",
            "test_name_mk": "Вкупен аеробен микробен број",
            "test_method": "Ph.Eur. 2.6.12",
            "spec_type": "NUMERIC_MAX",
            "unit": "CFU/g",
            "release_limit_max": 100000.0,
            "sorting_order": 7,
        },
        {
            "test_name_en": "Total Yeast and Mold Count",
            "test_name_mk": "Вкупен број на квасци и плесени",
            "test_method": "Ph.Eur. 2.6.12",
            "spec_type": "NUMERIC_MAX",
            "unit": "CFU/g",
            "release_limit_max": 10000.0,
            "sorting_order": 8,
        },
        {
            "test_name_en": "Specified Micro-organisms",
            "test_name_mk": "Специфицирани микроорганизми",
            "test_method": "Ph.Eur. 2.6.13",
            "spec_type": "CATEGORICAL",
            "unit": "absent",
            "release_limit_max": None,
            "sorting_order": 9,
        },
        {
            "test_name_en": "Cannabinoid Profile",
            "test_name_mk": "Канабиноиден профил",
            "test_method": "Ph.Eur. 2.8.10",
            "spec_type": "CATEGORICAL",
            "unit": "qualitative",
            "release_limit_max": None,
            "sorting_order": 10,
        },
    ]

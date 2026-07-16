#!/usr/bin/env python3
"""Hierarchical GMP document ID utilities."""

from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

MIN_FAMILY, MAX_FAMILY = 1, 99
MIN_SOP, MAX_SOP = 0, 99
MIN_ANNEX, MAX_ANNEX = 1, 99
MIN_VERSION = 1

class DocumentIDError(ValueError):
    pass

class Department(Enum):
    QC = "QC"
    QA = "QA"
    PROD = "PROD"
    CULT = "CULT"
    SAN = "SAN"
    SEC = "SEC"
    HR = "HR"
    EQU = "EQU"
    REC = "REC"
    VAL = "VAL"
    TRN = "TRN"

@dataclass
class DocumentID:
    department: str
    family: int
    sop: int
    version: int = 1
    annex: Optional[int] = None

    def __post_init__(self):
        self.department = self._normalise_department(self.department)
        self.family = int(self.family)
        self.sop = int(self.sop)
        self.version = int(self.version)
        self.annex = self._normalise_annex(self.annex)

    @staticmethod
    def _normalise_department(d):
        return d.value if isinstance(d, Department) else d.strip().upper() if isinstance(d, str) else ""

    @staticmethod
    def _normalise_annex(a):
        if a is None or a == "":
            return None
        if isinstance(a, str):
            cleaned = a.strip().upper().lstrip('A')
            return int(cleaned)
        return int(a)

    def __str__(self):
        core = f"{self.department}_{self.family:02d}.{self.sop:02d}"
        if self.annex is not None:
            core += f"_A{self.annex:02d}"
        return f"{core}_v{self.version}"

    @property
    def family_key(self):
        return f"{self.department}_{self.family:02d}"

    def to_dict(self):
        return {"document_id": str(self), "department": self.department, "family": self.family, "sop": self.sop, "annex": self.annex, "version": self.version}

class DocumentIDGenerator:
    _PATTERN = re.compile(r"^(?P<department>[A-Z]{2,5})_(?P<family>\d{2})\.(?P<sop>\d{2})(?:_A(?P<annex>\d{2}))?_v(?P<version>\d+)$")

    def __init__(self):
        self._registry = {}

    def generate(self, dept, family, sop, *, version=MIN_VERSION, annex=None):
        doc = DocumentID(dept, family, sop, version, annex)
        self._registry[str(doc)] = doc
        return doc

    def parse(self, doc_id):
        m = self._PATTERN.fullmatch(doc_id.strip())
        if not m:
            raise DocumentIDError(f"Invalid: {doc_id}")
        c = m.groupdict()
        return DocumentID(c["department"], int(c["family"]), int(c["sop"]), int(c["version"]), int(c["annex"]) if c["annex"] else None)

    def is_valid(self, doc_id):
        return bool(self._PATTERN.fullmatch(doc_id.strip()))

    def build_family_registry(self):
        reg = {}
        for doc in self._registry.values():
            fk = doc.family_key
            reg.setdefault(fk, {"department": doc.department, "family": doc.family, "sops": {}})
            reg[fk]["sops"][doc.sop] = str(doc)
        return reg

_gen = DocumentIDGenerator()

def generate_document_id(dept, family, sop, *, version=MIN_VERSION, annex=None):
    return str(_gen.generate(dept, family, sop, version=version, annex=annex))

def parse_document_id(doc_id):
    return _gen.parse(doc_id).to_dict()

def is_valid_document_id(doc_id):
    return _gen.is_valid(doc_id)

def build_document_family_registry():
    return _gen.build_family_registry()

if __name__ == "__main__":
    print(generate_document_id("QC", 2, 1))
    print(generate_document_id("QC", 2, 1, annex=1))
    print(is_valid_document_id("QC_02.01_A01_v1"))
    print(build_document_family_registry())

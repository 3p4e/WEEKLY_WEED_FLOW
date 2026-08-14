"""QC LIMS router package.

Split from a single 5040-line qc.py into per-domain modules. `router` is
defined in `common` and every submodule registers its routes onto that same
shared instance via side-effect import.
"""
from .common import router
from . import (  # noqa: F401  (imported for route-registration side effects)
    specs, samples, laboratories, certificates, signatures, coq_docx,
    cert_register, oos, ecoa, genealogy, custody, leaves, coa_qa, coq_aggregation,
    potency, potency_import,
)

__all__ = ["router"]

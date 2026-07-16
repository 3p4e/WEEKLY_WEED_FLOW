"""
Sample Transport model for LIMS.

Per PP-QC-SOP-012 (Sample Transport, bilingual). Each SampleTransport row is a
shipment of QC sample(s) to an external laboratory, tracking the chain-of-custody
annex forms (SAR / MoIA / Transport Manifest+CoC / COO / Financial) and the
shipping status the frontend Transport screen renders directly.

This is distinct from ChainOfCustody (the generic internal custody-transfer log):
SampleTransport carries the external-lab, annex-form and courier fields that the
Transport / CoC screen needs.
"""

from datetime import date as date_type

from sqlalchemy import Boolean, Date, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SampleTransport(BaseModel):
    """
    External-lab sample transport / chain-of-custody record.

    Field names map onto the frontend SEED_TRANSPORTS object so the
    `/transport` endpoint can serialize a row directly.
    """

    __tablename__ = "sample_transports"

    transport_id: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True,
        doc="Human-readable transport key (frontend 'id'), e.g. TR-PP-2026-0042"
    )
    sample_id: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True,
        doc="Sample being shipped (frontend 'sample_id')"
    )
    batch_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default="",
        doc="Batch identifier (frontend 'batch_id')"
    )
    external_lab: Mapped[str] = mapped_column(
        String(40), nullable=False, default="",
        doc="External lab id the frontend EXT_LABS keys on (frontend 'lab')"
    )
    tests: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        doc="Tests requested at the external lab (frontend 'tests')"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        doc="draft | in_transit | received (frontend 'status')"
    )

    # ── Annex forms (PP-QC-SOP-012-A01..A05) ──
    form_sar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="A01 Sample Analysis Request (frontend 'sar')")
    form_moia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="A02 MoIA notification — controlled substances (frontend 'moia')")
    form_tmcoc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="A03 Transport Manifest + Chain of Custody (frontend 'tmcoc')")
    form_coo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="A04 Contractor Order (frontend 'coo')")
    form_fin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="A05 Financial Construction (frontend 'fin')")

    # ── Shipping ──
    created_date: Mapped[date_type | None] = mapped_column(Date, nullable=True, doc="Transport created date (frontend 'created')")
    shipped_date: Mapped[date_type | None] = mapped_column(Date, nullable=True, doc="Dispatch date (frontend 'shipped')")
    expected_date: Mapped[date_type | None] = mapped_column(Date, nullable=True, doc="Expected arrival date (frontend 'expected')")
    tracking: Mapped[str] = mapped_column(String(60), nullable=False, default="", doc="Courier tracking reference (frontend 'tracking')")

    def __repr__(self) -> str:
        return f"<SampleTransport {self.transport_id} [{self.status}]>"

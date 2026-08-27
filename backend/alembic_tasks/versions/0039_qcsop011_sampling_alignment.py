"""QCSOP 011 v3 sampling alignment — RQS mandatory fields, custody condition, sample taxonomy

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-21

Aligns the QC sampling / custody cluster (RQS → SFR → chain-of-custody → sample)
with the governing SOP QCSOP 011 v3.0 (PP-QC-SOP-017):

- qc_sampling_requests: the §6.1.4 mandatory RQS fields the model lacked
  (num_samples, required_tests, priority + justification, storage_location,
  material_status, specification link + reference), the §6.1.1/§6.1.6 QC
  Internal Control Number assigned at registration (qc_control_number), and the
  §6.1.2 release-related flag that escalates registration to the QP.
- qc_sample_field_records: §6.2.3 / §6.3.2 receipt content (sampling_equipment,
  ambient_conditions, received_condition).
- qc_chain_of_custody: §6.3.1 condition confirmation per transfer
  (sample_condition, condition_ok).
- qc_samples: §6.2.1 sample-type taxonomy (sample_kind PC/MB/EXT/RET/STAB/RT/CC),
  §7.0 retention_expiry, and §6.7 non-conforming flagging.

All additive ALTER … ADD COLUMN. New CHECK/NOT-NULL columns carry a DEFAULT or
permit NULL so existing rows pass; GxP: an unknown value stays NULL for a human,
never fabricated. The existing RLS / audit trigger / grants cover the new
columns. No new tables, sequences, or grants. Identifier-FORMAT changes (the
§6.1.3 RQS ordinal) are forward-only in application code — issued records keep
their numbers (immutable), so no data migration here.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── RQS — §6.1.4 mandatory fields + §6.1.1 control number + §6.1.2 release flag
    op.execute("ALTER TABLE public.qc_sampling_requests ADD COLUMN qc_control_number text")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD COLUMN num_samples integer")
    op.execute("ALTER TABLE public.qc_sampling_requests"
               " ADD COLUMN required_tests jsonb NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE public.qc_sampling_requests"
               " ADD COLUMN priority text NOT NULL DEFAULT 'ROUTINE'")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD CONSTRAINT qc_rqs_priority_check"
               " CHECK (priority = ANY (ARRAY['ROUTINE'::text, 'URGENT'::text]))")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD COLUMN priority_justification text")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD COLUMN storage_location text")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD COLUMN material_status text")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD CONSTRAINT qc_rqs_material_status_check"
               " CHECK (material_status IS NULL OR material_status = ANY"
               " (ARRAY['QUARANTINE'::text, 'IN_PROCESS'::text, 'OTHER'::text]))")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD COLUMN specification_id uuid")
    op.execute("ALTER TABLE public.qc_sampling_requests ADD COLUMN spec_reference text")
    op.execute("ALTER TABLE public.qc_sampling_requests"
               " ADD COLUMN release_related boolean NOT NULL DEFAULT false")
    # ── SFR — §6.2.3 equipment + §6.3.2 receipt conditions
    op.execute("ALTER TABLE public.qc_sample_field_records ADD COLUMN sampling_equipment text")
    op.execute("ALTER TABLE public.qc_sample_field_records ADD COLUMN ambient_conditions text")
    op.execute("ALTER TABLE public.qc_sample_field_records ADD COLUMN received_condition text")
    # ── CoC — §6.3.1 condition confirmation per transfer
    op.execute("ALTER TABLE public.qc_chain_of_custody ADD COLUMN sample_condition text")
    op.execute("ALTER TABLE public.qc_chain_of_custody ADD COLUMN condition_ok boolean")
    # ── Sample — §6.2.1 type taxonomy + §7.0 retention + §6.7 non-conforming
    op.execute("ALTER TABLE public.qc_samples ADD COLUMN sample_kind text")
    op.execute("ALTER TABLE public.qc_samples ADD CONSTRAINT qc_samples_kind_check"
               " CHECK (sample_kind IS NULL OR sample_kind = ANY"
               " (ARRAY['PC'::text, 'MB'::text, 'EXT'::text, 'RET'::text,"
               " 'STAB'::text, 'RT'::text, 'CC'::text]))")
    op.execute("ALTER TABLE public.qc_samples ADD COLUMN retention_expiry date")
    op.execute("ALTER TABLE public.qc_samples"
               " ADD COLUMN non_conforming boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE public.qc_samples ADD COLUMN non_conforming_reason text")


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_samples DROP COLUMN non_conforming_reason")
    op.execute("ALTER TABLE public.qc_samples DROP COLUMN non_conforming")
    op.execute("ALTER TABLE public.qc_samples DROP COLUMN retention_expiry")
    op.execute("ALTER TABLE public.qc_samples DROP CONSTRAINT qc_samples_kind_check")
    op.execute("ALTER TABLE public.qc_samples DROP COLUMN sample_kind")
    op.execute("ALTER TABLE public.qc_chain_of_custody DROP COLUMN condition_ok")
    op.execute("ALTER TABLE public.qc_chain_of_custody DROP COLUMN sample_condition")
    op.execute("ALTER TABLE public.qc_sample_field_records DROP COLUMN received_condition")
    op.execute("ALTER TABLE public.qc_sample_field_records DROP COLUMN ambient_conditions")
    op.execute("ALTER TABLE public.qc_sample_field_records DROP COLUMN sampling_equipment")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN release_related")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN spec_reference")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN specification_id")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP CONSTRAINT qc_rqs_material_status_check")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN material_status")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN storage_location")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN priority_justification")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP CONSTRAINT qc_rqs_priority_check")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN priority")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN required_tests")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN num_samples")
    op.execute("ALTER TABLE public.qc_sampling_requests DROP COLUMN qc_control_number")

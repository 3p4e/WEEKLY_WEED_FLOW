"""QC LIMS U6: water tests + stability studies + sample transports (leaves)

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-16

The three deferred standalone Phase-2 leaves — no cross-dependencies, each a
self-contained record type from qc-lims-ao (models/water.py, stability.py,
transport.py).

- `qc_water_tests` (PP-QC-SOP-014, `PP-WT-YYYY-NNNN`) — one water-quality result
  for a sampling location on a date; the variable parameter set is a jsonb map;
  `grade` TW/BW/TR/RO; `passed` + an OOE note when it fails.
- `qc_stability_studies` (QCSOP 018, `PP-STB-YYYY-NNNN`) — one stability study
  (LT/ACC/INT) over a material + a jsonb list of batches; IN_PROGRESS→CLOSED,
  with protocol/schedule/report/shelf-life references.
- `qc_sample_transports` (PP-QC-SOP-012, `PP-TRN-YYYY-NNNN`) — a shipment of QC
  sample(s) to an external lab, tracking the five annex forms (SAR/MoIA/TMCoC/
  COO/FIN) and the shipping status draft→in_transit→received. Distinct from the
  U5 internal chain of custody: this carries external-lab + annex-form fields.

`sample_id`/`batch_id` on transport are free-text human refs (a shipment may
cite an external identifier), consistent with the prototype — not hard FKs.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WATER_GRADES = ("TW", "BW", "TR", "RO")
_STAB_TYPES = ("LT", "ACC", "INT")
_STAB_STATUSES = ("IN_PROGRESS", "CLOSED")
_TRN_STATUSES = ("draft", "in_transit", "received")


def upgrade() -> None:
    for seq in ("qc_wt_id_seq", "qc_stb_id_seq", "qc_trn_id_seq"):
        op.execute(f"CREATE SEQUENCE public.{seq} AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_water_tests (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            water_test_id text NOT NULL,
            result_date date,
            location text NOT NULL,
            grade text NOT NULL,
            parameters jsonb DEFAULT '{}'::jsonb NOT NULL,
            passed boolean DEFAULT true NOT NULL,
            ooe text,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_water_tests_pkey PRIMARY KEY (id),
            CONSTRAINT qc_water_tests_number_key UNIQUE (org_id, water_test_id),
            CONSTRAINT qc_water_tests_grade_check CHECK (grade = ANY (ARRAY[%s]))
        )
        """
        % ",".join(f"'{s}'::text" for s in _WATER_GRADES)
    )
    op.execute(
        """
        CREATE TABLE public.qc_stability_studies (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            study_id text NOT NULL,
            study_type text NOT NULL,
            material_code text NOT NULL,
            material_name_en text,
            material_name_mk text,
            batches jsonb DEFAULT '[]'::jsonb NOT NULL,
            started date,
            status text DEFAULT 'IN_PROGRESS'::text NOT NULL,
            protocol text,
            schedule text,
            report text,
            shelf_life text,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_stability_studies_pkey PRIMARY KEY (id),
            CONSTRAINT qc_stability_studies_number_key UNIQUE (org_id, study_id),
            CONSTRAINT qc_stability_studies_type_check CHECK (study_type = ANY (ARRAY[%s])),
            CONSTRAINT qc_stability_studies_status_check CHECK (status = ANY (ARRAY[%s]))
        )
        """
        % (",".join(f"'{s}'::text" for s in _STAB_TYPES),
           ",".join(f"'{s}'::text" for s in _STAB_STATUSES))
    )
    op.execute(
        """
        CREATE TABLE public.qc_sample_transports (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            transport_id text NOT NULL,
            sample_id text NOT NULL,
            batch_id text,
            external_lab text,
            tests jsonb DEFAULT '[]'::jsonb NOT NULL,
            status text DEFAULT 'draft'::text NOT NULL,
            form_sar boolean DEFAULT false NOT NULL,
            form_moia boolean DEFAULT false NOT NULL,
            form_tmcoc boolean DEFAULT false NOT NULL,
            form_coo boolean DEFAULT false NOT NULL,
            form_fin boolean DEFAULT false NOT NULL,
            shipped_date date,
            expected_date date,
            tracking text,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_sample_transports_pkey PRIMARY KEY (id),
            CONSTRAINT qc_sample_transports_number_key UNIQUE (org_id, transport_id),
            CONSTRAINT qc_sample_transports_status_check CHECK (status = ANY (ARRAY[%s]))
        )
        """
        % ",".join(f"'{s}'::text" for s in _TRN_STATUSES)
    )
    for tbl in ("qc_water_tests", "qc_stability_studies", "qc_sample_transports"):
        op.execute(f"ALTER TABLE ONLY public.{tbl} FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY org_isolation ON public.{tbl}"
            f" USING ((org_id = app.current_org_id()))"
            f" WITH CHECK ((org_id = app.current_org_id()))"
        )
        op.execute(
            f"CREATE TRIGGER audit_{tbl} AFTER INSERT OR DELETE OR UPDATE ON public.{tbl}"
            f" FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
        )
    op.execute("CREATE INDEX qc_water_tests_loc_idx ON public.qc_water_tests USING btree (org_id, location)")
    op.execute("CREATE INDEX qc_stability_studies_mat_idx ON public.qc_stability_studies USING btree (org_id, material_code)")
    op.execute("CREATE INDEX qc_sample_transports_status_idx ON public.qc_sample_transports USING btree (org_id, status)")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_water_tests,
                public.qc_stability_studies, public.qc_sample_transports TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_wt_id_seq, public.qc_stb_id_seq,
                public.qc_trn_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_water_tests,
                public.qc_stability_studies, public.qc_sample_transports TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_wt_id_seq, public.qc_stb_id_seq,
                public.qc_trn_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_sample_transports")
    op.execute("DROP TABLE public.qc_stability_studies")
    op.execute("DROP TABLE public.qc_water_tests")
    for seq in ("qc_trn_id_seq", "qc_stb_id_seq", "qc_wt_id_seq"):
        op.execute(f"DROP SEQUENCE public.{seq}")

"""product catalogue, selection campaigns, trichome checks, clone lineage

Revision ID: 0066
Revises: 0065
Create Date: 2026-09-05

The owner confirmed (2026-09-05) that the two ImB Specification documents are
the official statement of "the strains and potency ranges and grades and
codes", and that the nominal value of every potency grade must be the one
those pages print. Those pages are per PRODUCT, not per strain: one page is
one strain at one nominal Total Δ9-THC, coded <ABBR>_THC<nominal>:CBD1, with an
acceptance window of nominal ± 10 % relative (26 → 23.40–28.59 %). 48 pages,
42 distinct products, 22 strains.

The app's existing potency model is a per-cultivar LADDER of tiers (Spec I…IV)
imported from the August handoff. It cannot express the official scheme: it
allows one APPROVED ladder per cultivar, forbids overlapping windows, and caps
the top at exactly 30.00 % (CJ_THC28's window reaches 30.79). So this migration
adds the catalogue as its own table rather than bending the ladder:

1. qc_products — one row per official product. Windows are STORED, not derived,
   because the printed page is the specification: what the app checks against
   must be what the document says, byte for byte. Status DRAFT → APPROVED →
   SUPERSEDED with one APPROVED row per product code, the same shape (and the
   same segregation-of-duties rule in app code) the ladders use. No 30 % cap.

2. selection_campaigns — the "S1" in the owner's mother-plant ID: a selection
   event from seeds, new clones or phenotypes, numbered FACILITY-WIDE (S3 is
   the third such event the facility ran, whatever the strain).

3. trichome_checks — the documented record behind the harvest date. The owner's
   rule is that the flowering window (6–9 weeks) ends when trichome maturation
   says so, tracked progressively under a stereo or digital microscope "with
   documented records". A check is an observation, never a gate: like
   irrigation_events, nothing downstream blocks on it.

4. Lineage and target columns, all nullable so every existing row stays valid:
   plant_batches.product_id (the product a batch is grown to) and clone_source
   (own stock or imported — imported clones may stay some days longer in the
   clone rooms for quarantine, which shifts the expected date);
   clone_runs.product_id; qc_coq.product_id (the product a lot is certified
   against); plants.mother_plant_id / cutting_no / clone_no and
   clone_run_mothers.cutting_no, which together carry the owner's clone ID
   <mother>-<xx>.<nnn>: xx the consecutive cutting from that mother, nnn the
   clone within that cutting.

The mother_plants columns that the structured ID needs (product, campaign,
mother number, generation, stock number, parent) arrive in 0067, which is
allowed to be strict because it can refuse to run over rows that predate it.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("qc_products", "selection_campaigns", "trichome_checks")


def upgrade() -> None:
    # ── the official product catalogue ────────────────────────────────────
    op.execute(
        """
        CREATE TABLE public.qc_products (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            cultivar_id uuid NOT NULL,
            product_code text NOT NULL,
            grade numeric NOT NULL,
            nominal_pct numeric NOT NULL,
            window_min numeric NOT NULL,
            window_max numeric NOT NULL,
            doc_code text DEFAULT 'QCSP 001'::text NOT NULL,
            doc_version text DEFAULT 'v.03'::text NOT NULL,
            source text,
            status text DEFAULT 'DRAFT'::text NOT NULL,
            effective_date date,
            approved_by uuid,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_products_pkey PRIMARY KEY (id),
            CONSTRAINT qc_products_org_id_product_code_doc_version_key
                UNIQUE (org_id, product_code, doc_version),
            CONSTRAINT qc_products_cultivar_id_fkey FOREIGN KEY (cultivar_id)
                REFERENCES public.cultivars(id) ON DELETE RESTRICT,
            CONSTRAINT qc_products_grade_check CHECK ((grade > (0)::numeric) AND (grade <= (100)::numeric)),
            CONSTRAINT qc_products_window_check CHECK ((window_max > window_min)
                AND (nominal_pct >= window_min) AND (nominal_pct <= window_max)),
            CONSTRAINT qc_products_status_check CHECK (status = ANY (ARRAY['DRAFT'::text,
                'APPROVED'::text, 'SUPERSEDED'::text]))
        )
        """
    )
    # One live product per code, the same partial-unique shape as
    # qc_potency_specs_one_approved_idx (tasks 0058).
    op.execute(
        "CREATE UNIQUE INDEX qc_products_one_approved_idx ON public.qc_products"
        " USING btree (org_id, product_code) WHERE (status = 'APPROVED'::text)"
    )
    op.execute(
        "CREATE INDEX qc_products_org_cultivar_idx ON public.qc_products"
        " USING btree (org_id, cultivar_id, grade)"
    )

    # ── selection campaigns (the S<n> in a mother-plant ID) ───────────────
    op.execute(
        """
        CREATE TABLE public.selection_campaigns (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            seq integer NOT NULL,
            started_on date NOT NULL,
            material text NOT NULL,
            cultivar_id uuid,
            description text,
            note text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT selection_campaigns_pkey PRIMARY KEY (id),
            CONSTRAINT selection_campaigns_org_id_seq_key UNIQUE (org_id, seq),
            CONSTRAINT selection_campaigns_cultivar_id_fkey FOREIGN KEY (cultivar_id)
                REFERENCES public.cultivars(id) ON DELETE RESTRICT,
            CONSTRAINT selection_campaigns_seq_check CHECK (seq >= 1),
            CONSTRAINT selection_campaigns_material_check CHECK (material = ANY (ARRAY['seeds'::text,
                'clones'::text, 'phenotypes'::text]))
        )
        """
    )

    # ── trichome maturation checks (the documented record) ────────────────
    op.execute(
        """
        CREATE TABLE public.trichome_checks (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            batch_id uuid NOT NULL,
            room_id uuid,
            checked_on date NOT NULL,
            instrument text NOT NULL,
            magnification text,
            sample_sites integer,
            pct_clear numeric,
            pct_cloudy numeric,
            pct_amber numeric,
            verdict text NOT NULL,
            image_ref text,
            checked_by uuid NOT NULL,
            note text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT trichome_checks_pkey PRIMARY KEY (id),
            CONSTRAINT trichome_checks_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE RESTRICT,
            CONSTRAINT trichome_checks_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT trichome_checks_instrument_check CHECK (instrument = ANY (ARRAY['stereo'::text,
                'digital'::text])),
            CONSTRAINT trichome_checks_verdict_check CHECK (verdict = ANY (ARRAY['immature'::text,
                'approaching'::text, 'ready'::text, 'overripe'::text])),
            CONSTRAINT trichome_checks_sites_check CHECK ((sample_sites IS NULL) OR (sample_sites >= 1)),
            CONSTRAINT trichome_checks_pct_check CHECK (
                ((pct_clear IS NULL) OR ((pct_clear >= (0)::numeric) AND (pct_clear <= (100)::numeric)))
                AND ((pct_cloudy IS NULL) OR ((pct_cloudy >= (0)::numeric) AND (pct_cloudy <= (100)::numeric)))
                AND ((pct_amber IS NULL) OR ((pct_amber >= (0)::numeric) AND (pct_amber <= (100)::numeric)))),
            CONSTRAINT trichome_checks_sum_check CHECK (
                (pct_clear IS NULL) OR (pct_cloudy IS NULL) OR (pct_amber IS NULL)
                OR (((pct_clear + pct_cloudy + pct_amber) >= (98)::numeric)
                    AND ((pct_clear + pct_cloudy + pct_amber) <= (102)::numeric)))
        )
        """
    )
    op.execute(
        "CREATE INDEX trichome_checks_batch_idx ON public.trichome_checks"
        " USING btree (batch_id, checked_on DESC)"
    )

    # ── target product + clone provenance on the batch ────────────────────
    op.execute("ALTER TABLE public.plant_batches ADD COLUMN product_id uuid")
    op.execute("ALTER TABLE public.plant_batches ADD CONSTRAINT plant_batches_product_id_fkey"
               " FOREIGN KEY (product_id) REFERENCES public.qc_products(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE public.plant_batches ADD COLUMN clone_source text")
    op.execute("ALTER TABLE public.plant_batches ADD CONSTRAINT plant_batches_clone_source_check"
               " CHECK ((clone_source IS NULL) OR (clone_source = ANY (ARRAY['own_stock'::text,"
               " 'imported'::text])))")
    op.execute("CREATE INDEX plant_batches_product_id_idx ON public.plant_batches"
               " USING btree (product_id)")

    op.execute("ALTER TABLE public.clone_runs ADD COLUMN product_id uuid")
    op.execute("ALTER TABLE public.clone_runs ADD CONSTRAINT clone_runs_product_id_fkey"
               " FOREIGN KEY (product_id) REFERENCES public.qc_products(id) ON DELETE SET NULL")

    # RESTRICT, not SET NULL: a CoQ's product is the specification the lot was
    # certified against — it must not silently vanish from an issued document.
    op.execute("ALTER TABLE public.qc_coq ADD COLUMN product_id uuid")
    op.execute("ALTER TABLE public.qc_coq ADD CONSTRAINT qc_coq_product_id_fkey"
               " FOREIGN KEY (product_id) REFERENCES public.qc_products(id) ON DELETE RESTRICT")

    # ── clone lineage: which mother, which cutting, which clone ───────────
    op.execute("ALTER TABLE public.clone_run_mothers ADD COLUMN cutting_no integer")
    op.execute("ALTER TABLE public.clone_run_mothers ADD CONSTRAINT clone_run_mothers_cutting_no_check"
               " CHECK ((cutting_no IS NULL) OR ((cutting_no >= 1) AND (cutting_no <= 99)))")
    op.execute("CREATE UNIQUE INDEX clone_run_mothers_mother_cutting_key ON public.clone_run_mothers"
               " USING btree (mother_plant_id, cutting_no) WHERE (cutting_no IS NOT NULL)")

    op.execute("ALTER TABLE public.plants ADD COLUMN mother_plant_id uuid")
    op.execute("ALTER TABLE public.plants ADD CONSTRAINT plants_mother_plant_id_fkey"
               " FOREIGN KEY (mother_plant_id) REFERENCES public.mother_plants(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE public.plants ADD COLUMN cutting_no integer")
    op.execute("ALTER TABLE public.plants ADD COLUMN clone_no integer")
    op.execute("ALTER TABLE public.plants ADD CONSTRAINT plants_cutting_no_check"
               " CHECK ((cutting_no IS NULL) OR ((cutting_no >= 1) AND (cutting_no <= 99)))")
    op.execute("ALTER TABLE public.plants ADD CONSTRAINT plants_clone_no_check"
               " CHECK ((clone_no IS NULL) OR ((clone_no >= 1) AND (clone_no <= 999)))")
    # The three travel together: a plant either carries its mother's lineage
    # whole, or carries none of it and keeps the legacy <date>_<cv>_<seq> id.
    op.execute("ALTER TABLE public.plants ADD CONSTRAINT plants_mother_lineage_check"
               " CHECK (((mother_plant_id IS NULL) = (cutting_no IS NULL))"
               " AND ((mother_plant_id IS NULL) = (clone_no IS NULL)))")
    op.execute("CREATE INDEX plants_mother_idx ON public.plants"
               " USING btree (mother_plant_id, cutting_no) WHERE (mother_plant_id IS NOT NULL)")

    # ── RLS + audit + grants: identical shape to 0045 / 0065 ──────────────
    for tbl in _NEW_TABLES:
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

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_products, public.selection_campaigns, public.trichome_checks TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_products, public.selection_campaigns, public.trichome_checks TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.plants_mother_idx")
    for con in ("plants_mother_lineage_check", "plants_clone_no_check",
                "plants_cutting_no_check", "plants_mother_plant_id_fkey"):
        op.execute(f"ALTER TABLE public.plants DROP CONSTRAINT {con}")
    op.execute("ALTER TABLE public.plants DROP COLUMN clone_no")
    op.execute("ALTER TABLE public.plants DROP COLUMN cutting_no")
    op.execute("ALTER TABLE public.plants DROP COLUMN mother_plant_id")

    op.execute("DROP INDEX public.clone_run_mothers_mother_cutting_key")
    op.execute("ALTER TABLE public.clone_run_mothers DROP CONSTRAINT clone_run_mothers_cutting_no_check")
    op.execute("ALTER TABLE public.clone_run_mothers DROP COLUMN cutting_no")

    op.execute("ALTER TABLE public.qc_coq DROP CONSTRAINT qc_coq_product_id_fkey")
    op.execute("ALTER TABLE public.qc_coq DROP COLUMN product_id")

    op.execute("ALTER TABLE public.clone_runs DROP CONSTRAINT clone_runs_product_id_fkey")
    op.execute("ALTER TABLE public.clone_runs DROP COLUMN product_id")

    op.execute("DROP INDEX public.plant_batches_product_id_idx")
    op.execute("ALTER TABLE public.plant_batches DROP CONSTRAINT plant_batches_clone_source_check")
    op.execute("ALTER TABLE public.plant_batches DROP COLUMN clone_source")
    op.execute("ALTER TABLE public.plant_batches DROP CONSTRAINT plant_batches_product_id_fkey")
    op.execute("ALTER TABLE public.plant_batches DROP COLUMN product_id")

    op.execute("DROP TABLE public.trichome_checks")
    op.execute("DROP TABLE public.selection_campaigns")
    op.execute("DROP TABLE public.qc_products")

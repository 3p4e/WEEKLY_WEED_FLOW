--
-- PostgreSQL database dump
--

\restrict MYNGZtixgvZDWYXdjoIsavjwTYrL5PBemo4vKpec2pVcSoVLzY9maYbAqDWqveH

-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: app; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA app;


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: current_org_id(); Type: FUNCTION; Schema: app; Owner: -
--

CREATE FUNCTION app.current_org_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.org_id', true), '')::uuid $$;


--
-- Name: current_role(); Type: FUNCTION; Schema: app; Owner: -
--

CREATE FUNCTION app."current_role"() RETURNS text
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.role', true), '') $$;


--
-- Name: current_user_id(); Type: FUNCTION; Schema: app; Owner: -
--

CREATE FUNCTION app.current_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;


--
-- Name: fn_audit_row(); Type: FUNCTION; Schema: app; Owner: -
--

CREATE FUNCTION app.fn_audit_row() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'app', 'public'
    SET "TimeZone" TO 'UTC'
    AS $$
DECLARE
  v_actor text := COALESCE(current_setting('app.user_id', true), 'system');
  v_prev  text;
  v_new   jsonb := CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  v_old   jsonb := CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  v_rec   text  := COALESCE((CASE WHEN TG_OP='DELETE' THEN v_old ELSE v_new END)->>'id', '');
  v_payload text;
BEGIN
  PERFORM pg_advisory_xact_lock(4019283746);  -- H1: serialize tail read; prevents concurrent hash-chain forks
  SELECT entry_hash INTO v_prev FROM audit_log ORDER BY id DESC LIMIT 1;
  -- IMPORTANT: convert_to(text,'UTF8'), never text::bytea (escape-format bug).
  -- H2: the function pins TimeZone=UTC, so now()::text here is zone-stable and
  -- /audit/verify can reproduce it from created_at without knowing who wrote it.
  v_payload := COALESCE(v_prev,'') || v_actor || TG_OP || TG_TABLE_NAME || v_rec
               || now()::text || COALESCE(v_new::text,'') || COALESCE(v_old::text,'');
  INSERT INTO audit_log(org_id,user_id,action,table_name,record_id,old_values,new_values,prev_hash,entry_hash)
  VALUES (
    NULLIF(current_setting('app.org_id', true),'')::uuid,
    NULLIF(current_setting('app.user_id', true),'')::uuid,
    TG_OP, TG_TABLE_NAME, v_rec, v_old, v_new, v_prev,
    encode(digest(convert_to(v_payload,'UTF8'),'sha256'),'hex')
  );
  RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;


--
-- Name: is_elevated(); Type: FUNCTION; Schema: app; Owner: -
--

CREATE FUNCTION app.is_elevated() RETURNS boolean
    LANGUAGE sql STABLE
    AS $$ SELECT app.current_role() IN ('ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','MU_MGR','QP') $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_agent_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_agent_bindings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    function_key text NOT NULL,
    letta_agent_id text NOT NULL,
    scope text DEFAULT 'org'::text NOT NULL,
    scope_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.ai_agent_bindings FORCE ROW LEVEL SECURITY;


--
-- Name: ai_pins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_pins (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    function_key text NOT NULL,
    task_id uuid,
    week_id uuid,
    title text,
    body text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    subject_user_id uuid,
    prompt_version text
);

ALTER TABLE ONLY public.ai_pins FORCE ROW LEVEL SECURITY;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id bigint NOT NULL,
    org_id uuid,
    user_id uuid,
    user_email text,
    action text NOT NULL,
    table_name text,
    record_id text,
    old_values jsonb,
    new_values jsonb,
    prev_hash text,
    entry_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.audit_log FORCE ROW LEVEL SECURITY;


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: biosecurity_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biosecurity_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    kind text NOT NULL,
    room_id uuid,
    location text,
    occurred_on date DEFAULT CURRENT_DATE NOT NULL,
    subject text,
    action text,
    measure_value numeric,
    measure_unit text,
    result text,
    action_taken text,
    performed_by uuid NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    CONSTRAINT biosecurity_events_action_on_fail_check CHECK (((result IS NULL) OR (result <> ALL (ARRAY['fail'::text, 'below_spec'::text])) OR ((action_taken IS NOT NULL) AND (length(btrim(action_taken)) > 0)))),
    CONSTRAINT biosecurity_events_kind_check CHECK ((kind = ANY (ARRAY['ahu_filter'::text, 'disinfection_mat'::text, 'contact_plate'::text, 'sentinel_bioassay'::text, 'gowning'::text]))),
    CONSTRAINT biosecurity_events_measure_check CHECK (((measure_value IS NULL) OR (measure_value >= (0)::numeric))),
    CONSTRAINT biosecurity_events_result_check CHECK (((result IS NULL) OR (result = ANY (ARRAY['pass'::text, 'fail'::text, 'below_spec'::text, 'pending'::text]))))
);

ALTER TABLE ONLY public.biosecurity_events FORCE ROW LEVEL SECURITY;


--
-- Name: calendar_weeks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calendar_weeks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    iso_year smallint NOT NULL,
    iso_week smallint NOT NULL,
    starts_on date NOT NULL,
    ends_on date NOT NULL
);

ALTER TABLE ONLY public.calendar_weeks FORCE ROW LEVEL SECURITY;


--
-- Name: corridor_cleanings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.corridor_cleanings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid NOT NULL,
    campaign text,
    trigger text NOT NULL,
    manifest_id uuid,
    ppm_strip_reading integer,
    cleaned_at timestamp with time zone DEFAULT now() NOT NULL,
    cleaned_by uuid NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT corridor_cleanings_movement_cites_manifest_check CHECK (((trigger <> 'waste_movement'::text) OR (manifest_id IS NOT NULL))),
    CONSTRAINT corridor_cleanings_ppm_check CHECK (((ppm_strip_reading IS NULL) OR (ppm_strip_reading >= 0))),
    CONSTRAINT corridor_cleanings_trigger_check CHECK ((trigger = ANY (ARRAY['waste_movement'::text, 'four_hourly'::text, 'shift_change'::text, 'other'::text])))
);

ALTER TABLE ONLY public.corridor_cleanings FORCE ROW LEVEL SECURITY;


--
-- Name: cultivars; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cultivars (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    name_mk text,
    note text,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.cultivars FORCE ROW LEVEL SECURITY;


--
-- Name: decon_bleach_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.decon_bleach_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid NOT NULL,
    cycle_id uuid,
    mixed_at timestamp with time zone DEFAULT now() NOT NULL,
    ppm_strip_reading integer NOT NULL,
    mixed_by uuid NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT decon_bleach_log_ppm_check CHECK ((ppm_strip_reading >= 0))
);

ALTER TABLE ONLY public.decon_bleach_log FORCE ROW LEVEL SECURITY;


--
-- Name: decon_positive_controls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.decon_positive_controls (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    control_code text NOT NULL,
    room_id uuid,
    material text NOT NULL,
    source_desc text,
    taken_at timestamp with time zone DEFAULT now() NOT NULL,
    taken_by uuid NOT NULL,
    storage_location text,
    frozen boolean DEFAULT true NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT decon_positive_controls_material_check CHECK ((material = ANY (ARRAY['leaf'::text, 'root'::text, 'surface_scraping'::text, 'other'::text])))
);

ALTER TABLE ONLY public.decon_positive_controls FORCE ROW LEVEL SECURITY;


--
-- Name: decon_room_cycles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.decon_room_cycles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid NOT NULL,
    campaign text NOT NULL,
    status text DEFAULT 'in_progress'::text NOT NULL,
    started_on date DEFAULT CURRENT_DATE NOT NULL,
    sealed_at timestamp with time zone,
    released_by uuid,
    released_at timestamp with time zone,
    release_note text,
    note text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT decon_room_cycles_status_check CHECK ((status = ANY (ARRAY['in_progress'::text, 'awaiting_verification'::text, 'released'::text, 'failed'::text])))
);

ALTER TABLE ONLY public.decon_room_cycles FORCE ROW LEVEL SECURITY;


--
-- Name: decon_step_signoffs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.decon_step_signoffs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    cycle_id uuid NOT NULL,
    step text NOT NULL,
    passed boolean,
    signed_by uuid NOT NULL,
    signed_at timestamp with time zone DEFAULT now() NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT decon_step_signoffs_step_check CHECK ((step = ANY (ARRAY['dry_clean'::text, 'detergent_wash'::text, 'rinse1_whitecloth'::text, 'bleach'::text, 'rinse2'::text])))
);

ALTER TABLE ONLY public.decon_step_signoffs FORCE ROW LEVEL SECURITY;


--
-- Name: decon_swabs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.decon_swabs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid NOT NULL,
    cycle_id uuid,
    swab_code text NOT NULL,
    location_desc text,
    taken_at timestamp with time zone DEFAULT now() NOT NULL,
    taken_by uuid NOT NULL,
    lab_name text,
    sent_at timestamp with time zone,
    result text DEFAULT 'pending'::text NOT NULL,
    ct_value numeric,
    result_at timestamp with time zone,
    action_taken text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT decon_swabs_result_check CHECK ((result = ANY (ARRAY['pending'::text, 'negative'::text, 'positive'::text, 'inconclusive'::text])))
);

ALTER TABLE ONLY public.decon_swabs FORCE ROW LEVEL SECURITY;


--
-- Name: decon_tool_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.decon_tool_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid NOT NULL,
    cycle_id uuid,
    tool_set text NOT NULL,
    ppm_strip_reading integer NOT NULL,
    soak_minutes numeric,
    checked_at timestamp with time zone DEFAULT now() NOT NULL,
    checked_by uuid NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT decon_tool_log_ppm_check CHECK ((ppm_strip_reading >= 0)),
    CONSTRAINT decon_tool_log_soak_check CHECK (((soak_minutes IS NULL) OR (soak_minutes >= (0)::numeric)))
);

ALTER TABLE ONLY public.decon_tool_log FORCE ROW LEVEL SECURITY;


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    name_mk text,
    parent_id uuid,
    head_user_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.departments FORCE ROW LEVEL SECURITY;


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    verb text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    task_id uuid,
    department_id uuid,
    params jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.events FORCE ROW LEVEL SECURITY;


--
-- Name: handoffs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.handoffs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL,
    from_dept_id uuid,
    to_dept_id uuid,
    requested_by uuid NOT NULL,
    status text DEFAULT 'proposed'::text NOT NULL,
    note text,
    resolved_by uuid,
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT handoffs_status_check CHECK ((status = ANY (ARRAY['proposed'::text, 'accepted'::text, 'rejected'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.handoffs FORCE ROW LEVEL SECURITY;


--
-- Name: harvests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.harvests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    room_id uuid,
    lot_code text NOT NULL,
    status text DEFAULT 'wet'::text NOT NULL,
    harvested_on date DEFAULT CURRENT_DATE NOT NULL,
    plants_harvested integer NOT NULL,
    wet_weight_g numeric NOT NULL,
    dried_on date,
    dry_flower_g numeric,
    dry_trim_g numeric,
    dry_waste_g numeric,
    phi_override_at timestamp with time zone,
    phi_override_by uuid,
    phi_override_reason text,
    harvested_by uuid NOT NULL,
    closed_at timestamp with time zone,
    closed_by uuid,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    CONSTRAINT harvests_close_evidence_check CHECK (((status <> 'closed'::text) OR ((closed_at IS NOT NULL) AND (closed_by IS NOT NULL)))),
    CONSTRAINT harvests_dry_evidence_check CHECK (((status = 'wet'::text) OR ((dried_on IS NOT NULL) AND (dry_flower_g IS NOT NULL)))),
    CONSTRAINT harvests_dry_flower_check CHECK (((dry_flower_g IS NULL) OR (dry_flower_g >= (0)::numeric))),
    CONSTRAINT harvests_dry_trim_check CHECK (((dry_trim_g IS NULL) OR (dry_trim_g >= (0)::numeric))),
    CONSTRAINT harvests_dry_waste_check CHECK (((dry_waste_g IS NULL) OR (dry_waste_g >= (0)::numeric))),
    CONSTRAINT harvests_phi_override_check CHECK ((((phi_override_at IS NULL) AND (phi_override_by IS NULL) AND (phi_override_reason IS NULL)) OR ((phi_override_at IS NOT NULL) AND (phi_override_by IS NOT NULL) AND (phi_override_reason IS NOT NULL) AND (length(btrim(phi_override_reason)) > 0)))),
    CONSTRAINT harvests_plants_check CHECK ((plants_harvested >= 0)),
    CONSTRAINT harvests_status_check CHECK ((status = ANY (ARRAY['wet'::text, 'dried'::text, 'closed'::text]))),
    CONSTRAINT harvests_wet_weight_check CHECK ((wet_weight_g >= (0)::numeric)),
    CONSTRAINT harvests_yield_check CHECK ((((COALESCE(dry_flower_g, (0)::numeric) + COALESCE(dry_trim_g, (0)::numeric)) + COALESCE(dry_waste_g, (0)::numeric)) <= wet_weight_g))
);

ALTER TABLE ONLY public.harvests FORCE ROW LEVEL SECURITY;


--
-- Name: ipm_applications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ipm_applications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid,
    batch_id uuid,
    product text NOT NULL,
    active_ingredient text,
    category text NOT NULL,
    method text,
    dose text,
    target text,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    rei_hours integer,
    phi_days integer,
    applied_by uuid NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    CONSTRAINT ipm_applications_category_check CHECK ((category = ANY (ARRAY['biological'::text, 'botanical'::text, 'chemical'::text, 'mechanical'::text, 'other'::text]))),
    CONSTRAINT ipm_applications_method_check CHECK (((method IS NULL) OR (method = ANY (ARRAY['spray'::text, 'drench'::text, 'fog'::text, 'dust'::text, 'release'::text, 'other'::text])))),
    CONSTRAINT ipm_applications_phi_check CHECK (((phi_days IS NULL) OR (phi_days >= 0))),
    CONSTRAINT ipm_applications_rei_check CHECK (((rei_hours IS NULL) OR (rei_hours >= 0))),
    CONSTRAINT ipm_applications_target_scope_check CHECK (((room_id IS NOT NULL) OR (batch_id IS NOT NULL)))
);

ALTER TABLE ONLY public.ipm_applications FORCE ROW LEVEL SECURITY;


--
-- Name: irrigation_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.irrigation_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid NOT NULL,
    batch_id uuid,
    applied_on date DEFAULT CURRENT_DATE NOT NULL,
    method text,
    water_volume_l numeric,
    feed_ec numeric,
    feed_ph numeric,
    runoff_ec numeric,
    runoff_ph numeric,
    nutrients text,
    applied_by uuid NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    CONSTRAINT irrigation_events_feed_ec_check CHECK (((feed_ec IS NULL) OR (feed_ec >= (0)::numeric))),
    CONSTRAINT irrigation_events_feed_ph_check CHECK (((feed_ph IS NULL) OR ((feed_ph >= (0)::numeric) AND (feed_ph <= (14)::numeric)))),
    CONSTRAINT irrigation_events_method_check CHECK (((method IS NULL) OR (method = ANY (ARRAY['drip'::text, 'hand'::text, 'flood'::text, 'boom'::text, 'other'::text])))),
    CONSTRAINT irrigation_events_runoff_ec_check CHECK (((runoff_ec IS NULL) OR (runoff_ec >= (0)::numeric))),
    CONSTRAINT irrigation_events_runoff_ph_check CHECK (((runoff_ph IS NULL) OR ((runoff_ph >= (0)::numeric) AND (runoff_ph <= (14)::numeric)))),
    CONSTRAINT irrigation_events_water_check CHECK (((water_volume_l IS NULL) OR (water_volume_l >= (0)::numeric)))
);

ALTER TABLE ONLY public.irrigation_events FORCE ROW LEVEL SECURITY;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    recipient_id uuid NOT NULL,
    event_id uuid NOT NULL,
    reason text NOT NULL,
    coalesce_key text NOT NULL,
    read_at timestamp with time zone,
    done_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT notifications_reason_check CHECK ((reason = ANY (ARRAY['assigned'::text, 'mentioned'::text, 'comment'::text, 'status'::text, 'due'::text, 'report'::text, 'capa_stuck'::text, 'validation_stuck'::text, 'workflow'::text])))
);

ALTER TABLE ONLY public.notifications FORCE ROW LEVEL SECURITY;


--
-- Name: plant_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plant_batches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    room_id uuid NOT NULL,
    strain text NOT NULL,
    plant_count integer NOT NULL,
    phase text NOT NULL,
    phase_since date DEFAULT CURRENT_DATE NOT NULL,
    note text,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    code text,
    cultivar_id uuid,
    CONSTRAINT plant_batches_phase_check CHECK ((phase = ANY (ARRAY['nursery'::text, 'clone'::text, 'veg'::text, 'flower'::text, 'mother'::text, 'drying'::text, 'harvested'::text, 'destroyed'::text]))),
    CONSTRAINT plant_batches_plant_count_check CHECK ((plant_count >= 0))
);

ALTER TABLE ONLY public.plant_batches FORCE ROW LEVEL SECURITY;


--
-- Name: plant_phase_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plant_phase_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    plant_id uuid,
    event text NOT NULL,
    from_phase text,
    to_phase text,
    qty integer,
    to_room_id uuid,
    occurred_on date DEFAULT CURRENT_DATE NOT NULL,
    reason text,
    note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT plant_phase_events_event_check CHECK ((event = ANY (ARRAY['create'::text, 'move'::text, 'cull'::text, 'destroy'::text, 'harvest'::text, 'note'::text]))),
    CONSTRAINT plant_phase_events_qty_check CHECK (((qty IS NULL) OR (qty >= 0)))
);

ALTER TABLE ONLY public.plant_phase_events FORCE ROW LEVEL SECURITY;


--
-- Name: plants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    room_id uuid,
    cultivar_id uuid,
    plant_code text NOT NULL,
    clone_date date,
    seq integer NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    status_since date DEFAULT CURRENT_DATE NOT NULL,
    reason text,
    note text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT plants_seq_check CHECK ((seq >= 1)),
    CONSTRAINT plants_status_check CHECK ((status = ANY (ARRAY['active'::text, 'culled'::text, 'destroyed'::text, 'harvested'::text, 'moved'::text])))
);

ALTER TABLE ONLY public.plants FORCE ROW LEVEL SECURITY;


--
-- Name: qc_batch_genealogy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_batch_genealogy (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    parent_batch_id text NOT NULL,
    child_batch_id text NOT NULL,
    relation text DEFAULT 'GENERIC'::text NOT NULL,
    quantity numeric,
    unit text,
    notes text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_batch_genealogy_no_self CHECK ((parent_batch_id <> child_batch_id)),
    CONSTRAINT qc_batch_genealogy_relation_check CHECK ((relation = ANY (ARRAY['CULTIVATION'::text, 'PROCESSING'::text, 'PACKAGING'::text, 'BLEND'::text, 'GENERIC'::text])))
);

ALTER TABLE ONLY public.qc_batch_genealogy FORCE ROW LEVEL SECURITY;


--
-- Name: qc_certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_certificates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    coa_number text NOT NULL,
    batch_id text NOT NULL,
    specification_id uuid NOT NULL,
    sample_id uuid,
    report_date date,
    status text DEFAULT 'DRAFT'::text NOT NULL,
    decision text,
    cert_type text DEFAULT 'ICOA'::text NOT NULL,
    source_lab text,
    analyst_id uuid,
    reviewer_id uuid,
    approver_id uuid,
    notes text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    coq_document_id text,
    coq_generated_at timestamp with time zone,
    supersedes_id uuid,
    revision_reason text,
    laboratory_id uuid,
    retention_start date,
    retention_expiry date,
    archive_ref text,
    cultivation_batch text,
    product_code text,
    packaging text,
    packaging_date date,
    manufacture_date date,
    expiry_date date,
    retest_date date,
    botanical_type text,
    chemotype text,
    void_reason text,
    voided_by uuid,
    voided_at timestamp with time zone,
    analysis_start_date date,
    analysis_end_date date,
    sampling_location text,
    issue_language text DEFAULT 'EN-MK'::text NOT NULL,
    translation_verified_by uuid,
    translation_verified_at timestamp with time zone,
    CONSTRAINT qc_certificates_cert_type_check CHECK ((cert_type = ANY (ARRAY['ICOA'::text, 'ECOA'::text, 'COQ'::text, 'WATER'::text, 'OTHER'::text]))),
    CONSTRAINT qc_certificates_decision_check CHECK (((decision IS NULL) OR (decision = ANY (ARRAY['PASS'::text, 'FAIL'::text])))),
    CONSTRAINT qc_certificates_language_check CHECK ((issue_language = ANY (ARRAY['EN'::text, 'EN-MK'::text]))),
    CONSTRAINT qc_certificates_status_check CHECK ((status = ANY (ARRAY['DRAFT'::text, 'REVIEWED'::text, 'APPROVED'::text, 'RELEASED'::text, 'SUPERSEDED'::text, 'VOIDED'::text])))
);

ALTER TABLE ONLY public.qc_certificates FORCE ROW LEVEL SECURITY;


--
-- Name: qc_chain_of_custody; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_chain_of_custody (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    sample_id uuid NOT NULL,
    from_user_id uuid,
    to_user_id uuid,
    transferred_at timestamp with time zone DEFAULT now() NOT NULL,
    from_location text,
    to_location text,
    transfer_reason text,
    transfer_type text,
    sfr_id uuid,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    sample_condition text,
    condition_ok boolean,
    CONSTRAINT qc_chain_of_custody_type_check CHECK (((transfer_type IS NULL) OR (transfer_type = ANY (ARRAY['FIELD_TO_LAB'::text, 'LAB_INTERNAL'::text, 'LAB_TO_DISPOSAL'::text, 'STABILITY_TRANSFER'::text]))))
);

ALTER TABLE ONLY public.qc_chain_of_custody FORCE ROW LEVEL SECURITY;


--
-- Name: qc_coa_chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_coa_chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer DEFAULT 0 NOT NULL,
    content text NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE(content, ''::text))) STORED,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.qc_coa_chunks FORCE ROW LEVEL SECURITY;


--
-- Name: qc_coa_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_coa_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    doc_number text NOT NULL,
    source_institution text,
    batch_id text NOT NULL,
    material_code text,
    specification_id uuid,
    sample_id uuid,
    original_filename text,
    mime_type text,
    storage_ref text,
    page_count integer,
    report_date date,
    status text DEFAULT 'UPLOADED'::text NOT NULL,
    promoted_coa_id uuid,
    notes text,
    uploaded_by uuid,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    laboratory_id uuid,
    review_deadline date,
    reviewed_at timestamp with time zone,
    review_window_met boolean,
    CONSTRAINT qc_coa_documents_status_check CHECK ((status = ANY (ARRAY['UPLOADED'::text, 'EXTRACTED'::text, 'REVIEWED'::text, 'PROMOTED'::text, 'REJECTED'::text])))
);

ALTER TABLE ONLY public.qc_coa_documents FORCE ROW LEVEL SECURITY;


--
-- Name: qc_coa_extractions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_coa_extractions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    document_id uuid NOT NULL,
    raw_label text NOT NULL,
    raw_value text,
    numeric_value double precision,
    unit text,
    parameter_id uuid,
    test_name text,
    lower_limit double precision,
    upper_limit double precision,
    complies boolean,
    grade_status text DEFAULT 'unmapped'::text NOT NULL,
    confidence double precision,
    source_page integer,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    lab_verdict text,
    CONSTRAINT qc_coa_extractions_grade_check CHECK ((grade_status = ANY (ARRAY['unmapped'::text, 'graded'::text, 'unknown'::text])))
);

ALTER TABLE ONLY public.qc_coa_extractions FORCE ROW LEVEL SECURITY;


--
-- Name: qc_coa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_coa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_coa_verifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_coa_verifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    coa_id uuid NOT NULL,
    source_document_id uuid,
    verdict text NOT NULL,
    checked integer DEFAULT 0 NOT NULL,
    mismatches integer DEFAULT 0 NOT NULL,
    details jsonb DEFAULT '[]'::jsonb NOT NULL,
    verified_by uuid,
    verified_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_coa_verifications_verdict_check CHECK ((verdict = ANY (ARRAY['VERIFIED'::text, 'DISCREPANCY'::text])))
);

ALTER TABLE ONLY public.qc_coa_verifications FORCE ROW LEVEL SECURITY;


--
-- Name: qc_coq; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_coq (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    coq_number text NOT NULL,
    batch_id text NOT NULL,
    product_name text,
    manufacture_date date,
    batch_size text,
    specification_id uuid NOT NULL,
    spec_reference text,
    status text DEFAULT 'DRAFT'::text NOT NULL,
    overall_conform boolean,
    comments text,
    oos_reference text,
    compiled_by uuid,
    compiled_at timestamp with time zone,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    void_reason text,
    voided_by uuid,
    voided_at timestamp with time zone,
    coq_document_id text,
    coq_generated_at timestamp with time zone,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_coq_status_check CHECK ((status = ANY (ARRAY['DRAFT'::text, 'APPROVED'::text, 'VOIDED'::text])))
);

ALTER TABLE ONLY public.qc_coq FORCE ROW LEVEL SECURITY;


--
-- Name: qc_coq_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_coq_lines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    coq_id uuid NOT NULL,
    parameter_id uuid,
    parameter_name text NOT NULL,
    test_method text,
    acceptance_criterion text,
    result_value text,
    result_numeric numeric,
    unit text,
    complies boolean,
    testing_lab text,
    source_coa_id uuid,
    source_coa_number text,
    sorting_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.qc_coq_lines FORCE ROW LEVEL SECURITY;


--
-- Name: qc_coq_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_coq_sources (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    coq_id uuid NOT NULL,
    coa_id uuid NOT NULL,
    coa_number text NOT NULL,
    cert_type text,
    issue_date date,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.qc_coq_sources FORCE ROW LEVEL SECURITY;


--
-- Name: qc_document_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_document_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    object_type text NOT NULL,
    object_id uuid NOT NULL,
    filename text NOT NULL,
    content_type text,
    size_bytes integer NOT NULL,
    sha256 text NOT NULL,
    content bytea NOT NULL,
    uploaded_by uuid,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_document_files_size_check CHECK ((size_bytes >= 0))
);

ALTER TABLE ONLY public.qc_document_files FORCE ROW LEVEL SECURITY;


--
-- Name: qc_ecoa_checklist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_ecoa_checklist (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    document_id uuid NOT NULL,
    sample_id_match boolean,
    method_per_tqa boolean,
    units_per_spec boolean,
    conformance_by_pp boolean,
    discrepancies text,
    notes text,
    outcome text DEFAULT 'PENDING'::text NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_ecoa_checklist_outcome_check CHECK ((outcome = ANY (ARRAY['PENDING'::text, 'ACCEPTED'::text, 'REJECTED'::text])))
);

ALTER TABLE ONLY public.qc_ecoa_checklist FORCE ROW LEVEL SECURITY;


--
-- Name: qc_field_placeholders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_field_placeholders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    raw_label text NOT NULL,
    normalized_label text NOT NULL,
    occurrences integer DEFAULT 1 NOT NULL,
    suggested_test_name text,
    mapped_parameter_id uuid,
    status text DEFAULT 'OPEN'::text NOT NULL,
    first_seen_document_id uuid,
    resolved_by uuid,
    resolved_at timestamp with time zone,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_field_placeholders_status_check CHECK ((status = ANY (ARRAY['OPEN'::text, 'MAPPED'::text, 'IGNORED'::text])))
);

ALTER TABLE ONLY public.qc_field_placeholders FORCE ROW LEVEL SECURITY;


--
-- Name: qc_lab_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_lab_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_laboratories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_laboratories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    lab_code text NOT NULL,
    name text NOT NULL,
    accreditation_body text,
    accreditation_number text,
    iso17025_scope jsonb DEFAULT '[]'::jsonb NOT NULL,
    quality_agreement_ref text,
    locale text,
    decimal_separator text DEFAULT '.'::text NOT NULL,
    country text,
    contact text,
    status text DEFAULT 'ACTIVE'::text NOT NULL,
    notes text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_laboratories_decimal_sep_check CHECK ((decimal_separator = ANY (ARRAY['.'::text, ','::text]))),
    CONSTRAINT qc_laboratories_status_check CHECK ((status = ANY (ARRAY['ACTIVE'::text, 'INACTIVE'::text])))
);

ALTER TABLE ONLY public.qc_laboratories FORCE ROW LEVEL SECURITY;


--
-- Name: qc_oos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_oos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_oos_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_oos_notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    oos_id uuid NOT NULL,
    part text NOT NULL,
    recipients jsonb DEFAULT '[]'::jsonb NOT NULL,
    message text,
    acknowledged boolean DEFAULT false NOT NULL,
    acknowledged_at timestamp with time zone,
    sent_by_id uuid,
    sent_at timestamp with time zone DEFAULT now() NOT NULL,
    acknowledged_by_id uuid,
    CONSTRAINT qc_oos_notifications_part_check CHECK ((part = ANY (ARRAY['A'::text, 'B'::text, 'C'::text, 'D'::text])))
);

ALTER TABLE ONLY public.qc_oos_notifications FORCE ROW LEVEL SECURITY;


--
-- Name: qc_oos_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_oos_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    oos_number text NOT NULL,
    result_id uuid,
    sample_id uuid,
    batch_id text NOT NULL,
    material_code text,
    test_name text,
    method_ref text,
    specification_value text,
    obtained_value text,
    oos_type text DEFAULT 'OOS'::text NOT NULL,
    risk_level text,
    phase text DEFAULT 'I'::text NOT NULL,
    status text DEFAULT 'OPEN'::text NOT NULL,
    detection_date date,
    detected_by_id uuid,
    timeline_deadline date,
    lab_investigation_result text,
    lab_error boolean DEFAULT false NOT NULL,
    invalidated boolean DEFAULT false NOT NULL,
    retest_result text,
    phase_i_completed_at timestamp with time zone,
    phase_i_completed_by_id uuid,
    root_cause_category text,
    root_cause_description text,
    impact_assessment text,
    capa_reference text,
    effectiveness_check_date date,
    effectiveness_check_result text,
    phase_ii_completed_at timestamp with time zone,
    phase_ii_completed_by_id uuid,
    disposition text,
    disposition_reason text,
    qp_approved_at timestamp with time zone,
    qp_approved_by_id uuid,
    closed_at timestamp with time zone,
    closed_by_id uuid,
    notes text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_oos_records_disposition_check CHECK (((disposition IS NULL) OR (disposition = ANY (ARRAY['RELEASE'::text, 'REJECT'::text, 'REPROCESS'::text, 'RETAIN'::text])))),
    CONSTRAINT qc_oos_records_phase_check CHECK ((phase = ANY (ARRAY['I'::text, 'II'::text]))),
    CONSTRAINT qc_oos_records_risk_check CHECK (((risk_level IS NULL) OR (risk_level = ANY (ARRAY['HIGH'::text, 'MEDIUM'::text, 'LOW'::text])))),
    CONSTRAINT qc_oos_records_status_check CHECK ((status = ANY (ARRAY['OPEN'::text, 'PHASE_I'::text, 'PHASE_II'::text, 'CLOSED'::text]))),
    CONSTRAINT qc_oos_records_type_check CHECK ((oos_type = ANY (ARRAY['OOS'::text, 'OOT'::text, 'OOE'::text, 'OOC'::text])))
);

ALTER TABLE ONLY public.qc_oos_records FORCE ROW LEVEL SECURITY;


--
-- Name: qc_oos_register; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_oos_register (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    oos_id uuid NOT NULL,
    action text NOT NULL,
    actor_id uuid,
    details text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.qc_oos_register FORCE ROW LEVEL SECURITY;


--
-- Name: qc_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    coa_id uuid NOT NULL,
    parameter_id uuid,
    test_name text NOT NULL,
    result_value text,
    result_numeric numeric,
    unit text,
    lower_limit numeric,
    upper_limit numeric,
    complies boolean,
    status text DEFAULT 'unknown'::text NOT NULL,
    analyst_id uuid,
    verified_by_id uuid,
    result_date date,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    source_document_code text,
    source_document_date date,
    source_institution text,
    lab_verdict text,
    CONSTRAINT qc_results_status_check CHECK ((status = ANY (ARRAY['pass'::text, 'fail'::text, 'marginal'::text, 'unknown'::text])))
);

ALTER TABLE ONLY public.qc_results FORCE ROW LEVEL SECURITY;


--
-- Name: qc_rqs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_rqs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_sample_field_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_sample_field_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    sfr_number text NOT NULL,
    rqs_id uuid,
    sampling_location text NOT NULL,
    sampling_coordinates text,
    barrel_numbers jsonb DEFAULT '[]'::jsonb NOT NULL,
    num_containers integer,
    destination_facility text NOT NULL,
    destination_location text,
    planned_departure timestamp with time zone,
    actual_departure timestamp with time zone,
    planned_arrival timestamp with time zone,
    actual_arrival timestamp with time zone,
    status text DEFAULT 'CREATED'::text NOT NULL,
    sampled_by_id uuid,
    escort_id uuid,
    received_by_id uuid,
    sample_id uuid,
    notes text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    sampling_equipment text,
    ambient_conditions text,
    received_condition text,
    CONSTRAINT qc_sample_field_records_status_check CHECK ((status = ANY (ARRAY['CREATED'::text, 'IN_FIELD'::text, 'COMPLETED'::text, 'CANCELLED'::text])))
);

ALTER TABLE ONLY public.qc_sample_field_records FORCE ROW LEVEL SECURITY;


--
-- Name: qc_sample_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_sample_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_sample_transports; Type: TABLE; Schema: public; Owner: -
--

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
    CONSTRAINT qc_sample_transports_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'in_transit'::text, 'received'::text])))
);

ALTER TABLE ONLY public.qc_sample_transports FORCE ROW LEVEL SECURITY;


--
-- Name: qc_samples; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_samples (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    sample_id text NOT NULL,
    batch_id text NOT NULL,
    sample_type text,
    material_code text NOT NULL,
    material_name_en text,
    material_name_mk text,
    sampling_date date,
    status text DEFAULT 'COLLECTED'::text NOT NULL,
    location text,
    quantity numeric,
    quantity_unit text,
    retention_sample boolean DEFAULT false NOT NULL,
    parent_id uuid,
    sampling_plan_id uuid,
    notes text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    sample_kind text,
    retention_expiry date,
    non_conforming boolean DEFAULT false NOT NULL,
    non_conforming_reason text,
    tested_by uuid,
    reviewed_by uuid,
    CONSTRAINT qc_samples_kind_check CHECK (((sample_kind IS NULL) OR (sample_kind = ANY (ARRAY['PC'::text, 'MB'::text, 'EXT'::text, 'RET'::text, 'STAB'::text, 'RT'::text, 'CC'::text])))),
    CONSTRAINT qc_samples_status_check CHECK ((status = ANY (ARRAY['COLLECTED'::text, 'IN_TRANSIT'::text, 'RECEIVED'::text, 'IN_TEST'::text, 'TESTED'::text, 'REVIEWED'::text, 'APPROVED'::text, 'RELEASED'::text, 'REJECTED'::text, 'QUARANTINE'::text])))
);

ALTER TABLE ONLY public.qc_samples FORCE ROW LEVEL SECURITY;


--
-- Name: qc_sampling_plan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_sampling_plan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_sampling_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_sampling_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    plan_id text NOT NULL,
    material_code text NOT NULL,
    sampling_frequency text DEFAULT 'EVERY_BATCH'::text NOT NULL,
    sample_size_formula text DEFAULT 'ROUNDUP(SQRT(N)*1.5)'::text NOT NULL,
    min_sample_size integer,
    max_sample_size integer,
    active boolean DEFAULT true NOT NULL,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_sampling_plans_freq_check CHECK ((sampling_frequency = ANY (ARRAY['EVERY_BATCH'::text, 'PERIODIC'::text, 'RANDOM'::text])))
);

ALTER TABLE ONLY public.qc_sampling_plans FORCE ROW LEVEL SECURITY;


--
-- Name: qc_sampling_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_sampling_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    rqs_number text NOT NULL,
    material_code text NOT NULL,
    material_name_en text,
    material_name_mk text,
    batch_id text,
    originating_department text NOT NULL,
    requested_by_id uuid,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    assigned_sp_type text,
    status text DEFAULT 'OPEN'::text NOT NULL,
    registered_by_id uuid,
    registered_at timestamp with time zone,
    registration_deadline timestamp with time zone,
    registration_window_met boolean,
    assigned_to_id uuid,
    assigned_at timestamp with time zone,
    completed_at timestamp with time zone,
    sample_id uuid,
    cancelled_by_id uuid,
    cancelled_at timestamp with time zone,
    cancellation_reason text,
    notes text,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    qc_control_number text,
    num_samples integer,
    required_tests jsonb DEFAULT '[]'::jsonb NOT NULL,
    priority text DEFAULT 'ROUTINE'::text NOT NULL,
    priority_justification text,
    storage_location text,
    material_status text,
    specification_id uuid,
    spec_reference text,
    release_related boolean DEFAULT false NOT NULL,
    CONSTRAINT qc_rqs_material_status_check CHECK (((material_status IS NULL) OR (material_status = ANY (ARRAY['QUARANTINE'::text, 'IN_PROCESS'::text, 'OTHER'::text])))),
    CONSTRAINT qc_rqs_priority_check CHECK ((priority = ANY (ARRAY['ROUTINE'::text, 'URGENT'::text]))),
    CONSTRAINT qc_sampling_requests_status_check CHECK ((status = ANY (ARRAY['OPEN'::text, 'REGISTERED'::text, 'IN_PROGRESS'::text, 'COMPLETED'::text, 'CANCELLED'::text])))
);

ALTER TABLE ONLY public.qc_sampling_requests FORCE ROW LEVEL SECURITY;


--
-- Name: qc_sfr_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_sfr_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_signatures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_signatures (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    object_type text NOT NULL,
    object_id uuid NOT NULL,
    signer_id uuid NOT NULL,
    signer_name text NOT NULL,
    signer_role text,
    meaning text NOT NULL,
    statement text,
    signed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_signatures_meaning_check CHECK ((meaning = ANY (ARRAY['AUTHORED'::text, 'REVIEWED'::text, 'APPROVED'::text, 'RELEASED'::text, 'VERIFIED'::text, 'COQ_ISSUED'::text])))
);

ALTER TABLE ONLY public.qc_signatures FORCE ROW LEVEL SECURITY;


--
-- Name: qc_spec_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_spec_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_spec_parameters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_spec_parameters (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    spec_id uuid NOT NULL,
    test_name_en text NOT NULL,
    test_name_mk text,
    test_method text,
    spec_type text,
    lower_limit numeric,
    upper_limit numeric,
    unit text,
    pharmacopoeia_ref text,
    test_location text,
    sorting_order integer DEFAULT 0 NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    computed_kind text,
    component_a_id uuid,
    component_b_id uuid,
    CONSTRAINT qc_spec_parameters_computed_kind_check CHECK (((computed_kind IS NULL) OR (computed_kind = ANY (ARRAY['total_thc'::text, 'total_cbd'::text]))))
);

ALTER TABLE ONLY public.qc_spec_parameters FORCE ROW LEVEL SECURITY;


--
-- Name: qc_specifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qc_specifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    spec_id text NOT NULL,
    material_code text NOT NULL,
    material_name_en text NOT NULL,
    material_name_mk text,
    version integer DEFAULT 1 NOT NULL,
    effective_date date,
    status text DEFAULT 'DRAFT'::text NOT NULL,
    thc_grade text,
    thc_acceptance_min numeric,
    thc_acceptance_max numeric,
    notes text,
    approved_by uuid,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_specifications_status_check CHECK ((status = ANY (ARRAY['INITIATED'::text, 'DRAFT'::text, 'QC_REVIEW'::text, 'QA_APPROVED'::text, 'NUMBERED'::text, 'TRAINED'::text, 'ACTIVE'::text, 'UNDER_CHANGE'::text, 'SUPERSEDED'::text, 'WITHDRAWN'::text]))),
    CONSTRAINT qc_specifications_thc_grade_check CHECK (((thc_grade IS NULL) OR (thc_grade = ANY (ARRAY['GRADE_I'::text, 'GRADE_II'::text, 'GRADE_III'::text, 'GRADE_IV'::text, 'GRADE_V'::text])))),
    CONSTRAINT qc_specifications_version_check CHECK ((version >= 1))
);

ALTER TABLE ONLY public.qc_specifications FORCE ROW LEVEL SECURITY;


--
-- Name: qc_stability_studies; Type: TABLE; Schema: public; Owner: -
--

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
    CONSTRAINT qc_stability_studies_status_check CHECK ((status = ANY (ARRAY['IN_PROGRESS'::text, 'CLOSED'::text]))),
    CONSTRAINT qc_stability_studies_type_check CHECK ((study_type = ANY (ARRAY['LT'::text, 'ACC'::text, 'INT'::text])))
);

ALTER TABLE ONLY public.qc_stability_studies FORCE ROW LEVEL SECURITY;


--
-- Name: qc_stb_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_stb_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_trn_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_trn_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qc_water_tests; Type: TABLE; Schema: public; Owner: -
--

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
    CONSTRAINT qc_water_tests_grade_check CHECK ((grade = ANY (ARRAY['TW'::text, 'BW'::text, 'TR'::text, 'RO'::text])))
);

ALTER TABLE ONLY public.qc_water_tests FORCE ROW LEVEL SECURITY;


--
-- Name: qc_wt_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qc_wt_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rooms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rooms (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    name_mk text,
    kind text DEFAULT 'flower'::text NOT NULL,
    sort integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT rooms_kind_check CHECK ((kind = ANY (ARRAY['nursery'::text, 'veg'::text, 'flower'::text, 'mother'::text, 'dry'::text, 'other'::text])))
);

ALTER TABLE ONLY public.rooms FORCE ROW LEVEL SECURITY;


--
-- Name: task_assignees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_assignees (
    task_id uuid NOT NULL,
    user_id uuid NOT NULL,
    org_id uuid NOT NULL,
    role text DEFAULT 'assignee'::text NOT NULL,
    assigned_by uuid,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    accepted boolean,
    accepted_at timestamp with time zone
);

ALTER TABLE ONLY public.task_assignees FORCE ROW LEVEL SECURITY;


--
-- Name: task_comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_comments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL,
    user_id uuid NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.task_comments FORCE ROW LEVEL SECURITY;


--
-- Name: task_dependencies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_dependencies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL,
    depends_on_task_id uuid NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT task_dependencies_no_self CHECK ((task_id <> depends_on_task_id))
);

ALTER TABLE ONLY public.task_dependencies FORCE ROW LEVEL SECURITY;


--
-- Name: task_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL,
    url text NOT NULL,
    label text,
    kind text DEFAULT 'other'::text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT task_links_kind_check CHECK ((kind = ANY (ARRAY['drive'::text, 'sop'::text, 'doc'::text, 'other'::text])))
);

ALTER TABLE ONLY public.task_links FORCE ROW LEVEL SECURITY;


--
-- Name: task_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_progress (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL,
    user_id uuid NOT NULL,
    day_label text NOT NULL,
    note text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.task_progress FORCE ROW LEVEL SECURITY;


--
-- Name: task_workflow_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_workflow_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL,
    action text NOT NULL,
    from_state text NOT NULL,
    to_state text NOT NULL,
    actor_id uuid NOT NULL,
    actor_role text,
    remark text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT task_workflow_events_action_check CHECK ((action = ANY (ARRAY['SUBMIT'::text, 'APPROVE'::text, 'REJECT'::text, 'BLOCK'::text, 'UNBLOCK'::text])))
);

ALTER TABLE ONLY public.task_workflow_events FORCE ROW LEVEL SECURITY;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    user_id uuid NOT NULL,
    parent_id uuid,
    title text NOT NULL,
    description text,
    status text DEFAULT 'pending'::text NOT NULL,
    priority text DEFAULT 'medium'::text NOT NULL,
    workflow_state text DEFAULT 'draft'::text NOT NULL,
    task_type text DEFAULT 'other'::text NOT NULL,
    reference_code text,
    blocker_reason text,
    recurrence jsonb,
    department text,
    department_id uuid,
    week_id uuid,
    week_start date,
    days text[] DEFAULT '{}'::text[] NOT NULL,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    due_date date,
    completed_date date,
    estimated_hours numeric,
    actual_hours numeric,
    outcome text,
    is_archived boolean DEFAULT false NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    external_ref text,
    attributes jsonb DEFAULT '{}'::jsonb NOT NULL,
    progress smallint DEFAULT 0 NOT NULL,
    node_kind text DEFAULT 'task'::text NOT NULL,
    batch_id uuid,
    CONSTRAINT tasks_hours_nonnegative_check CHECK ((((estimated_hours IS NULL) OR (estimated_hours >= (0)::numeric)) AND ((actual_hours IS NULL) OR (actual_hours >= (0)::numeric)))),
    CONSTRAINT tasks_node_kind_check CHECK ((node_kind = ANY (ARRAY['task'::text, 'annex'::text, 'step'::text]))),
    CONSTRAINT tasks_progress_check CHECK (((progress >= 0) AND (progress <= 100))),
    CONSTRAINT tasks_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'ongoing'::text, 'review'::text, 'stuck'::text, 'postponed'::text, 'completed'::text]))),
    CONSTRAINT tasks_task_type_check CHECK ((task_type = ANY (ARRAY['capa'::text, 'sop'::text, 'validation'::text, 'document'::text, 'lab'::text, 'meeting'::text, 'admin'::text, 'other'::text])))
);

ALTER TABLE ONLY public.tasks FORCE ROW LEVEL SECURITY;


--
-- Name: waste_manifest_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.waste_manifest_lines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    manifest_id uuid NOT NULL,
    batch_id uuid,
    room_id uuid,
    plant_qty integer,
    weight_kg numeric,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid NOT NULL,
    CONSTRAINT waste_manifest_lines_plant_qty_check CHECK (((plant_qty IS NULL) OR (plant_qty >= 0))),
    CONSTRAINT waste_manifest_lines_quantified_check CHECK (((plant_qty IS NOT NULL) OR (weight_kg IS NOT NULL))),
    CONSTRAINT waste_manifest_lines_weight_check CHECK (((weight_kg IS NULL) OR (weight_kg >= (0)::numeric)))
);

ALTER TABLE ONLY public.waste_manifest_lines FORCE ROW LEVEL SECURITY;


--
-- Name: waste_manifests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.waste_manifests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    manifest_code text NOT NULL,
    waste_type text NOT NULL,
    reason text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    campaign text,
    origin_room_id uuid,
    destination text,
    carrier_name text,
    carrier_ref text,
    gross_weight_kg numeric,
    weighed_at timestamp with time zone,
    weighed_by uuid,
    sealed_at timestamp with time zone,
    witnessed_at timestamp with time zone,
    witnessed_by uuid,
    disposed_at timestamp with time zone,
    disposed_by uuid,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    CONSTRAINT waste_manifests_disposal_evidence_check CHECK (((status <> 'disposed'::text) OR ((disposed_at IS NOT NULL) AND (disposed_by IS NOT NULL)))),
    CONSTRAINT waste_manifests_gross_weight_check CHECK (((gross_weight_kg IS NULL) OR (gross_weight_kg >= (0)::numeric))),
    CONSTRAINT waste_manifests_reason_check CHECK ((reason = ANY (ARRAY['hlvd_eradication'::text, 'routine_cull'::text, 'failed_qc'::text, 'expired'::text, 'spillage'::text, 'other'::text]))),
    CONSTRAINT waste_manifests_seal_evidence_check CHECK (((status = 'draft'::text) OR ((sealed_at IS NOT NULL) AND (weighed_by IS NOT NULL)))),
    CONSTRAINT waste_manifests_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'sealed'::text, 'witnessed'::text, 'disposed'::text]))),
    CONSTRAINT waste_manifests_waste_type_check CHECK ((waste_type = ANY (ARRAY['plant_material'::text, 'root_substrate'::text, 'growing_medium'::text, 'trim'::text, 'packaging'::text, 'other'::text]))),
    CONSTRAINT waste_manifests_witness_evidence_check CHECK (((status = ANY (ARRAY['draft'::text, 'sealed'::text])) OR ((witnessed_at IS NOT NULL) AND (witnessed_by IS NOT NULL))))
);

ALTER TABLE ONLY public.waste_manifests FORCE ROW LEVEL SECURITY;


--
-- Name: weekly_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weekly_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    kind text NOT NULL,
    week_start date NOT NULL,
    week_end date NOT NULL,
    content jsonb DEFAULT '{}'::jsonb NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    created_by uuid,
    locked_by uuid,
    locked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    department_id uuid,
    CONSTRAINT weekly_documents_kind_check CHECK ((kind = ANY (ARRAY['plan'::text, 'report'::text]))),
    CONSTRAINT weekly_documents_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'locked'::text])))
);

ALTER TABLE ONLY public.weekly_documents FORCE ROW LEVEL SECURITY;


--
-- Name: work_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL,
    user_id uuid NOT NULL,
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    hours numeric,
    note text,
    source text DEFAULT 'manual'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT work_sessions_hours_positive_check CHECK (((hours IS NULL) OR (hours > (0)::numeric))),
    CONSTRAINT work_sessions_range_check CHECK (((ended_at IS NULL) OR (ended_at > started_at))),
    CONSTRAINT work_sessions_source_check CHECK ((source = ANY (ARRAY['manual'::text, 'timer'::text, 'capture'::text])))
);

ALTER TABLE ONLY public.work_sessions FORCE ROW LEVEL SECURITY;


--
-- Name: ai_agent_bindings ai_agent_bindings_org_id_function_key_scope_scope_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_agent_bindings
    ADD CONSTRAINT ai_agent_bindings_org_id_function_key_scope_scope_id_key UNIQUE (org_id, function_key, scope, scope_id);


--
-- Name: ai_agent_bindings ai_agent_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_agent_bindings
    ADD CONSTRAINT ai_agent_bindings_pkey PRIMARY KEY (id);


--
-- Name: ai_pins ai_pins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pins
    ADD CONSTRAINT ai_pins_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: biosecurity_events biosecurity_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biosecurity_events
    ADD CONSTRAINT biosecurity_events_pkey PRIMARY KEY (id);


--
-- Name: calendar_weeks calendar_weeks_org_id_iso_year_iso_week_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_weeks
    ADD CONSTRAINT calendar_weeks_org_id_iso_year_iso_week_key UNIQUE (org_id, iso_year, iso_week);


--
-- Name: calendar_weeks calendar_weeks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_weeks
    ADD CONSTRAINT calendar_weeks_pkey PRIMARY KEY (id);


--
-- Name: corridor_cleanings corridor_cleanings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corridor_cleanings
    ADD CONSTRAINT corridor_cleanings_pkey PRIMARY KEY (id);


--
-- Name: cultivars cultivars_org_id_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cultivars
    ADD CONSTRAINT cultivars_org_id_code_key UNIQUE (org_id, code);


--
-- Name: cultivars cultivars_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cultivars
    ADD CONSTRAINT cultivars_pkey PRIMARY KEY (id);


--
-- Name: decon_bleach_log decon_bleach_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_bleach_log
    ADD CONSTRAINT decon_bleach_log_pkey PRIMARY KEY (id);


--
-- Name: decon_positive_controls decon_positive_controls_org_id_control_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_positive_controls
    ADD CONSTRAINT decon_positive_controls_org_id_control_code_key UNIQUE (org_id, control_code);


--
-- Name: decon_positive_controls decon_positive_controls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_positive_controls
    ADD CONSTRAINT decon_positive_controls_pkey PRIMARY KEY (id);


--
-- Name: decon_room_cycles decon_room_cycles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_room_cycles
    ADD CONSTRAINT decon_room_cycles_pkey PRIMARY KEY (id);


--
-- Name: decon_step_signoffs decon_step_signoffs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_step_signoffs
    ADD CONSTRAINT decon_step_signoffs_pkey PRIMARY KEY (id);


--
-- Name: decon_swabs decon_swabs_org_id_swab_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_swabs
    ADD CONSTRAINT decon_swabs_org_id_swab_code_key UNIQUE (org_id, swab_code);


--
-- Name: decon_swabs decon_swabs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_swabs
    ADD CONSTRAINT decon_swabs_pkey PRIMARY KEY (id);


--
-- Name: decon_tool_log decon_tool_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_tool_log
    ADD CONSTRAINT decon_tool_log_pkey PRIMARY KEY (id);


--
-- Name: departments departments_org_id_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_org_id_code_key UNIQUE (org_id, code);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: handoffs handoffs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_pkey PRIMARY KEY (id);


--
-- Name: harvests harvests_org_id_lot_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvests
    ADD CONSTRAINT harvests_org_id_lot_code_key UNIQUE (org_id, lot_code);


--
-- Name: harvests harvests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvests
    ADD CONSTRAINT harvests_pkey PRIMARY KEY (id);


--
-- Name: ipm_applications ipm_applications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ipm_applications
    ADD CONSTRAINT ipm_applications_pkey PRIMARY KEY (id);


--
-- Name: irrigation_events irrigation_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.irrigation_events
    ADD CONSTRAINT irrigation_events_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: plant_batches plant_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_batches
    ADD CONSTRAINT plant_batches_pkey PRIMARY KEY (id);


--
-- Name: plant_phase_events plant_phase_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_phase_events
    ADD CONSTRAINT plant_phase_events_pkey PRIMARY KEY (id);


--
-- Name: plants plants_batch_id_seq_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plants
    ADD CONSTRAINT plants_batch_id_seq_key UNIQUE (batch_id, seq);


--
-- Name: plants plants_org_id_plant_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plants
    ADD CONSTRAINT plants_org_id_plant_code_key UNIQUE (org_id, plant_code);


--
-- Name: plants plants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plants
    ADD CONSTRAINT plants_pkey PRIMARY KEY (id);


--
-- Name: qc_batch_genealogy qc_batch_genealogy_edge_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_batch_genealogy
    ADD CONSTRAINT qc_batch_genealogy_edge_key UNIQUE (org_id, parent_batch_id, child_batch_id);


--
-- Name: qc_batch_genealogy qc_batch_genealogy_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_batch_genealogy
    ADD CONSTRAINT qc_batch_genealogy_pkey PRIMARY KEY (id);


--
-- Name: qc_certificates qc_certificates_coa_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_certificates
    ADD CONSTRAINT qc_certificates_coa_number_key UNIQUE (org_id, coa_number);


--
-- Name: qc_certificates qc_certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_certificates
    ADD CONSTRAINT qc_certificates_pkey PRIMARY KEY (id);


--
-- Name: qc_chain_of_custody qc_chain_of_custody_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_chain_of_custody
    ADD CONSTRAINT qc_chain_of_custody_pkey PRIMARY KEY (id);


--
-- Name: qc_coa_chunks qc_coa_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_chunks
    ADD CONSTRAINT qc_coa_chunks_pkey PRIMARY KEY (id);


--
-- Name: qc_coa_documents qc_coa_documents_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_documents
    ADD CONSTRAINT qc_coa_documents_number_key UNIQUE (org_id, doc_number);


--
-- Name: qc_coa_documents qc_coa_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_documents
    ADD CONSTRAINT qc_coa_documents_pkey PRIMARY KEY (id);


--
-- Name: qc_coa_extractions qc_coa_extractions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_extractions
    ADD CONSTRAINT qc_coa_extractions_pkey PRIMARY KEY (id);


--
-- Name: qc_coa_verifications qc_coa_verifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_verifications
    ADD CONSTRAINT qc_coa_verifications_pkey PRIMARY KEY (id);


--
-- Name: qc_coq_lines qc_coq_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq_lines
    ADD CONSTRAINT qc_coq_lines_pkey PRIMARY KEY (id);


--
-- Name: qc_coq qc_coq_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq
    ADD CONSTRAINT qc_coq_number_key UNIQUE (org_id, coq_number);


--
-- Name: qc_coq qc_coq_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq
    ADD CONSTRAINT qc_coq_pkey PRIMARY KEY (id);


--
-- Name: qc_coq_sources qc_coq_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq_sources
    ADD CONSTRAINT qc_coq_sources_pkey PRIMARY KEY (id);


--
-- Name: qc_coq_sources qc_coq_sources_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq_sources
    ADD CONSTRAINT qc_coq_sources_unique UNIQUE (org_id, coq_id, coa_id);


--
-- Name: qc_document_files qc_document_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_document_files
    ADD CONSTRAINT qc_document_files_pkey PRIMARY KEY (id);


--
-- Name: qc_ecoa_checklist qc_ecoa_checklist_document_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_ecoa_checklist
    ADD CONSTRAINT qc_ecoa_checklist_document_key UNIQUE (org_id, document_id);


--
-- Name: qc_ecoa_checklist qc_ecoa_checklist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_ecoa_checklist
    ADD CONSTRAINT qc_ecoa_checklist_pkey PRIMARY KEY (id);


--
-- Name: qc_field_placeholders qc_field_placeholders_label_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_field_placeholders
    ADD CONSTRAINT qc_field_placeholders_label_key UNIQUE (org_id, normalized_label);


--
-- Name: qc_field_placeholders qc_field_placeholders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_field_placeholders
    ADD CONSTRAINT qc_field_placeholders_pkey PRIMARY KEY (id);


--
-- Name: qc_laboratories qc_laboratories_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_laboratories
    ADD CONSTRAINT qc_laboratories_code_key UNIQUE (org_id, lab_code);


--
-- Name: qc_laboratories qc_laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_laboratories
    ADD CONSTRAINT qc_laboratories_pkey PRIMARY KEY (id);


--
-- Name: qc_oos_notifications qc_oos_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_notifications
    ADD CONSTRAINT qc_oos_notifications_pkey PRIMARY KEY (id);


--
-- Name: qc_oos_records qc_oos_records_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_records
    ADD CONSTRAINT qc_oos_records_number_key UNIQUE (org_id, oos_number);


--
-- Name: qc_oos_records qc_oos_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_records
    ADD CONSTRAINT qc_oos_records_pkey PRIMARY KEY (id);


--
-- Name: qc_oos_register qc_oos_register_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_register
    ADD CONSTRAINT qc_oos_register_pkey PRIMARY KEY (id);


--
-- Name: qc_results qc_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_results
    ADD CONSTRAINT qc_results_pkey PRIMARY KEY (id);


--
-- Name: qc_sample_field_records qc_sample_field_records_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sample_field_records
    ADD CONSTRAINT qc_sample_field_records_number_key UNIQUE (org_id, sfr_number);


--
-- Name: qc_sample_field_records qc_sample_field_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sample_field_records
    ADD CONSTRAINT qc_sample_field_records_pkey PRIMARY KEY (id);


--
-- Name: qc_sample_transports qc_sample_transports_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sample_transports
    ADD CONSTRAINT qc_sample_transports_number_key UNIQUE (org_id, transport_id);


--
-- Name: qc_sample_transports qc_sample_transports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sample_transports
    ADD CONSTRAINT qc_sample_transports_pkey PRIMARY KEY (id);


--
-- Name: qc_samples qc_samples_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_samples
    ADD CONSTRAINT qc_samples_pkey PRIMARY KEY (id);


--
-- Name: qc_samples qc_samples_sample_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_samples
    ADD CONSTRAINT qc_samples_sample_id_key UNIQUE (org_id, sample_id);


--
-- Name: qc_sampling_plans qc_sampling_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sampling_plans
    ADD CONSTRAINT qc_sampling_plans_pkey PRIMARY KEY (id);


--
-- Name: qc_sampling_plans qc_sampling_plans_plan_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sampling_plans
    ADD CONSTRAINT qc_sampling_plans_plan_id_key UNIQUE (org_id, plan_id);


--
-- Name: qc_sampling_requests qc_sampling_requests_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sampling_requests
    ADD CONSTRAINT qc_sampling_requests_number_key UNIQUE (org_id, rqs_number);


--
-- Name: qc_sampling_requests qc_sampling_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sampling_requests
    ADD CONSTRAINT qc_sampling_requests_pkey PRIMARY KEY (id);


--
-- Name: qc_signatures qc_signatures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_signatures
    ADD CONSTRAINT qc_signatures_pkey PRIMARY KEY (id);


--
-- Name: qc_spec_parameters qc_spec_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_spec_parameters
    ADD CONSTRAINT qc_spec_parameters_pkey PRIMARY KEY (id);


--
-- Name: qc_specifications qc_specifications_material_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_specifications
    ADD CONSTRAINT qc_specifications_material_version_key UNIQUE (org_id, material_code, version);


--
-- Name: qc_specifications qc_specifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_specifications
    ADD CONSTRAINT qc_specifications_pkey PRIMARY KEY (id);


--
-- Name: qc_specifications qc_specifications_spec_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_specifications
    ADD CONSTRAINT qc_specifications_spec_id_key UNIQUE (org_id, spec_id);


--
-- Name: qc_stability_studies qc_stability_studies_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_stability_studies
    ADD CONSTRAINT qc_stability_studies_number_key UNIQUE (org_id, study_id);


--
-- Name: qc_stability_studies qc_stability_studies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_stability_studies
    ADD CONSTRAINT qc_stability_studies_pkey PRIMARY KEY (id);


--
-- Name: qc_water_tests qc_water_tests_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_water_tests
    ADD CONSTRAINT qc_water_tests_number_key UNIQUE (org_id, water_test_id);


--
-- Name: qc_water_tests qc_water_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_water_tests
    ADD CONSTRAINT qc_water_tests_pkey PRIMARY KEY (id);


--
-- Name: rooms rooms_org_id_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rooms
    ADD CONSTRAINT rooms_org_id_code_key UNIQUE (org_id, code);


--
-- Name: rooms rooms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rooms
    ADD CONSTRAINT rooms_pkey PRIMARY KEY (id);


--
-- Name: task_assignees task_assignees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignees
    ADD CONSTRAINT task_assignees_pkey PRIMARY KEY (task_id, user_id);


--
-- Name: task_comments task_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_comments
    ADD CONSTRAINT task_comments_pkey PRIMARY KEY (id);


--
-- Name: task_dependencies task_dependencies_edge_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_dependencies
    ADD CONSTRAINT task_dependencies_edge_key UNIQUE (task_id, depends_on_task_id);


--
-- Name: task_dependencies task_dependencies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_dependencies
    ADD CONSTRAINT task_dependencies_pkey PRIMARY KEY (id);


--
-- Name: task_links task_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_links
    ADD CONSTRAINT task_links_pkey PRIMARY KEY (id);


--
-- Name: task_progress task_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_progress
    ADD CONSTRAINT task_progress_pkey PRIMARY KEY (id);


--
-- Name: task_workflow_events task_workflow_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_workflow_events
    ADD CONSTRAINT task_workflow_events_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: waste_manifest_lines waste_manifest_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_manifest_lines
    ADD CONSTRAINT waste_manifest_lines_pkey PRIMARY KEY (id);


--
-- Name: waste_manifests waste_manifests_org_id_manifest_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_manifests
    ADD CONSTRAINT waste_manifests_org_id_manifest_code_key UNIQUE (org_id, manifest_code);


--
-- Name: waste_manifests waste_manifests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_manifests
    ADD CONSTRAINT waste_manifests_pkey PRIMARY KEY (id);


--
-- Name: weekly_documents weekly_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_documents
    ADD CONSTRAINT weekly_documents_pkey PRIMARY KEY (id);


--
-- Name: work_sessions work_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_sessions
    ADD CONSTRAINT work_sessions_pkey PRIMARY KEY (id);


--
-- Name: ai_agent_bindings_org_scope_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ai_agent_bindings_org_scope_uniq ON public.ai_agent_bindings USING btree (org_id, function_key) WHERE (scope = 'org'::text);


--
-- Name: audit_log_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_created_at_idx ON public.audit_log USING btree (created_at DESC);


--
-- Name: audit_log_table_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_table_idx ON public.audit_log USING btree (table_name, record_id);


--
-- Name: biosecurity_events_open_fail_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX biosecurity_events_open_fail_idx ON public.biosecurity_events USING btree (org_id, occurred_on DESC) WHERE (result = ANY (ARRAY['fail'::text, 'below_spec'::text]));


--
-- Name: biosecurity_events_org_kind_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX biosecurity_events_org_kind_idx ON public.biosecurity_events USING btree (org_id, kind, occurred_on DESC);


--
-- Name: biosecurity_events_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX biosecurity_events_room_idx ON public.biosecurity_events USING btree (room_id, occurred_on DESC) WHERE (room_id IS NOT NULL);


--
-- Name: corridor_cleanings_manifest_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX corridor_cleanings_manifest_idx ON public.corridor_cleanings USING btree (manifest_id) WHERE (manifest_id IS NOT NULL);


--
-- Name: corridor_cleanings_org_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX corridor_cleanings_org_room_idx ON public.corridor_cleanings USING btree (org_id, room_id, cleaned_at DESC);


--
-- Name: decon_bleach_log_org_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX decon_bleach_log_org_room_idx ON public.decon_bleach_log USING btree (org_id, room_id, mixed_at);


--
-- Name: decon_positive_controls_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX decon_positive_controls_org_idx ON public.decon_positive_controls USING btree (org_id, taken_at);


--
-- Name: decon_room_cycles_open_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX decon_room_cycles_open_idx ON public.decon_room_cycles USING btree (org_id, room_id, campaign) WHERE (status = ANY (ARRAY['in_progress'::text, 'awaiting_verification'::text]));


--
-- Name: decon_room_cycles_org_campaign_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX decon_room_cycles_org_campaign_idx ON public.decon_room_cycles USING btree (org_id, campaign);


--
-- Name: decon_step_signoffs_cycle_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX decon_step_signoffs_cycle_idx ON public.decon_step_signoffs USING btree (cycle_id, signed_at);


--
-- Name: decon_swabs_cycle_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX decon_swabs_cycle_idx ON public.decon_swabs USING btree (cycle_id);


--
-- Name: decon_swabs_org_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX decon_swabs_org_room_idx ON public.decon_swabs USING btree (org_id, room_id);


--
-- Name: decon_tool_log_org_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX decon_tool_log_org_room_idx ON public.decon_tool_log USING btree (org_id, room_id, checked_at);


--
-- Name: events_org_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX events_org_created_idx ON public.events USING btree (org_id, created_at DESC);


--
-- Name: events_org_dept_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX events_org_dept_created_idx ON public.events USING btree (org_id, department_id, created_at DESC);


--
-- Name: harvests_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX harvests_batch_idx ON public.harvests USING btree (batch_id);


--
-- Name: harvests_org_harvested_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX harvests_org_harvested_idx ON public.harvests USING btree (org_id, harvested_on DESC);


--
-- Name: harvests_org_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX harvests_org_status_idx ON public.harvests USING btree (org_id, status);


--
-- Name: ipm_applications_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ipm_applications_batch_idx ON public.ipm_applications USING btree (batch_id, applied_at DESC) WHERE (batch_id IS NOT NULL);


--
-- Name: ipm_applications_org_applied_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ipm_applications_org_applied_idx ON public.ipm_applications USING btree (org_id, applied_at DESC);


--
-- Name: ipm_applications_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ipm_applications_room_idx ON public.ipm_applications USING btree (room_id, applied_at DESC) WHERE (room_id IS NOT NULL);


--
-- Name: irrigation_events_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX irrigation_events_batch_idx ON public.irrigation_events USING btree (batch_id, applied_on DESC) WHERE (batch_id IS NOT NULL);


--
-- Name: irrigation_events_org_applied_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX irrigation_events_org_applied_idx ON public.irrigation_events USING btree (org_id, applied_on DESC);


--
-- Name: irrigation_events_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX irrigation_events_room_idx ON public.irrigation_events USING btree (room_id, applied_on DESC);


--
-- Name: notifications_coalesce_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX notifications_coalesce_idx ON public.notifications USING btree (recipient_id, coalesce_key) WHERE ((read_at IS NULL) AND (done_at IS NULL));


--
-- Name: notifications_recipient_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notifications_recipient_created_idx ON public.notifications USING btree (recipient_id, created_at DESC);


--
-- Name: notifications_unread_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notifications_unread_idx ON public.notifications USING btree (recipient_id) WHERE ((read_at IS NULL) AND (done_at IS NULL));


--
-- Name: plant_batches_org_code_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX plant_batches_org_code_key ON public.plant_batches USING btree (org_id, code) WHERE (code IS NOT NULL);


--
-- Name: plant_batches_org_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX plant_batches_org_room_idx ON public.plant_batches USING btree (org_id, room_id) WHERE is_active;


--
-- Name: plant_phase_events_org_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX plant_phase_events_org_batch_idx ON public.plant_phase_events USING btree (org_id, batch_id, occurred_on);


--
-- Name: plants_active_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX plants_active_batch_idx ON public.plants USING btree (batch_id) WHERE (status = 'active'::text);


--
-- Name: plants_org_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX plants_org_batch_idx ON public.plants USING btree (org_id, batch_id);


--
-- Name: qc_batch_genealogy_child_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_batch_genealogy_child_idx ON public.qc_batch_genealogy USING btree (org_id, child_batch_id);


--
-- Name: qc_batch_genealogy_parent_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_batch_genealogy_parent_idx ON public.qc_batch_genealogy USING btree (org_id, parent_batch_id);


--
-- Name: qc_certificates_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_certificates_batch_idx ON public.qc_certificates USING btree (org_id, batch_id);


--
-- Name: qc_certificates_spec_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_certificates_spec_idx ON public.qc_certificates USING btree (org_id, specification_id);


--
-- Name: qc_chain_of_custody_sample_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_chain_of_custody_sample_idx ON public.qc_chain_of_custody USING btree (org_id, sample_id);


--
-- Name: qc_coa_chunks_doc_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coa_chunks_doc_idx ON public.qc_coa_chunks USING btree (org_id, document_id);


--
-- Name: qc_coa_chunks_tsv_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coa_chunks_tsv_idx ON public.qc_coa_chunks USING gin (tsv);


--
-- Name: qc_coa_documents_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coa_documents_batch_idx ON public.qc_coa_documents USING btree (org_id, batch_id);


--
-- Name: qc_coa_documents_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coa_documents_status_idx ON public.qc_coa_documents USING btree (org_id, status);


--
-- Name: qc_coa_extractions_document_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coa_extractions_document_idx ON public.qc_coa_extractions USING btree (org_id, document_id);


--
-- Name: qc_coa_verifications_coa_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coa_verifications_coa_idx ON public.qc_coa_verifications USING btree (org_id, coa_id);


--
-- Name: qc_coq_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coq_batch_idx ON public.qc_coq USING btree (org_id, batch_id);


--
-- Name: qc_coq_lines_coq_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coq_lines_coq_idx ON public.qc_coq_lines USING btree (org_id, coq_id);


--
-- Name: qc_coq_one_approved_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX qc_coq_one_approved_idx ON public.qc_coq USING btree (org_id, batch_id, specification_id) WHERE (status = 'APPROVED'::text);


--
-- Name: qc_coq_sources_coq_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_coq_sources_coq_idx ON public.qc_coq_sources USING btree (org_id, coq_id);


--
-- Name: qc_document_files_object_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_document_files_object_idx ON public.qc_document_files USING btree (org_id, object_type, object_id);


--
-- Name: qc_ecoa_checklist_document_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_ecoa_checklist_document_idx ON public.qc_ecoa_checklist USING btree (org_id, document_id);


--
-- Name: qc_field_placeholders_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_field_placeholders_status_idx ON public.qc_field_placeholders USING btree (org_id, status);


--
-- Name: qc_laboratories_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_laboratories_status_idx ON public.qc_laboratories USING btree (org_id, status);


--
-- Name: qc_oos_notifications_oos_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_oos_notifications_oos_idx ON public.qc_oos_notifications USING btree (org_id, oos_id);


--
-- Name: qc_oos_records_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_oos_records_batch_idx ON public.qc_oos_records USING btree (org_id, batch_id);


--
-- Name: qc_oos_records_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_oos_records_status_idx ON public.qc_oos_records USING btree (org_id, status);


--
-- Name: qc_oos_register_oos_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_oos_register_oos_idx ON public.qc_oos_register USING btree (org_id, oos_id);


--
-- Name: qc_results_coa_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_results_coa_idx ON public.qc_results USING btree (org_id, coa_id);


--
-- Name: qc_sample_field_records_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_sample_field_records_status_idx ON public.qc_sample_field_records USING btree (org_id, status);


--
-- Name: qc_sample_transports_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_sample_transports_status_idx ON public.qc_sample_transports USING btree (org_id, status);


--
-- Name: qc_samples_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_samples_batch_idx ON public.qc_samples USING btree (org_id, batch_id);


--
-- Name: qc_samples_parent_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_samples_parent_idx ON public.qc_samples USING btree (org_id, parent_id) WHERE (parent_id IS NOT NULL);


--
-- Name: qc_samples_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_samples_status_idx ON public.qc_samples USING btree (org_id, status);


--
-- Name: qc_sampling_plans_material_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_sampling_plans_material_idx ON public.qc_sampling_plans USING btree (org_id, material_code) WHERE active;


--
-- Name: qc_sampling_requests_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_sampling_requests_batch_idx ON public.qc_sampling_requests USING btree (org_id, batch_id);


--
-- Name: qc_sampling_requests_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_sampling_requests_status_idx ON public.qc_sampling_requests USING btree (org_id, status);


--
-- Name: qc_signatures_object_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_signatures_object_idx ON public.qc_signatures USING btree (org_id, object_type, object_id);


--
-- Name: qc_spec_parameters_spec_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_spec_parameters_spec_idx ON public.qc_spec_parameters USING btree (org_id, spec_id);


--
-- Name: qc_specifications_material_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_specifications_material_idx ON public.qc_specifications USING btree (org_id, material_code);


--
-- Name: qc_specifications_one_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX qc_specifications_one_active_idx ON public.qc_specifications USING btree (org_id, material_code) WHERE (status = 'ACTIVE'::text);


--
-- Name: qc_stability_studies_mat_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_stability_studies_mat_idx ON public.qc_stability_studies USING btree (org_id, material_code);


--
-- Name: qc_water_tests_loc_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_water_tests_loc_idx ON public.qc_water_tests USING btree (org_id, location);


--
-- Name: task_dependencies_dep_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX task_dependencies_dep_idx ON public.task_dependencies USING btree (org_id, depends_on_task_id);


--
-- Name: task_links_task_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX task_links_task_idx ON public.task_links USING btree (task_id);


--
-- Name: task_progress_task_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX task_progress_task_idx ON public.task_progress USING btree (task_id);


--
-- Name: task_workflow_events_task_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX task_workflow_events_task_idx ON public.task_workflow_events USING btree (org_id, task_id);


--
-- Name: tasks_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_batch_idx ON public.tasks USING btree (batch_id) WHERE (batch_id IS NOT NULL);


--
-- Name: tasks_dept_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_dept_idx ON public.tasks USING btree (department_id);


--
-- Name: tasks_due_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_due_idx ON public.tasks USING btree (org_id, due_date) WHERE (due_date IS NOT NULL);


--
-- Name: tasks_org_external_ref_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX tasks_org_external_ref_key ON public.tasks USING btree (org_id, external_ref) WHERE ((external_ref IS NOT NULL) AND (is_deleted = false));


--
-- Name: tasks_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_org_idx ON public.tasks USING btree (org_id);


--
-- Name: tasks_org_week_start_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_org_week_start_idx ON public.tasks USING btree (org_id, week_start DESC, created_at DESC);


--
-- Name: tasks_owner_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_owner_idx ON public.tasks USING btree (user_id);


--
-- Name: tasks_parent_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_parent_idx ON public.tasks USING btree (parent_id);


--
-- Name: tasks_week_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_week_idx ON public.tasks USING btree (week_id);


--
-- Name: waste_manifest_lines_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX waste_manifest_lines_batch_idx ON public.waste_manifest_lines USING btree (batch_id) WHERE (batch_id IS NOT NULL);


--
-- Name: waste_manifest_lines_manifest_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX waste_manifest_lines_manifest_idx ON public.waste_manifest_lines USING btree (manifest_id);


--
-- Name: waste_manifests_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX waste_manifests_org_idx ON public.waste_manifests USING btree (org_id, created_at DESC);


--
-- Name: waste_manifests_org_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX waste_manifests_org_status_idx ON public.waste_manifests USING btree (org_id, status);


--
-- Name: weekly_documents_org_kind_week_dept_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX weekly_documents_org_kind_week_dept_key ON public.weekly_documents USING btree (org_id, kind, week_start, department_id) WHERE (department_id IS NOT NULL);


--
-- Name: weekly_documents_org_kind_week_orgwide_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX weekly_documents_org_kind_week_orgwide_key ON public.weekly_documents USING btree (org_id, kind, week_start) WHERE (department_id IS NULL);


--
-- Name: weekly_documents_org_week_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX weekly_documents_org_week_idx ON public.weekly_documents USING btree (org_id, week_start);


--
-- Name: work_sessions_org_started_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX work_sessions_org_started_idx ON public.work_sessions USING btree (org_id, started_at);


--
-- Name: work_sessions_task_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX work_sessions_task_idx ON public.work_sessions USING btree (task_id);


--
-- Name: ai_agent_bindings audit_ai_agent_bindings; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_ai_agent_bindings AFTER INSERT OR DELETE OR UPDATE ON public.ai_agent_bindings FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: ai_pins audit_ai_pins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_ai_pins AFTER INSERT OR DELETE OR UPDATE ON public.ai_pins FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: biosecurity_events audit_biosecurity_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_biosecurity_events AFTER INSERT OR DELETE OR UPDATE ON public.biosecurity_events FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: calendar_weeks audit_calendar_weeks; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_calendar_weeks AFTER INSERT OR DELETE OR UPDATE ON public.calendar_weeks FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: corridor_cleanings audit_corridor_cleanings; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_corridor_cleanings AFTER INSERT OR DELETE OR UPDATE ON public.corridor_cleanings FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: cultivars audit_cultivars; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_cultivars AFTER INSERT OR DELETE OR UPDATE ON public.cultivars FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: decon_bleach_log audit_decon_bleach_log; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_decon_bleach_log AFTER INSERT OR DELETE OR UPDATE ON public.decon_bleach_log FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: decon_positive_controls audit_decon_positive_controls; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_decon_positive_controls AFTER INSERT OR DELETE OR UPDATE ON public.decon_positive_controls FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: decon_room_cycles audit_decon_room_cycles; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_decon_room_cycles AFTER INSERT OR DELETE OR UPDATE ON public.decon_room_cycles FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: decon_step_signoffs audit_decon_step_signoffs; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_decon_step_signoffs AFTER INSERT OR DELETE OR UPDATE ON public.decon_step_signoffs FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: decon_swabs audit_decon_swabs; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_decon_swabs AFTER INSERT OR DELETE OR UPDATE ON public.decon_swabs FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: decon_tool_log audit_decon_tool_log; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_decon_tool_log AFTER INSERT OR DELETE OR UPDATE ON public.decon_tool_log FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: departments audit_departments; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_departments AFTER INSERT OR DELETE OR UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: handoffs audit_handoffs; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_handoffs AFTER INSERT OR DELETE OR UPDATE ON public.handoffs FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: harvests audit_harvests; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_harvests AFTER INSERT OR DELETE OR UPDATE ON public.harvests FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: ipm_applications audit_ipm_applications; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_ipm_applications AFTER INSERT OR DELETE OR UPDATE ON public.ipm_applications FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: irrigation_events audit_irrigation_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_irrigation_events AFTER INSERT OR DELETE OR UPDATE ON public.irrigation_events FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: plant_batches audit_plant_batches; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_plant_batches AFTER INSERT OR DELETE OR UPDATE ON public.plant_batches FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: plant_phase_events audit_plant_phase_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_plant_phase_events AFTER INSERT OR DELETE OR UPDATE ON public.plant_phase_events FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: plants audit_plants; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_plants AFTER INSERT OR DELETE OR UPDATE ON public.plants FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_batch_genealogy audit_qc_batch_genealogy; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_batch_genealogy AFTER INSERT OR DELETE OR UPDATE ON public.qc_batch_genealogy FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_certificates audit_qc_certificates; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_certificates AFTER INSERT OR DELETE OR UPDATE ON public.qc_certificates FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_chain_of_custody audit_qc_chain_of_custody; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_chain_of_custody AFTER INSERT OR DELETE OR UPDATE ON public.qc_chain_of_custody FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_coa_chunks audit_qc_coa_chunks; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_coa_chunks AFTER INSERT OR DELETE OR UPDATE ON public.qc_coa_chunks FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_coa_documents audit_qc_coa_documents; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_coa_documents AFTER INSERT OR DELETE OR UPDATE ON public.qc_coa_documents FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_coa_extractions audit_qc_coa_extractions; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_coa_extractions AFTER INSERT OR DELETE OR UPDATE ON public.qc_coa_extractions FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_coa_verifications audit_qc_coa_verifications; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_coa_verifications AFTER INSERT OR DELETE OR UPDATE ON public.qc_coa_verifications FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_coq audit_qc_coq; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_coq AFTER INSERT OR DELETE OR UPDATE ON public.qc_coq FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_coq_lines audit_qc_coq_lines; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_coq_lines AFTER INSERT OR DELETE OR UPDATE ON public.qc_coq_lines FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_coq_sources audit_qc_coq_sources; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_coq_sources AFTER INSERT OR DELETE OR UPDATE ON public.qc_coq_sources FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_document_files audit_qc_document_files; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_document_files AFTER INSERT OR DELETE OR UPDATE ON public.qc_document_files FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_ecoa_checklist audit_qc_ecoa_checklist; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_ecoa_checklist AFTER INSERT OR DELETE OR UPDATE ON public.qc_ecoa_checklist FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_field_placeholders audit_qc_field_placeholders; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_field_placeholders AFTER INSERT OR DELETE OR UPDATE ON public.qc_field_placeholders FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_laboratories audit_qc_laboratories; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_laboratories AFTER INSERT OR DELETE OR UPDATE ON public.qc_laboratories FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_oos_notifications audit_qc_oos_notifications; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_oos_notifications AFTER INSERT OR DELETE OR UPDATE ON public.qc_oos_notifications FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_oos_records audit_qc_oos_records; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_oos_records AFTER INSERT OR DELETE OR UPDATE ON public.qc_oos_records FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_oos_register audit_qc_oos_register; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_oos_register AFTER INSERT OR DELETE OR UPDATE ON public.qc_oos_register FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_results audit_qc_results; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_results AFTER INSERT OR DELETE OR UPDATE ON public.qc_results FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_sample_field_records audit_qc_sample_field_records; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_sample_field_records AFTER INSERT OR DELETE OR UPDATE ON public.qc_sample_field_records FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_sample_transports audit_qc_sample_transports; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_sample_transports AFTER INSERT OR DELETE OR UPDATE ON public.qc_sample_transports FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_samples audit_qc_samples; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_samples AFTER INSERT OR DELETE OR UPDATE ON public.qc_samples FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_sampling_plans audit_qc_sampling_plans; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_sampling_plans AFTER INSERT OR DELETE OR UPDATE ON public.qc_sampling_plans FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_sampling_requests audit_qc_sampling_requests; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_sampling_requests AFTER INSERT OR DELETE OR UPDATE ON public.qc_sampling_requests FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_signatures audit_qc_signatures; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_signatures AFTER INSERT OR DELETE OR UPDATE ON public.qc_signatures FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_spec_parameters audit_qc_spec_parameters; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_spec_parameters AFTER INSERT OR DELETE OR UPDATE ON public.qc_spec_parameters FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_specifications audit_qc_specifications; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_specifications AFTER INSERT OR DELETE OR UPDATE ON public.qc_specifications FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_stability_studies audit_qc_stability_studies; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_stability_studies AFTER INSERT OR DELETE OR UPDATE ON public.qc_stability_studies FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_water_tests audit_qc_water_tests; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_water_tests AFTER INSERT OR DELETE OR UPDATE ON public.qc_water_tests FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: rooms audit_rooms; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_rooms AFTER INSERT OR DELETE OR UPDATE ON public.rooms FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_assignees audit_task_assignees; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_assignees AFTER INSERT OR DELETE OR UPDATE ON public.task_assignees FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_comments audit_task_comments; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_comments AFTER INSERT OR DELETE OR UPDATE ON public.task_comments FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_dependencies audit_task_dependencies; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_dependencies AFTER INSERT OR DELETE OR UPDATE ON public.task_dependencies FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_links audit_task_links; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_links AFTER INSERT OR DELETE OR UPDATE ON public.task_links FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_progress audit_task_prog; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_prog AFTER INSERT OR DELETE OR UPDATE ON public.task_progress FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_workflow_events audit_task_workflow_events; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_workflow_events AFTER INSERT OR DELETE OR UPDATE ON public.task_workflow_events FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: tasks audit_tasks; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_tasks AFTER INSERT OR DELETE OR UPDATE ON public.tasks FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: waste_manifest_lines audit_waste_manifest_lines; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_waste_manifest_lines AFTER INSERT OR DELETE OR UPDATE ON public.waste_manifest_lines FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: waste_manifests audit_waste_manifests; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_waste_manifests AFTER INSERT OR DELETE OR UPDATE ON public.waste_manifests FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: weekly_documents audit_weekly_documents; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_weekly_documents AFTER INSERT OR DELETE OR UPDATE ON public.weekly_documents FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: work_sessions audit_work_sessions; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_work_sessions AFTER INSERT OR DELETE OR UPDATE ON public.work_sessions FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: ai_pins ai_pins_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pins
    ADD CONSTRAINT ai_pins_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: ai_pins ai_pins_week_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pins
    ADD CONSTRAINT ai_pins_week_id_fkey FOREIGN KEY (week_id) REFERENCES public.calendar_weeks(id) ON DELETE CASCADE;


--
-- Name: biosecurity_events biosecurity_events_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biosecurity_events
    ADD CONSTRAINT biosecurity_events_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: corridor_cleanings corridor_cleanings_manifest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corridor_cleanings
    ADD CONSTRAINT corridor_cleanings_manifest_id_fkey FOREIGN KEY (manifest_id) REFERENCES public.waste_manifests(id) ON DELETE RESTRICT;


--
-- Name: corridor_cleanings corridor_cleanings_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corridor_cleanings
    ADD CONSTRAINT corridor_cleanings_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: decon_bleach_log decon_bleach_log_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_bleach_log
    ADD CONSTRAINT decon_bleach_log_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT;


--
-- Name: decon_bleach_log decon_bleach_log_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_bleach_log
    ADD CONSTRAINT decon_bleach_log_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: decon_positive_controls decon_positive_controls_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_positive_controls
    ADD CONSTRAINT decon_positive_controls_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: decon_room_cycles decon_room_cycles_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_room_cycles
    ADD CONSTRAINT decon_room_cycles_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: decon_step_signoffs decon_step_signoffs_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_step_signoffs
    ADD CONSTRAINT decon_step_signoffs_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT;


--
-- Name: decon_swabs decon_swabs_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_swabs
    ADD CONSTRAINT decon_swabs_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT;


--
-- Name: decon_swabs decon_swabs_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_swabs
    ADD CONSTRAINT decon_swabs_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: decon_tool_log decon_tool_log_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_tool_log
    ADD CONSTRAINT decon_tool_log_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT;


--
-- Name: decon_tool_log decon_tool_log_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decon_tool_log
    ADD CONSTRAINT decon_tool_log_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: departments departments_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: handoffs handoffs_from_dept_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_from_dept_id_fkey FOREIGN KEY (from_dept_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: handoffs handoffs_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: handoffs handoffs_to_dept_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_to_dept_id_fkey FOREIGN KEY (to_dept_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: harvests harvests_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvests
    ADD CONSTRAINT harvests_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT;


--
-- Name: harvests harvests_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvests
    ADD CONSTRAINT harvests_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: ipm_applications ipm_applications_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ipm_applications
    ADD CONSTRAINT ipm_applications_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT;


--
-- Name: ipm_applications ipm_applications_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ipm_applications
    ADD CONSTRAINT ipm_applications_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: irrigation_events irrigation_events_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.irrigation_events
    ADD CONSTRAINT irrigation_events_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT;


--
-- Name: irrigation_events irrigation_events_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.irrigation_events
    ADD CONSTRAINT irrigation_events_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: notifications notifications_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: plant_batches plant_batches_cultivar_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_batches
    ADD CONSTRAINT plant_batches_cultivar_id_fkey FOREIGN KEY (cultivar_id) REFERENCES public.cultivars(id) ON DELETE RESTRICT;


--
-- Name: plant_batches plant_batches_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_batches
    ADD CONSTRAINT plant_batches_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: plant_phase_events plant_phase_events_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_phase_events
    ADD CONSTRAINT plant_phase_events_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT;


--
-- Name: plant_phase_events plant_phase_events_plant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_phase_events
    ADD CONSTRAINT plant_phase_events_plant_id_fkey FOREIGN KEY (plant_id) REFERENCES public.plants(id) ON DELETE RESTRICT;


--
-- Name: plant_phase_events plant_phase_events_to_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_phase_events
    ADD CONSTRAINT plant_phase_events_to_room_id_fkey FOREIGN KEY (to_room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: plants plants_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plants
    ADD CONSTRAINT plants_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT;


--
-- Name: plants plants_cultivar_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plants
    ADD CONSTRAINT plants_cultivar_id_fkey FOREIGN KEY (cultivar_id) REFERENCES public.cultivars(id) ON DELETE RESTRICT;


--
-- Name: plants plants_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plants
    ADD CONSTRAINT plants_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: qc_certificates qc_certificates_laboratory_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_certificates
    ADD CONSTRAINT qc_certificates_laboratory_fkey FOREIGN KEY (laboratory_id) REFERENCES public.qc_laboratories(id) ON DELETE SET NULL;


--
-- Name: qc_certificates qc_certificates_sample_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_certificates
    ADD CONSTRAINT qc_certificates_sample_fkey FOREIGN KEY (sample_id) REFERENCES public.qc_samples(id) ON DELETE SET NULL;


--
-- Name: qc_certificates qc_certificates_spec_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_certificates
    ADD CONSTRAINT qc_certificates_spec_fkey FOREIGN KEY (specification_id) REFERENCES public.qc_specifications(id) ON DELETE RESTRICT;


--
-- Name: qc_certificates qc_certificates_supersedes_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_certificates
    ADD CONSTRAINT qc_certificates_supersedes_id_fkey FOREIGN KEY (supersedes_id) REFERENCES public.qc_certificates(id);


--
-- Name: qc_chain_of_custody qc_chain_of_custody_sample_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_chain_of_custody
    ADD CONSTRAINT qc_chain_of_custody_sample_fkey FOREIGN KEY (sample_id) REFERENCES public.qc_samples(id) ON DELETE CASCADE;


--
-- Name: qc_chain_of_custody qc_chain_of_custody_sfr_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_chain_of_custody
    ADD CONSTRAINT qc_chain_of_custody_sfr_fkey FOREIGN KEY (sfr_id) REFERENCES public.qc_sample_field_records(id) ON DELETE SET NULL;


--
-- Name: qc_coa_chunks qc_coa_chunks_document_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_chunks
    ADD CONSTRAINT qc_coa_chunks_document_fkey FOREIGN KEY (document_id) REFERENCES public.qc_coa_documents(id) ON DELETE CASCADE;


--
-- Name: qc_coa_documents qc_coa_documents_laboratory_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_documents
    ADD CONSTRAINT qc_coa_documents_laboratory_fkey FOREIGN KEY (laboratory_id) REFERENCES public.qc_laboratories(id) ON DELETE SET NULL;


--
-- Name: qc_coa_documents qc_coa_documents_promoted_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_documents
    ADD CONSTRAINT qc_coa_documents_promoted_fkey FOREIGN KEY (promoted_coa_id) REFERENCES public.qc_certificates(id) ON DELETE SET NULL;


--
-- Name: qc_coa_documents qc_coa_documents_sample_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_documents
    ADD CONSTRAINT qc_coa_documents_sample_fkey FOREIGN KEY (sample_id) REFERENCES public.qc_samples(id) ON DELETE SET NULL;


--
-- Name: qc_coa_documents qc_coa_documents_spec_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_documents
    ADD CONSTRAINT qc_coa_documents_spec_fkey FOREIGN KEY (specification_id) REFERENCES public.qc_specifications(id) ON DELETE SET NULL;


--
-- Name: qc_coa_extractions qc_coa_extractions_document_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_extractions
    ADD CONSTRAINT qc_coa_extractions_document_fkey FOREIGN KEY (document_id) REFERENCES public.qc_coa_documents(id) ON DELETE CASCADE;


--
-- Name: qc_coa_extractions qc_coa_extractions_parameter_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_extractions
    ADD CONSTRAINT qc_coa_extractions_parameter_fkey FOREIGN KEY (parameter_id) REFERENCES public.qc_spec_parameters(id) ON DELETE SET NULL;


--
-- Name: qc_coa_verifications qc_coa_verifications_coa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_verifications
    ADD CONSTRAINT qc_coa_verifications_coa_fkey FOREIGN KEY (coa_id) REFERENCES public.qc_certificates(id) ON DELETE CASCADE;


--
-- Name: qc_coa_verifications qc_coa_verifications_document_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coa_verifications
    ADD CONSTRAINT qc_coa_verifications_document_fkey FOREIGN KEY (source_document_id) REFERENCES public.qc_coa_documents(id) ON DELETE SET NULL;


--
-- Name: qc_coq_lines qc_coq_lines_coq_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq_lines
    ADD CONSTRAINT qc_coq_lines_coq_fkey FOREIGN KEY (coq_id) REFERENCES public.qc_coq(id) ON DELETE CASCADE;


--
-- Name: qc_coq_sources qc_coq_sources_coa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq_sources
    ADD CONSTRAINT qc_coq_sources_coa_fkey FOREIGN KEY (coa_id) REFERENCES public.qc_certificates(id) ON DELETE RESTRICT;


--
-- Name: qc_coq_sources qc_coq_sources_coq_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq_sources
    ADD CONSTRAINT qc_coq_sources_coq_fkey FOREIGN KEY (coq_id) REFERENCES public.qc_coq(id) ON DELETE CASCADE;


--
-- Name: qc_coq qc_coq_spec_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_coq
    ADD CONSTRAINT qc_coq_spec_fkey FOREIGN KEY (specification_id) REFERENCES public.qc_specifications(id) ON DELETE RESTRICT;


--
-- Name: qc_ecoa_checklist qc_ecoa_checklist_document_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_ecoa_checklist
    ADD CONSTRAINT qc_ecoa_checklist_document_fkey FOREIGN KEY (document_id) REFERENCES public.qc_coa_documents(id) ON DELETE CASCADE;


--
-- Name: qc_field_placeholders qc_field_placeholders_document_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_field_placeholders
    ADD CONSTRAINT qc_field_placeholders_document_fkey FOREIGN KEY (first_seen_document_id) REFERENCES public.qc_coa_documents(id) ON DELETE SET NULL;


--
-- Name: qc_field_placeholders qc_field_placeholders_parameter_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_field_placeholders
    ADD CONSTRAINT qc_field_placeholders_parameter_fkey FOREIGN KEY (mapped_parameter_id) REFERENCES public.qc_spec_parameters(id) ON DELETE SET NULL;


--
-- Name: qc_oos_notifications qc_oos_notifications_oos_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_notifications
    ADD CONSTRAINT qc_oos_notifications_oos_fkey FOREIGN KEY (oos_id) REFERENCES public.qc_oos_records(id) ON DELETE CASCADE;


--
-- Name: qc_oos_records qc_oos_records_result_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_records
    ADD CONSTRAINT qc_oos_records_result_fkey FOREIGN KEY (result_id) REFERENCES public.qc_results(id) ON DELETE SET NULL;


--
-- Name: qc_oos_records qc_oos_records_sample_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_records
    ADD CONSTRAINT qc_oos_records_sample_fkey FOREIGN KEY (sample_id) REFERENCES public.qc_samples(id) ON DELETE SET NULL;


--
-- Name: qc_oos_register qc_oos_register_oos_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_oos_register
    ADD CONSTRAINT qc_oos_register_oos_fkey FOREIGN KEY (oos_id) REFERENCES public.qc_oos_records(id) ON DELETE CASCADE;


--
-- Name: qc_results qc_results_coa_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_results
    ADD CONSTRAINT qc_results_coa_fkey FOREIGN KEY (coa_id) REFERENCES public.qc_certificates(id) ON DELETE CASCADE;


--
-- Name: qc_results qc_results_param_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_results
    ADD CONSTRAINT qc_results_param_fkey FOREIGN KEY (parameter_id) REFERENCES public.qc_spec_parameters(id) ON DELETE SET NULL;


--
-- Name: qc_sample_field_records qc_sample_field_records_rqs_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sample_field_records
    ADD CONSTRAINT qc_sample_field_records_rqs_fkey FOREIGN KEY (rqs_id) REFERENCES public.qc_sampling_requests(id) ON DELETE SET NULL;


--
-- Name: qc_sample_field_records qc_sample_field_records_sample_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sample_field_records
    ADD CONSTRAINT qc_sample_field_records_sample_fkey FOREIGN KEY (sample_id) REFERENCES public.qc_samples(id) ON DELETE SET NULL;


--
-- Name: qc_samples qc_samples_parent_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_samples
    ADD CONSTRAINT qc_samples_parent_fkey FOREIGN KEY (parent_id) REFERENCES public.qc_samples(id) ON DELETE SET NULL;


--
-- Name: qc_samples qc_samples_plan_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_samples
    ADD CONSTRAINT qc_samples_plan_fkey FOREIGN KEY (sampling_plan_id) REFERENCES public.qc_sampling_plans(id) ON DELETE SET NULL;


--
-- Name: qc_sampling_requests qc_sampling_requests_sample_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_sampling_requests
    ADD CONSTRAINT qc_sampling_requests_sample_fkey FOREIGN KEY (sample_id) REFERENCES public.qc_samples(id) ON DELETE SET NULL;


--
-- Name: qc_spec_parameters qc_spec_parameters_component_a_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_spec_parameters
    ADD CONSTRAINT qc_spec_parameters_component_a_id_fkey FOREIGN KEY (component_a_id) REFERENCES public.qc_spec_parameters(id);


--
-- Name: qc_spec_parameters qc_spec_parameters_component_b_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_spec_parameters
    ADD CONSTRAINT qc_spec_parameters_component_b_id_fkey FOREIGN KEY (component_b_id) REFERENCES public.qc_spec_parameters(id);


--
-- Name: qc_spec_parameters qc_spec_parameters_spec_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_spec_parameters
    ADD CONSTRAINT qc_spec_parameters_spec_fkey FOREIGN KEY (spec_id) REFERENCES public.qc_specifications(id) ON DELETE CASCADE;


--
-- Name: task_assignees task_assignees_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignees
    ADD CONSTRAINT task_assignees_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_comments task_comments_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_comments
    ADD CONSTRAINT task_comments_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_dependencies task_dependencies_dep_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_dependencies
    ADD CONSTRAINT task_dependencies_dep_fkey FOREIGN KEY (depends_on_task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_dependencies task_dependencies_task_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_dependencies
    ADD CONSTRAINT task_dependencies_task_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_links task_links_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_links
    ADD CONSTRAINT task_links_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_progress task_progress_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_progress
    ADD CONSTRAINT task_progress_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_workflow_events task_workflow_events_task_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_workflow_events
    ADD CONSTRAINT task_workflow_events_task_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT;


--
-- Name: tasks tasks_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: tasks tasks_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_week_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_week_id_fkey FOREIGN KEY (week_id) REFERENCES public.calendar_weeks(id) ON DELETE SET NULL;


--
-- Name: waste_manifest_lines waste_manifest_lines_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_manifest_lines
    ADD CONSTRAINT waste_manifest_lines_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT;


--
-- Name: waste_manifest_lines waste_manifest_lines_manifest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_manifest_lines
    ADD CONSTRAINT waste_manifest_lines_manifest_id_fkey FOREIGN KEY (manifest_id) REFERENCES public.waste_manifests(id) ON DELETE CASCADE;


--
-- Name: waste_manifest_lines waste_manifest_lines_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_manifest_lines
    ADD CONSTRAINT waste_manifest_lines_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: waste_manifests waste_manifests_origin_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_manifests
    ADD CONSTRAINT waste_manifests_origin_room_id_fkey FOREIGN KEY (origin_room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


--
-- Name: work_sessions work_sessions_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_sessions
    ADD CONSTRAINT work_sessions_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: ai_agent_bindings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ai_agent_bindings ENABLE ROW LEVEL SECURITY;

--
-- Name: ai_pins; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ai_pins ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_log audit_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_insert ON public.audit_log FOR INSERT WITH CHECK (true);


--
-- Name: audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_log audit_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_read ON public.audit_log FOR SELECT USING ((app.is_elevated() AND ((org_id = app.current_org_id()) OR (org_id IS NULL))));


--
-- Name: biosecurity_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.biosecurity_events ENABLE ROW LEVEL SECURITY;

--
-- Name: calendar_weeks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.calendar_weeks ENABLE ROW LEVEL SECURITY;

--
-- Name: corridor_cleanings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.corridor_cleanings ENABLE ROW LEVEL SECURITY;

--
-- Name: cultivars; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cultivars ENABLE ROW LEVEL SECURITY;

--
-- Name: decon_bleach_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.decon_bleach_log ENABLE ROW LEVEL SECURITY;

--
-- Name: decon_positive_controls; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.decon_positive_controls ENABLE ROW LEVEL SECURITY;

--
-- Name: decon_room_cycles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.decon_room_cycles ENABLE ROW LEVEL SECURITY;

--
-- Name: decon_step_signoffs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.decon_step_signoffs ENABLE ROW LEVEL SECURITY;

--
-- Name: decon_swabs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.decon_swabs ENABLE ROW LEVEL SECURITY;

--
-- Name: decon_tool_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.decon_tool_log ENABLE ROW LEVEL SECURITY;

--
-- Name: departments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;

--
-- Name: events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

--
-- Name: events events_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY events_insert ON public.events FOR INSERT WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: events events_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY events_read ON public.events FOR SELECT USING ((org_id = app.current_org_id()));


--
-- Name: handoffs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.handoffs ENABLE ROW LEVEL SECURITY;

--
-- Name: harvests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.harvests ENABLE ROW LEVEL SECURITY;

--
-- Name: ipm_applications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ipm_applications ENABLE ROW LEVEL SECURITY;

--
-- Name: irrigation_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.irrigation_events ENABLE ROW LEVEL SECURITY;

--
-- Name: notifications notif_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY notif_insert ON public.notifications FOR INSERT WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: notifications notif_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY notif_select ON public.notifications FOR SELECT USING (((org_id = app.current_org_id()) AND (recipient_id = app.current_user_id())));


--
-- Name: notifications notif_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY notif_update ON public.notifications FOR UPDATE USING (((org_id = app.current_org_id()) AND (recipient_id = app.current_user_id()))) WITH CHECK (((org_id = app.current_org_id()) AND (recipient_id = app.current_user_id())));


--
-- Name: notifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

--
-- Name: ai_agent_bindings org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.ai_agent_bindings USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: ai_pins org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.ai_pins USING (((org_id = app.current_org_id()) AND ((subject_user_id IS NULL) OR (subject_user_id = app.current_user_id()) OR app.is_elevated()))) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: biosecurity_events org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.biosecurity_events USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: calendar_weeks org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.calendar_weeks USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: corridor_cleanings org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.corridor_cleanings USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: cultivars org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.cultivars USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: decon_bleach_log org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.decon_bleach_log USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: decon_positive_controls org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.decon_positive_controls USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: decon_room_cycles org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.decon_room_cycles USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: decon_step_signoffs org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.decon_step_signoffs USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: decon_swabs org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.decon_swabs USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: decon_tool_log org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.decon_tool_log USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: departments org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.departments USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: handoffs org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.handoffs USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: harvests org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.harvests USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: ipm_applications org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.ipm_applications USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: irrigation_events org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.irrigation_events USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: plant_batches org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.plant_batches USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: plant_phase_events org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.plant_phase_events USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: plants org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.plants USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_batch_genealogy org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_batch_genealogy USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_certificates org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_certificates USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_coa_chunks org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_coa_chunks USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_coa_documents org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_coa_documents USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_coa_extractions org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_coa_extractions USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_coa_verifications org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_coa_verifications USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_coq org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_coq USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_coq_lines org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_coq_lines USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_coq_sources org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_coq_sources USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_document_files org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_document_files USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_ecoa_checklist org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_ecoa_checklist USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_field_placeholders org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_field_placeholders USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_laboratories org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_laboratories USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_oos_notifications org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_oos_notifications USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_oos_records org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_oos_records USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_oos_register org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_oos_register USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_results org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_results USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_sample_field_records org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_sample_field_records USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_sample_transports org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_sample_transports USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_samples org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_samples USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_sampling_plans org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_sampling_plans USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_sampling_requests org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_sampling_requests USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_signatures org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_signatures USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_spec_parameters org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_spec_parameters USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_specifications org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_specifications USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_stability_studies org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_stability_studies USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_water_tests org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_water_tests USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: rooms org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.rooms USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: task_assignees org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.task_assignees USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: task_comments org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.task_comments USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: task_dependencies org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.task_dependencies USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: task_links org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.task_links USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: task_workflow_events org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.task_workflow_events USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: waste_manifest_lines org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.waste_manifest_lines USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: waste_manifests org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.waste_manifests USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: work_sessions org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.work_sessions USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_chain_of_custody org_isolation_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation_insert ON public.qc_chain_of_custody FOR INSERT WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_chain_of_custody org_isolation_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation_select ON public.qc_chain_of_custody FOR SELECT USING ((org_id = app.current_org_id()));


--
-- Name: plant_batches; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.plant_batches ENABLE ROW LEVEL SECURITY;

--
-- Name: plant_phase_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.plant_phase_events ENABLE ROW LEVEL SECURITY;

--
-- Name: plants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.plants ENABLE ROW LEVEL SECURITY;

--
-- Name: task_progress progress_rw; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY progress_rw ON public.task_progress USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_batch_genealogy; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_batch_genealogy ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_certificates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_certificates ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_chain_of_custody; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_chain_of_custody ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_coa_chunks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_coa_chunks ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_coa_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_coa_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_coa_extractions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_coa_extractions ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_coa_verifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_coa_verifications ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_coq; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_coq ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_coq_lines; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_coq_lines ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_coq_sources; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_coq_sources ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_document_files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_document_files ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_ecoa_checklist; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_ecoa_checklist ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_field_placeholders; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_field_placeholders ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_laboratories; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_laboratories ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_oos_notifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_oos_notifications ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_oos_records; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_oos_records ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_oos_register; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_oos_register ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_results; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_results ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_sample_field_records; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_sample_field_records ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_sample_transports; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_sample_transports ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_samples; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_samples ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_sampling_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_sampling_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_sampling_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_sampling_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_signatures; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_signatures ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_spec_parameters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_spec_parameters ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_specifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_specifications ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_stability_studies; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_stability_studies ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_water_tests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_water_tests ENABLE ROW LEVEL SECURITY;

--
-- Name: rooms; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rooms ENABLE ROW LEVEL SECURITY;

--
-- Name: task_assignees; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_assignees ENABLE ROW LEVEL SECURITY;

--
-- Name: task_comments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_comments ENABLE ROW LEVEL SECURITY;

--
-- Name: task_dependencies; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_dependencies ENABLE ROW LEVEL SECURITY;

--
-- Name: task_links; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_links ENABLE ROW LEVEL SECURITY;

--
-- Name: task_progress; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_progress ENABLE ROW LEVEL SECURITY;

--
-- Name: task_workflow_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_workflow_events ENABLE ROW LEVEL SECURITY;

--
-- Name: tasks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

--
-- Name: tasks tasks_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tasks_read ON public.tasks FOR SELECT USING (((org_id = app.current_org_id()) AND ((user_id = app.current_user_id()) OR app.is_elevated() OR (EXISTS ( SELECT 1
   FROM public.task_assignees a
  WHERE ((a.task_id = tasks.id) AND (a.user_id = app.current_user_id())))))));


--
-- Name: tasks tasks_write; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tasks_write ON public.tasks USING (((org_id = app.current_org_id()) AND ((user_id = app.current_user_id()) OR app.is_elevated() OR (EXISTS ( SELECT 1
   FROM public.task_assignees a
  WHERE ((a.task_id = tasks.id) AND (a.user_id = app.current_user_id()))))))) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: waste_manifest_lines; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.waste_manifest_lines ENABLE ROW LEVEL SECURITY;

--
-- Name: waste_manifests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.waste_manifests ENABLE ROW LEVEL SECURITY;

--
-- Name: weekly_documents wd_delete; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY wd_delete ON public.weekly_documents FOR DELETE USING (((org_id = app.current_org_id()) AND (status = 'draft'::text)));


--
-- Name: weekly_documents wd_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY wd_insert ON public.weekly_documents FOR INSERT WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: weekly_documents wd_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY wd_select ON public.weekly_documents FOR SELECT USING ((org_id = app.current_org_id()));


--
-- Name: weekly_documents wd_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY wd_update ON public.weekly_documents FOR UPDATE USING (((org_id = app.current_org_id()) AND (status = 'draft'::text))) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: weekly_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.weekly_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: work_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_sessions ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict MYNGZtixgvZDWYXdjoIsavjwTYrL5PBemo4vKpec2pVcSoVLzY9maYbAqDWqveH


--
-- PostgreSQL database dump
--

\restrict yokNF5b0hUhlxF9v5sgRhbcY1Vd9droW3iB0cnFijLfJ2nQ9KZREwLkg8mrS6JO

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
    AS $$
DECLARE
  v_actor text := COALESCE(current_setting('app.user_id', true), 'system');
  v_prev  text;
  v_new   jsonb := CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  v_old   jsonb := CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  v_rec   text  := COALESCE((CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END).id::text, '');
  v_payload text;
BEGIN
  PERFORM pg_advisory_xact_lock(4019283746);  -- H1: serialize tail read; prevents concurrent hash-chain forks
  SELECT entry_hash INTO v_prev FROM audit_log ORDER BY id DESC LIMIT 1;
  -- IMPORTANT: convert_to(text,'UTF8'), never text::bytea (escape-format bug).
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
    CONSTRAINT notifications_reason_check CHECK ((reason = ANY (ARRAY['assigned'::text, 'mentioned'::text, 'comment'::text, 'status'::text, 'due'::text, 'report'::text, 'capa_stuck'::text, 'validation_stuck'::text])))
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
    CONSTRAINT plant_batches_phase_check CHECK ((phase = ANY (ARRAY['clone'::text, 'veg'::text, 'flower'::text, 'mother'::text, 'drying'::text]))),
    CONSTRAINT plant_batches_plant_count_check CHECK ((plant_count >= 0))
);

ALTER TABLE ONLY public.plant_batches FORCE ROW LEVEL SECURITY;


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
    CONSTRAINT qc_certificates_cert_type_check CHECK ((cert_type = ANY (ARRAY['ICOA'::text, 'ECOA'::text, 'COQ'::text, 'WATER'::text, 'OTHER'::text]))),
    CONSTRAINT qc_certificates_decision_check CHECK (((decision IS NULL) OR (decision = ANY (ARRAY['PASS'::text, 'FAIL'::text])))),
    CONSTRAINT qc_certificates_status_check CHECK ((status = ANY (ARRAY['DRAFT'::text, 'REVIEWED'::text, 'APPROVED'::text, 'RELEASED'::text])))
);

ALTER TABLE ONLY public.qc_certificates FORCE ROW LEVEL SECURITY;


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
    CONSTRAINT qc_results_status_check CHECK ((status = ANY (ARRAY['pass'::text, 'fail'::text, 'marginal'::text, 'unknown'::text])))
);

ALTER TABLE ONLY public.qc_results FORCE ROW LEVEL SECURITY;


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
    created_at timestamp with time zone DEFAULT now() NOT NULL
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
    CONSTRAINT tasks_hours_nonnegative_check CHECK ((((estimated_hours IS NULL) OR (estimated_hours >= (0)::numeric)) AND ((actual_hours IS NULL) OR (actual_hours >= (0)::numeric)))),
    CONSTRAINT tasks_node_kind_check CHECK ((node_kind = ANY (ARRAY['task'::text, 'annex'::text, 'step'::text]))),
    CONSTRAINT tasks_progress_check CHECK (((progress >= 0) AND (progress <= 100))),
    CONSTRAINT tasks_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'ongoing'::text, 'review'::text, 'stuck'::text, 'postponed'::text, 'completed'::text]))),
    CONSTRAINT tasks_task_type_check CHECK ((task_type = ANY (ARRAY['capa'::text, 'sop'::text, 'validation'::text, 'document'::text, 'lab'::text, 'meeting'::text, 'admin'::text, 'other'::text])))
);

ALTER TABLE ONLY public.tasks FORCE ROW LEVEL SECURITY;


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
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


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
-- Name: qc_results qc_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qc_results
    ADD CONSTRAINT qc_results_pkey PRIMARY KEY (id);


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
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


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
-- Name: audit_log_table_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_table_idx ON public.audit_log USING btree (table_name, record_id);


--
-- Name: events_org_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX events_org_created_idx ON public.events USING btree (org_id, created_at DESC);


--
-- Name: events_org_dept_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX events_org_dept_created_idx ON public.events USING btree (org_id, department_id, created_at DESC);


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
-- Name: plant_batches_org_room_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX plant_batches_org_room_idx ON public.plant_batches USING btree (org_id, room_id) WHERE is_active;


--
-- Name: qc_certificates_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_certificates_batch_idx ON public.qc_certificates USING btree (org_id, batch_id);


--
-- Name: qc_certificates_spec_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_certificates_spec_idx ON public.qc_certificates USING btree (org_id, specification_id);


--
-- Name: qc_results_coa_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX qc_results_coa_idx ON public.qc_results USING btree (org_id, coa_id);


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
-- Name: departments audit_departments; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_departments AFTER INSERT OR DELETE OR UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: handoffs audit_handoffs; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_handoffs AFTER INSERT OR DELETE OR UPDATE ON public.handoffs FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: plant_batches audit_plant_batches; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_plant_batches AFTER INSERT OR DELETE OR UPDATE ON public.plant_batches FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_certificates audit_qc_certificates; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_certificates AFTER INSERT OR DELETE OR UPDATE ON public.qc_certificates FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_results audit_qc_results; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_results AFTER INSERT OR DELETE OR UPDATE ON public.qc_results FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_samples audit_qc_samples; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_samples AFTER INSERT OR DELETE OR UPDATE ON public.qc_samples FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_sampling_plans audit_qc_sampling_plans; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_sampling_plans AFTER INSERT OR DELETE OR UPDATE ON public.qc_sampling_plans FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_spec_parameters audit_qc_spec_parameters; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_spec_parameters AFTER INSERT OR DELETE OR UPDATE ON public.qc_spec_parameters FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: qc_specifications audit_qc_specifications; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_qc_specifications AFTER INSERT OR DELETE OR UPDATE ON public.qc_specifications FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: rooms audit_rooms; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_rooms AFTER INSERT OR DELETE OR UPDATE ON public.rooms FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_dependencies audit_task_dependencies; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_dependencies AFTER INSERT OR DELETE OR UPDATE ON public.task_dependencies FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_progress audit_task_prog; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_prog AFTER INSERT OR DELETE OR UPDATE ON public.task_progress FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: tasks audit_tasks; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_tasks AFTER INSERT OR DELETE OR UPDATE ON public.tasks FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


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
-- Name: notifications notifications_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: plant_batches plant_batches_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plant_batches
    ADD CONSTRAINT plant_batches_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id) ON DELETE RESTRICT;


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
-- Name: calendar_weeks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.calendar_weeks ENABLE ROW LEVEL SECURITY;

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
-- Name: calendar_weeks org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.calendar_weeks USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: departments org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.departments USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: handoffs org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.handoffs USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: plant_batches org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.plant_batches USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_certificates org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_certificates USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_results org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_results USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_samples org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_samples USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_sampling_plans org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_sampling_plans USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_spec_parameters org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_spec_parameters USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_specifications org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.qc_specifications USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


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
-- Name: work_sessions org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.work_sessions USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: plant_batches; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.plant_batches ENABLE ROW LEVEL SECURITY;

--
-- Name: task_progress progress_rw; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY progress_rw ON public.task_progress USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: qc_certificates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_certificates ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_results; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_results ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_samples; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_samples ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_sampling_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_sampling_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_spec_parameters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_spec_parameters ENABLE ROW LEVEL SECURITY;

--
-- Name: qc_specifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.qc_specifications ENABLE ROW LEVEL SECURITY;

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

\unrestrict yokNF5b0hUhlxF9v5sgRhbcY1Vd9droW3iB0cnFijLfJ2nQ9KZREwLkg8mrS6JO


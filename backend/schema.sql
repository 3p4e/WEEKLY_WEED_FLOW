--
-- PostgreSQL database dump
--

\restrict mg7zfo1FGcRsWp2ASbuRymZ7Iij18uFiJQb65LdwKU1JLIhxe1ja09XdV0Ximmc

-- Dumped from database version 17.10
-- Dumped by pg_dump version 17.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
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
    AS $$ SELECT app.current_role() IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD','QA_AUDITOR') $$;


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
    created_at timestamp with time zone DEFAULT now() NOT NULL
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
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.organizations FORCE ROW LEVEL SECURITY;


--
-- Name: password_reset_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    code_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.password_reset_codes FORCE ROW LEVEL SECURITY;


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    org_id uuid NOT NULL,
    username text NOT NULL,
    email text,
    password_hash text NOT NULL,
    full_name text NOT NULL,
    display_name text,
    role text DEFAULT 'USER'::text NOT NULL,
    function_role text,
    department_id uuid,
    avatar_url text,
    is_active boolean DEFAULT true NOT NULL,
    must_change_password boolean DEFAULT true NOT NULL,
    password_set_at timestamp with time zone,
    created_by uuid,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT profiles_role_check CHECK ((role = ANY (ARRAY['ADMIN'::text, 'DEPT_HEAD'::text, 'PROJECT_LEAD'::text, 'TEAM_LEADER'::text, 'USER'::text, 'QA_AUDITOR'::text])))
);

ALTER TABLE ONLY public.profiles FORCE ROW LEVEL SECURITY;


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
    department text,
    department_id uuid,
    week_id uuid,
    week_start date,
    days text[] DEFAULT '{}'::text[] NOT NULL,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    deps uuid[] DEFAULT '{}'::uuid[] NOT NULL,
    progress_notes jsonb DEFAULT '[]'::jsonb NOT NULL,
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
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.tasks FORCE ROW LEVEL SECURITY;


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
-- Name: handoffs handoffs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_slug_key UNIQUE (slug);


--
-- Name: password_reset_codes password_reset_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_codes
    ADD CONSTRAINT password_reset_codes_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_username_key UNIQUE (username);


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
-- Name: audit_log_table_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_table_idx ON public.audit_log USING btree (table_name, record_id);


--
-- Name: task_progress_task_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX task_progress_task_idx ON public.task_progress USING btree (task_id);


--
-- Name: tasks_dept_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_dept_idx ON public.tasks USING btree (department_id);


--
-- Name: tasks_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tasks_org_idx ON public.tasks USING btree (org_id);


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
-- Name: departments audit_departments; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_departments AFTER INSERT OR DELETE OR UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: handoffs audit_handoffs; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_handoffs AFTER INSERT OR DELETE OR UPDATE ON public.handoffs FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: profiles audit_profiles; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_profiles AFTER INSERT OR DELETE OR UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: task_progress audit_task_prog; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_task_prog AFTER INSERT OR DELETE OR UPDATE ON public.task_progress FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: tasks audit_tasks; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_tasks AFTER INSERT OR DELETE OR UPDATE ON public.tasks FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: ai_agent_bindings ai_agent_bindings_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_agent_bindings
    ADD CONSTRAINT ai_agent_bindings_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: ai_pins ai_pins_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pins
    ADD CONSTRAINT ai_pins_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: ai_pins ai_pins_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pins
    ADD CONSTRAINT ai_pins_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


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
-- Name: calendar_weeks calendar_weeks_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_weeks
    ADD CONSTRAINT calendar_weeks_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: departments departments_head_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_head_fk FOREIGN KEY (head_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: departments departments_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


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
-- Name: handoffs handoffs_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: handoffs handoffs_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.profiles(id);


--
-- Name: handoffs handoffs_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.handoffs
    ADD CONSTRAINT handoffs_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


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
-- Name: password_reset_codes password_reset_codes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_codes
    ADD CONSTRAINT password_reset_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: profiles profiles_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: profiles profiles_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: profiles profiles_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: task_assignees task_assignees_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignees
    ADD CONSTRAINT task_assignees_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: task_assignees task_assignees_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignees
    ADD CONSTRAINT task_assignees_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: task_assignees task_assignees_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignees
    ADD CONSTRAINT task_assignees_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_assignees task_assignees_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_assignees
    ADD CONSTRAINT task_assignees_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: task_comments task_comments_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_comments
    ADD CONSTRAINT task_comments_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: task_comments task_comments_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_comments
    ADD CONSTRAINT task_comments_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_comments task_comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_comments
    ADD CONSTRAINT task_comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id);


--
-- Name: task_progress task_progress_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_progress
    ADD CONSTRAINT task_progress_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: task_progress task_progress_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_progress
    ADD CONSTRAINT task_progress_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_progress task_progress_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_progress
    ADD CONSTRAINT task_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id);


--
-- Name: tasks tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: tasks tasks_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: tasks tasks_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: tasks tasks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id);


--
-- Name: tasks tasks_week_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_week_id_fkey FOREIGN KEY (week_id) REFERENCES public.calendar_weeks(id) ON DELETE SET NULL;


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
-- Name: handoffs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.handoffs ENABLE ROW LEVEL SECURITY;

--
-- Name: ai_agent_bindings org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.ai_agent_bindings USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: ai_pins org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.ai_pins USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


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
-- Name: task_assignees org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.task_assignees USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: task_comments org_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_isolation ON public.task_comments USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: organizations org_self; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_self ON public.organizations USING ((id = app.current_org_id()));


--
-- Name: organizations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

--
-- Name: password_reset_codes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.password_reset_codes ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles profiles_manage; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY profiles_manage ON public.profiles USING (((org_id = app.current_org_id()) AND app.is_elevated())) WITH CHECK (((org_id = app.current_org_id()) AND app.is_elevated()));


--
-- Name: profiles profiles_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY profiles_read ON public.profiles FOR SELECT USING ((org_id = app.current_org_id()));


--
-- Name: profiles profiles_self; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY profiles_self ON public.profiles FOR UPDATE USING ((id = app.current_user_id())) WITH CHECK ((id = app.current_user_id()));


--
-- Name: task_progress progress_rw; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY progress_rw ON public.task_progress USING ((org_id = app.current_org_id())) WITH CHECK ((org_id = app.current_org_id()));


--
-- Name: password_reset_codes reset_self; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY reset_self ON public.password_reset_codes USING (((user_id = app.current_user_id()) OR app.is_elevated())) WITH CHECK (true);


--
-- Name: task_assignees; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_assignees ENABLE ROW LEVEL SECURITY;

--
-- Name: task_comments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.task_comments ENABLE ROW LEVEL SECURITY;

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
-- PostgreSQL database dump complete
--

\unrestrict mg7zfo1FGcRsWp2ASbuRymZ7Iij18uFiJQb65LdwKU1JLIhxe1ja09XdV0Ximmc


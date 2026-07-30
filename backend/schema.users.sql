--
-- PostgreSQL database dump
--

\restrict mZtVDvUBWv5GjlWphzEs5TM8qjan3eUMVZXgB3AcBwSI8KiJWd1Jp9GkwUFaeHD

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
    CONSTRAINT profiles_role_check CHECK ((role = ANY (ARRAY['ADMIN'::text, 'OWNER'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text, 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SE_MGR'::text, 'CU_MGR'::text, 'MU_MGR'::text, 'QP'::text, 'USER'::text])))
);

ALTER TABLE ONLY public.profiles FORCE ROW LEVEL SECURITY;


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


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
-- Name: audit_log_table_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_table_idx ON public.audit_log USING btree (table_name, record_id);


--
-- Name: organizations audit_organizations; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_organizations AFTER INSERT OR DELETE OR UPDATE ON public.organizations FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: profiles audit_profiles; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_profiles AFTER INSERT OR DELETE OR UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();


--
-- Name: profiles profiles_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: profiles profiles_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


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
-- Name: organizations org_self; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY org_self ON public.organizations USING ((id = app.current_org_id()));


--
-- Name: organizations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

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
-- PostgreSQL database dump complete
--

\unrestrict mZtVDvUBWv5GjlWphzEs5TM8qjan3eUMVZXgB3AcBwSI8KiJWd1Jp9GkwUFaeHD


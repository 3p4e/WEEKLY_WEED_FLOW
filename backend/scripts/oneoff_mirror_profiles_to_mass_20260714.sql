-- Mirror the 6 touched account rows (4 new managers + ceo.kes/own.jc refresh)
-- from live into the wwf_mass users DB, preserving exact UUIDs. Upsert by id;
-- no deletes. Same column order (SELECT * / LIKE profiles).
\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE _pmir (LIKE public.profiles);
COPY _pmir FROM '/tmp/prof6.copy';
INSERT INTO public.profiles SELECT * FROM _pmir
ON CONFLICT (id) DO UPDATE SET
  org_id=EXCLUDED.org_id, username=EXCLUDED.username, email=EXCLUDED.email,
  password_hash=EXCLUDED.password_hash, full_name=EXCLUDED.full_name, display_name=EXCLUDED.display_name,
  role=EXCLUDED.role, function_role=EXCLUDED.function_role, department_id=EXCLUDED.department_id,
  avatar_url=EXCLUDED.avatar_url, is_active=EXCLUDED.is_active, must_change_password=EXCLUDED.must_change_password,
  password_set_at=EXCLUDED.password_set_at, created_by=EXCLUDED.created_by, is_deleted=EXCLUDED.is_deleted,
  created_at=EXCLUDED.created_at, updated_at=EXCLUDED.updated_at;
\echo == the 6 accounts now on mass ==
SELECT username||' | '||role||' | '||id||' | active='||is_active FROM public.profiles
WHERE username IN ('cum.elen','whm.log','mam.rez','sem.andr','ceo.kes','own.jc') ORDER BY username;
COMMIT;

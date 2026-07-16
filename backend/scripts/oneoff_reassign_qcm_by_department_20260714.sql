-- Redistribute qcm.blani captured SOP themes to the correct department managers.
-- Non-QC theme subtrees move (owner user_id + department) off QC to the dept manager.
-- QC themes stay with qcm.blani. CEO-order themes are handled separately (Phase C).
-- Audit trail attributes the change to admin via app.* GUCs. Snapshot taken first.
\set ON_ERROR_STOP on
BEGIN;
SELECT set_config('app.user_id','996f1eec-0ebf-40d1-a7f8-5d491fbb5a89',true);  -- admin
SELECT set_config('app.org_id','a0a0a0a0-0000-4000-8000-000000000001',true);
SELECT set_config('app.role','ADMIN',true);

\echo == starting: qcm.blani task count (expect 552) ==
SELECT count(*) AS qcm_before FROM tasks WHERE user_id='f61b6f0f-821a-44d9-ba46-a64f7ef34f44'::uuid AND is_deleted=false;

-- ── QA → qam.jovana (dept quality_assurance) ──────────────────────────────
WITH RECURSIVE roots(id) AS (VALUES
  ('0ccb7028-fb17-45cf-9af1-bf7310135d6c'::uuid),('3cfab6d6-d251-436e-8be0-0c74fdea30d0'),
  ('8afc9222-d33d-447c-942b-64dd551b769c'),('8e88fa24-3091-42d1-9e76-a7102c242e46'),
  ('8ffeb12b-3b1f-40fa-9c0b-931e3c31775b'),('b25b3c10-a72d-4eee-8313-f26a28164db3'),
  ('0b30aca9-dfb6-488b-bda1-76b3eae420ac')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='8103b299-9658-4c3d-b806-07068d6e64c1', department_id='6c8bb827-b3dc-4afc-8881-65bfa2351261',
  department=(SELECT name FROM departments WHERE id='6c8bb827-b3dc-4afc-8881-65bfa2351261'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- ── Cultivation → cum.elen (dept cultivation) ─────────────────────────────
WITH RECURSIVE roots(id) AS (VALUES
  ('34fe7473-5f3a-4a45-8c44-e4ab2d18d91d'::uuid),('b059a83e-ac93-4b45-aa4a-e271d2d1079b')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='9dfad6ce-6704-493c-8a8c-3a56afefbed6', department_id='7966fa88-b83e-4afc-9a97-04453f664e74',
  department=(SELECT name FROM departments WHERE id='7966fa88-b83e-4afc-9a97-04453f664e74'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- ── Logistics → whm.log (dept logistics) ──────────────────────────────────
WITH RECURSIVE roots(id) AS (VALUES
  ('080fe64a-ce3d-4815-95c9-f053c34109ed'::uuid),('8a5ca30b-db32-4064-a9b0-c1ce796f2ec3')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='e880f30f-7105-4d12-9b96-f1dfcaaeb32b', department_id='055e4c91-ccb4-41ca-aef6-d80078998136',
  department=(SELECT name FROM departments WHERE id='055e4c91-ccb4-41ca-aef6-d80078998136'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- ── Maintenance/MU → mam.rez (dept tooling) ───────────────────────────────
WITH RECURSIVE roots(id) AS (VALUES
  ('a728e2b4-6768-401c-969b-4290032c5ee1'::uuid),('6c5108cd-dde8-40e7-b0c9-357d9bd78583'),
  ('355c6d01-0811-40eb-8929-27ef4e5259fc'),('79e7af75-05b8-45d6-a15e-78b6ba9af387'),
  ('e6f9edcf-7b5a-46a8-9263-8c75367773e3')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='4578d506-919b-4db2-8eb8-c3c15d15c80e', department_id='a16b580c-26b4-4ce5-bd1e-c05260aef976',
  department=(SELECT name FROM departments WHERE id='a16b580c-26b4-4ce5-bd1e-c05260aef976'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

\echo == after: distribution among the captured set (expect qcm=378, qam+83, cum+19, whm+9, mam+63) ==
SELECT CASE user_id::text
  WHEN 'f61b6f0f-821a-44d9-ba46-a64f7ef34f44' THEN 'qcm.blani (QC) — stays'
  WHEN '8103b299-9658-4c3d-b806-07068d6e64c1' THEN 'qam.jovana (QA)'
  WHEN '9dfad6ce-6704-493c-8a8c-3a56afefbed6' THEN 'cum.elen (Cultivation)'
  WHEN 'e880f30f-7105-4d12-9b96-f1dfcaaeb32b' THEN 'whm.log (Logistics)'
  WHEN '4578d506-919b-4db2-8eb8-c3c15d15c80e' THEN 'mam.rez (Maintenance)'
  ELSE user_id::text END AS owner, count(*)
FROM tasks WHERE is_deleted=false AND user_id IN (
  'f61b6f0f-821a-44d9-ba46-a64f7ef34f44','8103b299-9658-4c3d-b806-07068d6e64c1',
  '9dfad6ce-6704-493c-8a8c-3a56afefbed6','e880f30f-7105-4d12-9b96-f1dfcaaeb32b',
  '4578d506-919b-4db2-8eb8-c3c15d15c80e')
GROUP BY 1 ORDER BY 2 DESC;

COMMIT;

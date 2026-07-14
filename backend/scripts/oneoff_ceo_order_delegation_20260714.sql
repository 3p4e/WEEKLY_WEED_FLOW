-- Phase C: the 4 "CEO Order" theme roots move to ceo.kes ownership (org-wide,
-- no department — matches CEO's org-wide scope). Their 51 execution sub-tasks
-- (documents) + descendant versions are then individually delegated to the
-- department that actually does the work, using the SAME cross-department
-- delegation mechanic already native to the app (parent_id is left untouched;
-- only department_id/user_id change, so the CEO-order root stays visible to
-- every department with a delegated child under it — verified via the
-- existing _assert_scope_visible / list_tasks scope rule: a manager sees a
-- task if its OWN parent has a child in their department). QC-classified
-- sub-tasks are a no-op (already owned by qcm.blani / qc department).
\set ON_ERROR_STOP on
BEGIN;
SELECT set_config('app.user_id','996f1eec-0ebf-40d1-a7f8-5d491fbb5a89',true);  -- admin
SELECT set_config('app.org_id','a0a0a0a0-0000-4000-8000-000000000001',true);
SELECT set_config('app.role','ADMIN',true);

\echo == before: qcm.blani task count ==
SELECT count(*) AS qcm_before FROM tasks WHERE user_id='f61b6f0f-821a-44d9-ba46-a64f7ef34f44'::uuid AND is_deleted=false;

-- ── 1) The 4 order roots themselves -> ceo.kes, org-wide (no department) ──
UPDATE tasks SET user_id='a8d1003b-3648-4c07-9fec-19f14681abca', department_id=NULL, department=NULL,
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN ('456c5e31-5a91-433a-a795-2f54ca7ee765','c5c93ac6-7553-42c3-a85a-3150d892702e',
             '0d826db2-52cf-4ebd-85f2-e249cde1d02a','cde1a8a3-b700-4906-89df-afa77a6685a0');

-- ── 2) Delegate execution sub-tasks (document + its version descendants) ──
-- QA (6 docs): EU GMP dossier, consultant documentation, SMF x2, Tetra Hip audit, weekly quality/GMP report
WITH RECURSIVE roots(id) AS (VALUES
  ('cff0aad7-7447-49b6-bfd1-f6af1c4656cd'::uuid),('bdf4ca4f-9617-4a03-98e5-b8c79747fd68'),
  ('b2702d22-e55f-4d28-b18f-32ff0985e022'),('4852ad06-f878-4729-b8fe-c9019126d4ee'),
  ('d3282417-12aa-4e68-8151-7d1151248ae5'),('5a944636-060c-43f1-b498-1c4eb8e49a43')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='8103b299-9658-4c3d-b806-07068d6e64c1', department_id='6c8bb827-b3dc-4afc-8881-65bfa2351261',
  department=(SELECT name FROM departments WHERE id='6c8bb827-b3dc-4afc-8881-65bfa2351261'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- Production (7 docs): room layouts, hand-off to QC, repackage, forecast, processing report, transition plan, maintain production
WITH RECURSIVE roots(id) AS (VALUES
  ('d8919b1a-fe2e-4f14-bb3f-1b1ea7d4c513'::uuid),('a62a2b6e-9799-422a-aac5-89ed448f1ca2'),
  ('c705da95-e7d1-44e2-83a8-75ca25f50446'),('f764c03d-d1e9-4e65-a9b0-f5e80671225a'),
  ('4dabeaa3-a4de-4abd-9266-fec0cdad7106'),('788b2394-8327-4da9-a8f2-4bfd31a32824'),
  ('d0d78f97-766a-4fbf-bd2b-744f91a8149d')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='5141a2b4-09a0-49e8-9b1a-3af180a12081', department_id='6f596b11-c867-4bed-9435-0c5afb006502',
  department=(SELECT name FROM departments WHERE id='6f596b11-c867-4bed-9435-0c5afb006502'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- Logistics (2 docs): export documentation, primary packaging procurement
WITH RECURSIVE roots(id) AS (VALUES
  ('76340491-7ce5-4d2a-a9ce-7607b8f049fb'::uuid),('01e9dff8-016b-4995-a1e3-aa9fdcda6ad7')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='e880f30f-7105-4d12-9b96-f1dfcaaeb32b', department_id='055e4c91-ccb4-41ca-aef6-d80078998136',
  department=(SELECT name FROM departments WHERE id='055e4c91-ccb4-41ca-aef6-d80078998136'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- Maintenance (12 docs): all Facility & HVAC Remediation items + weekly technical status report
WITH RECURSIVE roots(id) AS (VALUES
  ('69d78a05-dfdd-4f2f-83ac-9e49fcd7d65d'::uuid),('0a781bb9-9a1c-4442-82bb-94e3293cb664'),
  ('fff4cb07-d034-4c80-936b-02a40b085493'),('f7ea0222-88ba-4287-905e-03bb91bfc457'),
  ('5f4ab89c-b688-412b-bd2d-d875424b2395'),('5bd71e68-f622-4a80-95d0-82e93b8c6645'),
  ('1672f392-4439-4739-8056-0932544e12d7'),('23af68cc-26bd-4ea6-905a-3c54a26f5948'),
  ('db4a4756-a255-4ad7-8947-34e599971771'),('df450505-39d6-47c4-875d-a46e3b98c596'),
  ('488c9946-e074-4fb3-97c2-8b1db44616ca'),('3eb43e00-7729-4979-93b6-d836a0e30b0f')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='4578d506-919b-4db2-8eb8-c3c15d15c80e', department_id='a16b580c-26b4-4ce5-bd1e-c05260aef976',
  department=(SELECT name FROM departments WHERE id='a16b580c-26b4-4ce5-bd1e-c05260aef976'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- Cultivation (15 docs): disinfection/quarantine/hygiene/zoning/room-cleaning, mother-plant destruction,
-- micropropagation setup, team formation, weekly cultivation status + transition progress reporting
WITH RECURSIVE roots(id) AS (VALUES
  ('9ee2f283-317b-44d1-a35f-227c2a1d9f7a'::uuid),('a1bf55d7-2bd6-4670-8bc1-282c6fdd7d39'),
  ('99da12e8-291e-4923-9633-e2bbabc29a1e'),('742d82ca-9111-4da2-bbcf-2df42d94e0fb'),
  ('51c5f020-ec1b-473b-98f4-d55a84794872'),('bdb84118-6794-4314-bb90-249955c3981f'),
  ('bc348cca-a8b5-4ec2-99a8-928c1560bfda'),('f813820c-eba5-4f3f-830c-322186831bfe'),
  ('637f48c2-bcdf-44f8-b995-8208bd07be70'),('9ffda780-a333-415f-8df0-4d1fcc194dc7'),
  ('733d6d30-47e5-42c2-b858-541763c117ff'),('e2587058-d9d1-44de-b79e-1ae59c4bf561'),
  ('7a78e72d-5dfe-4f76-848d-7102c7370437'),('be312844-0c7c-44f5-9f6d-827f95175e2c'),
  ('dc0cab8f-1271-480f-93eb-c6c2ce93fc12')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='9dfad6ce-6704-493c-8a8c-3a56afefbed6', department_id='7966fa88-b83e-4afc-9a97-04453f664e74',
  department=(SELECT name FROM departments WHERE id='7966fa88-b83e-4afc-9a97-04453f664e74'),
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- CEO/COO management-level (4 docs, stay with CEO, org-wide/no department):
-- written itemized plan, integrate weekly reports by sector, financial framework, blocker escalation
WITH RECURSIVE roots(id) AS (VALUES
  ('7bcc1aa2-183d-448f-863c-b5578e31394a'::uuid),('b99cab0d-e2cf-4735-a213-c263eaae5967'),
  ('22961051-563a-480a-998c-e14a075e721f'),('dbf75801-c52d-4f23-a9ba-5f741415406b')),
sub AS (SELECT id FROM tasks WHERE id IN (SELECT id FROM roots) AND is_deleted=false
        UNION ALL SELECT t.id FROM tasks t JOIN sub s ON t.parent_id=s.id WHERE t.is_deleted=false)
UPDATE tasks SET user_id='a8d1003b-3648-4c07-9fec-19f14681abca', department_id=NULL, department=NULL,
  updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
WHERE id IN (SELECT id FROM sub);

-- QC (5 docs): laboratory method validation, Tranche-1 sampling/CoA, batch opening/visual/physical
-- inspection, customs sampling of new genetics -- NO-OP, already qcm.blani / qc department.

\echo == after: distribution among all touched owners ==
SELECT CASE user_id::text
  WHEN 'f61b6f0f-821a-44d9-ba46-a64f7ef34f44' THEN 'qcm.blani (QC)'
  WHEN 'a8d1003b-3648-4c07-9fec-19f14681abca' THEN 'ceo.kes (CEO)'
  WHEN '8103b299-9658-4c3d-b806-07068d6e64c1' THEN 'qam.jovana (QA)'
  WHEN '9dfad6ce-6704-493c-8a8c-3a56afefbed6' THEN 'cum.elen (Cultivation)'
  WHEN 'e880f30f-7105-4d12-9b96-f1dfcaaeb32b' THEN 'whm.log (Logistics)'
  WHEN '4578d506-919b-4db2-8eb8-c3c15d15c80e' THEN 'mam.rez (Maintenance)'
  WHEN '5141a2b4-09a0-49e8-9b1a-3af180a12081' THEN 'prm.ced (Production)'
  ELSE user_id::text END AS owner, count(*)
FROM tasks WHERE is_deleted=false
GROUP BY 1 ORDER BY 2 DESC;

\echo == sanity: CEO-order roots now owned by ceo.kes with NULL department ==
SELECT title, user_id, department_id FROM tasks WHERE id IN
 ('456c5e31-5a91-433a-a795-2f54ca7ee765','c5c93ac6-7553-42c3-a85a-3150d892702e',
  '0d826db2-52cf-4ebd-85f2-e249cde1d02a','cde1a8a3-b700-4906-89df-afa77a6685a0');

COMMIT;

-- Enrichment: give every captured task a start week. Tasks missing week_start
-- (version-level items with no independent Drive linkage) inherit their parent
-- document's week_start, so they render on the board/timeline instead of being
-- date-less. Org-wide (the set is now spread across department managers).
-- NOT touched: due_date (deliberately set only on completed items by the
-- hierarchy build) and work-session ended_at (single-save events have no
-- honest duration — fabricating one would invent a work record).
\set ON_ERROR_STOP on
BEGIN;
SELECT set_config('app.user_id','996f1eec-0ebf-40d1-a7f8-5d491fbb5a89',true);  -- admin
SELECT set_config('app.org_id','a0a0a0a0-0000-4000-8000-000000000001',true);
SELECT set_config('app.role','ADMIN',true);

\echo == before: tasks missing week_start (org-wide) ==
SELECT count(*) AS missing_before FROM tasks
WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND is_deleted=false AND week_start IS NULL;

-- Up to 3 passes to cover any multi-level nesting (idempotent; each pass only
-- touches rows still NULL whose parent now has a week_start).
UPDATE tasks c SET week_start=p.week_start, updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
FROM tasks p WHERE c.parent_id=p.id AND c.is_deleted=false AND c.week_start IS NULL AND p.week_start IS NOT NULL
  AND c.org_id='a0a0a0a0-0000-4000-8000-000000000001';
UPDATE tasks c SET week_start=p.week_start, updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
FROM tasks p WHERE c.parent_id=p.id AND c.is_deleted=false AND c.week_start IS NULL AND p.week_start IS NOT NULL
  AND c.org_id='a0a0a0a0-0000-4000-8000-000000000001';
UPDATE tasks c SET week_start=p.week_start, updated_by='996f1eec-0ebf-40d1-a7f8-5d491fbb5a89', updated_at=now()
FROM tasks p WHERE c.parent_id=p.id AND c.is_deleted=false AND c.week_start IS NULL AND p.week_start IS NOT NULL
  AND c.org_id='a0a0a0a0-0000-4000-8000-000000000001';

\echo == after: tasks still missing week_start (expect 0, or only genuine top-level orphans) ==
SELECT count(*) AS missing_after,
 count(*) FILTER (WHERE parent_id IS NULL) AS toplevel_orphans
FROM tasks WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND is_deleted=false AND week_start IS NULL;
\echo == coverage now ==
SELECT count(*) total, count(*) FILTER (WHERE week_start IS NOT NULL) with_start
FROM tasks WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND is_deleted=false;

COMMIT;

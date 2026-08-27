-- Purely Plant room register — real facility codes (2026-07-30)
--
-- WHY THIS EXISTS
-- The `rooms` registry for org purely-plant held eight PLACEHOLDER codes
-- (grow_1..grow_6, nursery, veg_room) that do not exist anywhere in the
-- facility. The signed room register ("Overview of Rooms with the Net Usable
-- Areas", 27.12.2023), which the HLVd eradication plan §07/§08 is built from,
-- uses the real designations C88/C146/C150/C152/C155/C158/C169/C170/C171/
-- C176-C179/C180-C185. The owner has confirmed those codes are correct against
-- the detailed facility layout, which resolves the one open item the plan itself
-- flagged (Appendix B: "Rooms 1-6 -> C180-C185 mapping is an assumption
-- requiring confirmation").
--
-- WHY RENAME RATHER THAN REPLACE
-- Verified before writing this: all eight placeholder rooms had ZERO
-- plant_batches and there were ZERO decon_room_cycles, so nothing referenced
-- them. With no history to preserve there is no inference risk in assigning the
-- real codes, and renaming keeps each row's own audit history (created as
-- grow_1, became c180) instead of leaving eight dead rows in the registry.
-- Had any batch existed, the grow_N -> C18X mapping would have been an
-- assumption and this script would NOT have been safe to write.
--
-- WHY THE NAMES CARRY BOTH DESIGNATIONS
-- The plan schedules work by "Room 1..6" but the register identifies rooms by
-- C180..C185, and §10 requires those two be reconciled "in a one-page table
-- signed by Production and QA" precisely because conflating them loses a room.
-- Putting both in the room NAME puts that reconciliation in the data rather than
-- in someone's head: code c180, name "Flowering 1.1 · Room 1".
--
-- Codes are lowercased because rooms.code is constrained to ^[a-z0-9_]{1,64}$
-- (see RoomIn.code in app/api/facility.py). C180 is therefore stored as c180.
--
-- SUPERSEDED NAMES — read this before running on a fresh environment. The
-- flowering room NAMES below are the originals and were revised twice the same
-- day; run all three scripts in order to end up where production actually is:
--   1. this script
--   2. oneoff_fix_flowering_room_names_20260730.sql       (dropped "Room N")
--   3. oneoff_restore_flowering_room_numbers_20260730.sql (restored it, on
--      positional evidence from the detailed layout drawing)
-- The names below are left as-run rather than back-edited, so the audit trail
-- and these files tell the same story. Everything else here is current.
--
-- IDEMPOTENT: re-running changes nothing. The renames are guarded on the
-- placeholder code still being present; the inserts are ON CONFLICT DO NOTHING.
-- Run against the tasks DB as a superuser:
--   docker exec -i wwf-db-tasks psql -U postgres -d wwf_tasks -v ON_ERROR_STOP=1 \
--     < oneoff_seed_purelyplant_rooms_20260730.sql

\set ORG 'a0a0a0a0-0000-4000-8000-000000000001'

BEGIN;

-- Refuse to run if a placeholder has acquired references since this was
-- written. Renaming is only safe while nothing points at these rows.
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n
  FROM plant_batches b JOIN rooms r ON r.id = b.room_id
  WHERE r.org_id = 'a0a0a0a0-0000-4000-8000-000000000001'
    AND r.code IN ('grow_1','grow_2','grow_3','grow_4','grow_5','grow_6','nursery','veg_room');
  IF n > 0 THEN
    RAISE EXCEPTION 'REFUSING: % plant_batches now reference the placeholder rooms; '
                    'the grow_N -> C18X mapping is no longer safe to assume', n;
  END IF;
END $$;

-- ── rename the eight placeholders to their real designations ──
UPDATE rooms SET code='c176', name='Clone 1 · C176',        name_mk='Клонови 1 · C176',      kind='nursery', sort=20, updated_at=now() WHERE org_id=:'ORG' AND code='nursery';
UPDATE rooms SET code='c178', name='Vegetation 1 · C178',   name_mk='Вегетација 1 · C178',   kind='veg',     sort=30, updated_at=now() WHERE org_id=:'ORG' AND code='veg_room';
UPDATE rooms SET code='c180', name='Flowering 1.1 · Room 1', name_mk='Цветање 1.1 · Соба 1', kind='flower',  sort=40, updated_at=now() WHERE org_id=:'ORG' AND code='grow_1';
UPDATE rooms SET code='c181', name='Flowering 1.2 · Room 2', name_mk='Цветање 1.2 · Соба 2', kind='flower',  sort=41, updated_at=now() WHERE org_id=:'ORG' AND code='grow_2';
UPDATE rooms SET code='c182', name='Flowering 1.3 · Room 3', name_mk='Цветање 1.3 · Соба 3', kind='flower',  sort=42, updated_at=now() WHERE org_id=:'ORG' AND code='grow_3';
UPDATE rooms SET code='c183', name='Flowering 1.4 · Room 4', name_mk='Цветање 1.4 · Соба 4', kind='flower',  sort=43, updated_at=now() WHERE org_id=:'ORG' AND code='grow_4';
UPDATE rooms SET code='c184', name='Flowering 1.5 · Room 5', name_mk='Цветање 1.5 · Соба 5', kind='flower',  sort=44, updated_at=now() WHERE org_id=:'ORG' AND code='grow_5';
UPDATE rooms SET code='c185', name='Flowering 1.6 · Room 6', name_mk='Цветање 1.6 · Соба 6', kind='flower',  sort=45, updated_at=now() WHERE org_id=:'ORG' AND code='grow_6';

-- ── add the rooms the registry was missing entirely ──
-- C171 mothers, the second clone and veg rooms, the seed and quarantine rooms,
-- the nutrient/irrigation room, and the five cultivation corridors the plan
-- cleans near-daily (§25). T161 (water plant) is deliberately EXCLUDED — the
-- plan excludes it from the campaign and keeps it running (§07).
INSERT INTO rooms (org_id, code, name, name_mk, kind, sort) VALUES
  (:'ORG', 'c171', 'Mother plants · C171',          'Мајки растенија · C171',              'mother',  10),
  (:'ORG', 'c177', 'Clone 2 · C177',                'Клонови 2 · C177',                    'nursery', 21),
  (:'ORG', 'c179', 'Vegetation 2 · C179',           'Вегетација 2 · C179',                 'veg',     31),
  (:'ORG', 'c88',  'Seed store · C88',              'Складиште за семе · C88',             'other',   50),
  (:'ORG', 'c150', 'Sick-plant quarantine · C150',  'Карантин за болни растенија · C150',  'other',   51),
  (:'ORG', 'c158', 'Nutrient & irrigation · C158',  'Хранливи материи и наводнување · C158','other',  60),
  (:'ORG', 'c146', 'Corridor · C146',               'Коридор · C146',                      'other',   70),
  (:'ORG', 'c152', 'Corridor · C152',               'Коридор · C152',                      'other',   71),
  (:'ORG', 'c155', 'Corridor · C155',               'Коридор · C155',                      'other',   72),
  (:'ORG', 'c169', 'Corridor · C169',               'Коридор · C169',                      'other',   73),
  (:'ORG', 'c170', 'Corridor · C170',               'Коридор · C170',                      'other',   74)
ON CONFLICT (org_id, code) DO NOTHING;

COMMIT;

-- verification
SELECT code, name, kind, sort, is_active
FROM rooms WHERE org_id = 'a0a0a0a0-0000-4000-8000-000000000001'
ORDER BY sort, code;

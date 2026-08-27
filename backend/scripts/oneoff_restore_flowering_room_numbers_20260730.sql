-- Restore the Room-N label on the flowering rooms (2026-07-30, SECOND revision)
--
-- HISTORY, because this reverses an earlier correction in the same day and the
-- reason matters more than the change:
--   1. Seeded as "Flowering 1.1 · Room 1". At that point the Room-N <-> C18X
--      mapping was flagged "requires QA confirmation" by BOTH the eradication
--      plan (Appendix B) and the CEO's Facility Execution Map, so asserting it
--      was unfounded.
--   2. Stripped to "Flowering 1.1 · C180" — correct given what was known.
--   3. Restored here, because the owner supplied the architectural drawing
--      ("Purely Plant Layout - Detailed.pdf", GSPublisher, ground floor) and it
--      RESOLVES the mapping. This is new evidence, not a changed opinion.
--
-- THE EVIDENCE. The drawing carries "FLOWERING PREMISE 1.1".."1.6" and
-- "C180".."C185" as separate text labels. Extracted with `pdftotext -layout`,
-- which preserves horizontal position, the two sets align one-to-one and
-- monotonically:
--     FLOWERING PREMISE 1.1 @ x=724   <->  C180 @ x=727   (dx  3)
--     FLOWERING PREMISE 1.2 @ x=784   <->  C181 @ x=795   (dx 11)
--     FLOWERING PREMISE 1.3 @ x=878   <->  C182 @ x=880   (dx  2)
--     FLOWERING PREMISE 1.4 @ x=938   <->  C183 @ x=945   (dx  7)
--     FLOWERING PREMISE 1.5 @ x=1022  <->  C184 @ x=1030  (dx  8)
--     FLOWERING PREMISE 1.6 @ x=1119  <->  C185 @ x=1124  (dx  5)
-- Every dx is 2-11 columns while adjacent rooms are 60-100 columns apart, so no
-- other pairing is geometrically possible. The same method confirms C150 =
-- "КАРАНТИН ЗА БОЛНИ РАСТЕНИЈА" (sick-plant quarantine, dx 34, same line).
--
-- Combined with the plan's §08 zone map, which pairs C180="Room 1" .. C185="Room
-- 6", two independent documents now agree, which is the corroboration that was
-- missing. Room N = Flowering 1.N = C(179+N).
--
-- STILL OUTSTANDING, and deliberately not claimed by this script: QA's SIGNATURE
-- on the one-page reconciliation table the plan's §10 requires. Verifying a
-- drawing is evidence; it is not a signed controlled document. The data is now
-- correct and useful; the process step remains open.
BEGIN;
UPDATE rooms SET name='Flowering 1.1 · C180 · Room 1', name_mk='Цветање 1.1 · C180 · Соба 1', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c180';
UPDATE rooms SET name='Flowering 1.2 · C181 · Room 2', name_mk='Цветање 1.2 · C181 · Соба 2', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c181';
UPDATE rooms SET name='Flowering 1.3 · C182 · Room 3', name_mk='Цветање 1.3 · C182 · Соба 3', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c182';
UPDATE rooms SET name='Flowering 1.4 · C183 · Room 4', name_mk='Цветање 1.4 · C183 · Соба 4', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c183';
UPDATE rooms SET name='Flowering 1.5 · C184 · Room 5', name_mk='Цветање 1.5 · C184 · Соба 5', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c184';
UPDATE rooms SET name='Flowering 1.6 · C185 · Room 6', name_mk='Цветање 1.6 · C185 · Соба 6', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c185';
COMMIT;
SELECT code, name, name_mk FROM rooms
WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND kind='flower' ORDER BY sort;

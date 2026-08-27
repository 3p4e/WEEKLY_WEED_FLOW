-- Correction (2026-07-30): drop the unconfirmed Room-N assertion from the
-- flowering room names.
--
-- "Flowering 1.1 .. 1.6" and "C180 .. C185" both come from the signed register
-- (27.12.2023), so pairing them in order is register-sourced and safe. What is
-- NOT confirmed is the equation of those with the campaign's operational
-- "Room 1..6": the eradication plan's Appendix B calls it "an assumption
-- requiring confirmation", and the CEO's execution map of 29.07.2026 repeats
-- verbatim that "the mapping of Rooms 1-6 to C180-C185 requires QA
-- confirmation". Asserting it in master data would have propagated an unverified
-- claim into a GxP record — and the specific harm is real, since the harvest
-- schedule is written as "Room 3 on 31.07": cleaning c182 believing it is Room 3
-- when it is not is exactly the error the plan's §10 reconciliation exists to
-- prevent.
--
-- Add the Room-N label back in one UPDATE once Production + QA have signed the
-- one-page reconciliation table the plan requires.
BEGIN;
UPDATE rooms SET name='Flowering 1.1 · C180', name_mk='Цветање 1.1 · C180', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c180';
UPDATE rooms SET name='Flowering 1.2 · C181', name_mk='Цветање 1.2 · C181', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c181';
UPDATE rooms SET name='Flowering 1.3 · C182', name_mk='Цветање 1.3 · C182', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c182';
UPDATE rooms SET name='Flowering 1.4 · C183', name_mk='Цветање 1.4 · C183', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c183';
UPDATE rooms SET name='Flowering 1.5 · C184', name_mk='Цветање 1.5 · C184', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c184';
UPDATE rooms SET name='Flowering 1.6 · C185', name_mk='Цветање 1.6 · C185', updated_at=now()
  WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND code='c185';
COMMIT;
SELECT code, name FROM rooms
WHERE org_id='a0a0a0a0-0000-4000-8000-000000000001' AND kind='flower' ORDER BY sort;

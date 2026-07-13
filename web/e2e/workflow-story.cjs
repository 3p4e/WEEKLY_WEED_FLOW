/* workflow-story.cjs — the made-up-but-realistic content for the connected
   cross-department demo. ONE batch ("Wedding Crasher WC-0426") flows through
   every department as a single parent task; each department is a delegated
   subtask (stage) with its own checklist of sub-subtasks. The executives then
   see the whole tree roll up.

   This is data only (no Playwright) so the storyline is easy to read and edit
   in one place, separate from the recording mechanics in record-workflow.cjs.  */

const BATCH = {
  ref: 'WC-0426',
  strain: 'Wedding Crasher',
  title: 'Batch WC-0426 · Wedding Crasher — Harvest → Release → Dispatch',
  desc:
    'End-to-end coordination of finished-flower batch WC-0426 (Wedding Crasher, ' +
    'Flower Room 2, 48 plants). One batch, seven departments: harvest and dry, ' +
    'process and package, sample and test, release on spec, then pick, seal and ' +
    'dispatch under chain of custody. Each stage below is delegated to the ' +
    'responsible department and rolls up to this batch.',
  // Informational coordination task — the app itself is not a GMP/QMS record.
  est: '2',
};

/* Seven department stages, in the real order the batch moves through the site.
   `code` maps to the seeded department; `attrs` fills that department's own
   template fields; `subs` are the sub-subtasks (checklist) with descriptions;
   `handoffTo` is the next department in the chain (used only in captions). */
const STAGES = [
  {
    code: 'cultivation', mgr: 'm.cultivation', order: 1,
    stage: {
      title: 'Harvest & dry — Flower Room 2 (Wedding Crasher)',
      desc: 'Cut, wet-weigh and transfer 48 Wedding Crasher plants from Flower Room 2 to Dry Room A. Target 10–11% final moisture over a 10-day dry.',
      attrs: { room: 'GR-F2', strain: 'Wedding Crasher', plant_count: '48' },
      est: '9',
    },
    subs: [
      { title: 'Final flush check + defoliation', desc: 'Confirm 7-day flush complete; strip fan leaves; photograph canopy for the batch record.' },
      { title: 'Cut & wet-weigh 48 plants → 62.4 kg wet', desc: 'Harvest all 48 plants, wet-weigh per plant, reconcile to 62.4 kg total on scale SCL-01.' },
      { title: 'Hang in Dry Room A @ 60% RH / 18°C', desc: 'Transfer to Dry Room A; log start conditions; hand the room over to Maintenance for climate hold.' },
    ],
    liveSub: { title: 'Tag & log plant IDs into batch record', desc: 'Barcode each hang line and record plant IDs against WC-0426.' },
    handoffTo: 'tooling',
    next: { title: 'Transplant Wedding Crasher clones → Veg 1 (batch WC-0428)', attrs: { room: 'GR-V1', strain: 'Wedding Crasher', plant_count: '60' } },
  },
  {
    code: 'tooling', mgr: 'm.tooling', order: 2,
    stage: {
      title: 'Hold Dry Room A climate + ready the trim line',
      desc: 'Keep Dry Room A at 60% RH / 18°C for the full dry; sanitize and stage the trim line (Twister T4) ready for Production.',
      attrs: { equipment_ref: 'AHU-2', maintenance_type: 'Sanitation' },
      est: '4',
    },
    subs: [
      { title: 'Swap AHU-2 filters, log differential pressure', desc: 'Replace pre/HEPA filters on AHU-2 serving Dry Room A; record ΔP before/after.' },
      { title: 'Verify 60% RH / 18°C hold for 10 days', desc: 'Trend RH/temp twice daily; flag any excursion beyond ±3% RH to QA.' },
      { title: 'Sanitize & function-test trim line T4', desc: 'Clean-in-place Twister T4; run test cycle; sign line clearance for Production.' },
    ],
    liveSub: { title: 'Calibrate room hygrometer against reference', desc: 'Two-point calibration of the Dry Room A hygrometer vs the reference meter.' },
    handoffTo: 'production',
    next: { title: 'Preventive maintenance — chiller CH-1 quarterly', attrs: { equipment_ref: 'CH-1', maintenance_type: 'Preventive' } },
  },
  {
    code: 'production', mgr: 'm.production', order: 3,
    stage: {
      title: 'Dry, cure, trim & package lot WC-0426',
      desc: 'Take WC-0426 from dry to finished packaged goods: cure, machine + hand trim to 11.8 kg, then package into 100 g jars for QC sampling.',
      attrs: { batch_ref: 'WC-0426', process_step: 'Dry-cure-trim-pack' },
      est: '16',
    },
    subs: [
      { title: 'Cure 7 days, burp daily to 11% moisture', desc: 'Move to cure totes; burp daily; confirm 11% moisture before trim.' },
      { title: 'Machine + hand trim → 11.8 kg trimmed', desc: 'Trim on T4; hand-finish A-grade; reconcile yield to 11.8 kg; collect trim for extraction.' },
      { title: 'Package 118 × 100 g jars, lot WC-0426', desc: 'Fill, N₂-flush and seal 118 jars; apply lot labels; stage for QC sampling.' },
    ],
    liveSub: { title: 'First-article seal-integrity check (first 10 jars)', desc: 'Vacuum-decay test the first 10 sealed jars before running the batch.' },
    handoffTo: 'qc',
    next: { title: 'Line changeover + cleaning verification (next lot)', attrs: { batch_ref: 'WC-0430', process_step: 'Changeover' } },
  },
  {
    code: 'qc', mgr: 'm.qc', order: 4, locksReport: true,
    stage: {
      title: 'Sample & test lot WC-0426 (release panel)',
      desc: 'Pull the release-panel samples for WC-0426 and run potency, moisture, microbial and pesticide testing; issue the Certificate of Analysis.',
      attrs: { sample_ref: 'WC-0426-S01', inspection_type: 'Release panel', batch_ref: 'WC-0426' },
      est: '6',
    },
    subs: [
      { title: 'Pull 6 samples per plan QC-SP-07', desc: 'Randomized sampling across the 118 jars per sampling plan QC-SP-07; log in the sample register.' },
      { title: 'Potency 22.4% THC · moisture 10.8%', desc: 'HPLC potency and moisture balance; both within release spec.' },
      { title: 'Microbial + pesticide panel — PASS', desc: 'TYMC/TAMC and multi-residue pesticide screen; all results conform. Issue COA-WC-0426.' },
    ],
    liveSub: { title: 'Retain 2 jars in the sample library', desc: 'Set aside 2 sealed jars as retention samples for the required shelf life.' },
    handoffTo: 'quality_assurance',
    next: { title: 'HPLC quarterly calibration + system suitability', attrs: { sample_ref: 'CAL-2026-Q3', inspection_type: 'Calibration', batch_ref: 'N/A' } },
  },
  {
    code: 'quality_assurance', mgr: 'm.qa', order: 5,
    stage: {
      title: 'Batch disposition & release — WC-0426',
      desc: 'Independent QA review of the WC-0426 batch record and COA against specification, yield reconciliation, and final release disposition.',
      attrs: { doc_ref: 'COA-WC-0426', capa_ref: 'N/A' },
      est: '3',
    },
    subs: [
      { title: 'Review COA vs release spec — conforms', desc: 'Verify potency, moisture and micro results against the WC release specification.' },
      { title: 'Reconcile yield 11.8 kg vs theoretical', desc: 'Confirm the trim yield is within the expected range; no unexplained loss.' },
      { title: 'Sign disposition: RELEASED', desc: 'Complete the batch review checklist and set disposition to RELEASED for dispatch.' },
    ],
    liveSub: { title: 'File COA + batch record to the WC-0426 dossier', desc: 'Attach the signed COA and completed record to the batch dossier index.' },
    handoffTo: 'logistics',
    next: { title: 'Periodic review — Labeling & Label Control SOP', attrs: { doc_ref: 'QASOP-031', capa_ref: 'N/A' } },
  },
  {
    code: 'logistics', mgr: 'm.logistics', order: 6,
    stage: {
      title: 'Dispatch PO-778 — WC-0426 → Dispensary North',
      desc: 'Pick, pack and manifest 40 × 100 g jars of released lot WC-0426 for order PO-778, and schedule the courier window.',
      attrs: { flow: 'out', batch_ref: 'WC-0426' },
      est: '3',
    },
    subs: [
      { title: 'Pick & pack 40 × 100 g jars for PO-778', desc: 'Pull 40 released jars from the dispatch cage; pack with tamper-evident wrap.' },
      { title: 'Generate manifest + transport ticket', desc: 'Produce the shipping manifest, lot traceability and transport ticket for PO-778.' },
      { title: 'Book courier window — Thu 14:00', desc: 'Schedule the licensed courier for Thursday 14:00; notify Security for escort.' },
    ],
    liveSub: { title: 'Update stock ledger + bin locations', desc: 'Decrement WC-0426 on-hand by 40 jars and update dispatch-cage bin counts.' },
    handoffTo: 'security',
    next: { title: 'Receive nutrient shipment — PO-802 (inbound)', attrs: { flow: 'in', batch_ref: 'PO-802' } },
  },
  {
    code: 'security', mgr: 'm.security', order: 7,
    stage: {
      title: 'Chain of custody & escort — PO-778',
      desc: 'Seal, photograph and escort the PO-778 shipment; maintain unbroken chain of custody from the dispatch bay to Dispensary North.',
      attrs: { area: 'Dispatch Bay', incident_type: 'Escort' },
      est: '2',
    },
    subs: [
      { title: 'Seal & photograph pallet (tamper tags)', desc: 'Apply numbered tamper tags; photograph the sealed pallet; record tag numbers.' },
      { title: 'GPS transport + two-guard escort', desc: 'Activate GPS tracker; assign two guards; log departure time and route.' },
      { title: 'Confirm delivery signature at Dispensary North', desc: 'Obtain and file the delivery signature; close the chain-of-custody log.' },
    ],
    liveSub: { title: 'Review dispatch-bay CCTV for the load-out', desc: 'Pull and retain the CCTV clip covering the PO-778 load-out window.' },
    handoffTo: null,
    next: { title: 'Camera firmware updates — perimeter zone C', attrs: { area: 'Zone C', incident_type: 'Maintenance' } },
  },
];

module.exports = { BATCH, STAGES };

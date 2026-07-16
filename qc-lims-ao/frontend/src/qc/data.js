// QC Lab static data — enums, labels, test specs, seed data — ported from the
// prototype qc/data.js (aligned with the QC_LIMS_Ao backend models).

export const SampleType = { RAW_MATERIAL: 'RAW_MATERIAL', IPC: 'IPC', FINISHED_PRODUCT: 'FINISHED_PRODUCT', STABILITY: 'STABILITY', WATER: 'WATER', ENVIRONMENTAL: 'ENVIRONMENTAL' };
export const SampleTypeLabel = {
  RAW_MATERIAL: { en: 'Raw Material', mk: 'Суровина' }, IPC: { en: 'In-Process Control', mk: 'Меѓупроцесна контрола' },
  FINISHED_PRODUCT: { en: 'Finished Product', mk: 'Готов производ' }, STABILITY: { en: 'Stability', mk: 'Стабилност' },
  WATER: { en: 'Water System', mk: 'Водоснабдување' }, ENVIRONMENTAL: { en: 'Environmental', mk: 'Еколошки мониторинг' },
};
export const SampleStatus = { COLLECTED: 'COLLECTED', IN_TEST: 'IN_TEST', TESTED: 'TESTED', APPROVED: 'APPROVED', REJECTED: 'REJECTED' };
export const SampleStatusLabel = {
  COLLECTED: { en: 'Collected', mk: 'Земен' }, IN_TEST: { en: 'In Test', mk: 'Во тестирање' },
  TESTED: { en: 'Tested', mk: 'Тестиран' }, APPROVED: { en: 'Approved', mk: 'Одобрен' }, REJECTED: { en: 'Rejected', mk: 'Одбиен' },
};
export const SampleStatusColor = { COLLECTED: 'var(--blue)', IN_TEST: 'var(--orange)', TESTED: 'var(--violet,#7A5BE0)', APPROVED: 'var(--green)', REJECTED: 'var(--red)' };
export const SampleStatusBg = { COLLECTED: 'var(--blue-soft)', IN_TEST: 'var(--orange-soft)', TESTED: 'var(--violet-soft,#ECE6FB)', APPROVED: 'var(--green-soft)', REJECTED: 'var(--red-soft)' };

export const SamplingPoint = {
  SP_01: { code: 'SP-01', en: 'Raw material arrival', mk: 'Прием на суровина' },
  SP_06: { code: 'SP-06', en: 'Reception sampling (flower)', mk: 'Прием — цвет' },
  SP_07: { code: 'SP-07', en: 'IPC — Drying', mk: 'МПК — Сушење' },
  SP_08: { code: 'SP-08', en: 'IPC — Curing', mk: 'МПК — Зреење' },
  SP_09: { code: 'SP-09', en: 'Finished product (pkg day 1)', mk: 'Готов производ (паковање ден 1)' },
  SP_10: { code: 'SP-10', en: 'Finished product (pkg day 2+)', mk: 'Готов производ (паковање ден 2+)' },
  SP_11: { code: 'SP-11', en: 'Stability pull', mk: 'Стабилност' },
};
export const PotencyGrade = { A: { en: 'Grade A — Premium', mk: 'Класа А — Премиум' }, B: { en: 'Grade B — Standard', mk: 'Класа Б — Стандард' }, C: { en: 'Grade C — Extract', mk: 'Класа В — Екстракт' } };
export const OOSPhase = { PHASE_I: 'PHASE_I', PHASE_II: 'PHASE_II', CLOSED: 'CLOSED' };
export const OOSPhaseLabel = { PHASE_I: { en: 'Phase I — Lab Error Check', mk: 'Фаза I — Лабораториска грешка' }, PHASE_II: { en: 'Phase II — Full Investigation', mk: 'Фаза II — Целосна истрага' }, CLOSED: { en: 'Closed', mk: 'Затворено' } };

export const TEST_SPECS = [
  { id: 'THC', p: 'THC Content', mk: 'ТХК Содржина', method: 'HPLC (Ph. Eur. 2.2.29)', specMin: 18.0, specMax: 25.0, unit: '% w/w' },
  { id: 'CBD', p: 'CBD Content', mk: 'ЦБД Содржина', method: 'HPLC (Ph. Eur. 2.2.29)', specMin: 0, specMax: 1.0, unit: '% w/w' },
  { id: 'MOIST', p: 'Moisture Content', mk: 'Влажност', method: 'Karl Fischer (USP <921>)', specMin: 8.0, specMax: 13.0, unit: '%' },
  { id: 'AW', p: 'Water Activity', mk: 'Активност на вода', method: 'Capacitance (USP <922>)', specMin: 0, specMax: 0.65, unit: 'Aw' },
  { id: 'TYMC', p: 'TYMC', mk: 'ТИМК', method: 'Ph. Eur. 2.6.12', specMin: 0, specMax: 100, unit: 'CFU/g', specLabel: '≤ 10² CFU/g' },
  { id: 'TAMC', p: 'TAMC', mk: 'ТАМК', method: 'Ph. Eur. 2.6.12', specMin: 0, specMax: 10000, unit: 'CFU/g', specLabel: '≤ 10⁴ CFU/g' },
  { id: 'GNB', p: 'Bile-tolerant GNB', mk: 'ГНБ', method: 'Ph. Eur. 2.6.13', specMin: 0, specMax: 100, unit: 'CFU/g', specLabel: '≤ 10² CFU/g' },
  { id: 'AFLA', p: 'Aflatoxins (Total)', mk: 'Афлатоксини', method: 'LC-MS/MS', specMin: 0, specMax: 4.0, unit: 'µg/kg' },
  { id: 'PEST', p: 'Pesticide Residues', mk: 'Пестициди', method: 'GC-MS/MS (EU 2019/1009)', conform: true },
  { id: 'CD', p: 'Cadmium (Cd)', mk: 'Кадмиум', method: 'ICP-MS (Ph. Eur. 2.4.20)', specMin: 0, specMax: 0.20, unit: 'mg/kg' },
  { id: 'PB', p: 'Lead (Pb)', mk: 'Олово', method: 'ICP-MS (Ph. Eur. 2.4.20)', specMin: 0, specMax: 0.50, unit: 'mg/kg' },
  { id: 'APP', p: 'Appearance', mk: 'Изглед', method: 'Visual', conform: true },
  { id: 'FM', p: 'Foreign Matter', mk: 'Странични материи', method: 'Ph. Eur. 2.8.2', specMin: 0, specMax: 2.0, unit: '%' },
];

export const PEOPLE = {
  elena: { name: 'Elena Stojanova', init: 'ES', role: 'HOD · QC', mk: 'Елена Стојанова', bg: '#15A86B' },
  sofija: { name: 'Sofija Trajkova', init: 'ST', role: 'QA Officer', mk: 'Софија Трајкова', bg: '#7A5BE0' },
  jana: { name: 'Jana Kostova', init: 'JK', role: 'QP · Release', mk: 'Јана Костова', bg: '#C2410C' },
  stefan: { name: 'Stefan Georgiev', init: 'SG', role: 'QC Analyst', mk: 'Стефан Георгиев', bg: '#2F6BFF' },
  ana: { name: 'Ana Nikolova', init: 'AN', role: 'Sampling', mk: 'Ана Николова', bg: '#E5484D' },
  blagoj: { name: 'Blagoj Dimov', init: 'BD', role: 'QC Analyst', mk: 'Благој Димов', bg: '#0EA5A5' },
};

export const NAV = [
  { id: 'dash', label: { en: 'Dashboard', mk: 'Контролна табла' }, icon: 'trend' },
  { id: 'samples', label: { en: 'Samples', mk: 'Примероци' }, icon: 'flask' },
  { id: 'specs', label: { en: 'Specifications', mk: 'Спецификации' }, icon: 'doc' },
  { id: 'rqs', label: { en: 'Sample Requests', mk: 'Барања за примерок' }, icon: 'beaker' },
  { id: 'sp06', label: { en: 'Reception (SP-06)', mk: 'Прием (СП-06)' }, icon: 'barcode' },
  { id: 'results', label: { en: 'Results Entry', mk: 'Внес резултати' }, icon: 'grid' },
  { id: 'review', label: { en: 'Progressive Review', mk: 'Прогресивен преглед' }, icon: 'check' },
  { id: 'oos', label: { en: 'OOS Investigation', mk: 'ООС Истрага' }, icon: 'alert' },
  { id: 'capa', label: { en: 'CAPA', mk: 'КПА' }, icon: 'wrench' },
  { id: 'transport', label: { en: 'Transport / CoC', mk: 'Транспорт' }, icon: 'box' },
  { id: 'water', label: { en: 'Water QC', mk: 'Вода КК' }, icon: 'drop' },
  { id: 'stability', label: { en: 'Stability', mk: 'Стабилност' }, icon: 'clock' },
  { id: 'genealogy', label: { en: 'Genealogy', mk: 'Генеалогија' }, icon: 'layers' },
  { id: 'knowledge', label: { en: 'Knowledge Base', mk: 'База на знаење' }, icon: 'doc' },
  { id: 'aiaudit', label: { en: 'AI Audit', mk: 'АИ ревизија' }, icon: 'shield' },
  { id: 'search', label: { en: 'AI Search', mk: 'АИ Пребарување' }, icon: 'sparkle' },
  { id: 'audit', label: { en: 'Audit Trail', mk: 'Ревизорска трага' }, icon: 'list' },
];

export const SEED_SAMPLES = [
  { id: 'PP-SMP-2026-0041', sample_id: 'PP-SMP-2026-0041', coa: 'PP-COA-2026-0018', batch_id: 'PP-FP-2026-003', material_name_en: 'Gorilla Glue #4 (Flower)', material_name_mk: 'Горила Глу #4 (Цвет)', sample_type: 'FINISHED_PRODUCT', sampling_point: 'SP_09', lab: 'In-house', status: 'APPROVED', date: '2026-06-01', analyst: 'elena', reviewer: 'sofija', qp: 'jana', esig: true, potency_grade: 'B', results: { THC: '22.40', CBD: '0.34', MOIST: '11.2', AW: '0.58', TYMC: '<10', TAMC: '120', GNB: 'ND', AFLA: '<LOQ', PEST: 'Conform', CD: '0.04', PB: '0.11', APP: 'Conforms', FM: '0.3' }, notes: '4-zone composite from Trim Hall. Full panel.', linkedTask: 'T-602' },
  { id: 'PP-SMP-2026-0040', sample_id: 'PP-SMP-2026-0040', coa: 'PP-COA-2026-0017', batch_id: 'PP-FP-2026-002', material_name_en: 'Blue Dream (Flower)', material_name_mk: 'Блу Дрим (Цвет)', sample_type: 'FINISHED_PRODUCT', sampling_point: 'SP_09', lab: 'In-house', status: 'IN_TEST', date: '2026-05-30', analyst: 'stefan', reviewer: '', qp: '', esig: false, results: {}, notes: 'Awaiting HPLC reagent.' },
  { id: 'PP-SMP-2026-0039', sample_id: 'PP-SMP-2026-0039', coa: 'PP-COA-2026-0016', batch_id: 'PP-FP-2026-001', material_name_en: 'Gorilla Glue #4 (Trim)', material_name_mk: 'Горила Глу #4 (Трим)', sample_type: 'FINISHED_PRODUCT', sampling_point: 'SP_09', lab: 'External — Agilent MK', status: 'APPROVED', date: '2026-05-28', analyst: 'sofija', reviewer: 'jana', qp: 'jana', esig: true, potency_grade: 'B', results: { THC: '18.70', CBD: '0.22', MOIST: '10.8', AW: '0.52', TYMC: '<10', TAMC: '80', GNB: 'ND', AFLA: '<LOQ', PEST: 'Conform', CD: '0.06', PB: '0.09', APP: 'Conforms', FM: '0.5' }, notes: 'External lab report.' },
  { id: 'PP-SMP-2026-0038', sample_id: 'PP-SMP-2026-0038', coa: 'PP-COA-2026-0015', batch_id: 'PP-FP-2025-048', material_name_en: 'Blue Dream (Pre-roll)', material_name_mk: 'Блу Дрим (Пре-рол)', sample_type: 'FINISHED_PRODUCT', sampling_point: 'SP_10', lab: 'In-house', status: 'REJECTED', date: '2026-05-26', analyst: 'elena', reviewer: 'jana', qp: 'jana', esig: true, results: { THC: '14.20', CBD: '0.45', MOIST: '12.1', AW: '0.61', TYMC: '20', TAMC: '200', GNB: 'ND', AFLA: '<LOQ', PEST: '0.45 ppm Myclobutanil', CD: '0.03', PB: '0.08', APP: 'Conforms', FM: '0.8' }, notes: 'THC below spec. Pesticide OOS.', oos: 'PP-OOS-2026-003' },
  { id: 'PP-SMP-2026-0037', sample_id: 'PP-SMP-2026-0037', coa: 'PP-COA-2026-0014', batch_id: 'PP-IPC-2026-012', material_name_en: 'Gorilla Glue #4 (IPC — Drying)', material_name_mk: 'Горила Глу #4 (МПК — Сушење)', sample_type: 'IPC', sampling_point: 'SP_07', lab: 'In-house', status: 'APPROVED', date: '2026-05-25', analyst: 'blagoj', reviewer: 'elena', qp: '', esig: true, potency_grade: 'B', results: { THC: '21.10', MOIST: '42.5', AW: '0.88' }, notes: 'Drying IPC — day 3 check.' },
  { id: 'PP-SMP-2026-0036', sample_id: 'PP-SMP-2026-0036', coa: 'PP-COA-2026-0013', batch_id: 'PP-RM-2026-008', material_name_en: 'Cannabis Flower (Raw Material)', material_name_mk: 'Канабис цвет (Суровина)', sample_type: 'RAW_MATERIAL', sampling_point: 'SP_06', lab: 'In-house', status: 'APPROVED', date: '2026-05-22', analyst: 'ana', reviewer: 'elena', qp: 'jana', esig: true, results: { THC: '23.80', CBD: '0.28', MOIST: '58.2', APP: 'Conforms', FM: '0.2' }, notes: 'SP-06 reception — Flower Room 3 harvest.' },
];

export const SEED_OOS = [
  { id: 'PP-OOS-2026-003', sample_id: 'PP-SMP-2026-0038', batch_id: 'PP-FP-2025-048', phase: 'PHASE_II', param: 'PEST', result: '0.45 ppm Myclobutanil', spec: 'Conform (0 ppm)', opened: '2026-05-26', opened_by: 'elena', phase1: { conclusion: 'Lab error ruled out. Instrument calibration confirmed.', completed: '2026-05-26', by: 'elena' }, phase2: { root_cause: 'IPM spray residue — Flower Room 1 ventilation inadequate post-application.', capa: 'CAPA-2026-011: Install extraction fans, extend withholding period to 14 days.', status: 'open' } },
  { id: 'PP-OOS-2026-002', sample_id: 'PP-SMP-2026-0038', batch_id: 'PP-FP-2025-048', phase: 'PHASE_I', param: 'THC', result: '14.20%', spec: '18.0–25.0%', opened: '2026-05-26', opened_by: 'elena', phase1: { conclusion: 'Confirmed below-spec. Not lab error — inherent sample variance.', completed: '2026-05-27', by: 'stefan' }, phase2: null },
];

export const SEED_AUDIT = [
  { ts: '2026-06-01 14:32', user: 'elena', action: 'E-signature applied', target: 'PP-COA-2026-0018', detail: 'Final approval — QC HOD sign-off', type: 'esig' },
  { ts: '2026-06-01 14:28', user: 'sofija', action: 'Results reviewed', target: 'PP-COA-2026-0018', detail: 'QA review — no deviations', type: 'review' },
  { ts: '2026-06-01 11:45', user: 'elena', action: 'Results entered', target: 'PP-SMP-2026-0041', detail: '13 parameters — all within spec', type: 'data' },
  { ts: '2026-06-01 09:12', user: 'ana', action: 'Sample collected', target: 'PP-SMP-2026-0041', detail: 'Batch PP-FP-2026-003, 4-zone composite', type: 'custody' },
  { ts: '2026-05-30 16:45', user: 'stefan', action: 'Sample collected', target: 'PP-SMP-2026-0040', detail: 'Batch PP-FP-2026-002, Flower Room 1', type: 'custody' },
  { ts: '2026-05-28 10:20', user: 'sofija', action: 'CoA uploaded', target: 'PP-COA-2026-0016', detail: 'External Agilent MK — AI-extracted 9 params', type: 'upload' },
  { ts: '2026-05-26 15:30', user: 'elena', action: 'OOS opened', target: 'PP-OOS-2026-003', detail: 'Myclobutanil 0.45 ppm — Pesticide non-conform', type: 'oos' },
  { ts: '2026-05-26 14:10', user: 'elena', action: 'OOS opened', target: 'PP-OOS-2026-002', detail: 'THC 14.20% below spec 18.0%', type: 'oos' },
  { ts: '2026-05-25 09:00', user: 'blagoj', action: 'IPC results entered', target: 'PP-SMP-2026-0037', detail: 'Drying IPC — moisture 42.5%', type: 'data' },
  { ts: '2026-05-22 11:30', user: 'ana', action: 'SP-06 reception', target: 'PP-SMP-2026-0036', detail: 'Cannabis flower batch PP-RM-2026-008, children created: SP-07, SP-08, SP-09', type: 'custody' },
];

// ── Language-aware helpers ──
export const makeQcLabels = (lang) => {
  const tr = (obj) => (typeof obj === 'object' && obj ? obj[lang] || obj.en || '' : String(obj || ''));
  return {
    tr,
    statusLabel: (st) => tr(SampleStatusLabel[st] || { en: st, mk: st }),
    typeLabel: (tp) => tr(SampleTypeLabel[tp] || { en: tp, mk: tp }),
    spLabel: (sp) => (SamplingPoint[sp] ? tr(SamplingPoint[sp]) : sp),
    materialName: (s) => (lang === 'mk' ? s.material_name_mk || s.material_name_en : s.material_name_en),
    personName: (id) => {
      const p = PEOPLE[id];
      return p ? (lang === 'mk' ? p.mk || p.name : p.name) : id || '';
    },
  };
};

export const passCheck = (specId, val) => {
  const spec = TEST_SPECS.find((s) => s.id === specId);
  if (!spec) return true;
  if (spec.conform) return val === 'Conform' || val === 'Conforms' || val === 'ND' || val === 'Not detected';
  const n = parseFloat(val);
  if (isNaN(n)) return String(val).startsWith('<') || val === 'ND' || val === 'Not detected';
  return n >= spec.specMin && n <= spec.specMax;
};

// QC Lab state: view routing, selections, filters, data (samples/oos/audit),
// localStorage persistence, and live backend loading with offline fallback.
// Ported from QC.state + qc/core.js + qc/p1.js loadFromAPI.

import { useState, useCallback, useEffect, useRef } from 'react';
import { api } from '../api/client.js';
import { SEED_SAMPLES, SEED_OOS, SEED_AUDIT, passCheck } from './data.js';

const DATA_KEY = 'qc_data_v2';

function loadLocal() {
  try {
    const s = JSON.parse(localStorage.getItem(DATA_KEY));
    if (s && s.samples) return { samples: s.samples, oos: s.oos || [], audit: s.audit || [] };
  } catch {
    /* ignore */
  }
  return {
    samples: structuredClone(SEED_SAMPLES),
    oos: structuredClone(SEED_OOS),
    audit: structuredClone(SEED_AUDIT),
  };
}

// Map backend sample payload → UI shape (defensive; field names may vary).
const mapSamples = (arr) =>
  (arr.items || arr).map((s) => ({
    id: s.sample_id || s.id,
    sample_id: s.sample_id || s.id,
    coa: s.coa_number || s.coa_id || '',
    batch_id: s.batch_id || '',
    material_name_en: s.material_name_en || s.material_name || '',
    material_name_mk: s.material_name_mk || s.material_name_en || '',
    sample_type: s.sample_type || 'FINISHED_PRODUCT',
    sampling_point: s.sampling_point_type || s.sampling_point || 'SP_09',
    lab: s.test_location === 'EXTERNAL' ? 'External' : 'In-house',
    status: s.status || 'COLLECTED',
    date: (s.sampling_date || s.created_at || '').slice(0, 10),
    analyst: s.analyst_id || s.sampled_by_id || 'elena',
    esig: s.status === 'APPROVED',
    potency_grade: s.potency_grade || '',
    results: s.results || {},
    notes: s.notes || '',
  }));

const mapAudit = (arr) =>
  (arr.items || arr).map((e) => ({
    ts: (e.timestamp || e.created_at || '').slice(0, 16).replace('T', ' '),
    user: e.user_id || e.user || 'system',
    action: e.action || '',
    target: e.record_identifier || e.record_id || e.target || '',
    detail: e.new_value || e.details || e.detail || '',
    type: (e.action || '').toLowerCase().includes('sign')
      ? 'esig'
      : (e.action || '').toLowerCase().includes('oos')
      ? 'oos'
      : 'data',
  }));

// Specs: backend list (no params) + per-spec detail (parameters) → screen shape.
const mapSpecParam = (p) => ({
  test: p.test_name_en,
  mk: p.test_name_mk,
  method: p.test_method,
  type: p.spec_type,
  rel_min: p.release_limit_min ?? p.lower_limit,
  rel_max: p.release_limit_max ?? p.upper_limit,
  op_min: p.operational_limit_min,
  op_max: p.operational_limit_max,
  unit: p.unit,
  ref: p.pharmacopoeia_ref,
});
const mapSpec = (s, detail) => ({
  id: s.id || s.spec_id,
  spec_id: s.spec_id,
  material_code: s.material_code,
  material_name_en: s.material_name_en,
  material_name_mk: s.material_name_mk,
  version: s.version,
  status: s.status,
  effective_date: (s.effective_date || '').slice(0, 10),
  approved_by: '',
  approvals: [],
  params: (detail?.parameters || []).map(mapSpecParam),
});

export function useQC({ apiBase, authed, onToast }) {
  const [view, setView] = useState('dash');
  const [selSample, setSelSample] = useState(null);
  const [selOOS, setSelOOS] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [data, setData] = useState(loadLocal);
  const [online, setOnline] = useState(false);
  // Live collections for the sprint screens. null until loaded from the backend;
  // each screen falls back to its bundled seed while null (offline mode).
  const [live, setLive] = useState({
    specs: null, rqs: null, transports: null, capa: null, water: null, stability: null,
  });

  const persist = useRef((d) => {
    try {
      localStorage.setItem(DATA_KEY, JSON.stringify(d));
    } catch {
      /* ignore */
    }
  }).current;

  const setSamples = useCallback(
    (updater) =>
      setData((prev) => {
        const samples = typeof updater === 'function' ? updater(prev.samples) : updater;
        const next = { ...prev, samples };
        persist(next);
        return next;
      }),
    [persist]
  );

  // ── Live backend load (graceful fallback to seed) ──
  const loadFromAPI = useCallback(async () => {
    if (!apiBase || !authed) return false;
    try {
      onToast?.('Connecting to backend…', 'info');
      const [samples, oos, audit, specList, rqs, transports, capa, water, stability] =
        await Promise.all([
          api.listSamples().catch(() => null),
          api.listOOS().catch(() => null),
          api.listAudit().catch(() => null),
          api.listSpecs().catch(() => null),
          api.listSamplingRequests().catch(() => null),
          api.listTransport().catch(() => null),
          api.listCAPA().catch(() => null),
          api.listWater().catch(() => null),
          api.listStability().catch(() => null),
        ]);
      setData((prev) => ({
        samples: samples ? mapSamples(samples) : prev.samples,
        oos: oos ? oos.items || oos : prev.oos,
        audit: audit ? mapAudit(audit) : prev.audit,
      }));
      // Specs need per-row detail for parameters (list omits them).
      let specs = null;
      if (specList) {
        const list = specList.items || specList;
        // Detail lookup is by UUID id (not the business spec_id key).
        const details = await Promise.all(
          list.map((s) => api.getSpec(s.id).catch(() => null))
        );
        specs = list.map((s, i) => mapSpec(s, details[i]));
      }
      setLive((prev) => ({
        specs: specs ?? prev.specs,
        rqs: rqs ? rqs.items || rqs : prev.rqs,
        transports: transports ? transports.items || transports : prev.transports,
        capa: capa ? capa.items || capa : prev.capa,
        water: water ? water.items || water : prev.water,
        stability: stability ? stability.items || stability : prev.stability,
      }));
      setOnline(true);
      onToast?.('Live data loaded ✓', 'success');
      return true;
    } catch {
      onToast?.('Backend unreachable — using local data', 'error');
      return false;
    }
  }, [apiBase, authed, onToast]);

  useEffect(() => {
    if (apiBase && authed) loadFromAPI();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, authed]);

  // ── Navigation ──
  const navigate = useCallback((v) => {
    setView(v);
    setSelSample(null);
    setSelOOS(null);
  }, []);
  const viewSample = useCallback((id) => {
    setSelSample(id);
    setView('detail');
  }, []);
  const editResults = useCallback((id) => {
    setSelSample(id);
    setView('results');
  }, []);
  const viewOOS = useCallback((id) => {
    setSelOOS(id);
    setView('oosDetail');
  }, []);

  // ── Mutations (offline-friendly) ──
  const updateResult = useCallback(
    (sampleId, specId, value) =>
      setSamples((arr) =>
        arr.map((s) => (s.id === sampleId ? { ...s, results: { ...(s.results || {}), [specId]: value } } : s))
      ),
    [setSamples]
  );
  const applyEsig = useCallback(
    (sampleId) => {
      setSamples((arr) => arr.map((s) => (s.id === sampleId ? { ...s, esig: true, status: 'APPROVED' } : s)));
      onToast?.('E-signature applied ✓', 'success');
    },
    [setSamples, onToast]
  );

  const sample = useCallback((id) => data.samples.find((s) => s.id === id || s.sample_id === id), [data.samples]);

  return {
    view, selSample, selOOS, filterStatus, filterType, online,
    samples: data.samples, oos: data.oos, audit: data.audit,
    // Live sprint-screen collections (null → screen uses its bundled seed).
    specs: live.specs, rqs: live.rqs, transports: live.transports,
    capa: live.capa, water: live.water, stability: live.stability,
    setFilterStatus, setFilterType,
    navigate, viewSample, editResults, viewOOS,
    updateResult, applyEsig, sample, loadFromAPI, passCheck,
  };
}

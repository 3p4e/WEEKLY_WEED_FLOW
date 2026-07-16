// HTTP client for the QC_LIMS_Ao FastAPI backend.
//
// In dev, Vite proxies the API prefixes to the backend (see vite.config.js); in
// production the SPA is served same-origin by FastAPI. Either way we use
// relative paths. A bearer token (from /auth/login) is persisted in
// localStorage and attached to every request.
//
// The client is offline-tolerant: callers can fall back to seed data when
// `offline` is thrown, so the app stays fully interactive without a backend.

const TOKEN_KEY = 'gf_token';

let token = localStorage.getItem(TOKEN_KEY) || '';

export function getToken() {
  return token;
}
export function setToken(t) {
  token = t || '';
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}
export function isAuthed() {
  return !!token;
}

async function request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(15000),
  };
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  if (body !== undefined) opts.body = JSON.stringify(body);

  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    const err = new Error('offline');
    err.offline = true;
    throw err;
  }
  if (res.status === 401) {
    setToken('');
    const err = new Error('unauthorized');
    err.status = 401;
    throw err;
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

const qs = (params) => {
  const s = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v != null && v !== '')
  ).toString();
  return s ? `?${s}` : '';
};

export const api = {
  // ── Auth ──
  async login(email, password) {
    const d = await request('POST', '/auth/login', { email, password });
    setToken(d.access_token || d.token || '');
    return d;
  },
  logout() {
    setToken('');
  },
  health: () => request('GET', '/health'),

  // ── Samples ──
  listSamples: (params) => request('GET', '/samples' + qs(params)),
  getSample: (id) => request('GET', `/samples/${id}`),
  receiveSP06: (body) => request('POST', '/samples/receive/sp06', body),
  transferCustody: (id, body) => request('POST', `/samples/${id}/custody/transfer`, body),
  getGenealogy: (id) => request('GET', `/samples/${id}/genealogy`),
  updatePotency: (id, body) => request('POST', `/samples/${id}/potency`, body),

  // ── Specifications ──
  // The list route is "/specifications/" (trailing slash); without it the
  // StaticFiles catch-all shadows the path. Detail is by UUID id.
  listSpecs: (params) => request('GET', '/specifications/' + qs(params)),
  getSpec: (id) => request('GET', `/specifications/${id}`),

  // ── Certificate of Analysis ──
  listCoAs: (params) => request('GET', '/coa' + qs(params)),
  getCoA: (id) => request('GET', `/coa/${id}`),
  signCoA: (id, body) => request('POST', `/coa/${id}/sign`, body),

  // ── OOS investigations ──
  listOOS: (params) => request('GET', '/oos' + qs(params)),
  getOOS: (id) => request('GET', `/oos/${id}`),
  createOOS: (body) => request('POST', '/oos', body),
  updateOOS: (id, body) => request('PATCH', `/oos/${id}`, body),

  // ── Audit trail ──
  listAudit: (params) => request('GET', '/audit' + qs(params)),

  // ── Sprint screens (live data) ──
  listSamplingRequests: (params) => request('GET', '/sampling-requests' + qs(params)),
  listTransport: (params) => request('GET', '/transport' + qs(params)),
  listCAPA: (params) => request('GET', '/capa' + qs(params)),
  listWater: (params) => request('GET', '/water' + qs(params)),
  listStability: (params) => request('GET', '/stability' + qs(params)),

  // ── AI (optional; degrade gracefully) ──
  aiChat: (message) => request('POST', '/ai/chat', { message }),
  aiLabSearch: (query, labData) => request('POST', '/ai/lab-search', { query, lab_data: labData }),

  raw: request,
};

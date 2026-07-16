// Fetch client — same-origin; nginx proxies API path-prefixes to the backend.
const TOKEN = 'wwf_token';
let token = localStorage.getItem(TOKEN) || '';

export const getToken = () => token;
export function setToken(t) {
  token = t || '';
  if (t) localStorage.setItem(TOKEN, t); else localStorage.removeItem(TOKEN);
}

async function req(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const res = await fetch(path, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) { setToken(''); throw Object.assign(new Error('unauthorized'), { status: 401 }); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw Object.assign(new Error(d.detail || 'HTTP ' + res.status), { status: res.status });
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (email, password, remember_device = false) => req('POST', '/auth/login', { email, password, remember_device }),
  me: () => req('GET', '/auth/me'),
  changePassword: (new_password, current_password) => req('POST', '/auth/change-password', { new_password, current_password }),
  weeks: () => req('GET', '/weeks'),
  departments: () => req('GET', '/departments'),
  tasks: (qs = '') => req('GET', '/tasks' + qs),
  task: (id) => req('GET', '/tasks/' + id),
  createTask: (t) => req('POST', '/tasks', t),
  updateTask: (id, patch) => req('PATCH', '/tasks/' + id, patch),
  aiFunctions: () => req('GET', '/ai/functions'),
  aiInvoke: (fn, input) => req('POST', '/ai/' + fn, { input }),
};

// Real backend client — same shape/behavior as the proven web/gf/api.js
// (this exact client has been validated all session against the live
// FastAPI backend). window.GF_API_BASE lets index.html point at a
// different origin for local/dev verification; empty string = same-origin.
window.GF_API = {
  base: window.GF_API_BASE || '',
  token: sessionStorage.getItem('gfnext_token') || '',
  user: JSON.parse(sessionStorage.getItem('gfnext_user') || 'null'),

  _headers() {
    const h = { 'Content-Type': 'application/json' };
    if (this.token) h['Authorization'] = 'Bearer ' + this.token;
    return h;
  },
  async _req(method, path, body) {
    const res = await fetch(this.base + path, {
      method, headers: this._headers(),
      body: body == null ? undefined : JSON.stringify(body),
    });
    if (res.status === 401) {
      this.logout();
      throw new Error('unauthorized');
    }
    if (!res.ok) {
      let detail = '';
      try {
        if ((res.headers.get('content-type') || '').includes('application/json')) {
          const errBody = await res.json();
          detail = (errBody && (errBody.detail || errBody.error)) || '';
        }
      } catch (e) {}
      const err = new Error(detail || ('HTTP ' + res.status + ' ' + path));
      err.status = res.status;
      throw err;
    }
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
  },

  async login(username, password) {
    const data = await this._req('POST', '/auth/login', { email: username, password });
    this.token = data.access_token; this.user = data.user;
    sessionStorage.setItem('gfnext_token', this.token);
    sessionStorage.setItem('gfnext_user', JSON.stringify(this.user));
    return data;
  },
  logout() {
    this.token = ''; this.user = null;
    sessionStorage.removeItem('gfnext_token'); sessionStorage.removeItem('gfnext_user');
  },
  me()          { return this._req('GET', '/auth/me'); },
  directory()   { return this._req('GET', '/auth/directory'); },
  departments() { return this._req('GET', '/departments'); },
  weeks()       { return this._req('GET', '/weeks'); },
  tasks(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/tasks' + (p ? '?' + p : ''));
  },
  getTask(id)           { return this._req('GET', '/tasks/' + id); },
  createTask(t)         { return this._req('POST', '/tasks', t); },
  updateTask(id, patch) { return this._req('PATCH', '/tasks/' + id, patch); },
  addProgress(id, p)    { return this._req('POST', '/tasks/' + id + '/progress', p); },
  assign(taskId, userId, role)  { return this._req('POST', '/tasks/' + taskId + '/assignees', { user_id: userId, role: role || 'assignee' }); },
  unassign(taskId, userId)      { return this._req('DELETE', '/tasks/' + taskId + '/assignees/' + userId); },
  weeklyReport(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/reports/weekly' + (p ? '?' + p : ''));
  },
};

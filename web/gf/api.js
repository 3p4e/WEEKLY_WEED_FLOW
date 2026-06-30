/* api.js — WEEKLY_WEED_FLOW backend client for the GrowFlow UI.
   Same-origin: nginx proxies /auth, /departments, /weeks, /tasks, /ai to the API. */
window.GF = window.GF || {};

GF.API = {
  base: '',                       // same origin (nginx proxies to the backend)
  token: sessionStorage.getItem('wwf_token') || '',
  user: JSON.parse(sessionStorage.getItem('wwf_user') || 'null'),

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
    if (res.status === 401) { GF.API.logout(); throw new Error('unauthorized'); }
    if (!res.ok) throw new Error('HTTP ' + res.status + ' ' + path);
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
  },

  async login(username, password) {
    const data = await this._req('POST', '/auth/login', { email: username, password });
    this.token = data.access_token; this.user = data.user;
    sessionStorage.setItem('wwf_token', this.token);
    sessionStorage.setItem('wwf_user', JSON.stringify(this.user));
    return data;
  },
  logout() {
    this.token = ''; this.user = null;
    sessionStorage.removeItem('wwf_token'); sessionStorage.removeItem('wwf_user');
  },
  changePassword(newPassword, currentPassword) {
    return this._req('POST', '/auth/change-password', { new_password: newPassword, current_password: currentPassword || null });
  },
  me() { return this._req('GET', '/auth/me'); },
  listUsers()      { return this._req('GET', '/auth/users'); },
  createUser(body) { return this._req('POST', '/auth/users', body); },
  deleteUser(id)   { return this._req('DELETE', '/auth/users/' + id); },

  departments() { return this._req('GET', '/departments'); },
  weeks()       { return this._req('GET', '/weeks'); },
  tasks(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/tasks' + (p ? '?' + p : ''));
  },
  createTask(t)        { return this._req('POST', '/tasks', t); },
  updateTask(id, patch){ return this._req('PATCH', '/tasks/' + id, patch); },
  addProgress(id, p)   { return this._req('POST', '/tasks/' + id + '/progress', p); },
  ai(fn, payload)      { return this._req('POST', '/ai/' + fn, payload || {}); },

  audit(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/audit' + (p ? '?' + p : ''));
  },
  auditTables() { return this._req('GET', '/audit/tables'); },
  auditVerify() { return this._req('GET', '/audit/verify'); },

  comments(taskId)          { return this._req('GET',  '/tasks/' + taskId + '/comments'); },
  addComment(taskId, text)  { return this._req('POST', '/tasks/' + taskId + '/comments', { content: text }); },
  assignees(taskId)         { return this._req('GET',  '/tasks/' + taskId + '/assignees'); },
  assign(taskId, userId, role) { return this._req('POST', '/tasks/' + taskId + '/assignees', { user_id: userId, role: role || 'assignee' }); },
  unassign(taskId, userId)  { return this._req('DELETE', '/tasks/' + taskId + '/assignees/' + userId); },
  ack(taskId, accepted, reason) { return this._req('POST', '/tasks/' + taskId + '/ack', { accepted: accepted, reason: reason || null }); },

  weeklyReport(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/reports/weekly' + (p ? '?' + p : ''));
  },
};

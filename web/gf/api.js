/* api.js — WEEKLY_WEED_FLOW backend client for the GrowFlow UI.
   Same-origin: nginx proxies /auth, /departments, /weeks, /tasks, /sessions,
   /ai, /audit, /reports to the API. */
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
    if (res.status === 401) {
      // A failed /auth/login must NOT tear down and rebuild the login card the
      // user is already looking at — showLogin() re-renders the entry splash,
      // detaching the #wwf-login-msg node doLogin captured, so the "Invalid
      // username or password" message was written into a dead element and the
      // user got silently bounced back to the leaf splash with no feedback.
      // doLogin's own catch renders the error on the live card instead.
      const hadSession = !!GF.API.token;
      if (path !== '/auth/login') {
        GF.API.logout();
        // Re-show the login overlay from every call site, not just the 3 that
        // happened to check for it — otherwise an expired/invalidated token
        // mid-session leaves a half-rendered app behind a toast. BUT only when
        // a session actually existed: a stray boot-time 401 with no token
        // means the user is ALREADY at the splash — rebuilding it out from
        // under them resets the reveal and eats whatever they were typing.
        if (hadSession && GF.WWF && GF.WWF.showLogin) GF.WWF.showLogin();
      }
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
      // A session can go from must_change_password=false to true mid-session
      // (e.g. an admin resets it) — route back to the forced-change screen
      // instead of leaving the user stuck behind a toast with no way back.
      if (res.status === 403 && /password change required/i.test(detail) && GF.WWF && GF.WWF.showChangePw) {
        GF.WWF.showChangePw();
      }
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
    sessionStorage.setItem('wwf_token', this.token);
    sessionStorage.setItem('wwf_user', JSON.stringify(this.user));
    return data;
  },
  logout() {
    this.token = ''; this.user = null;
    sessionStorage.removeItem('wwf_token'); sessionStorage.removeItem('wwf_user');
  },
  async changePassword(newPassword, currentPassword) {
    const data = await this._req('POST', '/auth/change-password',
      { new_password: newPassword, current_password: currentPassword || null });
    // The old token is invalidated server-side the instant this succeeds
    // (its pwv claim no longer matches profiles.password_set_at) — adopt
    // the fresh one the response carries, or every call right after this
    // one 401s.
    if (data.access_token) {
      this.token = data.access_token;
      sessionStorage.setItem('wwf_token', this.token);
    }
    return data;
  },
  me() { return this._req('GET', '/auth/me'); },
  directory()      { return this._req('GET', '/auth/directory'); },
  listUsers()      { return this._req('GET', '/auth/users'); },
  createUser(body) { return this._req('POST', '/auth/users', body); },
  updateUser(id, body) { return this._req('PATCH', '/auth/users/' + id, body); },
  resetPassword(id)    { return this._req('POST', '/auth/users/' + id + '/reset-password'); },
  deleteUser(id)   { return this._req('DELETE', '/auth/users/' + id); },
  listDeletedUsers() { return this._req('GET', '/auth/users/deleted'); },
  purgeUser(id)    { return this._req('DELETE', '/auth/users/' + id + '/purge'); },

  departments() { return this._req('GET', '/departments'); },
  weeks()       { return this._req('GET', '/weeks'); },
  tasks(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/tasks' + (p ? '?' + p : ''));
  },
  getTask(id)          { return this._req('GET', '/tasks/' + id); },
  createTask(t)        { return this._req('POST', '/tasks', t); },
  updateTask(id, patch){ return this._req('PATCH', '/tasks/' + id, patch); },
  addProgress(id, p)   { return this._req('POST', '/tasks/' + id + '/progress', p); },
  ai(fn, payload)      { return this._req('POST', '/ai/' + fn, payload || {}); },
  bilingual(body)      { return this._req('POST', '/intake/bilingual', body); },
  aiFunctions()        { return this._req('GET', '/ai/functions'); },
  aiAgents()           { return this._req('GET', '/ai/agents'); },
  aiBindings()         { return this._req('GET', '/ai/bindings'); },
  setAiBinding(fn, b)  { return this._req('PUT', '/ai/bindings/' + fn, b); },
  deleteAiBinding(fn)  { return this._req('DELETE', '/ai/bindings/' + fn); },

  // Work sessions (the overtime engine) + external task links (v2)
  sessions(taskId)         { return this._req('GET',    '/tasks/' + taskId + '/sessions'); },
  addSession(taskId, body) { return this._req('POST',   '/tasks/' + taskId + '/sessions', body); },
  deleteSession(id)        { return this._req('DELETE', '/sessions/' + id); },
  addLink(taskId, body)    { return this._req('POST',   '/tasks/' + taskId + '/links', body); },
  deleteLink(taskId, id)   { return this._req('DELETE', '/tasks/' + taskId + '/links/' + id); },

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

  // Weekly Plan/Report DOCUMENTS: compile -> review -> lock -> PDF
  getDocument(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/reports/documents' + (p ? '?' + p : ''));
  },
  documentStatus(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/reports/documents/status' + (p ? '?' + p : ''));
  },
  compileDocument(body)     { return this._req('POST', '/reports/documents/compile', body); },
  previewDocument(body)     { return this._req('POST', '/reports/documents/preview', body); },
  patchDocument(id, content){ return this._req('PATCH', '/reports/documents/' + id, { content }); },
  patchDocumentSection(id, key, patch) { return this._req('PATCH', '/reports/documents/' + id + '/sections/' + encodeURIComponent(key), patch); },
  lockDocument(id)          { return this._req('POST', '/reports/documents/' + id + '/lock'); },

  weeklyReport(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/reports/weekly' + (p ? '?' + p : ''));
  },
  pins(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/ai/pins' + (p ? '?' + p : ''));
  },
};

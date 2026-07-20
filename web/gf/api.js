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
      const authErr = new Error('unauthorized');
      authErr.status = 401;   // parity with the generic branch (callers key on e.status)
      throw authErr;
    }
    if (!res.ok) {
      let detail = '';
      try {
        if ((res.headers.get('content-type') || '').includes('application/json')) {
          const errBody = await res.json();
          detail = (errBody && (errBody.detail || errBody.error)) || '';
        }
      } catch (e) {}
      // Structured error details (objects — e.g. the DocEngine verify-fail 422
      // carries {verify, error}) ride along on err.detail; the message stays a
      // string so every existing caller keeps working.
      let detailObj = null;
      if (detail && typeof detail === 'object') {
        detailObj = detail;
        detail = detail.error || JSON.stringify(detail);
      }
      // A session can go from must_change_password=false to true mid-session
      // (e.g. an admin resets it) — route back to the forced-change screen
      // instead of leaving the user stuck behind a toast with no way back.
      if (res.status === 403 && /password change required/i.test(detail) && GF.WWF && GF.WWF.showChangePw) {
        GF.WWF.showChangePw();
      }
      const err = new Error(detail || ('HTTP ' + res.status + ' ' + path));
      err.status = res.status;
      if (detailObj) err.detail = detailObj;
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
  notifications(q)     { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/notifications' + (u?'?'+u:'')); },
  notifDigest(window)  { return this._req('GET', '/notifications/digest?window=' + (window || 'daily')); },
  notifUnread()        { return this._req('GET', '/notifications/unread-count'); },
  notifRead(id)        { return this._req('POST', '/notifications/' + id + '/read'); },
  notifReadAll()       { return this._req('POST', '/notifications/read-all'); },
  notifDone(id)        { return this._req('POST', '/notifications/' + id + '/done'); },
  facility()               { return this._req('GET', '/facility'); },
  analytics(weeks = 8)     { return this._req('GET', '/reports/analytics?weeks=' + weeks); },
  auditPrep(programs)      { return this._req('GET', '/reports/audit-prep' + (programs ? '?programs=' + encodeURIComponent(programs) : '')); },
  // qms-api retired platform-wide — its legacy wrappers (qmsStats/qmsDocuments/qmsDocument/qmsHierarchy/qmsFamilies/qmsRagQuery/qmsDownloadUrl) were removed; QMS Studio (DocEngine) below is the successor.
  // QC LIMS — specifications (U1)
  qcSpecs(q)               { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/specifications' + (u?'?'+u:'')); },
  qcSpec(id)               { return this._req('GET', '/qc/specifications/' + id); },
  qcCreateSpec(b)          { return this._req('POST', '/qc/specifications', b); },
  qcPatchSpec(id, b)       { return this._req('PATCH', '/qc/specifications/' + id, b); },
  qcAddSpecParam(id, b)    { return this._req('POST', '/qc/specifications/' + id + '/parameters', b); },
  qcDeleteSpecParam(id, pid){ return this._req('DELETE', '/qc/specifications/' + id + '/parameters/' + pid); },
  // QC LIMS — samples + sampling plans (U2)
  qcSamples(q)             { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/samples' + (u?'?'+u:'')); },
  qcSample(id)             { return this._req('GET', '/qc/samples/' + id); },
  qcCreateSample(b)        { return this._req('POST', '/qc/samples', b); },
  qcPatchSample(id, b)     { return this._req('PATCH', '/qc/samples/' + id, b); },
  qcSamplingPlans(q)       { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/sampling-plans' + (u?'?'+u:'')); },
  qcCreateSamplingPlan(b)  { return this._req('POST', '/qc/sampling-plans', b); },
  // QC LIMS — certificates of analysis + test results (U3)
  qcCoas(q)                { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/certificates' + (u?'?'+u:'')); },
  qcCoa(id)                { return this._req('GET', '/qc/certificates/' + id); },
  qcCreateCoa(b)           { return this._req('POST', '/qc/certificates', b); },
  qcPatchCoa(id, b)        { return this._req('PATCH', '/qc/certificates/' + id, b); },
  qcAddResult(id, b)       { return this._req('POST', '/qc/certificates/' + id + '/results', b); },
  qcGenerateCoq(id)        { return this._req('POST', '/qc/certificates/' + id + '/coq'); },
  qcReviseCoa(id, b)       { return this._req('POST', '/qc/certificates/' + id + '/revise', b); },

  qcOos(q)                 { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/oos' + (u?'?'+u:'')); },
  qcOosOne(id)             { return this._req('GET', '/qc/oos/' + id); },
  qcCreateOos(b)           { return this._req('POST', '/qc/oos', b); },
  qcPatchOos(id, b)        { return this._req('PATCH', '/qc/oos/' + id, b); },
  qcAddOosRegister(id, b)  { return this._req('POST', '/qc/oos/' + id + '/register', b); },
  qcAddOosNotify(id, b)    { return this._req('POST', '/qc/oos/' + id + '/notifications', b); },
  qcAckOosNotify(id, nid)  { return this._req('POST', '/qc/oos/' + id + '/notifications/' + nid + '/ack'); },
  qcCapa(q)                { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/capa' + (u?'?'+u:'')); },
  // eCOA ingestion (Phase 3 U2) — CoA in → grade → promote → certificate
  qcCoaDocs(q)             { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/coa-documents' + (u?'?'+u:'')); },
  qcCoaDoc(id)             { return this._req('GET', '/qc/coa-documents/' + id); },
  qcCreateCoaDoc(b)        { return this._req('POST', '/qc/coa-documents', b); },
  qcPatchCoaDoc(id, b)     { return this._req('PATCH', '/qc/coa-documents/' + id, b); },
  qcSubmitExtractions(id, items) { return this._req('POST', '/qc/coa-documents/' + id + '/extractions', { items }); },
  qcPatchExtraction(id, eid, b)  { return this._req('PATCH', '/qc/coa-documents/' + id + '/extractions/' + eid, b); },
  qcPromoteCoaDoc(id)      { return this._req('POST', '/qc/coa-documents/' + id + '/promote'); },
  qcPlaceholders(q)        { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/coa-placeholders' + (u?'?'+u:'')); },
  qcPatchPlaceholder(id, b){ return this._req('PATCH', '/qc/coa-placeholders/' + id, b); },
  qcVerifyCert(id)         { return this._req('POST', '/qc/certificates/' + id + '/verify'); },
  qcVerifications(id)      { return this._req('GET', '/qc/certificates/' + id + '/verifications'); },
  // Custody cluster (U5) — sampling requests (RQS), field records (SFR), chain of custody
  qcRqs(q)                 { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/sampling-requests' + (u?'?'+u:'')); },
  qcRqsOne(id)             { return this._req('GET', '/qc/sampling-requests/' + id); },
  qcCreateRqs(b)           { return this._req('POST', '/qc/sampling-requests', b); },
  qcPatchRqs(id, b)        { return this._req('PATCH', '/qc/sampling-requests/' + id, b); },
  qcSfr(q)                 { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/field-records' + (u?'?'+u:'')); },
  qcSfrOne(id)             { return this._req('GET', '/qc/field-records/' + id); },
  qcCreateSfr(b)           { return this._req('POST', '/qc/field-records', b); },
  qcPatchSfr(id, b)        { return this._req('PATCH', '/qc/field-records/' + id, b); },
  qcCustody(sampleId)      { return this._req('GET', '/qc/samples/' + sampleId + '/custody'); },
  qcAddCustody(sampleId, b){ return this._req('POST', '/qc/samples/' + sampleId + '/custody', b); },
  // QC leaves (U6) — water / stability / transport
  qcWater(q)               { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/water-tests' + (u?'?'+u:'')); },
  qcCreateWater(b)         { return this._req('POST', '/qc/water-tests', b); },
  qcPatchWater(id, b)      { return this._req('PATCH', '/qc/water-tests/' + id, b); },
  qcStability(q)           { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/stability-studies' + (u?'?'+u:'')); },
  qcCreateStability(b)     { return this._req('POST', '/qc/stability-studies', b); },
  qcPatchStability(id, b)  { return this._req('PATCH', '/qc/stability-studies/' + id, b); },
  qcTransports(q)          { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/transports' + (u?'?'+u:'')); },
  qcCreateTransport(b)     { return this._req('POST', '/qc/transports', b); },
  qcPatchTransport(id, b)  { return this._req('PATCH', '/qc/transports/' + id, b); },
  // CoA RAG Q&A (P3-U4)
  qcCoaChunks(docId)       { return this._req('GET', '/qc/coa-documents/' + docId + '/chunks'); },
  qcIndexCoaChunks(docId, chunks) { return this._req('POST', '/qc/coa-documents/' + docId + '/chunks', { chunks }); },
  qcCoaQa(b)               { return this._req('POST', '/qc/coa-qa', b); },
  // QMS Studio — DocEngine (dedicated Letta-powered document AI)
  studioQuestionnaires()   { return this._req('GET', '/qms/studio/questionnaires'); },
  studioQuestionnaire(key) { return this._req('GET', '/qms/studio/questionnaires/' + encodeURIComponent(key)); },
  studioStartWorkflow(b)   { return this._req('POST', '/qms/studio/workflows', b); },
  studioWorkflow(id)       { return this._req('GET', '/qms/studio/workflows/' + encodeURIComponent(id)); },
  studioDocuments()        { return this._req('GET', '/qms/studio/documents'); },
  studioDocument(did)      { return this._req('GET', '/qms/studio/documents/' + encodeURIComponent(did)); },
  studioBuild(body)        { return this._req('POST', '/qms/studio/build', body); },
  studioDocxUrl(id)        { return '/qms/studio/documents/' + encodeURIComponent(id) + '/download'; },
  studioPdfUrl(id)         { return '/qms/studio/documents/' + encodeURIComponent(id) + '/pdf'; },
  approvalsPending()       { return this._req('GET', '/approvals/pending'); },
  facilityAddRoom(b)       { return this._req('POST', '/facility/rooms', b); },
  facilityPatchRoom(id,b)  { return this._req('PATCH', '/facility/rooms/' + id, b); },
  facilityAddBatch(b)      { return this._req('POST', '/facility/batches', b); },
  facilityPatchBatch(id,b) { return this._req('PATCH', '/facility/batches/' + id, b); },
  activity(q)          { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/activity' + (u?'?'+u:'')); },
  deleteUser(id)   { return this._req('DELETE', '/auth/users/' + id); },
  listDeletedUsers() { return this._req('GET', '/auth/users/deleted'); },
  purgeUser(id)    { return this._req('DELETE', '/auth/users/' + id + '/purge'); },

  departments() { return this._req('GET', '/departments'); },
  createDepartment(b) { return this._req('POST', '/departments', b); },
  weeks()       { return this._req('GET', '/weeks'); },
  tasks(q = {}) {
    const p = new URLSearchParams(q).toString();
    return this._req('GET', '/tasks' + (p ? '?' + p : ''));
  },
  getTask(id)          { return this._req('GET', '/tasks/' + id); },
  taskTree(q = {})     { const p = new URLSearchParams(q).toString(); return this._req('GET', '/tasks/tree' + (p ? '?' + p : '')); },
  createTask(t)        { return this._req('POST', '/tasks', t); },
  updateTask(id, patch){ return this._req('PATCH', '/tasks/' + id, patch); },
  // TMS T1 — dependency graph (blocker edges) + cross-department handoffs
  addDependency(id, dependsOn) { return this._req('POST', '/tasks/' + id + '/dependencies', { depends_on_task_id: dependsOn }); },
  deleteDependency(id, depId)  { return this._req('DELETE', '/tasks/' + id + '/dependencies/' + depId); },
  handoffs(id)                 { return this._req('GET', '/tasks/' + id + '/handoffs'); },
  proposeHandoff(id, toDeptId, note) { return this._req('POST', '/tasks/' + id + '/handoffs', { to_dept_id: toDeptId, note: note || null }); },
  resolveHandoff(handoffId, status)  { return this._req('POST', '/handoffs/' + handoffId + '/resolve', { status }); },
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

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
  // AL() lives in core.js, which loads AFTER this file (index.html's ordered
  // script list). By the time any request can fail it is long since defined —
  // but this file must not assume that, so fall back to English rather than
  // let a ReferenceError replace the error we are trying to report.
  _msg(en, mk) {
    try { return AL(en, mk); } catch (e) { return en; }
  },
  // Without a timeout a hung backend never settles: the await never resolves,
  // the caller's spinner never clears, and the only thing between the user and
  // a permanently stuck screen is GF.once's per-button guard — which blocks a
  // SECOND click, it does not rescue the first one.
  //
  // Both values sit just PAST the matching nginx proxy_read_timeout
  // (web/nginx.conf: 60s general, 180s for /intake and the DocEngine agent
  // routes), never before it. That ordering is the whole point: whichever hop
  // gives up first is the one that writes the error the user sees, and nginx's
  // 504 says something ("the server took too long") that a silent client-side
  // abort cannot. Undercutting the proxy would also cancel slow-but-healthy
  // calls — a large report that nginx would happily have waited out.
  _TIMEOUT_MS: 65000,
  _SLOW_TIMEOUT_MS: 190000,
  // Exactly the paths web/nginx.conf gives its own 180s block — kept in step
  // with that file deliberately, and no wider: /ai is NOT here, because nginx
  // reads it for 60s and its backend timeout is 15s.
  _SLOW_PATHS: /^\/(?:intake\/|qms\/(?:rag-query|studio\/(?:build|workflows\/[^/]+\/(?:chat|revise))))/,

  _timeoutFor(path) {
    return this._SLOW_PATHS.test(path) ? this._SLOW_TIMEOUT_MS : this._TIMEOUT_MS;
  },

  async _req(method, path, body, timeoutMs) {
    // Capture the token THIS request actually sends, before the fetch's
    // await hands control back to the event loop. _headers() reads
    // `this.token` synchronously right here, so `sentToken` is exactly what
    // went out on the wire for this call — even if `this.token` is rotated
    // to a different value while this request is still in flight.
    const sentToken = this.token;
    const ctl = new AbortController();
    const limit = timeoutMs || this._timeoutFor(path);
    const timer = setTimeout(() => ctl.abort(), limit);
    let res;
    try {
      res = await fetch(this.base + path, {
        method, headers: this._headers(),
        body: body == null ? undefined : JSON.stringify(body),
        signal: ctl.signal,
      });
    } catch (e) {
      // Distinguish "we gave up waiting" from "the network refused" — the two
      // need different things from the user, and both used to surface as the
      // same opaque "Failed to fetch".
      const timedOut = e && e.name === 'AbortError';
      const err = new Error(timedOut
        ? GF.API._msg('The server did not respond in time — it may still be working. Try again in a moment.',
                      'Серверот не одговори навреме — можеби сè уште работи. Обидете се повторно за момент.')
        : GF.API._msg('Could not reach the server. Check your connection.',
                      'Не може да се дојде до серверот. Проверете ја врската.'));
      err.status = 0;              // no HTTP status: nothing came back
      err.timeout = !!timedOut;    // callers that want to offer a retry can key on this
      throw err;
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 401) {
      // A failed /auth/login must NOT tear down and rebuild the login card the
      // user is already looking at — showLogin() re-renders the entry splash,
      // detaching the #wwf-login-msg node doLogin captured, so the "Invalid
      // username or password" message was written into a dead element and the
      // user got silently bounced back to the leaf splash with no feedback.
      // doLogin's own catch renders the error on the live card instead.
      if (path !== '/auth/login') {
        // A 401 only means "this session is dead" if the token that was
        // ACTUALLY REJECTED (sentToken) still matches the token GF.API is
        // CURRENTLY using. changePassword() installs a fresh token the
        // instant the server confirms the change, and the server invalidates
        // the OLD token immediately — so a request that was already in
        // flight with that old token (a background poll, say) can 401 AFTER
        // the swap. That is not the current session dying; it is a stale
        // request meeting a token that was legitimately rotated out from
        // under it. Logging out here would undo a successful, intentional
        // credential change, so only tear the session down when nothing has
        // rotated the token since this request was sent.
        if (sentToken === GF.API.token) {
          const hadSession = !!GF.API.token;
          GF.API.logout();
          // Re-show the login overlay from every call site, not just the 3 that
          // happened to check for it — otherwise an expired/invalidated token
          // mid-session leaves a half-rendered app behind a toast. BUT only when
          // a session actually existed: a stray boot-time 401 with no token
          // means the user is ALREADY at the splash — rebuilding it out from
          // under them resets the reveal and eats whatever they were typing.
          if (hadSession && GF.WWF && GF.WWF.showLogin) GF.WWF.showLogin();
        }
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
    // The manual "Log out" button reloads the page right after this (a full
    // reload clears all in-memory state anyway), but an in-tab 401 mid-session
    // does NOT reload — without this, a stale search/department/tag filter
    // from the PREVIOUS user's session would silently carry over into
    // whoever re-logs in on the same tab next.
    if (window.GF && GF.state) {
      GF.state.search = ''; GF.state.deptFilter = null; GF.state.tagFilter = null;
    }
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
  // Param renamed from `window` (shadowed the global `window` for this whole
  // function body — harmless here since nothing in the body needed it, but a
  // trap for the next edit that does).
  notifDigest(win)     { return this._req('GET', '/notifications/digest?window=' + (win || 'daily')); },
  notifUnread()        { return this._req('GET', '/notifications/unread-count'); },
  notifRead(id)        { return this._req('POST', '/notifications/' + id + '/read'); },
  notifReadAll()       { return this._req('POST', '/notifications/read-all'); },
  notifDone(id)        { return this._req('POST', '/notifications/' + id + '/done'); },
  facility()               { return this._req('GET', '/facility'); },

  // ── Cultivation (migration 0045) — cultivar master, coded batches, plants ──
  // A batch is one cultivar in one flowering room (code like GP072501); plant
  // ids are <clone-date>_<cultivar>_<seq>. cultivationGenPlants is CHUNKED and
  // RESUMABLE server-side: call it again to finish an interrupted fill rather
  // than restarting, and never expect it to be instant for a ~2000-plant room.
  cultivars()                    { return this._req('GET',  '/cultivation/cultivars'); },
  cultivarCreate(body)           { return this._req('POST', '/cultivation/cultivars', body); },
  cultivarPatch(id, body)        { return this._req('PATCH','/cultivation/cultivars/' + id, body); },
  cultivationBatches(active = true) {
    return this._req('GET', '/cultivation/batches?active=' + (active ? 'true' : 'false'));
  },
  cultivationBatchCreate(body)   { return this._req('POST', '/cultivation/batches', body); },
  cultivationGenPlants(batchId)  { return this._req('POST', '/cultivation/batches/' + batchId + '/plants'); },
  cultivationPlants(batchId, q = {}) {
    const u = new URLSearchParams(q).toString();
    return this._req('GET', '/cultivation/batches/' + batchId + '/plants' + (u ? '?' + u : ''));
  },
  cultivationMove(batchId, body) { return this._req('POST', '/cultivation/batches/' + batchId + '/move', body); },
  // Phase 3 (migration 0054): every task that carries this batch's id — the
  // auto-generated per-phase set plus any hand-linked via the ordinary task
  // create/PATCH endpoints. Read-only; linking happens on the task side.
  cultivationBatchTasks(batchId) { return this._req('GET', '/cultivation/batches/' + batchId + '/tasks'); },
  // Registering from the product specification: the next batch number for a
  // cultivar (constant head = the cultivar code, tail suggested from what the
  // org already holds). The code field pre-fills it; the tail stays editable.
  cultivationBatchCode(cultivarId) { return this._req('GET', '/cultivation/batch-code?cultivar_id=' + encodeURIComponent(cultivarId)); },
  cultivationBatchPatch(id, b)   { return this._req('PATCH', '/cultivation/batches/' + id, b); },
  // Trichome maturation checks (0066): the documented record behind a harvest
  // date. Never a gate — the harvest form shows the latest verdict, nothing more.
  trichomeChecks(q)              { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/cultivation/trichome-checks' + (u?'?'+u:'')); },
  trichomeCheck(b)               { return this._req('POST', '/cultivation/trichome-checks', b); },
  // Selection campaigns — the S<n> in a mother-plant id, numbered facility-wide.
  campaigns()                    { return this._req('GET', '/cultivation/campaigns'); },
  campaignCreate(b)              { return this._req('POST', '/cultivation/campaigns', b); },
  campaignPatch(id, b)           { return this._req('PATCH', '/cultivation/campaigns/' + id, b); },
  // Propagation (migration 0065, app/api/propagation.py): the mother-plant
  // bank and clone runs — the clone end of cultivation's span. Same
  // /cultivation prefix, separate server module, like harvest and irrigation.
  mothers(active = true)         { return this._req('GET', '/cultivation/mothers?active=' + (active ? 'true' : 'false')); },
  motherNextCode(q)              { const u = new URLSearchParams(q).toString(); return this._req('GET', '/cultivation/mothers/next-code?' + u); },
  motherPotency(id)              { return this._req('GET', '/cultivation/mothers/' + id + '/potency'); },
  motherCreate(body)             { return this._req('POST', '/cultivation/mothers', body); },
  motherPatch(id, body)          { return this._req('PATCH', '/cultivation/mothers/' + id, body); },
  cloneRuns(active = true)       { return this._req('GET', '/cultivation/clone-runs?active=' + (active ? 'true' : 'false')); },
  cloneRunCreate(body)           { return this._req('POST', '/cultivation/clone-runs', body); },
  cloneRunPatch(id, body)        { return this._req('PATCH', '/cultivation/clone-runs/' + id, body); },

  // ── Harvest / yield + IPM applications (migration 0051) ──
  // Same /cultivation prefix, separate server module: a harvest and a spray
  // record carry one interlocking control between them, the PRE-HARVEST
  // INTERVAL. Always call harvestClearance() before offering the cut — it
  // reports what is blocking and the date it clears, so the operator sees the
  // control instead of discovering it as a 409. The server still enforces it;
  // this is the explanation, never the gate.
  //
  // Creating a harvest also writes the qc_batch_genealogy edge
  // `batch code -> lot code` with relation CULTIVATION. That edge is what
  // connects cultivation to the CoA chain, so a lot code must be a brand-new
  // identifier — reusing a batch or processing code is a 409.
  //
  // Overriding a PHI block needs QA authority AND a written reason; a recorder
  // sending phi_override_reason gets a 403, and a blank reason a 422.
  ipmApplications(q = {})        { const u = new URLSearchParams(q).toString(); return this._req('GET', '/cultivation/ipm' + (u ? '?' + u : '')); },
  ipmApply(body)                 { return this._req('POST', '/cultivation/ipm', body); },
  harvestClearance(batchId, on)  { return this._req('GET', '/cultivation/harvest-clearance/' + batchId + (on ? '?on=' + encodeURIComponent(on) : '')); },
  harvests(q = {})               { const u = new URLSearchParams(q).toString(); return this._req('GET', '/cultivation/harvests' + (u ? '?' + u : '')); },
  harvest(id)                    { return this._req('GET',  '/cultivation/harvests/' + id); },
  harvestCreate(body)            { return this._req('POST', '/cultivation/harvests', body); },
  harvestDry(id, body)           { return this._req('POST', '/cultivation/harvests/' + id + '/dry', body); },
  harvestClose(id, body)         { return this._req('POST', '/cultivation/harvests/' + id + '/close', body || {}); },
  harvestYield()                 { return this._req('GET',  '/cultivation/yield'); },
  // Irrigation / feeding (migration 0052) — the last Phase 2 record, room-level
  // and dated, no downstream gate. A third module on the /cultivation prefix.
  irrigation(q = {})             { const u = new URLSearchParams(q).toString(); return this._req('GET', '/cultivation/irrigation' + (u ? '?' + u : '')); },
  irrigationLog(body)            { return this._req('POST', '/cultivation/irrigation', body); },

  // ── Decontamination campaign (migration 0046) ──
  // The 5 steps are ordered and rinse1_whitecloth must PASS before bleach is
  // accepted (a soiled cloth reopens the wash), and release is QA-only against
  // an all-negative swab set — the server rejects violations with 409, so the
  // UI should surface `detail` rather than pre-guessing the rule.
  deconCycles(campaign)          { return this._req('GET',  '/decon/cycles' + (campaign ? '?campaign=' + encodeURIComponent(campaign) : '')); },
  deconCycle(id)                 { return this._req('GET',  '/decon/cycles/' + id); },
  deconCycleCreate(body)         { return this._req('POST', '/decon/cycles', body); },
  deconStep(cycleId, body)       { return this._req('POST', '/decon/cycles/' + cycleId + '/steps', body); },
  deconRelease(cycleId, body)    { return this._req('POST', '/decon/cycles/' + cycleId + '/release', body || {}); },
  deconBleachLog(q = {})         { const u = new URLSearchParams(q).toString(); return this._req('GET', '/decon/bleach-log' + (u ? '?' + u : '')); },
  deconBleachAdd(body)           { return this._req('POST', '/decon/bleach-log', body); },
  deconSwabs(q = {})             { const u = new URLSearchParams(q).toString(); return this._req('GET', '/decon/swabs' + (u ? '?' + u : '')); },
  deconSwabAdd(body)             { return this._req('POST', '/decon/swabs', body); },
  deconSwabResult(id, body)      { return this._req('PATCH','/decon/swabs/' + id + '/result', body); },
  // Corridor cleaning CADENCE (migration 0049), not a plain log: the response
  // carries `interval_minutes`, a derived `overdue` per corridor, and
  // `movements_without_cleaning` — disposed waste manifests with no corridor
  // cleaning recorded after them. Read the flags; do not recompute the interval
  // client-side, or the two copies will disagree about what "overdue" means.
  deconCorridors(campaign)       { return this._req('GET',  '/decon/corridors' + (campaign ? '?campaign=' + encodeURIComponent(campaign) : '')); },
  deconCorridorCleanings(roomId) { return this._req('GET',  '/decon/corridors/' + roomId + '/cleanings'); },
  deconCorridorClean(body)       { return this._req('POST', '/decon/corridors/cleanings', body); },
  // Two real, migration-backed decon routes have no frontend caller at all
  // (product/feature-completeness gap, not a bug — no UI built here):
  //   GET/POST /decon/positive-controls — the frozen positive-controls log
  //   GET/POST /decon/tool-log          — the tool-sterilization PPM log
  // Biosecurity monitoring (migration 0053) — AHU filter, disinfection mat,
  // contact plate/sentinel bioassay, gowning. Second module on /decon.
  biosecurity(q = {})            { const u = new URLSearchParams(q).toString(); return this._req('GET', '/decon/biosecurity' + (u ? '?' + u : '')); },
  biosecurityLog(body)           { return this._req('POST', '/decon/biosecurity', body); },

  // ── Destruction / waste manifests (migration 0048) ──
  // A manifest climbs draft -> sealed -> witnessed -> disposed and each rung is a
  // different person's assertion. Four server gates answer 409 and the UI should
  // surface `detail` rather than restating the rule: an empty manifest cannot be
  // sealed, a sealed one accepts no line changes, the witness must differ from
  // whoever weighed it, and disposal follows witnessing. The per-batch
  // over-declare refusal is a 409 too — declared destruction may never exceed a
  // batch's plant count.
  wasteManifests(q = {})         { const u = new URLSearchParams(q).toString(); return this._req('GET', '/waste/manifests' + (u ? '?' + u : '')); },
  wasteManifest(id)              { return this._req('GET',  '/waste/manifests/' + id); },
  wasteManifestCreate(body)      { return this._req('POST', '/waste/manifests', body); },
  wasteLineAdd(id, body)         { return this._req('POST', '/waste/manifests/' + id + '/lines', body); },
  wasteLineDelete(id, lineId)    { return this._req('DELETE','/waste/manifests/' + id + '/lines/' + lineId); },
  wasteSeal(id, body)            { return this._req('POST', '/waste/manifests/' + id + '/seal', body); },
  wasteWitness(id, body)         { return this._req('POST', '/waste/manifests/' + id + '/witness', body || {}); },
  wasteDispose(id, body)         { return this._req('POST', '/waste/manifests/' + id + '/dispose', body); },
  wasteReconciliation()          { return this._req('GET',  '/waste/reconciliation'); },

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
  // QC LIMS — accredited laboratories (URS Chapter 7)
  qcLabs(q)                { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/laboratories' + (u?'?'+u:'')); },
  qcLab(id)                { return this._req('GET', '/qc/laboratories/' + id); },
  qcCreateLab(b)           { return this._req('POST', '/qc/laboratories', b); },
  qcPatchLab(id, b)        { return this._req('PATCH', '/qc/laboratories/' + id, b); },
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
  qcVoidCoa(id, reason)    { return this._req('POST', '/qc/certificates/' + id + '/void', { reason }); },
  qcTranslationVerified(id){ return this._req('POST', '/qc/certificates/' + id + '/translation-verified'); },
  // QCSOP 012 §6.4 — per-batch Certificate of Quality aggregation (C5)
  qcCoqs(q)                { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/coq' + (u?'?'+u:'')); },
  qcCoqOne(id)             { return this._req('GET', '/qc/coq/' + id); },
  qcCompileCoq(b)          { return this._req('POST', '/qc/coq', b); },
  qcReviewCoq(id)          { return this._req('POST', '/qc/coq/' + id + '/review'); },
  qcVoidCoq(id, reason)    { return this._req('POST', '/qc/coq/' + id + '/void', { reason }); },
  qcRenderCoq(id)          { return this._req('POST', '/qc/coq/' + id + '/render'); },
  // QC potency ladders (PP-QC-SPEC-001 / QCSP 001) + batch commercial identities
  qcPotencySpecs(q)        { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/potency-specs' + (u?'?'+u:'')); },
  qcPotencySpec(id)        { return this._req('GET', '/qc/potency-specs/' + id); },
  qcCreatePotencySpec(b)   { return this._req('POST', '/qc/potency-specs', b); },
  qcApprovePotencySpec(id) { return this._req('POST', '/qc/potency-specs/' + id + '/approve'); },
  qcSupersedePotencySpec(id){ return this._req('POST', '/qc/potency-specs/' + id + '/supersede'); },
  qcImportPotencySpecs(b)  { return this._req('POST', '/qc/potency-specs/import', b || {}); },
  qcPotencyDisposition(q)  { const u = new URLSearchParams(q).toString(); return this._req('GET', '/qc/potency-disposition?' + u); },
  qcSpecDocumentUrl(id, tier) { return '/qc/potency-specs/' + encodeURIComponent(id) + '/document?tier=' + encodeURIComponent(tier); },
  // The official ImB product catalogue (qc_products) — one page per product,
  // window = nominal ±10 %. The ladders above stay readable for CoQs issued
  // before it, but the catalogue is what a batch, a mother and a CoQ now name.
  qcProducts(q)            { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/products' + (u?'?'+u:'')); },
  qcProduct(id)            { return this._req('GET', '/qc/products/' + id); },
  qcProductCreate(b)       { return this._req('POST', '/qc/products', b); },
  qcProductPatch(id, b)    { return this._req('PATCH', '/qc/products/' + id, b); },
  qcApproveProduct(id)     { return this._req('POST', '/qc/products/' + id + '/approve'); },
  qcSupersedeProduct(id)   { return this._req('POST', '/qc/products/' + id + '/supersede'); },
  qcImportProducts(b)      { return this._req('POST', '/qc/products/import', b || {}); },
  qcProductPotency(id)     { return this._req('GET', '/qc/products/' + id + '/potency-history'); },
  qcProductConformance(q)  { const u = new URLSearchParams(q).toString(); return this._req('GET', '/qc/products/conformance?' + u); },
  qcProductDocumentUrl(id) { return '/qc/products/' + encodeURIComponent(id) + '/document'; },
  // GET /qc/certificates/{coa_id}/icoa-html?parameter_id=... (the single-
  // parameter internal-CoA HTML view, spec_html.py) is real and migration-
  // backed but has no frontend caller — sibling gap to the one above.
  qcCommercialIdentities(q){ const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/commercial-identities' + (u?'?'+u:'')); },
  qcImportCommercial()     { return this._req('POST', '/qc/commercial-identities/import'); },
  // PUT/DELETE /qc/commercial-identities/{batch_code} (edit/delete a single
  // commercial identity) is real and migration-backed but has no frontend
  // caller — only list + bulk-import are wired here. Feature-completeness
  // gap, not a bug; out of scope for a Low-severity mechanical fix.
  // QC LIMS — certificate register (QCLB 020 §6.13)
  qcRegister(q)            { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/qc/register' + (u?'?'+u:'')); },
  qcRegisterGaps(year)     { return this._req('GET', '/qc/register/gaps?year=' + encodeURIComponent(year)); },

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
  // External CoA Review Checklist (QCT 018) — QCSOP 012 §6.3.2
  qcChecklist(id)          { return this._req('GET', '/qc/coa-documents/' + id + '/checklist'); },
  qcSaveChecklist(id, b)   { return this._req('PUT', '/qc/coa-documents/' + id + '/checklist', b); },
  qcDecideChecklist(id, b) { return this._req('POST', '/qc/coa-documents/' + id + '/checklist/decide', b); },
  qcVerifyCert(id)         { return this._req('POST', '/qc/certificates/' + id + '/verify'); },
  qcVerifications(id)      { return this._req('GET', '/qc/certificates/' + id + '/verifications'); },
  // Annex 11 electronic signatures (re-authenticated attestation on a certificate)
  qcSign(id, b)            { return this._req('POST', '/qc/certificates/' + id + '/sign', b); },
  qcSignatures(id)         { return this._req('GET', '/qc/certificates/' + id + '/signatures'); },
  // Source-document custody (item 12) — store the original with a SHA-256
  qcUploadOriginal(docId, b) { return this._req('POST', '/qc/coa-documents/' + docId + '/originals', b); },
  qcOriginalDlUrl(fileId)  { return '/qc/document-files/' + encodeURIComponent(fileId) + '/download'; },
  // Workflow sign-off (SUMA v2): submit → approve/reject + QP quality block
  taskWorkflow(id)         { return this._req('GET', '/tasks/' + id + '/workflow'); },
  taskWorkflowAct(id, b)   { return this._req('POST', '/tasks/' + id + '/workflow', b); },
  // Batch genealogy (item 5) — variety→cultivation→processing→packaging, m:n blending
  qcGenealogy(batch)       { return this._req('GET', '/qc/genealogy/' + encodeURIComponent(batch)); },
  qcGenInherited(batch)    { return this._req('GET', '/qc/genealogy/' + encodeURIComponent(batch) + '/inherited-results'); },
  qcGenAddEdge(b)          { return this._req('POST', '/qc/genealogy', b); },
  qcGenDelEdge(id)         { return this._req('DELETE', '/qc/genealogy/' + id); },
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
  studioPresets()          { return this._req('GET', '/qms/studio/presets'); },
  studioChat(id, body)     { return this._req('POST', '/qms/studio/workflows/' + encodeURIComponent(id) + '/chat', body); },
  studioRevise(id, body)   { return this._req('POST', '/qms/studio/workflows/' + encodeURIComponent(id) + '/revise', body); },
  studioDocuments()        { return this._req('GET', '/qms/studio/documents'); },
  studioDocument(did)      { return this._req('GET', '/qms/studio/documents/' + encodeURIComponent(did)); },
  studioBuild(body)        { return this._req('POST', '/qms/studio/build', body); },
  studioDocxUrl(id)        { return '/qms/studio/documents/' + encodeURIComponent(id) + '/download'; },
  studioPdfUrl(id)         { return '/qms/studio/documents/' + encodeURIComponent(id) + '/pdf'; },
  approvalsPending()       { return this._req('GET', '/approvals/pending'); },
  facilityAddRoom(b)       { return this._req('POST', '/facility/rooms', b); },
  facilityPatchRoom(id,b)  { return this._req('PATCH', '/facility/rooms/' + id, b); },
  // The as-built layout register (tasks 0068): the building as the architect
  // drew it, 191 rooms keyed by the code printed on the ground-floor sheet.
  facilityLayout(q)        { const u = new URLSearchParams(q||{}).toString(); return this._req('GET', '/facility/layout' + (u?'?'+u:'')); },
  facilityLayoutRoom(id)   { return this._req('GET', '/facility/layout/' + id); },
  facilityLayoutPatch(id,b){ return this._req('PATCH', '/facility/layout/' + id, b); },
  facilityLayoutImport(b)  { return this._req('POST', '/facility/layout/import', b || {}); },
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

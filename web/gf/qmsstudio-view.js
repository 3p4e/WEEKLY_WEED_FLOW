/* qmsstudio-view.js — QMS Studio: Create (the DocEngine wizard).

   The questionnaire-driven controlled-document pipeline: pick a question
   bank → answer the rounds (every answer PRE-POPULATED, per the canonical
   questionnaire library — the user selects, never types regulation text) →
   document meta → the gf_ agent fleet generates section-by-section with
   regulatory checks → pp-document-suite formatting → hard `RESULT: PASS`
   verify gate → DOCX/PDF download.

   Read = elevated roles; AUTHORING = ADMIN/OWNER/QP/QA_MGR (backend gate is
   authoritative — the UI only mirrors it). Same graceful-unavailable
   contract: no docengine deployed → proxy answers 503 "DocEngine unavailable". */

(function () {
  const AUTHOR_ROLES = ['ADMIN', 'OWNER', 'QP', 'QA_MGR'];
  const canAuthor = () => AUTHOR_ROLES.includes((GF.API.user || {}).role);

  // step: 'pick' | 'answer' | 'meta' | 'running' | 'done' | 'failed'
  GF.WWF._qstu = { step: 'pick', list: null, q: null, qkey: '', answers: {},
                   meta: { title_mk: '', title_en: '', code: '', version: '1.0' },
                   job: null, docs: null, error: null, _poll: null };

  const st = () => GF.WWF._qstu;

  async function loadIndex() {
    const s = st();
    try {
      const [idx, docs] = await Promise.all([
        canAuthor() ? GF.API.studioQuestionnaires() : Promise.resolve({ questionnaires: [] }),
        GF.API.studioDocuments().catch(() => null),
      ]);
      s.list = idx.questionnaires; s.docs = docs ? docs.documents : null; s.error = null;
    } catch (e) { s.error = e.message; }
    if (GF.state.view === 'qmsstudio') GF.render.all();
  }

  GF.WWF.qstuOpen = async (key) => {
    const s = st();
    s.error = null;
    try {
      s.q = await GF.API.studioQuestionnaire(key);
      s.qkey = key; s.answers = {}; s.step = 'answer';
    } catch (e) { s.error = e.message; }
    GF.render.all();
  };

  GF.WWF.qstuPick = (qkey, multi, value) => {
    const s = st();
    if (multi) {
      const cur = s.answers[qkey] || [];
      s.answers[qkey] = cur.includes(value) ? cur.filter(v => v !== value) : [...cur, value];
    } else {
      s.answers[qkey] = s.answers[qkey] === value ? null : value;
    }
    GF.render.all();
  };

  GF.WWF.qstuToMeta = () => { st().step = 'meta'; GF.render.all(); };
  GF.WWF.qstuBack = () => {
    const s = st();
    s.step = s.step === 'meta' ? 'answer' : 'pick';
    GF.render.all();
  };

  GF.WWF.qstuMeta = (k, v) => { st().meta[k] = v; };

  GF.WWF.qstuStart = async () => {
    const s = st();
    const m = s.meta;
    if (!m.title_mk.trim() || !m.title_en.trim() || !m.code.trim()) {
      s.error = AL('Both titles and the document code are required.',
                   'Двата наслови и кодот на документот се задолжителни.');
      GF.render.all(); return;
    }
    s.error = null; s.step = 'running'; s.job = null;
    GF.render.all();
    try {
      const r = await GF.API.studioStartWorkflow({
        questionnaire: s.qkey, answers: s.answers, meta: {
          title_mk: m.title_mk.trim(), title_en: m.title_en.trim(),
          code: m.code.trim(), version: (m.version || '1.0').trim(),
        },
      });
      s.job = { id: r.job_id, status: r.status, stage: '' };
      poll();
    } catch (e) { s.step = 'meta'; s.error = e.message; GF.render.all(); }
  };

  function poll() {
    const s = st();
    if (s._poll) clearTimeout(s._poll);
    s._poll = setTimeout(async () => {
      if (!s.job) return;
      try {
        const j = await GF.API.studioWorkflow(s.job.id);
        s.job = { id: j.id, status: j.status, stage: j.stage, result: j.result, error: j.error };
        if (j.status === 'done') { s.step = 'done'; loadIndex(); }
        else if (j.status === 'failed') { s.step = 'failed'; }
        else poll();
      } catch (e) { poll(); /* transient poll errors: keep trying */ }
      if (GF.state.view === 'qmsstudio') GF.render.all();
    }, 2500);
  }

  GF.WWF.qstuReset = () => {
    const s = st();
    if (s._poll) clearTimeout(s._poll);
    Object.assign(s, { step: 'pick', q: null, qkey: '', answers: {}, job: null, error: null,
                       meta: { title_mk: '', title_en: '', code: '', version: '1.0' } });
    loadIndex(); GF.render.all();
  };

  // ---- rendering ----
  const opt = (qq, o) => {
    const v = typeof o === 'object' ? o.v : o;
    const sel = qq.multi ? (st().answers[qq.key] || []).includes(v)
                         : st().answers[qq.key] === v;
    const def = typeof o === 'object' && o.default;
    return `<span class="chip-opt ${sel ? 'on' : ''}" style="margin:2px"
      onclick="GF.WWF.qstuPick('${qq.key}', ${qq.multi}, '${GF.esc(v).replace(/'/g, '&#39;')}')"
      >${GF.esc(v)}${def && !sel ? ' ✓' : ''}</span>`;
  };

  const answerStep = () => {
    const s = st();
    const rounds = s.q.rounds.map(rnd => `
      <div class="panel ana-panel" style="margin-bottom:10px">
        <div class="ana-h" style="margin-bottom:6px">${GF.esc(AL(rnd.title.en, rnd.title.mk))}</div>
        ${rnd.questions.map(qq => `
          <div style="margin-bottom:8px">
            <div class="ana-note" style="margin:0 0 4px">${GF.esc(AL(qq.label.en, qq.label.mk))}${qq.multi ? ' ·' + AL(' multi', ' повеќе') : ''}</div>
            <div class="chips">${qq.options.map(o => opt(qq, o)).join('')}</div>
          </div>`).join('')}
      </div>`).join('');
    return rounds + `
      <div style="display:flex;gap:8px">
        <button class="btn btn-sm" onclick="GF.WWF.qstuBack()">${GF.t('cancel')}</button>
        <button class="btn btn-primary btn-sm" onclick="GF.WWF.qstuToMeta()">${AL('Continue', 'Продолжи')} →</button>
      </div>
      <div class="ana-note" style="margin-top:8px">${AL(
        'Unanswered questions auto-complete to the most compliant option.',
        'Неодговорените прашања автоматски се пополнуваат со најусогласената опција.')}</div>`;
  };

  const metaStep = () => {
    const s = st(); const m = s.meta;
    const inp = (k, lbl, ph) => `
      <label class="ana-note" style="display:block;margin:8px 0 2px">${lbl}</label>
      <input class="qms-search" style="width:100%" value="${GF.esc(m[k])}" placeholder="${ph}"
        oninput="GF.WWF.qstuMeta('${k}', this.value)">`;
    return `
      <div class="panel ana-panel">
        <div class="ana-h">${AL('Document identity', 'Идентитет на документот')}</div>
        ${inp('title_mk', AL('Title (Macedonian)', 'Наслов (македонски)'), 'СОП за …')}
        ${inp('title_en', AL('Title (English)', 'Наслов (англиски)'), 'SOP for …')}
        ${inp('code', AL('Document code', 'Код на документ'), 'QCSOP-0XX')}
        ${inp('version', AL('Version', 'Верзија'), '1.0')}
      </div>
      ${s.error ? `<div style="color:var(--red-fg,var(--red));margin:8px 0">${GF.esc(s.error)}</div>` : ''}
      <div style="display:flex;gap:8px;margin-top:10px">
        <button class="btn btn-sm" onclick="GF.WWF.qstuBack()">← ${AL('Back', 'Назад')}</button>
        <button class="btn btn-primary btn-sm" onclick="GF.WWF.qstuStart()">${AL('Generate document', 'Генерирај документ')}</button>
      </div>`;
  };

  const runningStep = () => {
    const s = st();
    const stage = (s.job && s.job.stage) || 'queued';
    return `
      <div class="panel ana-panel" style="text-align:center;padding:28px">
        <div class="mw-spin" style="margin:0 auto 12px"></div>
        <div class="ana-h">${AL('The agent fleet is writing…', 'Флотата агенти пишува…')}</div>
        <div class="ana-note mono">${GF.esc(stage)}</div>
        <div class="ana-note">${AL(
          'Sections are generated, checked against the regulatory corpus, audited, then formatted and verified.',
          'Секциите се генерираат, се проверуваат според регулаторниот корпус, се ревидираат, па се форматираат и верификуваат.')}</div>
      </div>`;
  };

  const doneStep = () => {
    const s = st(); const r = (s.job && s.job.result) || {};
    const did = r.document_id;
    const reg = (r.regulatory || []).map(f =>
      `<div class="qms-hit"><div class="qms-hit-b">${GF.esc(String(f).slice(0, 500))}</div></div>`).join('');
    return `
      <div class="panel ana-panel" style="margin-bottom:10px">
        <div class="ana-h" style="color:var(--green)">✓ ${AL('Verified — RESULT: PASS', 'Верификувано — RESULT: PASS')}</div>
        <pre class="mono" style="white-space:pre-wrap;font-size:11px;margin:8px 0">${GF.esc(r.verify || '')}</pre>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${did ? `<a class="btn btn-primary btn-sm" href="#"
                     onclick="return GF.WWF.qstuDl('${did}','docx')">${AL('Download DOCX', 'Преземи DOCX')}</a>
                  <a class="btn btn-sm" href="#" onclick="return GF.WWF.qstuDl('${did}','pdf')">${AL('Download PDF', 'Преземи PDF')}</a>` : ''}
          <button class="btn btn-sm" onclick="GF.WWF.qstuReset()">${AL('New document', 'Нов документ')}</button>
        </div>
      </div>
      ${reg ? `<div class="panel ana-panel"><div class="ana-h">${AL('Regulatory check', 'Регулаторна проверка')}</div>
               <div class="qms-list">${reg}</div></div>` : ''}`;
  };

  // authed binary download: fetch with the bearer header, save via blob URL
  GF.WWF.qstuDl = (did, kind) => {
    const url = kind === 'pdf' ? GF.API.studioPdfUrl(did) : GF.API.studioDocxUrl(did);
    fetch(url, { headers: { Authorization: 'Bearer ' + GF.API.token } })
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.blob(); })
      .then(b => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = did + '.' + kind;
        a.click(); URL.revokeObjectURL(a.href);
      })
      .catch(e => GF.toast && GF.toast(AL('Download failed: ', 'Преземањето не успеа: ') + e.message));
    return false;
  };

  const failedStep = () => {
    const s = st(); const j = s.job || {};
    const verify = j.result && j.result.verify;
    return `
      <div class="panel ana-panel">
        <div class="ana-h" style="color:var(--red-fg,var(--red))">${AL('Generation failed', 'Генерирањето не успеа')}</div>
        <div class="ana-note">${GF.esc(j.error || '')}</div>
        ${verify ? `<pre class="mono" style="white-space:pre-wrap;font-size:11px">${GF.esc(verify)}</pre>
          <div class="ana-note">${AL(
            'The document failed the verification gate and was NOT produced — a failing document is never shipped.',
            'Документот не ја помина верификацијата и НЕ е произведен — документ што паѓа никогаш не се испорачува.')}</div>` : ''}
        <button class="btn btn-sm" style="margin-top:8px" onclick="GF.WWF.qstuReset()">${AL('Start over', 'Одново')}</button>
      </div>`;
  };

  const pickStep = () => {
    const s = st();
    let top;
    if (!canAuthor()) {
      top = `<div class="ana-note">${AL(
        'Document authoring is limited to QA, QP and admins. Generated documents appear below.',
        'Изработката на документи е ограничена на ОК, КвЛ и администратори. Генерираните документи се подолу.')}</div>`;
    } else if (s.error) {
      top = `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(s.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.qstuReset()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    } else if (!s.list) {
      top = `<div class="mw-skel" style="height:64px"></div>`;
    } else {
      top = `<div class="panel ana-panel"><div class="ana-h">${AL('Start from a question bank', 'Почни од банка прашања')}</div>
        <div class="chips" style="margin-top:8px">${s.list.map(q => `
          <span class="chip-opt" onclick="GF.WWF.qstuOpen('${GF.esc(q.key)}')">
            ${GF.esc(AL(q.title.en, q.title.mk))} · ${GF.esc(q.doctype)}</span>`).join('')}
        </div></div>`;
    }
    const docs = s.docs ? `
      <div class="panel ana-panel" style="margin-top:10px">
        <div class="ana-h">${AL('Generated documents', 'Генерирани документи')}</div>
        ${s.docs.length ? s.docs.map(d => `
          <div class="qms-hit"><div class="qms-hit-h">
            <span class="mono qms-code">${GF.esc(d.code)}</span>
            <span class="ana-note" style="margin:0">${GF.esc(d.doctype)} · v${GF.esc(d.version)}</span></div>
            <div class="qms-hit-b">${GF.esc(d.title_mk)} | ${GF.esc(d.title_en)}
              <a href="#" onclick="return GF.WWF.qstuDl('${d.id}','docx')" style="margin-left:8px">DOCX</a>
              <a href="#" onclick="return GF.WWF.qstuDl('${d.id}','pdf')" style="margin-left:4px">PDF</a>
            </div></div>`).join('')
          : `<div class="ana-note">${AL('Nothing generated yet.', 'Сè уште нема генерирано.')}</div>`}
      </div>` : '';
    return top + docs;
  };

  GF.views.qmsstudio = () => {
    const s = st();
    const head = GF.viewHead
      ? GF.viewHead('doc_create', 'doc_create_sub')
      : `<h2>${AL('Create Document', 'Креирај документ')}</h2>`;
    if (s.list === null && s.step === 'pick' && !s.error) loadIndex();
    const body = { pick: pickStep, answer: answerStep, meta: metaStep,
                   running: runningStep, done: doneStep, failed: failedStep }[s.step]();
    return head + body;
  };

  GF.WWF._registerFullPageView({
    key: 'qmsstudio', icon: 'plus',
    label: () => AL('Create', 'Креирај'),
    insertBefore: 'qms-end',   // QMS Studio group (render.js sidebar)
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();

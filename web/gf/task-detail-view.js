/* ============================================================================
   TASK DETAIL — the Mass Weed design's full-screen task "screen"
   ----------------------------------------------------------------------------
   Ports design/mass-weed-mockup/task-detail.html (shared shell) and, for
   Quality-Control tasks, the deeper design/mass-weed-mockup/task-detail-qc.html
   (Lab Testing Lifecycle stepper, OOx deviation flag, CoA/CoQ certificate).

   WIRED TO REAL DATA, not a mock. Every value comes from the live task object
   (GF.task), its children (GF.state.children), and the same lazy endpoints the
   card already uses — comments/assignees via GF.WWF.loadCollab, links/deps via
   GF.WWF.loadExtras, work sessions via GF.API.sessions. Every control invokes
   the real action (GF.setStatus / GF.toggleDone / GF.WWF.setProgress /
   GF.openAdd / GF.API.addComment / GF.WWF.openWorklog).

   The QC lab-lifecycle / deviation / certificate panels are INFORMATIONAL and
   local-only — exactly as the design frames them ("WWF stays informational
   only … it is NOT the SFR record, the Main Lab Register, or the CoA/CoQ …
   reference only — held in the Register, not here"). They explore the QCSOP
   workflow for a QC task; they do not persist QMS state. That is the design's
   own contract, mirrored verbatim.

   Presentation is a full-screen .overlay.as-screen — the same surface the New
   Task create screen uses — so opening a task "forwards" to its screen rather
   than floating a popup.
   ============================================================================ */
(function () {
  if (typeof window === 'undefined' || !window.GF) return;
  GF.WWF = GF.WWF || {};

  const L = (en, mk) => (GF.state && GF.state.lang === 'mk' && mk) ? mk : en;
  const esc = (s) => GF.esc(s == null ? '' : String(s));
  const has = (v) => v != null && String(v).trim() !== '';

  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtDate(s) {
    if (!has(s)) return '';
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s));
    if (!m) return esc(s);
    return MON[+m[2] - 1] + ' ' + (+m[3]);
  }

  // Local, per-open UI state (QC informational sections + async payloads).
  let S = null;

  function isQC(t) { return t && t.dept === 'qc'; }

  // ── tiny render helpers ────────────────────────────────────────────────
  function avSm(id) {
    const p = (GF.PEOPLE && GF.PEOPLE[id]) || null;
    const init = p ? p.init : (has(id) ? String(id).slice(0, 2).toUpperCase() : '—');
    const bg = p ? p.bg : 'var(--mw-cyan-dim)';
    const nm = p ? p.name : (has(id) ? id : '—');
    return `<span class="av-sm" style="background:${esc(bg)}">${esc(init)}</span>${esc(nm)}`;
  }
  function pill(text, color, shadowColor) {
    return `<span class="pill" style="color:${color};box-shadow:inset 0 0 0 1px ${shadowColor || color}">${esc(text)}</span>`;
  }
  function field(labelHtml, valueHtml) {
    return `<div class="field"><span class="fl">${labelHtml}</span><span class="fv">${valueHtml}</span></div>`;
  }
  function recurrenceText(t) {
    const r = t.recurrence;
    if (!r || !r.freq) return L('One-time', 'Еднократно');
    const freq = { daily: L('day', 'ден'), weekly: L('week', 'недела'), monthly: L('month', 'месец') }[r.freq] || r.freq;
    const n = r.interval || 1;
    const base = n > 1 ? L(`Every ${n} ${freq}s`, `На секои ${n} ${freq}`) : L(`Every ${freq}`, `Секој ${freq}`);
    return esc(r.until ? `${base} · ${L('until', 'до')} ${fmtDate(r.until)}` : base);
  }

  // ── header / thead / refrow ────────────────────────────────────────────
  function headerHTML(t) {
    const d = GF.dep(t.dept);
    const metaPills =
      pill(GF.depName(t.dept), esc(d.color), esc(d.color) + '66') +
      pill(GF.taskTypeLabel ? GF.taskTypeLabel(t.type) : t.type, 'var(--mw-cyan)', 'rgba(94,200,240,.3)') +
      pill(GF.prLabel(t.pr), 'var(--mw-stat-lo)', 'rgba(240,90,90,.4)') +
      pill(GF.statusLabel(t.status), esc((GF.STATUS_COLORS && GF.STATUS_COLORS[t.status]) || 'var(--mw-stat-mid)')) +
      (has(t.due) ? `<span class="td-due">${L('Due', 'Рок')} ${fmtDate(t.due)}</span>` : '');
    return `
      <div class="thead">
        <div class="chk ${t.status === 'done' ? 'done' : ''}" id="td-mainchk" title="${L('Toggle done', 'Заврши')}"></div>
        <div>
          <h1>${esc(t.title)}</h1>
          <div class="meta">${metaPills}</div>
        </div>
      </div>`;
  }
  function refrowHTML(t) {
    const chips = [];
    if (has(t.ref)) chips.push(`<span class="mw-attr" style="--mw-acc:${esc(GF.dep(t.dept).color)}">${L('SOP', 'СОП')} <b>${esc(t.ref)}</b></span>`);
    if (has(t.type)) chips.push(`<span class="mw-attr" style="--mw-acc:var(--mw-cyan)">${L('Type', 'Тип')} <b>${esc(GF.taskTypeLabel ? GF.taskTypeLabel(t.type) : t.type)}</b></span>`);
    (t.tags || []).slice(0, 6).forEach(tag => chips.push(`<span class="mw-htag">#${esc(tag)}</span>`));
    return chips.length ? `<div class="refrow">${chips.join('')}</div>` : '';
  }

  // ── left column ────────────────────────────────────────────────────────
  function descHTML(t) {
    const body = has(t.desc) ? esc(t.desc) : `<span style="color:var(--mw-text-faint)">${L('No description.', 'Нема опис.')}</span>`;
    return `<div class="sec"><div class="sec__t">${L('Description', 'Опис')}</div><div class="desc">${body}</div></div>`;
  }

  function subtasksHTML(t) {
    const kids = (GF.state.children && GF.state.children[t.id]) || [];
    const done = kids.filter(k => k.status === 'done').length;
    const rows = kids.length ? kids.map(k => {
      const who = (k.owner && GF.PEOPLE && GF.PEOPLE[k.owner]) ? `<span class="who">${esc(GF.PEOPLE[k.owner].init)}</span>` : '';
      return `<div class="mw-subnode ${k.status === 'done' ? 'done' : ''}">
        <span class="box ${k.status === 'done' ? 'done' : ''}" data-td-sub="${esc(k.id)}"></span>
        <span class="t">${esc(k.title)}</span>${who}</div>`;
    }).join('') : `<div style="font-size:12px;color:var(--mw-text-faint);padding:2px">${L('No subtasks yet.', 'Сè уште нема подзадачи.')}</div>`;
    const pct = kids.length ? Math.round(done / kids.length * 100) : 0;
    const canAdd = GF.can && GF.can('create');
    const add = canAdd ? `<div class="mw-subghost">
        <input class="mw-input" id="td-subadd" placeholder="${L('+ Add subtask…', '+ Додади подзадача…')}" style="padding:8px 12px;font-size:12.5px;max-width:260px">
      </div>` : '';
    return `<div class="sec">
      <div class="sec__t">${L('Subtasks', 'Подзадачи')}<span class="side">· <span>${done}/${kids.length}</span> · ${L('unlimited nesting', 'неограничени нивоа')}</span></div>
      <div id="td-subs">${rows}</div>
      <div class="mw-stat__track subbar"><div class="mw-stat__fill mw-stat__fill--mid" style="width:${pct}%"></div></div>
      ${add}</div>`;
  }

  function attachmentsHTML(t) {
    const x = GF.WWF._extras && GF.WWF._extras[t.id];
    let inner;
    if (!x || !x.loaded) {
      inner = `<div style="font-size:12px;color:var(--mw-text-faint)">${L('Loading…', 'Се вчитува…')}</div>`;
    } else if (x.links && x.links.length) {
      inner = x.links.map(l => `<a class="att" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">
        ${GF.icon('file', 'icon')}<span class="an">${esc(l.label || l.url)}</span><span class="as">${esc(l.kind || '')}</span></a>`).join('');
    } else {
      inner = `<div style="font-size:12px;color:var(--mw-text-faint)">${L('No attachments.', 'Нема прилози.')}</div>`;
    }
    return `<div class="sec"><div class="sec__t">${L('Attachments', 'Прилози')}</div>${inner}</div>`;
  }

  function commentsHTML(t) {
    const c = GF.WWF._collab && GF.WWF._collab[t.id];
    let list;
    if (!c || !c.loaded) {
      list = `<div style="font-size:12px;color:var(--mw-text-faint)">${L('Loading…', 'Се вчитува…')}</div>`;
    } else if (c.comments && c.comments.length) {
      list = c.comments.map(cm => {
        const p = (GF.PEOPLE && GF.PEOPLE[cm.author]) || null;
        const nm = p ? p.name : (cm.author || '—');
        const init = p ? p.init : String(nm).slice(0, 2).toUpperCase();
        const when = GF.WWF._when ? GF.WWF._when(cm.created_at) : (cm.created_at || '');
        return `<div class="cmt"><div class="av">${esc(init)}</div><div class="bd">
          <div class="hd"><span class="nm">${esc(nm)}</span><span class="ts">${esc(when)}</span></div>
          <div class="tx">${esc(cm.content)}</div></div></div>`;
      }).join('');
    } else {
      list = `<div style="font-size:12px;color:var(--mw-text-faint)">${L('No comments yet.', 'Сè уште нема коментари.')}</div>`;
    }
    return `<div class="sec" style="margin-bottom:0">
      <div class="sec__t">${L('Comments', 'Коментари')}</div>
      <div>${list}</div>
      <div class="cbox"><input type="text" id="td-cinput" placeholder="${L('Add a comment…', 'Додади коментар…')}">
        <button class="mw-btn" id="td-csend">${L('Send', 'Испрати')}</button></div></div>`;
  }

  // ── right column ───────────────────────────────────────────────────────
  function sidebarHTML(t) {
    const rows = [];
    rows.push(field(L('Accountable', 'Одговорен'), avSm(t.owner)));
    if ((t.helpers || []).length) {
      rows.push(field(L('Responsible', 'Извршители'), (t.helpers).map(avSm).join('<span style="width:6px"></span>')));
    }
    const c = GF.WWF._collab && GF.WWF._collab[t.id];
    if (c && c.loaded && c.assignees && c.assignees.length) {
      const ack = c.assignees.map(a => {
        const p = (GF.PEOPLE && GF.PEOPLE[a.user_id]) || null;
        const nm = p ? p.name : a.user_id;
        const chip = a.accepted === true ? `<span class="mw-ack mw-ack--accepted">${L('Accepted', 'Прифатено')}</span>`
          : a.accepted === false ? `<span class="mw-ack mw-ack--declined">${L('Declined', 'Одбиено')}</span>`
            : `<span class="mw-ack mw-ack--pending">${L('Pending', 'Во исчекување')}</span>`;
        return `<span style="display:inline-flex;align-items:center;gap:6px">${esc(nm)}${chip}</span>`;
      }).join('<span style="width:8px"></span>');
      rows.push(field(L('Acknowledgement', 'Потврда'), ack));
    }
    const x = GF.WWF._extras && GF.WWF._extras[t.id];
    if (x && x.loaded) {
      if (x.blockedBy && x.blockedBy.length) {
        rows.push(field(L('Depends on', 'Зависи од'), x.blockedBy.map(o =>
          `<span class="mw-dep ${o.status === 'done' ? 'met' : 'unmet'}"><span class="dot"></span>${esc(o.title)}</span>`).join(' ')));
      }
      if (x.blocks && x.blocks.length) {
        rows.push(field(L('Blocks', 'Блокира'), x.blocks.map(o =>
          `<span class="mw-dep ${o.status === 'done' ? 'met' : 'unmet'}"><span class="dot"></span>${esc(o.title)}</span>`).join(' ')));
      }
    }
    rows.push(field(L('Recurrence', 'Повторување'), recurrenceText(t)));
    if (has(t.ref)) rows.push(field(L('SOP ref', 'СОП реф.'),
      `<a class="link" href="#" title="${L('Reference only — no controlled content is hosted here.', 'Само референца — тука не се чува контролирана содржина.')}" onclick="return false">${esc(t.ref)}</a>`));
    if (has(t.est)) rows.push(field(L('Est. time', 'Проц. време'), esc(t.est) + 'h'));
    return `<div class="mw-panel mw-panel--alt" style="margin-bottom:16px">${rows.join('')}</div>`;
  }

  function logProgressHTML(t) {
    const STAT = [
      { st: 'working', en: 'Working', mk: 'Работи', c: 'var(--mw-stat-mid)' },
      { st: 'review', en: 'Review', mk: 'Преглед', c: 'var(--mw-cyan)' },
      { st: 'done', en: 'Done', mk: 'Готово', c: '#2BE8A0' },
    ];
    const STAT2 = [
      { st: 'stuck', en: 'Stuck', mk: 'Блокирано', c: 'var(--mw-stat-lo)' },
      { st: 'postponed', en: 'Postponed', mk: 'Одложено', c: 'var(--mw-stat-mid-2)' },
    ];
    const btn = (s) => `<button data-td-st="${s.st}" class="${t.status === s.st ? 'on' : ''}" style="--st:${s.c}">${L(s.en, s.mk)}</button>`;
    const pct = GF.progress ? GF.progress(t) : (t.progressPct || 0);
    const sess = (S && S.sessLoaded) ? (S.sessions || []) : null;
    let sessList;
    if (sess == null) sessList = `<div style="font-size:12px;color:var(--mw-text-faint)">${L('Loading…', 'Се вчитува…')}</div>`;
    else if (sess.length) sessList = sess.map(x => `<div class="sess"><span class="d">${esc(fmtDate(x.started_at))}</span><span class="h">${esc(x.hours != null ? x.hours : '')}h</span><span class="n">${esc(x.note || (GF.PEOPLE && GF.PEOPLE[x.user_id] && GF.PEOPLE[x.user_id].name) || '—')}</span></div>`).join('');
    else sessList = `<div style="font-size:12px;color:var(--mw-text-faint)">${L('No sessions logged.', 'Нема запишани сесии.')}</div>`;
    const totH = sess ? sess.reduce((a, x) => a + (parseFloat(x.hours) || 0), 0) : (t.sessionHours || 0);
    const canEdit = GF.can && GF.can('status', t);
    return `<div class="mw-panel" style="margin-bottom:16px">
      <div class="sec__t" style="margin-bottom:12px">${L('Log Progress', 'Внеси напредок')}</div>
      <div class="pl-k">${L('Status', 'Статус')}</div>
      <div class="pl-stat" id="td-plstat">${STAT.map(btn).join('')}</div>
      <div class="pl-stat2">${STAT2.map(btn).join('')}</div>
      <div class="pl-row" style="justify-content:space-between;margin-top:14px;margin-bottom:2px">
        <span class="pl-k">${L('Completion', 'Комплетност')}</span><span class="pl-v" id="td-pctv">${pct}%</span></div>
      <input type="range" min="0" max="100" step="5" value="${pct}" class="pl-range" id="td-range" ${canEdit ? '' : 'disabled'}>
      ${canEdit ? `<button class="pl-log" id="td-pctbtn" style="width:100%;margin-bottom:16px">${L('Save completion', 'Зачувај комплетност')}</button>` : '<div style="margin-bottom:16px"></div>'}
      <div class="pl-row" style="justify-content:space-between;margin-bottom:2px">
        <span class="pl-k">${L('Work sessions', 'Работни сесии')}</span><span class="pl-v">${(Math.round(totH * 100) / 100)} H</span></div>
      <div id="td-sesslist" style="margin-bottom:8px">${sessList}</div>
      <button class="pl-log" id="td-logwork" style="width:100%">${GF.icon('clock', 'icon')} ${L('Log work…', 'Запиши работа…')}</button>
    </div>`;
  }

  function activityHTML(t) {
    const notes = (t.notes || []);
    const rows = notes.length ? notes.map(n => {
      const p = (has(n.by) && GF.PEOPLE && GF.PEOPLE[n.by]) ? GF.PEOPLE[n.by] : null;
      const who = p ? `<b>${esc(p.name)}</b> ` : '';
      return `<div class="act"><span class="dot"></span><div><div class="tx">${who}${esc(n.n)}</div><div class="ts">${esc(n.d || '')}</div></div></div>`;
    }).join('') : `<div style="font-size:12px;color:var(--mw-text-faint)">${L('No progress notes yet.', 'Сè уште нема белешки.')}</div>`;
    return `<div class="mw-panel"><div class="sec__t" style="margin-bottom:12px">${L('Activity', 'Активност')}</div>${rows}</div>`;
  }

  // ── QC informational sections (task-detail-qc.html) ────────────────────
  const PHASES = [
    { en: 'Request (RQS)', mk: 'Барање (RQS)' },
    { en: 'Sampling (SFR)', mk: 'Мострирање (SFR)' },
    { en: 'Testing (STR)', mk: 'Тестирање (STR)' },
    { en: 'Results (ARI)', mk: 'Резултати (ARI)' },
    { en: 'Closure', mk: 'Затворање' },
  ];
  const DEV = {
    oos: ['Out-of-Specification — result outside the registered specification limits.', 'Надвор од спецификација — резултат надвор од регистрираните граници.'],
    oot: ['Out-of-Trend — within spec but drifting from the historical trend.', 'Надвор од тренд — во рамки на спец., но отстапува од историскиот тренд.'],
    ooe: ['Out-of-Expectation — within spec but unexpected from process knowledge.', 'Надвор од очекување — во рамки на спец., но неочекувано според познавањето на процесот.'],
    ooc: ['Out-of-Control — a control/system parameter is outside its control limits.', 'Надвор од контрола — контролен/системски параметар надвор од своите граници.'],
  };
  const DEV_CHIPS = [
    { v: 'none', en: 'None', mk: 'Нема', c: 'var(--mw-text-dim)' },
    { v: 'oos', en: 'OOS', mk: 'OOS', c: 'var(--mw-stat-lo)' },
    { v: 'oot', en: 'OOT', mk: 'OOT', c: 'var(--mw-legendary)' },
    { v: 'ooe', en: 'OOE', mk: 'OOE', c: 'var(--mw-stat-mid)' },
    { v: 'ooc', en: 'OOC', mk: 'OOC', c: 'var(--mw-epic)' },
  ];

  function qcStepperHTML(t) {
    const acc = GF.dep(t.dept).color;
    const steps = PHASES.map((p, i) => {
      const cls = i < S.phase ? 'done' : i === S.phase ? 'current' : '';
      return `<div class="mw-step ${cls}" data-td-p="${i}"><span class="mw-step__n">${i + 1}</span><span class="mw-step__t">${L(p.en, p.mk)}</span></div>`;
    }).join('');
    return `<div class="sec">
      <div class="sec__t">${L('Lab Testing Lifecycle', 'Животен циклус на тестирање')}<span class="side">· QCSOP 001 · ${L('reference only', 'само референца')}</span></div>
      <div class="td-stepper" id="td-stepper" style="--mw-acc:${esc(acc)}">${steps}</div>
      <div style="font-size:10px;color:var(--mw-text-faint);margin-top:8px;letter-spacing:.04em">${L('Informational tracker — the controlled record lives in the QC Register, not here.', 'Информативен приказ — контролираниот запис е во КК Регистарот, не тука.')}</div>
    </div>`;
  }
  function qcDeviationHTML() {
    const chips = DEV_CHIPS.map(d =>
      `<button class="mw-chip ${S.dev === d.v ? 'on' : ''}" data-td-dev="${d.v}" style="--cc:${d.c}">${d.v === 'none' ? '' : '<span class="d"></span>'}${L(d.en, d.mk)}</button>`).join('');
    const reveal = (S.dev && S.dev !== 'none') ? `<div class="mw-reveal mw-reveal--warn show" style="margin-top:10px">
      <div style="font-size:12.5px;color:var(--mw-text);line-height:1.55">${L(DEV[S.dev][0], DEV[S.dev][1])}</div>
      <div style="font-size:11px;color:var(--mw-text-faint);margin-top:8px;line-height:1.5">${L('Investigation per QCSOP 019 v2 — report to QC Supervisor ≤ 1 h, secure all preparations. Reference only.', 'Истрага според QCSOP 019 v2 — извести КК Супервизор ≤ 1 ч. Само референца.')}</div></div>` : '';
    return `<div class="sec">
      <div class="sec__t">${L('Deviation flag (OOx)', 'Ознака за отстапување (OOx)')}<span class="side">QCSOP 019 v2</span></div>
      <div class="mw-chips" id="td-dev">${chips}</div>${reveal}</div>`;
  }
  function qcCertHTML() {
    if (S.phase !== 4) return '';
    const types = [['iCoA', 'var(--mw-cyan)'], ['eCoA', 'var(--mw-cyan)'], ['CoQ', '#9B7BE8']];
    const chips = types.map(([v, c]) => `<button class="mw-chip ${S.certType === v ? 'on' : ''}" data-td-ct="${v}" style="--cc:${c}"><span class="d"></span>${v}</button>`).join('');
    const SLA = { iCoA: ['Prepared same working day as the last result', 'Изготвен истиот работен ден'], eCoA: ['Reviewed within 5 working days of receipt', 'Преглед во рок од 5 работни дена'], CoQ: ['Compiled once all source certs are approved/accepted', 'Составен по одобрување на изворните сертификати'] };
    const s = SLA[S.certType];
    return `<div class="mw-reveal mw-reveal--info show sec" style="margin-top:0">
      <div class="sec__t" style="margin-bottom:12px">${L('Certificate — Closure phase', 'Сертификат — фаза Затворање')}<span class="side">QCSOP 012 · ${L('reference only — held in the Register', 'само референца — во Регистарот')}</span></div>
      <div class="pl-k" style="margin-bottom:7px">${L('Type', 'Тип')}</div>
      <div class="mw-chips" id="td-cert">${chips}</div>
      <div style="font-size:10.5px;color:var(--mw-text-faint);margin-top:10px">${L('SLA: ' + s[0], 'Рок: ' + s[1])}</div>
      <div style="font-size:10.5px;color:var(--mw-text-faint);margin-top:6px">${L('Analysed by (Analyst) ▸ Reviewed & approved by (QC Manager)', 'Анализирал (Аналитичар) ▸ Прегледал и одобрил (КК Менаџер)')}</div>
    </div>`;
  }

  // ── full paint ─────────────────────────────────────────────────────────
  function paint() {
    const body = GF.$('td-body');
    if (!body || !S) return;
    const t = GF.task(S.id);
    if (!t) { GF.closeModal('td-modal'); return; }
    const scroller = GF.$('td-modal') || body;   // .overlay.as-screen is the scroll container
    const keep = scroller.scrollTop;

    const crumb = GF.$('td-crumb');
    if (crumb) crumb.innerHTML =
      `<a href="#" onclick="GF.setView('mywork');GF.closeModal('td-modal');return false">${L('Cycle Board', 'Табла')}</a><span>›</span>` +
      `<span>${esc(GF.depName(t.dept))}</span><span>›</span><span>${esc(t.id)}</span>`;

    const qcTop = isQC(t) ? qcStepperHTML(t) + qcCertHTML() : '';
    const leftQC = isQC(t) ? qcDeviationHTML() : '';

    body.innerHTML = `<div class="td-wrap" style="--mw-acc:${esc(GF.dep(t.dept).color)}">
      ${refrowHTML(t)}
      ${headerHTML(t)}
      ${qcTop}
      <div class="cols">
        <div class="mw-panel">
          ${descHTML(t)}
          ${leftQC}
          ${subtasksHTML(t)}
          ${attachmentsHTML(t)}
          ${commentsHTML(t)}
        </div>
        <div>
          ${sidebarHTML(t)}
          ${logProgressHTML(t)}
          ${activityHTML(t)}
        </div>
      </div></div>`;

    wire(t);
    scroller.scrollTop = keep;
  }

  // ── event wiring (re-bound each paint) ─────────────────────────────────
  function wire(t) {
    const on = (id, ev, fn) => { const el = GF.$(id); if (el) el.addEventListener(ev, fn); };

    on('td-mainchk', 'click', () => { if (GF.toggleDone) { GF.toggleDone(t.id); setTimeout(paint, 0); } });

    const plstat = GF.$('td-plstat');
    document.querySelectorAll('#td-plstat [data-td-st], .pl-stat2 [data-td-st]').forEach(b => {
      b.addEventListener('click', () => {
        const st = b.getAttribute('data-td-st');
        if (GF.setStatus) { GF.setStatus(t.id, st); setTimeout(paint, 0); }
      });
    });

    const range = GF.$('td-range'), pctv = GF.$('td-pctv');
    if (range && pctv) range.addEventListener('input', () => { pctv.textContent = range.value + '%'; });
    on('td-pctbtn', 'click', () => {
      const v = range ? parseInt(range.value, 10) : null;
      if (v != null && GF.WWF.setProgress) { GF.WWF.setProgress(t.id, v).then(paint).catch(() => {}); }
    });

    on('td-logwork', 'click', () => { if (GF.WWF.openWorklog) GF.WWF.openWorklog(t.id); });

    // subtasks: toggle done
    document.querySelectorAll('#td-subs [data-td-sub]').forEach(b => {
      b.addEventListener('click', () => {
        const cid = b.getAttribute('data-td-sub');
        if (GF.toggleDone) { GF.toggleDone(cid); setTimeout(paint, 0); }
      });
    });
    // subtasks: add (routes to the real create form, prefilled as subtask)
    const subadd = GF.$('td-subadd');
    if (subadd) subadd.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const v = e.target.value.trim(); if (!v) return;
      if (GF.openAdd) {
        GF.openAdd(t.weekId, t.id);
        const ti = GF.$('add-title'); if (ti) { ti.value = v; ti.focus(); }
      }
    });

    // comments
    const send = () => {
      const inp = GF.$('td-cinput'); if (!inp) return;
      const v = inp.value.trim(); if (!v) return;
      inp.value = '';
      if (!GF.API || !GF.API.addComment) return;
      GF.API.addComment(t.id, v)
        .then(() => GF.WWF.loadCollab ? GF.WWF.loadCollab(t.id) : null)
        .then(paint)
        .catch((err) => GF.toast ? GF.toast((err && err.message) || 'Comment failed', 'error') : null);
    };
    on('td-csend', 'click', send);
    on('td-cinput', 'keydown', (e) => { if (e.key === 'Enter') send(); });

    // QC informational controls (local only)
    document.querySelectorAll('#td-stepper [data-td-p]').forEach(s => {
      s.addEventListener('click', () => { S.phase = parseInt(s.getAttribute('data-td-p'), 10); paint(); });
    });
    document.querySelectorAll('#td-dev [data-td-dev]').forEach(c => {
      c.addEventListener('click', () => { S.dev = c.getAttribute('data-td-dev'); paint(); });
    });
    document.querySelectorAll('#td-cert [data-td-ct]').forEach(c => {
      c.addEventListener('click', () => { S.certType = c.getAttribute('data-td-ct'); paint(); });
    });
  }

  // ── shell + public entry ───────────────────────────────────────────────
  function ensureShell() {
    let el = GF.$('td-modal');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'td-modal';
    el.className = 'overlay as-screen';
    el.innerHTML = `<div class="modal">
      <div class="modal-head td-head">
        <div class="crumb td-crumb" id="td-crumb"></div>
        <div class="td-head__actions">
          <button class="btn btn-sm" id="td-edit">${GF.icon('settings', 'icon')} ${L('Edit', 'Уреди')}</button>
          <button class="btn-ghost" title="${L('Close', 'Затвори')}" onclick="GF.closeModal('td-modal')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button>
        </div>
      </div>
      <div class="modal-body" id="td-body"></div>
    </div>`;
    document.body.appendChild(el);
    return el;
  }

  GF.WWF.openTaskDetail = (id) => {
    const t = GF.task(id);
    if (!t) { if (GF.toast) GF.toast(L('Task not found', 'Задачата не е најдена'), 'error'); return; }
    S = { id, phase: 1, dev: 'none', certType: 'iCoA', certStatus: 'Draft', sessions: null, sessLoaded: false };
    ensureShell();

    const editBtn = GF.$('td-edit');
    if (editBtn) editBtn.onclick = () => { if (GF.WWF.openEdit) GF.WWF.openEdit(id); };

    paint();
    GF.openModal('td-modal');

    // lazy loads — each repaints the relevant panel as it lands, guarded so a
    // stale response (user opened a different task since) never overwrites.
    const stamp = id;
    if (GF.WWF.loadExtras) GF.WWF.loadExtras(id).then(() => { if (S && S.id === stamp) paint(); }).catch(() => {});
    if (GF.WWF.loadCollab) GF.WWF.loadCollab(id).then(() => { if (S && S.id === stamp) paint(); }).catch(() => {});
    if (GF.API && GF.API.sessions) GF.API.sessions(id)
      .then(s => { if (S && S.id === stamp) { S.sessions = s || []; S.sessLoaded = true; paint(); } })
      .catch(() => { if (S && S.id === stamp) { S.sessions = []; S.sessLoaded = true; paint(); } });
  };
})();

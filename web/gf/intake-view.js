/* ══════════════════════════════════════════════════════════════════════
   AI Intake — paste any document (a CEO email with bulk orders + plans, a
   meeting note, a GMP action list). A Letta agent extracts every actionable
   task + subtask across all departments; you review, edit, tick the ones you
   want, and Adopt them into your own account (POST /capture/import). The
   department each task belongs to is kept as its dept tag.

   Same GF.views.<key> + GF.WWF._registerFullPageView pattern as the other
   full-page views. Loads after import-view.js. ═══════════════════════════ */
GF.WWF._intake = { candidates: [], depts: [], filter: '' };

const _INTAKE_PRI = ['critical', 'high', 'medium', 'low'];
const _INTAKE_TYPES = ['capa', 'sop', 'validation', 'document', 'lab', 'meeting', 'admin', 'other'];

GF.views.intake = function () {
  return `<div id="intake-view" style="padding:4px 2px 40px;max-width:900px">
    <h2 style="margin:6px 4px 6px;font-size:19px;font-weight:800;color:var(--ink)">${AL('AI Intake', 'АИ Внес')}</h2>
    <div style="font-size:13px;color:var(--ink-2);margin:0 4px 14px">
      ${AL('Paste an email, plan or note. The AI extracts every task + subtask it finds across all departments — then pick which to adopt into your account.',
           'Залепете е-пошта, план или белешка. АИ ги извлекува сите задачи и подзадачи по сите оддели — потоа изберете кои да ги внесете во вашата сметка.')}
    </div>
    <textarea id="intake-text" spellcheck="false"
      placeholder="${AL('Paste the CEO email / plan text here…', 'Залепете го текстот тука…')}"
      style="width:100%;min-height:200px;font:13px/1.5 var(--font-ui,system-ui);background:var(--surface-2);border:1px solid var(--line);border-radius:11px;padding:12px;color:var(--ink);resize:vertical"></textarea>
    <div style="display:flex;gap:8px;align-items:center;margin-top:10px">
      <button class="btn btn-primary" onclick="GF.WWF.runExtract()">${GF.icon('sparkle')} ${AL('Analyze with AI', 'Анализирај со АИ')}</button>
      <span id="intake-busy" style="display:none;color:var(--ink-3);font-size:13px">${AL('Analyzing…', 'Се анализира…')}</span>
    </div>
    <div id="intake-result" style="margin-top:18px"></div>
  </div>`;
};

GF.WWF.runExtract = async () => {
  const ta = GF.$('intake-text'), out = GF.$('intake-result'), busy = GF.$('intake-busy');
  if (!ta || !out) return;
  const text = (ta.value || '').trim();
  if (text.length < 12) {
    out.innerHTML = `<div style="color:#E5484D;font-size:13px">${AL('Add more text first.', 'Додадете повеќе текст.')}</div>`;
    return;
  }
  busy.style.display = 'inline'; out.innerHTML = '';
  try {
    const r = await GF.API._req('POST', '/intake/extract', { text });
    if (!r.available) {
      const why = r.reason === 'not_configured'
        ? AL('No AI agent is bound for extraction. Ask an admin to bind one in Settings → AI.', 'Нема поврзан АИ агент. Побарајте админ да поврзе во Поставки → АИ.')
        : AL('The AI agent is unreachable right now. Try again shortly.', 'АИ агентот е недостапен. Обидете се повторно.');
      out.innerHTML = `<div style="color:#B45309;font-size:13px">${why}</div>`;
      return;
    }
    const st = GF.WWF._intake;
    st.depts = r.departments || [];
    st.filter = '';
    st.candidates = (r.candidates || []).map((c) => ({ ...c, _include: true }));
    GF.WWF._renderCandidates();
  } catch (e) {
    out.innerHTML = `<div style="color:#E5484D;font-size:13px">${AL('Extraction failed', 'Извлекувањето не успеа')}: ${GF.esc(e.message)}</div>`;
  } finally {
    busy.style.display = 'none';
  }
};

GF.WWF._renderCandidates = () => {
  const out = GF.$('intake-result'); if (!out) return;
  const st = GF.WWF._intake;
  if (!st.candidates.length) {
    out.innerHTML = `<div style="color:var(--ink-3);font-size:13px">${AL('No tasks were extracted from that text.', 'Не се извлечени задачи од тој текст.')}</div>`;
    return;
  }
  const deptOptions = [{ v: '', label: AL('— dept —', '— оддел —') }]
    .concat(st.depts.map((d) => ({ v: d.code, label: d.name })));
  // department filter (QC-only vs all, per the requested review flow)
  const filterOptions = [{ v: '', label: AL('All departments', 'Сите оддели') }]
    .concat(st.depts.map((d) => ({ v: d.code, label: d.name })));
  const priOptions = _INTAKE_PRI.map((x) => ({ v: x, label: GF.prLabel(x) }));
  const typeOptions = _INTAKE_TYPES.map((x) => ({ v: x, label: GF.taskTypeLabel(x) }));

  const cards = st.candidates.map((c, i) => {
    if (st.filter && c.department !== st.filter) return '';
    const subs = (c.subtasks || []).map((s) =>
      `<li style="margin:2px 0"><b>${GF.esc(s.title)}</b>${s.description ? ' — ' + GF.esc(s.description) : ''}</li>`).join('');
    return `<div style="border:1px solid var(--line);border-left:3px solid ${c._include ? 'var(--primary,#2BE8A0)' : 'var(--line)'};border-radius:10px;padding:10px 12px;margin:8px 0;background:var(--surface,#0B1913)">
      <div style="display:flex;align-items:flex-start;gap:10px">
        <input type="checkbox" ${c._include ? 'checked' : ''} onchange="GF.WWF._intakeSet(${i},'_include',this.checked);GF.WWF._renderCandidates()" style="margin-top:5px">
        <div style="flex:1">
          <input value="${GF.esc(c.title)}" oninput="GF.WWF._intakeSet(${i},'title',this.value)"
            style="width:100%;font-size:14px;font-weight:700;border:1px solid transparent;border-radius:6px;padding:3px 5px;background:transparent;color:var(--ink)"
            onfocus="this.style.borderColor='var(--line)'" onblur="this.style.borderColor='transparent'">
          <textarea oninput="GF.WWF._intakeSet(${i},'description',this.value)" rows="2"
            placeholder="${AL('description', 'опис')}"
            style="width:100%;font-size:12.5px;border:1px solid var(--line);border-radius:6px;padding:5px;margin-top:4px;background:var(--surface-2);color:var(--ink);resize:vertical">${GF.esc(c.description || '')}</textarea>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;font-size:12px">
            ${GF.selectField('intake-dept-' + i, { value: c.department || '', inline: true, title: AL('Department', 'Оддел'),
              options: deptOptions, onPick: (v) => GF.WWF._intakeSet(i, 'department', v) })}
            ${GF.selectField('intake-pri-' + i, { value: c.priority || 'medium', inline: true, title: AL('Priority', 'Приоритет'),
              options: priOptions, onPick: (v) => GF.WWF._intakeSet(i, 'priority', v) })}
            ${GF.selectField('intake-type-' + i, { value: c.task_type || 'other', inline: true, title: AL('Type', 'Тип'),
              options: typeOptions, onPick: (v) => GF.WWF._intakeSet(i, 'task_type', v) })}
            ${c.due_date ? `<span style="color:var(--ink-3);align-self:center">${AL('due', 'рок')} ${GF.esc(c.due_date)}</span>` : ''}
          </div>
          ${subs ? `<ul style="margin:8px 0 0 4px;padding-left:16px;font-size:12.5px;color:var(--ink-2)">${subs}</ul>` : ''}
        </div>
      </div>
    </div>`;
  }).join('');

  const nSel = st.candidates.filter((c) => c._include).length;
  out.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px">
      <b style="font-size:14px;color:var(--ink)">${st.candidates.length} ${AL('extracted', 'извлечени')}</b>
      ${GF.selectField('intake-filter', { value: st.filter || '', inline: true, title: AL('All departments', 'Сите оддели'),
        options: filterOptions, onPick: (v) => { GF.WWF._intake.filter = v; GF.WWF._renderCandidates(); } })}
      <div style="flex:1"></div>
      <button class="btn btn-primary" ${nSel ? '' : 'disabled'} onclick="GF.WWF.adoptSelected()">${AL('Adopt selected', 'Внеси избрани')} (${nSel})</button>
    </div>
    ${cards}
    <div id="intake-adopt-result" style="margin-top:12px"></div>`;
};

GF.WWF._intakeSet = (i, key, val) => {
  const c = GF.WWF._intake.candidates[i]; if (c) c[key] = val;
};

GF.WWF.adoptSelected = async () => {
  const st = GF.WWF._intake;
  const chosen = st.candidates.filter((c) => c._include && (c.title || '').trim());
  const out = GF.$('intake-adopt-result');
  if (!chosen.length) return;
  const rid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(36).slice(2));
  const tasks = chosen.map((c) => ({
    external_ref: 'intake:' + rid(),
    title: c.title.trim(),
    description: c.description || null,
    priority: c.priority || 'medium',
    task_type: c.task_type || 'other',
    reference_code: c.reference_code || null,
    department: c.department || null,       // canonical dept code (kept as the tag)
    due_date: c.due_date || null,
    subtasks: (c.subtasks || []).map((s) => ({ title: s.title, description: s.description || null })),
  }));
  if (out) out.innerHTML = `<span style="color:var(--ink-3);font-size:13px">${AL('Adopting…', 'Се внесува…')}</span>`;
  try {
    const r = await GF.API._req('POST', '/capture/import', { session_meta: { source: 'ai_intake' }, tasks });
    const skipped = (r.skipped || []).length;
    if (out) out.innerHTML = `<div style="background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:13px;color:var(--ink)">
      <b>${AL('Adopted', 'Внесени')}:</b> ${r.created} ${AL('created', 'нови')}, ${r.updated} ${AL('updated', 'ажурирани')}${skipped ? `, ${skipped} ${AL('skipped', 'прескокнати')}` : ''}.
    </div>`;
    // Drop the adopted ones from the candidate list so they can't be double-added.
    const takenTitles = new Set(chosen.map((c) => c.title.trim()));
    st.candidates = st.candidates.filter((c) => !(c._include && takenTitles.has((c.title || '').trim())));
    GF.WWF._renderCandidates();
    GF.toast && GF.toast(AL('Tasks adopted into your account', 'Задачите се внесени во вашата сметка'));
    if (GF.WWF.loadAndRender) GF.WWF.loadAndRender();
  } catch (e) {
    if (out) out.innerHTML = `<div style="color:#E5484D;font-size:13px">${AL('Adopt failed', 'Внесувањето не успеа')}: ${GF.esc(e.message)}</div>`;
  }
};

/* nav item just below Import; visible to every signed-in user (the backend
   owner-scopes adoption — you can only create work in your own account). */
GF.WWF._registerFullPageView({
  key: 'intake', icon: 'sparkle', label: () => AL('AI Intake', 'АИ Внес'),
  insertBefore: 'audit',
});

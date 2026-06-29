/* ai.js — AI helpers: Letta backend first, fallback to window.claude.complete.
   Endpoints:
     POST {base}/ai/paraphrase      {user, text}
     POST {base}/ai/parse-voice     {user, transcript, departments, people}
     POST {base}/ai/weekly-summary  {user, kind, week_label, tasks}
     POST {base}/ai/chat            {user, message}
*/
window.GF = window.GF || {};

GF.ai = {
  _user() {
    const u = GF.PEOPLE[GF.state.user] || {};
    return { id: GF.state.user, name: u.name || '', role: u.role || 'operator',
      department: GF.depName(u.dept || ''), lang: GF.state.lang };
  },

  async _post(path, body) {
    const base = GF.state.aiBase;
    if (!base) throw new Error('no-backend');
    const res = await fetch(base.replace(/\/+$/, '') + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async _fallback(prompt) {
    if (typeof window.claude === 'undefined' || !window.claude.complete) throw new Error('No AI available');
    return window.claude.complete(prompt);
  },

  /* Paraphrase a text input field in-place */
  async paraphraseInput(inputId) {
    const el = GF.$(inputId); if (!el || !el.value.trim()) return;
    const orig = el.value.trim();
    GF.toast(GF.t('paraphrase') + '…', 'info');
    try {
      const data = await this._post('/ai/paraphrase', { user: this._user(), text: orig });
      el.value = data.text || orig;
    } catch (e) {
      if (e.message === 'no-backend') {
        try {
          const r = await this._fallback(
            `Rewrite this task note as one clear professional sentence for a GMP cannabis facility. Keep batch/room IDs.\n\n${orig}`);
          el.value = r || orig;
        } catch { GF.toast('AI unavailable', 'error'); }
      } else GF.toast('AI error: ' + e.message, 'error');
    }
  },

  /* Paraphrase a task's description in-place */
  async paraphraseTask(taskId) {
    const t = GF.task(taskId); if (!t || !t.desc) { GF.toast('Nothing to rewrite', 'info'); return; }
    GF.toast(GF.t('paraphrase') + '…', 'info');
    try {
      const data = await this._post('/ai/paraphrase', { user: this._user(), text: t.desc });
      t.desc = data.text || t.desc;
    } catch (e) {
      if (e.message === 'no-backend') {
        try {
          const r = await this._fallback(`Rewrite concisely for GMP cannabis: ${t.desc}`);
          t.desc = r || t.desc;
        } catch { GF.toast('AI unavailable', 'error'); return; }
      } else { GF.toast('AI error', 'error'); return; }
    }
    GF.store.save(); GF.render.panels(); GF.toast('Rewritten ✓', 'success');
  },

  /* Parse voice transcript into structured task fields */
  async parseVoice(transcript) {
    const depts = GF.DEPTS.map(d => GF.state.lang === 'mk' ? d.mk : d.name);
    const people = Object.entries(GF.PEOPLE).map(([, p]) => p.name);
    try {
      return await this._post('/ai/parse-voice', { user: this._user(), transcript, departments: depts, people });
    } catch (e) {
      if (e.message === 'no-backend') {
        try {
          const r = await this._fallback(
            `Parse this spoken task into JSON {title,department,priority,assignee,due,days}. ` +
            `Valid depts: ${depts.join(', ')}. Valid people: ${people.join(', ')}. ` +
            `priority: critical|high|medium|low. Return ONLY JSON.\n\n"${transcript}"`);
          const m = (r || '').match(/\{[\s\S]*\}/);
          return m ? JSON.parse(m[0]) : { title: transcript };
        } catch { return { title: transcript }; }
      }
      return { title: transcript };
    }
  },

  /* Weekly summary or plan analysis */
  async summary(kind) {
    const wk = GF.calendar.weeks[GF.state.selWeek + (kind === 'plan' ? 1 : 0)];
    if (!wk) return;
    const tasks = GF.weekTasks(wk.id).map(t => ({
      title: t.title, dept: t.dept, owner: t.owner, status: t.status, pr: t.pr, days: t.days,
    }));
    GF.$('ai-out').innerHTML = `<div class="ai-loading"><span class="spinner"></span>${GF.t('generate')}…</div>`;
    GF.openModal('ai-modal');
    try {
      const data = await this._post('/ai/weekly-summary', {
        user: this._user(), kind, week_label: `W${wk.weekNum} ${wk.label}`, tasks });
      GF.$('ai-out').innerHTML = `<div class="ai-out">${GF.esc(data.text)}</div>`;
    } catch (e) {
      if (e.message === 'no-backend') {
        try {
          const prompt = kind === 'report'
            ? `Summarise this week's status: completed, in-progress, blockers. Bullet points.\n\n`
            : `Analyse next week's plan: priorities, risks, workload. Bullet points.\n\n`;
          const body = tasks.map(t => `- [${t.status}] ${t.title} (${t.dept}, ${t.owner}, ${t.pr})`).join('\n');
          const r = await this._fallback(prompt + body);
          GF.$('ai-out').innerHTML = `<div class="ai-out">${GF.esc(r)}</div>`;
        } catch { GF.$('ai-out').innerHTML = '<div class="ai-out">AI unavailable — configure the Letta gateway in Settings.</div>'; }
      } else { GF.$('ai-out').innerHTML = `<div class="ai-out">Error: ${GF.esc(e.message)}</div>`; }
    }
  },
};

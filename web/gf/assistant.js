/* assistant.js — unified GrowFlow AI Assistant drawer (Production + QC).
   Replaces the scattered AI buttons with one consistent surface:
   quick actions (deterministic, work offline) + free chat (uses
   window.claude.complete or the configured backend when available). */
window.GF = window.GF || {};

GF.assistant = {
  msgs: [],
  scope: 'prod',
  // Last user this thread belonged to — logging in as someone else must
  // start a fresh thread, never replay the previous session's chat.
  _lastUser: null,

  open(scope) {
    if (this._lastUser !== GF.state.user) { this._lastUser = GF.state.user; this.msgs = []; }
    // `window.APP` has never existed in this build — the truthiness test was
    // always false, so every assistant instance silently fell back to 'prod'
    // and the QC-specific quick actions could never appear for anyone. The
    // real mode lives on GF.state (core.js), same as every other view reads it.
    this.scope = scope || (GF.state && GF.state.view === 'qc' ? 'qc' : 'prod');
    GF.$('assistant-drawer')?.classList.add('open');
    GF.$('assistant-overlay')?.classList.add('open');
    if (!this.msgs.length) this._greet();
    this.render();
    setTimeout(() => GF.$('assistant-input')?.focus(), 120);
  },
  close() {
    GF.$('assistant-drawer')?.classList.remove('open');
    GF.$('assistant-overlay')?.classList.remove('open');
  },

  _greet() {
    const u = (GF.PEOPLE[GF.state.user] || {}).name || '';
    const hi = GF.state.lang === 'mk' ? 'Здраво' : 'Hi';
    this.msgs.push({ role: 'ai', text: `${hi}${u ? ', ' + u.split(' ')[0] : ''}. ${GF.t('ask_anything')}` });
  },

  _actions() {
    if (this.scope === 'qc') return [
      ['week_report', 'forward'], ['flag_risks', 'flag'],
    ];
    return [
      ['draft_task', 'plus'], ['week_report', 'forward'],
      ['flag_risks', 'flag'], ['suggest_handoffs', 'arrowR'],
    ];
  },

  render() {
    const st = this.statusInfo();
    const statusRow = `<div class="asst-status"><span class="dot" style="background:${st.dot}"></span>${GF.esc(st.label)}
      <button class="asst-test" onclick="GF.assistant.test()">${GF.state.lang === 'mk' ? 'Тест' : 'Test'}</button></div>`;
    const acts = this._actions().map(([k, ic]) =>
      `<button class="asst-act" onclick="GF.assistant.action('${k}')">${GF.icon(ic, 'icon', 'var(--orange)')}${GF.t(k)}</button>`).join('');
    const thread = this.msgs.map(m => m.role === 'ai'
      ? `<div class="asst-msg ai">${GF.icon('sparkle', 'icon', 'var(--orange)')}<div class="asst-bubble">${m.html || GF.esc(m.text)}</div></div>`
      : `<div class="asst-msg me"><div class="asst-bubble">${GF.esc(m.text)}</div></div>`).join('');
    GF.$('assistant-body').innerHTML =
      statusRow + `<div class="asst-actions">${acts}</div><div class="asst-thread" id="asst-thread">${thread}</div>`;
    // .asst-thread itself never scrolls (no overflow rule) — the scrollable
    // ancestor is #assistant-body (.asst-body); scrolling the child was a
    // silent no-op that left new messages unrevealed until a manual scroll.
    const body = GF.$('assistant-body'); if (body) body.scrollTop = body.scrollHeight;
  },

  _push(role, text, html) { this.msgs.push({ role, text, html }); this.render(); },

  /* ── Backend resolution ──
     integrate.js (loaded last, always present in the shipped app)
     UNCONDITIONALLY overrides provider()/statusInfo()/complete() below with
     versions that call the real backend `/ai/corpus_qa` catalog entry — see
     integrate.js's `if (GF.assistant) { ... }` block. What remains here is
     only the pre-integrate.js fallback (window.claude, when available),
     exercised solely if integrate.js ever failed to load.
     A 'gateway' branch used to sit here too (selected via GF.state.aiProvider
     === 'gateway' + GF.state.aiBase), calling GF.ai._post()/GF.ai._user() —
     neither function exists anywhere in this codebase (GF.ai only ever grew
     .summary/.paraphraseInput/.paraphraseTask/.bilingual/.parseVoice, all
     from integrate.js), so reaching that branch would have thrown. It never
     could be reached two ways over: integrate.js's override above runs first
     in every real session, AND gf_ai_base/gf_ai_provider are never written by
     any screen in the shipped app (that Settings UI lived only in the
     retired docs/GrowFlow Unified.html prototype, not web/gf/*.js), so
     aiProvider could never actually become 'gateway' even without the
     override. Confirmed dead in docs/AI-FEATURE-INVENTORY-2026-08-23.md
     ("assistant.js itself contains dead-looking logic ... that code never
     runs in production ... The drawer is correctly wired to the real
     system"). Removed rather than implemented: integrate.js's real backend
     path is the one and only supported non-'builtin' backend, so keeping a
     second, broken implementation of the same idea here would just be a
     second place for it to rot. */
  _builtin() { return typeof window.claude !== 'undefined' && !!window.claude.complete; },
  provider() {
    return this._builtin() ? 'builtin' : 'none';
  },
  statusInfo() {
    const p = this.provider();
    if (p === 'builtin') return { dot: 'var(--green)', label: GF.state.lang === 'mk' ? 'Вграден Claude' : 'Built-in Claude', on: true };
    return { dot: 'var(--ink-3)', label: GF.state.lang === 'mk' ? 'Нема AI' : 'No AI connected', on: false };
  },
  async complete(prompt) {
    if (this.provider() === 'builtin') return await window.claude.complete(prompt);
    throw new Error('no-ai');
  },
  async test() {
    this._push('ai', GF.state.lang === 'mk' ? 'Тестирање на врска…' : 'Testing connection…');
    try {
      const r = await this.complete('Reply with exactly: OK');
      const ok = /ok/i.test(r || '');
      GF.toast(ok ? (this.statusInfo().label + ' ✓') : AL('Connected, unexpected reply', 'Поврзано, неочекуван одговор'), ok ? 'success' : 'info');
    } catch (e) {
      GF.toast(e.message === 'no-ai' ? AL('No AI backend available', 'Нема достапен AI сервер')
                                      : AL('AI test failed: ', 'AI тестот не успеа: ') + e.message, 'error');
    }
  },

  /* ── Deterministic quick actions (no backend required) ── */
  action(name) {
    if (name === 'draft_task') {
      this.close();
      GF.openAdd(GF.state.selWeek);
      return;
    }
    const all = GF.weekTasks(GF.state.selWeek);
    if (name === 'week_report') {
      const by = s => all.filter(t => t.status === s).length;
      const rate = all.length ? Math.round(by('done') / all.length * 100) : 0;
      this._push('me', GF.t('week_report'));
      this._push('ai', '', `<b>${rate}% ${GF.t('completion')}</b> · ${all.length} ${GF.t('total')}<br>
        <span style="color:var(--green)">●</span> ${by('done')} ${GF.statusLabel('done')} ·
        <span style="color:var(--orange)">●</span> ${by('working')} ${GF.statusLabel('working')} ·
        <span style="color:var(--blue)">●</span> ${by('review')} ${GF.statusLabel('review')} ·
        <span style="color:var(--red)">●</span> ${by('stuck')} ${GF.statusLabel('stuck')}`);
      this._maybeEnrich('report', all);
    } else if (name === 'flag_risks') {
      const stuck = all.filter(t => t.status === 'stuck');
      const crit = all.filter(t => t.pr === 'critical' && t.status !== 'done');
      this._push('me', GF.t('flag_risks'));
      const rows = [...new Set([...stuck, ...crit])].map(t =>
        `<div class="asst-li"><span class="prtag ${t.pr}">${GF.prLabel(t.pr)}</span> ${GF.esc(t.title)}${t.blocker ? `<div class="asst-sub">⚠ ${GF.esc(t.blocker)}</div>` : ''}</div>`).join('');
      this._push('ai', '', rows || `✅ ${GF.state.lang === 'mk' ? 'Нема ризици' : 'No risks or blockers this week.'}`);
    } else if (name === 'suggest_handoffs') {
      const ready = all.filter(t => t.status === 'done' && GF.HANDOFF[t.dept]);
      this._push('me', GF.t('suggest_handoffs'));
      const rows = ready.map(t =>
        `<div class="asst-li">${GF.esc(GF.depName(t.dept))} ${GF.icon('arrowR', 'icon', 'var(--ink-3)')} ${GF.esc(GF.depName(GF.HANDOFF[t.dept]))}<div class="asst-sub">${GF.esc(t.title)}</div></div>`).join('');
      this._push('ai', '', rows || (GF.state.lang === 'mk' ? 'Нема готови предавања.' : 'No handoffs ready yet.'));
    }
  },

  /* Enrich a deterministic answer with AI prose when a model is reachable */
  async _maybeEnrich(kind, tasks) {
    if (this.provider() === 'none') return;
    try {
      const body = tasks.map(t => `- [${t.status}] ${t.title} (${GF.depName(t.dept)}, ${t.pr})`).join('\n');
      const r = await this.complete(
        `In 2 short sentences, give a production manager the headline for this week. Plain text.\n\n${body}`);
      if (r) this._push('ai', r.trim());
    } catch (e) {}
  },

  /* ── Free chat ── */
  async send() {
    const el = GF.$('assistant-input'); if (!el) return;
    const q = el.value.trim(); if (!q) return;
    el.value = '';
    this._push('me', q);
    this._push('ai', '', `<span class="asst-typing"><span></span><span></span><span></span></span>`);
    const thinking = this.msgs[this.msgs.length - 1];
    try {
      let answer;
      const ctx = this._context();
      if (this.provider() !== 'none') {
        answer = await this.complete(
          `You are GrowFlow's assistant for a GMP cannabis facility (${this.scope === 'qc' ? 'QC laboratory' : 'cultivation & production'}). ` +
          `Answer in ${GF.state.lang === 'mk' ? 'Macedonian' : 'English'}, concise and practical.\n\nContext:\n${ctx}\n\nQuestion: ${q}`);
      } else {
        answer = GF.state.lang === 'mk'
          ? 'Поврзете AI во Поставки за разговор. Брзите дејства работат и без него.'
          : 'Connect an AI backend in Settings for chat. The quick actions above work offline.';
      }
      thinking.html = null; thinking.text = answer || '—';
    } catch (e) {
      thinking.html = null;
      thinking.text = e.message === 'no-ai'
        ? AL('No AI backend available.', 'Нема достапен AI сервер.')
        : AL('AI error: ', 'AI грешка: ') + e.message;
    }
    this.render();
  },

  _context() {
    const all = GF.weekTasks(GF.state.selWeek);
    const wk = GF.calendar.weeks[GF.state.selWeek];
    return `Week ${wk.weekNum} (${wk.label}). ${all.length} tasks. ` +
      all.slice(0, 12).map(t => `${t.title} [${t.status}, ${GF.depName(t.dept)}]`).join('; ');
  },
};

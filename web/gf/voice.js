/* voice.js — Web Speech API dictation + voice capture modal for task creation. */
window.GF = window.GF || {};

GF.voice = {
  _rec: null,

  /* Inline dictation into an input field (mic toggle) */
  dictate(inputId) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { GF.toast(AL('Speech recognition not supported in this browser', 'Препознавањето говор не е поддржано во овој прелистувач'), 'error'); return; }
    if (this._rec) { this._rec.stop(); this._rec = null; this._setMicUI(inputId, false); return; }

    const lang = GF.state.lang === 'mk' ? 'mk-MK' : 'en-US';
    const rec = new SR();
    rec.continuous = true; rec.interimResults = true; rec.lang = lang;
    let final = '';
    rec.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript + ' ';
        else interim += e.results[i][0].transcript;
      }
      const el = GF.$(inputId); if (el) el.value = (final + interim).trim();
    };
    rec.onerror = (e) => { if (e.error !== 'aborted') GF.toast(AL('Mic error: ', 'Грешка со микрофон: ') + e.error, 'error'); };
    rec.onend = () => { this._rec = null; this._setMicUI(inputId, false); };
    rec.start(); this._rec = rec;
    this._setMicUI(inputId, true);
    GF.toast(GF.t('listening'), 'info');
  },

  _setMicUI(inputId, live) {
    const btn = GF.$('mic-' + inputId);
    if (btn) { btn.classList.toggle('rec', live); btn.innerHTML = GF.icon('mic'); }
  },

  /* Full voice capture modal (big mic, transcript, AI parsed fields, create) */
  _modalRec: null, _transcript: '', _parsed: null,

  openCapture(weekId) {
    GF.voice._transcript = ''; GF.voice._parsed = null;
    GF.voice._weekId = weekId || GF.state.selWeek;
    GF.openModal('voice-modal');
    this._renderCapture();
  },

  _renderCapture() {
    const t = this._transcript, p = this._parsed, live = !!this._modalRec;
    const wave = [10, 22, 38, 26, 48, 64, 40, 72, 30, 54, 84, 46, 68, 34, 58, 24, 44, 30, 18, 40, 60, 36, 50, 26, 14];
    const sheet = p ? `
      <div class="sec-label" style="color:var(--ink-3)">${GF.icon('sparkle','icon','var(--orange)')}${GF.t('auto_detected')}</div>
      <div class="parsed-grid">
        <div class="parsed-cell"><div class="pl">${GF.icon('grid','icon')}${GF.t('dept_label')}</div><div class="pv" style="color:var(--blue)">${GF.esc(p.department || '—')}</div></div>
        <div class="parsed-cell"><div class="pl">${GF.icon('flag','icon')}${GF.t('priority')}</div><div class="pv" style="color:var(--orange)">${GF.esc(p.priority || '—')}</div></div>
        <div class="parsed-cell"><div class="pl">${GF.icon('user','icon')}${GF.t('assignee')}</div><div class="pv" style="color:var(--blue)">${GF.esc(p.assignee || '—')}</div></div>
        <div class="parsed-cell"><div class="pl">${GF.icon('clock','icon')}${GF.t('due')}</div><div class="pv">${GF.esc(p.due || '—')}</div></div>
      </div>
      <div class="row" style="gap:10px">
        <button class="btn" style="flex:1;justify-content:center" onclick="GF.voice._parsed=null;GF.voice._renderCapture()">${GF.t('edit')}</button>
        <button class="btn btn-orange" style="flex:2;justify-content:center" onclick="GF.voice.createFromVoice()">${GF.icon('check','icon','#fff')}${GF.t('create_task')}</button>
      </div>` : `
      <div class="row" style="gap:10px">
        <button class="btn" style="flex:1;justify-content:center" onclick="GF.closeModal('voice-modal')">${GF.t('cancel')}</button>
        <button class="btn btn-orange" style="flex:2;justify-content:center" onclick="GF.voice.parseCapture()" ${!t ? 'disabled' : ''}>${GF.icon('sparkle','icon','#fff')}${GF.t('create_task')}</button>
      </div>`;

    GF.$('voice-content').innerHTML = `
      <div class="mic-stage">
        <div style="display:flex;gap:2px;background:rgba(255,255,255,.1);border-radius:9px;padding:3px;font-size:12px;font-weight:700">
          <span style="padding:5px 11px;border-radius:7px;${GF.state.lang==='en'?'background:var(--blue);color:#fff':'color:rgba(255,255,255,.6)'};cursor:pointer" onclick="GF.setLang('en');GF.voice._renderCapture()">EN</span>
          <span style="padding:5px 11px;border-radius:7px;${GF.state.lang==='mk'?'background:var(--blue);color:#fff':'color:rgba(255,255,255,.6)'};cursor:pointer" onclick="GF.setLang('mk');GF.voice._renderCapture()">МК</span>
        </div>
        <div style="font-size:11px;font-weight:700;letter-spacing:.4px;color:rgba(255,255,255,.55);text-transform:uppercase">${live ? GF.t('listening') : GF.t('speak_task')}</div>
        <div class="mic-rings">
          <div class="ring r1"></div><div class="ring r2"></div>
          <button class="mic-core ${live ? 'live' : ''}" onclick="GF.voice.toggleCaptureMic()">${GF.icon('mic','icon','#fff')}</button>
        </div>
        <div class="wave">${wave.map((h, i) => `<span style="height:${live ? h : 8}px;${!live ? 'opacity:.3' : i > 16 ? 'opacity:.35' : ''}"></span>`).join('')}</div>
      </div>
      <div class="transcript-sheet">
        <div class="transcript">${t ? GF.esc(t) : `<span class="ph">${GF.t('voice_hint')}</span>`}</div>
        ${sheet}
      </div>`;
  },

  toggleCaptureMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { GF.toast(AL('Speech recognition not supported in this browser', 'Препознавањето говор не е поддржано во овој прелистувач'), 'error'); return; }
    if (this._modalRec) { this._modalRec.stop(); this._modalRec = null; this._renderCapture(); return; }
    const lang = GF.state.lang === 'mk' ? 'mk-MK' : 'en-US';
    const rec = new SR(); rec.continuous = true; rec.interimResults = true; rec.lang = lang;
    let final = '';
    rec.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript + ' ';
        else interim += e.results[i][0].transcript;
      }
      this._transcript = (final + interim).trim();
      this._renderCapture();
    };
    rec.onerror = () => {};
    rec.onend = () => { this._modalRec = null; this._renderCapture(); };
    rec.start(); this._modalRec = rec; this._renderCapture();
  },

  async parseCapture() {
    if (!this._transcript) return;
    GF.toast(GF.t('auto_detected') + '…', 'info');
    this._parsed = await GF.ai.parseVoice(this._transcript);
    this._renderCapture();
  },

  // createFromVoice() is defined by integrate.js (loaded last), which
  // persists through the real API instead of local-only state.
};

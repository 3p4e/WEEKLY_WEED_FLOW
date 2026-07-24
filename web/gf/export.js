/* export.js — CSV / JSON raw exports + rollover. The old window.print() PDF
   was removed: presentable A4 bilingual PDFs are produced by the Document
   Engine (Report → Documents), server-rendered via WeasyPrint. */
window.GF = window.GF || {};

GF.export = {
  open(kind) {
    GF.export._kind = kind;
    GF.openModal('export-modal');
    GF.$('export-title').textContent = GF.t('export') + ' — ' + (kind === 'report' ? GF.t('report') : GF.t('plan'));
    const hint = GF.$('export-pdf-hint');
    if (hint) hint.textContent = AL('PDF reports live in Report → Documents',
                                    'PDF извештаите се во Извештај → Документи');
    const csvL = GF.$('export-csv-label');
    if (csvL) csvL.textContent = AL('Export CSV', 'Извези CSV');
    const jsonL = GF.$('export-json-label');
    if (jsonL) jsonL.textContent = AL('Export JSON', 'Извези JSON');
  },

  // Jump from the export modal to the real PDF (Document Engine in the Report view).
  goToDocuments() {
    GF.closeModal('export-modal');
    GF.setView('report');
  },

  run(fmt) {
    GF.closeModal('export-modal');
    const kind = this._kind || 'report';
    const weekId = kind === 'plan' ? GF.state.selWeek + 1 : GF.state.selWeek;
    const w = GF.calendar.weeks[weekId]; if (!w) return;
    const tasks = GF.weekTasks(weekId);
    const u = GF.PEOPLE[GF.state.user];
    const base = `GrowFlow_${kind}_W${w.weekNum}_${GF.state.user}`;

    if (fmt === 'csv') this._csv(base, w, tasks, u);
    if (fmt === 'json') this._json(base, w, tasks, u);
    GF.toast(fmt.toUpperCase() + AL(' exported', ' е извезен'), 'success');
  },

  _download(content, name, mime) {
    const blob = new Blob([content], { type: mime });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  },

  _csv(base, w, tasks, u) {
    // Spreadsheet apps (Excel/Sheets) treat a leading =+-@ as a formula \u2014
    // prefix with a quote to neutralize it before quoting the field, or a
    // task title becomes an arbitrary-formula injection vector on export.
    const esc = s => {
      let v = String(s || '');
      if (/^[=+\-@]/.test(v)) v = "'" + v;
      return '"' + v.replace(/"/g, '""') + '"';
    };
    let csv = '\uFEFF';
    csv += `${esc('GrowFlow Export')},${esc('W' + w.weekNum)},${esc(w.label)},${esc(new Date().toLocaleDateString())}\n`;
    csv += `${esc('User')},${esc(u.name)},${esc(u.roleLabel)}\n\n`;
    csv += 'ID,Title,Department,Status,Priority,Type,Reference,Due Date,Tags,Archived,Days,Owner,Progress Notes\n';
    tasks.forEach(t => {
      const d = GF.dep(t.dept);
      const notes = (t.notes || []).map(n => `${n.d}: ${n.n}`).join(' | ');
      csv += `${esc(t.id)},${esc(t.title)},${esc(d.name)},${t.status},${t.pr},${esc(t.type || '')},${esc(t.ref || '')},${esc(t.due || '')},${esc((t.tags||[]).join(', '))},${t.archived ? 'Y' : 'N'},${esc((t.days||[]).join(','))},${esc(GF.PEOPLE[t.owner]?.name)},${esc(notes)}\n`;
    });
    this._download(csv, base + '.csv', 'text/csv');
  },

  _json(base, w, tasks, u) {
    const done = tasks.filter(t => t.status === 'done').length;
    const payload = {
      version: '1.0', date: new Date().toISOString(),
      user: { name: u.name, role: u.roleLabel },
      week: { num: w.weekNum, label: w.label },
      telemetry: { total: tasks.length, done, rate: tasks.length ? Math.round(done / tasks.length * 100) : 0 },
      tasks: tasks.map(t => ({
        id: t.id, title: t.title, dept: t.dept, status: t.status, pr: t.pr,
        type: t.type, ref: t.ref, due: t.due, tags: t.tags, archived: t.archived,
        days: t.days, owner: t.owner, notes: t.notes, deps: t.deps,
      })),
    };
    this._download(JSON.stringify(payload, null, 2), base + '.json', 'application/json');
  },

};

// ── Rollover ──
GF.rollover = () => {
  const weekId = GF.state.selWeek;
  const nextId = weekId + 1;
  const incomplete = GF.weekTasks(weekId).filter(t => t.status !== 'done');
  if (!incomplete.length) { GF.toast(AL('All tasks are done — nothing to roll over', 'Сите задачи се завршени — нема што да се пренесе'), 'info'); return; }
  incomplete.forEach(t => { t.weekId = nextId; });
  GF.store.save(); GF.render.all();
  GF.toast(AL(`${incomplete.length} task(s) rolled to next week`, `${incomplete.length} задача(и) пренесени во следната недела`), 'success');
};

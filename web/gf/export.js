/* export.js — CSV / JSON / PDF export + rollover. */
window.GF = window.GF || {};

GF.export = {
  open(kind) {
    GF.export._kind = kind;
    GF.openModal('export-modal');
    GF.$('export-title').textContent = GF.t('export') + ' — ' + (kind === 'report' ? GF.t('report') : GF.t('plan'));
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
    if (fmt === 'pdf') this._pdf(base, w, tasks, u, kind);
    GF.toast(`${fmt.toUpperCase()} exported`, 'success');
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
    csv += 'ID,Title,Department,Status,Priority,Days,Owner,Progress Notes\n';
    tasks.forEach(t => {
      const d = GF.dep(t.dept);
      const notes = (t.notes || []).map(n => `${n.d}: ${n.n}`).join(' | ');
      csv += `${t.id},${esc(t.title)},${esc(d.name)},${t.status},${t.pr},${esc((t.days||[]).join(','))},${esc(GF.PEOPLE[t.owner]?.name)},${esc(notes)}\n`;
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
        days: t.days, owner: t.owner, notes: t.notes, deps: t.deps,
      })),
    };
    this._download(JSON.stringify(payload, null, 2), base + '.json', 'application/json');
  },

  _pdf(base, w, tasks, u, kind) {
    const isR = kind === 'report';
    const accent = isR ? '#2F6BFF' : '#FF7A1A';
    const done = tasks.filter(t => t.status === 'done').length;
    const rate = tasks.length ? Math.round(done / tasks.length * 100) : 0;
    const stuck = tasks.filter(t => t.status === 'stuck').length;
    const statusColor = { done: '#15A86B', working: '#FF7A1A', review: '#2F6BFF', stuck: '#E5484D', postponed: '#F6A609', pending: '#8A99B0' };

    let html = `<!doctype html><html><head><meta charset="utf-8"><title>${base}</title>
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&display=swap" rel="stylesheet">
    <style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Manrope',sans-serif;padding:28px 36px;font-size:12px;color:#16233B;line-height:1.5}@media print{body{padding:14px}@page{margin:14mm}}</style>
    </head><body>
    <div style="background:linear-gradient(135deg,${accent},${isR?'#1E4FD6':'#E2640A'});color:#fff;padding:20px 24px;border-radius:14px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:22px;font-weight:800;letter-spacing:-.5px">GrowFlow ${isR ? 'Weekly Report' : 'Weekly Plan'}</div>
      <div style="font-size:12px;opacity:.8;margin-top:3px">Week ${w.weekNum} — ${w.label}</div></div>
      <div style="text-align:right;font-size:11px;opacity:.85"><div style="font-weight:700">${GF.esc(u.name)}</div><div>${GF.esc(u.roleLabel)}</div></div>
    </div>
    <div style="display:flex;gap:12px;margin-bottom:20px">
      <div style="flex:1;background:#F0F5FF;border:1px solid #E2E8F1;border-radius:12px;padding:14px;text-align:center">
        <div style="font-size:28px;font-weight:800;color:${accent}">${tasks.length}</div><div style="font-size:10px;font-weight:700;color:#566884">TOTAL</div></div>
      <div style="flex:1;background:#DDF4EA;border:1px solid #E2E8F1;border-radius:12px;padding:14px;text-align:center">
        <div style="font-size:28px;font-weight:800;color:#15A86B">${rate}%</div><div style="font-size:10px;font-weight:700;color:#566884">DONE</div></div>
      <div style="flex:1;background:#FBE3E4;border:1px solid #E2E8F1;border-radius:12px;padding:14px;text-align:center">
        <div style="font-size:28px;font-weight:800;color:#E5484D">${stuck}</div><div style="font-size:10px;font-weight:700;color:#566884">STUCK</div></div>
    </div>`;

    tasks.forEach(t => {
      const sc = statusColor[t.status] || '#8A99B0';
      html += `<div style="border-left:4px solid ${sc};padding:8px 14px;margin-bottom:10px;border-radius:0 10px 10px 0;background:#F6F8FC">
        <div style="display:flex;align-items:center;gap:8px"><span style="font-weight:800;font-size:13px">${GF.esc(t.title)}</span>
        <span style="font-size:10px;font-weight:700;color:${sc};text-transform:uppercase">${t.status}</span></div>
        <div style="font-size:10px;color:#566884;margin-top:2px">${[t.id, GF.dep(t.dept).name].filter(Boolean).join(' · ')}</div>
        ${(t.notes || []).map(n => `<div style="font-size:10px;color:#16233B;margin-top:4px;padding-left:8px;border-left:2px solid #E2E8F1"><b>${n.d}:</b> ${GF.esc(n.n)}</div>`).join('')}
      </div>`;
    });

    html += `<div style="margin-top:24px;padding-top:8px;border-top:1px solid #E2E8F1;font-size:9px;color:#8A99B0;display:flex;justify-content:space-between">
      <span>GrowFlow · Medical Cannabis Production</span><span>${new Date().toLocaleDateString()}</span></div></body></html>`;
    const win = window.open('', '_blank');
    win.document.write(html); win.document.close();
    setTimeout(() => win.print(), 500);
  },
};

// ── Rollover ──
GF.rollover = () => {
  const weekId = GF.state.selWeek;
  const nextId = weekId + 1;
  const incomplete = GF.weekTasks(weekId).filter(t => t.status !== 'done');
  if (!incomplete.length) { GF.toast('All tasks are done — nothing to roll over', 'info'); return; }
  incomplete.forEach(t => { t.weekId = nextId; });
  GF.store.save(); GF.render.all();
  GF.toast(`${incomplete.length} task(s) rolled to next week`, 'success');
};

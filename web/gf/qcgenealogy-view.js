/* qcgenealogy-view.js — QC LIMS: batch genealogy (item 5, D2 = blending / m:n).

   The batch lineage variety → cultivation (AB…) → processing (P…) → packaging,
   as a directed m:n graph (a blended lot has several parents). Look up a batch
   to see its ancestors / descendants / direct edges, add or remove edges, and
   see the RELEASED-certificate results its finished-product CoQ can inherit from
   its ancestor lots (QCSOP 012 D3). Read = any elevated role; edit = QC writers.
   Full-page view in the QMS Studio zone, anchored 'qms-end'. */

(function () {
  // Shared QC/LIMS role gate (core.js GF.QC_WRITERS) — see that file's
  // comment; was a local copy-pasted array here.
  const canWrite = () => GF.QC_WRITERS.includes((GF.API.user || {}).role);
  const RELATIONS = ['CULTIVATION', 'PROCESSING', 'PACKAGING', 'BLEND', 'GENERIC'];

  GF.WWF._qcgen = { batch: '', data: null, inherited: null, loading: false, error: null };

  GF.WWF.loadQcGenealogy = async (batch) => {
    const st = GF.WWF._qcgen;
    const b = (batch != null ? batch : st.batch).trim();
    if (!b) { st.data = null; st.inherited = null; GF.render.all(); return; }
    st.batch = b; st.loading = true; st.error = null;
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const data = await GF.API.qcGenealogy(b);
      if (my !== st.lseq) return;
      st.data = data;
      const inherited = await GF.API.qcGenInherited(b).catch(() => null);
      if (my !== st.lseq) return;
      st.inherited = inherited;
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'qcgenealogy') GF.render.all();
  };

  GF.WWF.qcGenLookup = () => {
    const v = ((document.getElementById('qcgen-batch') || {}).value || '').trim();
    GF.WWF.loadQcGenealogy(v);
  };
  GF.WWF.qcGenAddEdge = async () => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const parent = mk('qcgen-parent'), child = mk('qcgen-child'), relation = mk('qcgen-rel') || 'GENERIC';
    if (!parent || !child) return GF.toast(AL('Parent and child batch are required', 'Потребни се родителска и детска серија'), 'error');
    try {
      await GF.API.qcGenAddEdge({ parent_batch_id: parent, child_batch_id: child, relation });
      GF.toast(AL('Edge added', 'Врската е додадена'));
      await GF.WWF.loadQcGenealogy(GF.WWF._qcgen.batch || child);
    } catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qcGenDelEdge = async (id) => {
    if (!confirm(AL('Remove this genealogy edge?', 'Да се отстрани оваа врска?'))) return;
    try { await GF.API.qcGenDelEdge(id); GF.toast(AL('Removed', 'Отстрането')); await GF.WWF.loadQcGenealogy(GF.WWF._qcgen.batch); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qcGenGo = (batch) => { GF.WWF.loadQcGenealogy(batch); };

  const relChip = (r) => `<span class="chip-opt" style="border-color:var(--accent);color:var(--accent)">${GF.esc(r || 'GENERIC')}</span>`;
  const batchLink = (b) => `<a href="#" class="mono" onclick="GF.WWF.qcGenGo('${GF.esc((b || '').replace(/'/g, ''))}');return false">${GF.esc(b)}</a>`;

  const graphPanel = (d) => {
    const edgeRow = (e, dir) => `<div class="qms-row" style="gap:8px;align-items:center">
      ${relChip(e.relation)}
      <span class="qms-title">${dir === 'up' ? batchLink(e.parent_batch_id) + ' → ' + GF.esc(e.child_batch_id) : GF.esc(e.parent_batch_id) + ' → ' + batchLink(e.child_batch_id)}</span>
      ${e.quantity != null ? `<span class="ana-note">${GF.esc(String(e.quantity))} ${GF.esc(e.unit || '')}</span>` : ''}
      ${canWrite() ? `<button class="btn btn-sm" onclick="GF.WWF.qcGenDelEdge('${e.id}')">✕</button>` : ''}
    </div>`;
    const list = (arr) => arr.length ? arr.map(a => `<span class="chip-opt" style="cursor:pointer" onclick="GF.WWF.qcGenGo('${GF.esc((a.batch_id || '').replace(/'/g, ''))}')">${GF.esc(a.batch_id)} <span class="ana-note">·${a.depth}</span></span>`).join(' ') : `<span class="ana-note">${AL('none', 'нема')}</span>`;
    return `<div class="panel ana-panel" style="margin-bottom:12px">
      <div class="ana-pt">${AL('Ancestors (up the chain)', 'Предци (нагоре)')}</div>
      <div style="margin:4px 0 10px">${list(d.ancestors)}</div>
      <div class="ana-pt">${AL('Descendants (down the chain)', 'Потомци (надолу)')}</div>
      <div style="margin:4px 0 10px">${list(d.descendants)}</div>
      <div class="ana-pt">${AL('Direct parents', 'Директни родители')}</div>
      ${d.parents.length ? d.parents.map(e => edgeRow(e, 'up')).join('') : `<div class="ana-note">${AL('none', 'нема')}</div>`}
      <div class="ana-pt" style="margin-top:8px">${AL('Direct children', 'Директни деца')}</div>
      ${d.children.length ? d.children.map(e => edgeRow(e, 'down')).join('') : `<div class="ana-note">${AL('none', 'нема')}</div>`}
    </div>`;
  };

  const inheritedPanel = (inh) => {
    if (!inh || !inh.inherited || !inh.inherited.length) {
      return `<div class="panel ana-panel"><div class="ana-pt">${AL('Inheritable ancestor results (QCSOP 012 D3)', 'Наследливи резултати од предци (QCSOP 012 D3)')}</div>
        <div class="ana-note">${AL('No RELEASED ancestor certificates to inherit from.', 'Нема ослободени сертификати од предци за наследување.')}</div></div>`;
    }
    return `<div class="panel ana-panel"><div class="ana-pt">${AL('Inheritable ancestor results (QCSOP 012 D3)', 'Наследливи резултати од предци (QCSOP 012 D3)')}</div>
      ${inh.inherited.map(b => `<div style="margin-top:8px">
        <div><b class="mono">${GF.esc(b.coa_number)}</b> <span class="ana-note">${AL('from', 'од')} ${GF.esc(b.from_batch_id)}</span> ${b.decision ? relChip(b.decision) : ''}</div>
        <table class="qcp-table" style="margin-top:4px"><tbody>${(b.results || []).map(r => `<tr>
          <td>${GF.esc(r.test_name)}</td>
          <td class="mono">${r.result_numeric != null ? GF.esc(String(r.result_numeric)) : GF.esc(r.result_value || '—')} ${GF.esc(r.unit || '')}</td>
          <td>${r.complies === true ? '✓' : r.complies === false ? '✗' : '—'}</td>
        </tr>`).join('')}</tbody></table>
      </div>`).join('')}</div>`;
  };

  GF.views.qcgenealogy = () => {
    const st = GF.WWF._qcgen;
    const head = GF.viewHead('qc_genealogy', 'qc_genealogy_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — batch genealogy: variety → cultivation → processing → packaging (blending supported), with CoQ-level inheritance of ancestor results.',
      'QMS Студио — генеалогија на серии: сорта → одгледување → преработка → пакување (со мешање), со наследување на резултати од предци.')}</div>`;
    const lookup = `<div class="panel ana-panel" style="margin-bottom:12px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <input id="qcgen-batch" placeholder="${AL('Batch code (e.g. PACK-2026-77)', 'Код на серија')}" value="${GF.esc(st.batch)}" style="min-width:220px">
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcGenLookup()">${AL('Look up lineage', 'Побарај лоза')}</button>
      </div>
      ${canWrite() ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px">
        <input id="qcgen-parent" placeholder="${AL('Parent batch', 'Родителска серија')}" style="width:150px">
        <span>→</span>
        <input id="qcgen-child" placeholder="${AL('Child batch', 'Детска серија')}" style="width:150px">
        <select id="qcgen-rel">${RELATIONS.map(r => `<option value="${r}">${r}</option>`).join('')}</select>
        <button class="btn btn-sm" onclick="GF.WWF.qcGenAddEdge()">${AL('Add edge', 'Додај врска')}</button>
      </div>` : ''}
    </div>`;
    if (st.loading) return head + zone + lookup + `<div class="mw-skel" style="height:160px"></div>`;
    if (st.error) return head + zone + lookup + `<div class="panel" style="padding:16px"><span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span></div>`;
    if (!st.data) return head + zone + lookup + `<div class="ana-note">${AL('Enter a batch code to trace its genealogy.', 'Внесете код на серија за да ја следите генеалогијата.')}</div>`;
    return head + zone + lookup + graphPanel(st.data) + inheritedPanel(st.inherited);
  };

  GF.WWF._registerFullPageView({
    key: 'qcgenealogy', icon: 'git-branch',
    label: () => AL('Batch genealogy', 'Генеалогија на серии'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();

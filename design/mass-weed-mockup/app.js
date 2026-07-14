/* MASS WEED — inventory terminal logic */
(function(){
  const $ = s => document.querySelector(s);
  const cats = window.MW_CATS, ITEMS = window.MW_ITEMS, STATS = window.MW_STATS, GL = window.MW_GLYPHS;
  let curCat = 'flower';
  let equipped = ITEMS.flower[0];   // "In Stock"
  let selected = null;              // "Selected Batch"
  let sortMode = 0;                 // 0 potency, 1 name, 2 rarity
  const sortLabels = ['Potency ▾','Name ▾','Grade ▾'];
  const rarOrder = { epic:4, rare:3, uncommon:2, common:1 };

  function pct(v,max){ return Math.max(3, Math.min(100, v/max*100)); }
  function tierAbs(v,max){ const f=v/max; return f>=0.6?'hi':f>=0.33?'mid':'lo'; }
  function tierCmp(v,ref){ if(v>ref*1.03) return 'hi'; if(v<ref*0.97) return 'lo'; return 'mid'; }

  function renderStats(el, item, cmpTo){
    const schema = STATS[item.cat];
    el.innerHTML = schema.map((row,i)=>{
      const [name,unit,max] = row;
      const v = item.stats[i];
      const tier = cmpTo ? tierCmp(v, cmpTo.cat===item.cat ? cmpTo.stats[i] : v) : tierAbs(v,max);
      return `<div class="mw-stat">
        <div class="mw-stat__head"><span class="mw-stat__name">${name}${unit?' ('+unit+')':''}</span><span class="mw-stat__val">${v}</span></div>
        <div class="mw-stat__track"><div class="mw-stat__fill mw-stat__fill--${tier}" style="width:${pct(v,max)}%"></div></div>
      </div>`;
    }).join('');
  }

  function renderCompare(){
    $('#nameA').textContent = equipped.name;
    $('#brandA').textContent = equipped.brand;
    $('#glyphA').innerHTML = GL[equipped.cat];
    renderStats($('#statsA'), equipped, null);
    if(selected){
      $('#nameB').textContent = selected.name;
      $('#brandB').textContent = selected.brand;
      $('#glyphB').innerHTML = GL[selected.cat];
      renderStats($('#statsB'), selected, equipped);
    } else {
      $('#nameB').textContent = '—';
      $('#brandB').textContent = 'No batch selected';
      $('#statsB').innerHTML = '';
    }
  }

  function sortedList(){
    const arr = ITEMS[curCat].slice();
    if(sortMode===0) arr.sort((a,b)=>b.stats[0]-a.stats[0]);
    else if(sortMode===1) arr.sort((a,b)=>a.name.localeCompare(b.name));
    else arr.sort((a,b)=>rarOrder[b.rarity]-rarOrder[a.rarity]);
    return arr;
  }

  function renderList(){
    const list = $('#list');
    list.innerHTML = sortedList().map(it=>{
      const isSel = selected && it.name===selected.name;
      const isEq  = it.name===equipped.name && it.cat===equipped.cat;
      const cls = isSel ? 'mw-row--selected' : (isEq ? 'mw-row--active' : '');
      const cat = cats.find(c=>c.id===it.cat).label;
      return `<div class="mw-row ${cls}" data-name="${it.name}">
        <span class="mw-row__label">${cat} — <span style="opacity:.6">${it.brand.split(' ')[0]}</span></span>
        <span class="mw-row__val" style="color:var(--mw-${it.rarity==='common'?'common':it.rarity==='rare'?'rare':it.rarity==='epic'?'epic':'uncommon'})">${it.name}</span>
      </div>`;
    }).join('');
    list.querySelectorAll('.mw-row').forEach(r=>{
      r.onclick = ()=>{ selected = ITEMS[curCat].find(x=>x.name===r.dataset.name); renderCompare(); renderList(); };
    });
  }

  function renderTabs(){
    $('#tabs').innerHTML = cats.map(c=>
      `<div class="mw-tab ${c.id===curCat?'mw-tab--active':''}" data-cat="${c.id}" title="${c.label}">${GL[c.glyph]}</div>`
    ).join('');
    $('#tabs').querySelectorAll('.mw-tab').forEach(t=>{
      t.onclick = ()=>{ curCat=t.dataset.cat; selected=null; $('#catTitle').textContent=cats.find(c=>c.id===curCat).label; renderTabs(); renderList(); };
    });
  }

  const RES = [
    { icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2c-1 5-5 7-5 11a5 5 0 0 0 10 0c0-4-4-6-5-11z"/></svg>', val:'128', label:'strains' },
    { icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4" y="7" width="16" height="13" rx="2"/><path d="M9 7V5a3 3 0 0 1 6 0v2"/></svg>', val:'46', label:'batches' },
    { icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v18M4 8l8-5 8 5"/></svg>', val:'300', label:'grams' },
    { icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M9.5 9.5h3.5a1.5 1.5 0 0 1 0 3h-2a1.5 1.5 0 0 0 0 3H14"/></svg>', val:'427,340', label:'revenue' }
  ];
  function renderRes(){
    $('#resbar').innerHTML = RES.map(r=>
      `<div class="mw-res"><span class="mw-res__icon">${r.icon}</span><span class="mw-res__val">${r.val}</span><span class="mw-label" style="font-size:10px;">${r.label}</span></div>`
    ).join('');
  }

  function renderRecovered(){
    $('#recovList').innerHTML = window.MW_RECOVERED.map(it=>{
      const cat = cats.find(c=>c.id===it.cat).label;
      return `<div class="mw-item mw-item--${it.rarity}">
        <span class="mw-item__cat">${cat}</span>
        <span class="mw-item__name">${it.name}</span>
        <span class="mw-item__brand">${it.brand}</span>
      </div>`;
    }).join('');
    $('#recovCount').textContent = window.MW_RECOVERED.length;
  }

  // actions
  window.openRecovered = ()=>{ $('#overlay').classList.add('open'); };
  window.closeRecovered = ()=>{ $('#overlay').classList.remove('open'); };
  window.stockSelected = ()=>{ if(selected){ equipped = selected; selected=null; renderCompare(); renderList(); } };
  window.reduceTrim = ()=>{ if(selected){ const i=ITEMS[curCat].findIndex(x=>x.name===selected.name); if(i>=0) ITEMS[curCat].splice(i,1); selected=null; renderCompare(); renderList(); } };
  window.reduceAllTrim = ()=>{ window.MW_RECOVERED.length=0; renderRecovered(); $('#recovCount').textContent=0; };
  window.takeAll = ()=>{ window.MW_RECOVERED.length=0; renderRecovered(); $('#recovCount').textContent=0; closeRecovered(); };

  $('#sortBtn').onclick = ()=>{ sortMode=(sortMode+1)%3; $('#sortBtn').textContent='Sort: '+sortLabels[sortMode]; renderList(); };
  $('#overlay').onclick = e=>{ if(e.target.id==='overlay') closeRecovered(); };

  // init
  $('#catTitle').textContent = cats.find(c=>c.id===curCat).label;
  renderTabs(); renderList(); renderCompare(); renderRes(); renderRecovered();
})();

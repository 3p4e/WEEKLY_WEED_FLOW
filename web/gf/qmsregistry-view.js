/* qmsregistry-view.js — QMS Studio: SOP Registry (RETIRED).

   This browsed the QMS Creator's document registry through the old qms-api
   proxy (/qms/documents, /qms/stats, /qms/hierarchy). qms-api was retired
   platform-wide (docs/PLATFORM-ROADMAP-2026-07.md) — its API key is blank on
   every stack, so those endpoints return 503 "QMS service unavailable"
   permanently, not intermittently. Controlled-document authoring +
   generated-document listing now live in Document Studio (qmsstudio-view.js,
   DocEngine-backed via /qms/studio/*).

   Previously this view fired the doomed network calls on every visit (3
   guaranteed round trips + console errors) before falling back to this same
   message — pure noise for a permanently-known outcome. Render the retired
   state directly; nothing to fetch, nothing to retry. Text is pinned by
   web/e2e/tests/qms-studio.spec.js. */

(function () {
  GF.views.qmsregistry = () => {
    const head = GF.viewHead
      ? GF.viewHead('sop_registry', 'sop_registry_sub')
      : `<h2>${AL('SOP Registry', 'Регистар на СОП')}</h2>`;
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — authoritative QMS documents. Operational tasks reference these records by code.',
      'QMS Студио — авторитативни QMS документи. Оперативните задачи ги референцираат овие записи по код.')}</div>`;
    return head + zone + `<div class="panel" style="padding:16px">
      <div class="ana-pt" style="margin:0 0 6px">${AL('SOP Registry retired', 'Регистарот на СОП е повлечен')}</div>
      <div class="ana-note">${AL(
        'The legacy SOP registry has been retired. Create and manage controlled documents in Document Studio.',
        'Наследениот регистар на СОП е повлечен. Креирајте и управувајте со контролирани документи во Студиото за документи.')}</div>
      <button class="btn btn-sm" style="margin-top:10px" onclick="GF.setView('qmsstudio')">${AL('Go to Document Studio', 'Оди во Студиото за документи')}</button>
    </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qmsregistry', icon: 'shield',
    label: () => AL('SOP Registry', 'Регистар на СОП'),
    insertBefore: 'qms-end',   // QMS Studio group (render.js sidebar)
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();

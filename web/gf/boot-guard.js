/* boot-guard.js — MUST load first.
   ONE job: if the saved-data schema changed between releases, drop stale
   GrowFlow app data so old-shaped records can't throw during hydrate.
   Standalone task-tracker build — only touches gf_* keys (no QC coupling). */
(function () {
  var SCHEMA_VERSION = '2026-06-01-r5';
  try {
    var v = localStorage.getItem('gf_schema_version');
    if (v !== SCHEMA_VERSION) {
      var kill = [];
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (/^gf_/.test(k) && k !== 'gf_schema_version') kill.push(k);
      }
      kill.forEach(function (k) { try { localStorage.removeItem(k); } catch (e) {} });
      localStorage.setItem('gf_schema_version', SCHEMA_VERSION);
    }
    // Clear any stale self-heal flags left by older builds so they can't block boot.
    try {
      sessionStorage.removeItem('gf_selfheal');
      sessionStorage.removeItem('gf_selfheal2');
      sessionStorage.removeItem('gf_heal');
    } catch (e) {}
  } catch (e) {}
})();

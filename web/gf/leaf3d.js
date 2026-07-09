/* leaf3d.js — interactive 3D leaf mark (three.js r160, self-hosted).
   A faithful port of Purely Plant's "Leaf 3D Interactive": idle float, click →
   spin (accelerates to 22×), THREE rapid clicks → wormhole implosion → emerge.
   Packaged as a mountable module so the same leaf is the splash hero AND the
   login logo. Requires window.THREE (gf/vendor/three.min.js loaded before this).
   Degrades gracefully: mount() returns null when three.js/WebGL is unavailable,
   and entry.js then falls back to the CSS .pp-leaf-anim leaf. The 348 KB mesh is
   fetched same-origin from /assets/pp-leaf-3d.obj (CSP-clean, service-worker
   cacheable) instead of inlined, so this file stays tiny. */
window.GF = window.GF || {};

GF.leaf3d = (function () {
  // ── OBJ parser (verbatim from the design source; position-only, fan-triangulated) ──
  function parseOBJToGeometry(text, THREE) {
    const verts = [], positions = [], lines = text.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.charCodeAt(0) === 118 && line.charCodeAt(1) === 32) {          // "v "
        const p = line.split(/\s+/); verts.push(+p[1], +p[2], +p[3]);
      } else if (line.charCodeAt(0) === 102 && line.charCodeAt(1) === 32) {   // "f "
        const p = line.split(/\s+/); const idx = [];
        for (let k = 1; k < p.length; k++) { if (!p[k]) continue; let vi = parseInt(p[k], 10); if (vi < 0) vi = verts.length / 3 + vi + 1; idx.push(vi - 1); }
        for (let k = 1; k < idx.length - 1; k++) { const tri = [idx[0], idx[k], idx[k + 1]]; for (let m = 0; m < 3; m++) { const b = tri[m] * 3; positions.push(verts[b], verts[b + 1], verts[b + 2]); } }
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    return geo;
  }

  // ── Idle-motion library (verbatim): 5 distinct floating/bobbing curves ──
  const IDLE_MOVES = [
    (t, D) => ({ ry: 0.28 + 0.62 * (0.5 - 0.5 * Math.cos(t * 2 * Math.PI / 4.6)), rx: D(6.5 + 2.5 * Math.cos(t * 2 * Math.PI / 3.4)), rz: D(1.2 * Math.sin(t * 2 * Math.PI / 3.4)) }),
    (t, D) => ({ ry: 0.4 + 0.35 * Math.sin(t * 2 * Math.PI / 5.2), rx: D(8 * Math.sin(t * 2 * Math.PI / 2.6)), rz: D(4 * Math.cos(t * 2 * Math.PI / 5.2)) }),
    (t, D) => ({ ry: 0.5 + 0.8 * Math.sin(t * 2 * Math.PI / 3.8), rx: D(5), rz: D(6 * Math.sin(t * 2 * Math.PI / 3.8 + 0.4)) }),
    (t, D) => ({ ry: 0.3 + t * 0.15 % (2 * Math.PI), rx: D(10 * Math.sin(t * 2 * Math.PI / 6)), rz: D(5 * Math.cos(t * 2 * Math.PI / 4.2)) }),
    (t, D) => ({ ry: 0.35 + 0.15 * Math.sin(t * 2 * Math.PI / 2.8), rx: D(4 + 6 * Math.sin(t * 2 * Math.PI / 1.8)), rz: D(2 * Math.cos(t * 2 * Math.PI / 2.4)) }),
  ];

  function supported() {
    if (!window.THREE) return false;
    try {
      const c = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl')));
    } catch (e) { return false; }
  }

  // Fetch the ~348 KB mesh ONCE and share the text across every leaf on the page
  // (splash + sidebar + header + assistant …). Each mount still parses its own
  // BufferGeometry — geometry can't cross WebGL contexts — but the network hit
  // and the service-worker read happen a single time.
  let _objText = null;
  function loadObjText(url) {
    if (!_objText) _objText = fetch(url).then(r => { if (!r.ok) throw new Error('leaf mesh ' + r.status); return r.text(); });
    return _objText;
  }

  // Mount the leaf into `stageEl`. opts: { size, shadowEl, objUrl, onEnter, onError }.
  // Returns { canvas, destroy() } or null if unavailable.
  function mount(stageEl, opts) {
    opts = opts || {};
    const THREE = window.THREE;
    if (!THREE || !supported()) return null;

    let disposed = false;
    const size = opts.size || 280;
    const height = Math.round(size * 1.166);
    // Glow scales with the leaf so a 30 px header logo isn't swallowed by the
    // same 26 px aura the 280 px splash uses.
    const gb = Math.max(5, Math.round(size * 0.093));
    // Small leaves are LOGOS (sidebar/header/assistant): keep their idle sway
    // gentle and mostly face-on so a 30 px leaf never rotates edge-on into an
    // unreadable sliver. The big splash leaf keeps its full dramatic motion, and
    // click-spin / wormhole stay full-range for every leaf.
    const logo = size < 120;
    stageEl.style.width = size + 'px';
    stageEl.style.height = height + 'px';
    stageEl.style.position = 'relative';
    stageEl.style.cursor = 'pointer';
    if (opts.shadowEl) { opts.shadowEl.style.width = (size * 0.7) + 'px'; opts.shadowEl.style.height = (size * 0.124) + 'px'; }

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, size / height, 0.1, 6000);
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    } catch (e) { return null; }
    renderer.setSize(size, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    if ('outputColorSpace' in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.filter = `drop-shadow(0 0 ${gb}px rgba(43,232,160,.55)) drop-shadow(0 0 ${Math.round(gb * 0.46)}px rgba(47,217,217,.4))`;
    renderer.domElement.style.display = 'block';
    stageEl.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0x22403a, 1.15));
    const key = new THREE.DirectionalLight(0xa9ffdb, 2.3); key.position.set(-0.7, 1.1, 1.3); scene.add(key);
    const rim = new THREE.DirectionalLight(0x2fd9d9, 1.7); rim.position.set(1.1, 0.4, -0.9); scene.add(rim);
    const fill = new THREE.DirectionalLight(0x2be8a0, 0.85); fill.position.set(0.2, -1, 0.6); scene.add(fill);

    const mat = new THREE.MeshStandardMaterial({ color: 0x1fb877, emissive: 0x0b6b45, emissiveIntensity: 0.5, metalness: 0.4, roughness: 0.32 });
    const group = new THREE.Group();
    scene.add(group);
    let geo = null;

    loadObjText(opts.objUrl || 'assets/pp-leaf-3d.obj')
      .then(text => {
        if (disposed) return;
        geo = parseOBJToGeometry(text, THREE);
        geo.center(); geo.computeVertexNormals(); geo.computeBoundingSphere();
        const R = (geo.boundingSphere && geo.boundingSphere.radius) || 40;
        group.add(new THREE.Mesh(geo, mat));
        camera.position.set(0, 0, R / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.02);
        camera.lookAt(0, 0, 0);
      })
      .catch(e => { if (opts.onError) try { opts.onError(e); } catch (_) {} });

    const D = THREE.MathUtils.degToRad;
    const t0 = performance.now();
    const cs = { count: 0, mode: 'idle', modeStart: 0, spinSpeed: 3, lastRy: 0.28, idleIdx: Math.floor(Math.random() * IDLE_MOVES.length), nextIdleAt: t0 + (8 + Math.random() * 6) * 1000, _settleTimer: 0, _resetTimer: 0 };

    // Every tap both reveals the login card (onEnter — idempotent on the caller
    // side, so "back to leaf" then tapping re-reveals) AND drives the spin/
    // wormhole state machine (verbatim thresholds from the design).
    const onClick = () => {
      if (opts.onEnter) try { opts.onEnter(); } catch (_) {}
      if (cs.mode === 'wormhole') return;
      cs.count++;
      cs.spinSpeed = Math.min(3 + cs.count * 2.5, 22);
      cs.mode = 'spin';
      cs.modeStart = performance.now();
      if (cs.count >= 3) {
        setTimeout(() => {
          cs.mode = 'wormhole'; cs.modeStart = performance.now();
          setTimeout(() => {
            cs.mode = 'emerge'; cs.modeStart = performance.now();
            cs.count = 0; cs.spinSpeed = 3;
            cs.idleIdx = Math.floor(Math.random() * IDLE_MOVES.length);
            setTimeout(() => { cs.mode = 'idle'; cs.modeStart = performance.now(); }, 1200);
          }, 2000);
        }, 600);
      } else {
        clearTimeout(cs._settleTimer);
        cs._settleTimer = setTimeout(() => {
          if (cs.mode === 'spin') { cs.mode = 'idle'; cs.modeStart = performance.now(); cs._resetTimer = setTimeout(() => { cs.count = 0; }, 2000); }
        }, 1200);
      }
    };
    stageEl.addEventListener('click', onClick);

    let raf = 0;
    function frame(now) {
      if (disposed) return;
      raf = requestAnimationFrame(frame);
      const t = (now - t0) / 1000;
      let ry, rx, rz, scl = 1;
      const mode = cs.mode;
      const elapsed = (now - cs.modeStart) / 1000;

      if (mode === 'spin') {
        ry = cs.lastRy + elapsed * (2 * Math.PI * cs.spinSpeed);
        rx = D(6 + 10 * Math.cos(t * 2 * Math.PI * 1.5));
        rz = D(4 * Math.sin(t * 2 * Math.PI * 1.5));
      } else if (mode === 'wormhole') {
        ry = cs.lastRy + elapsed * (2 * Math.PI * 20);
        rx = D(30 * Math.sin(elapsed * 12));
        rz = D(20 * Math.cos(elapsed * 8));
        const shrink = Math.max(0, 1 - elapsed / 1.6);
        scl = shrink * shrink;
        if (scl < 0.01) scl = 0;
        stageEl.style.filter = `drop-shadow(0 0 ${Math.round(gb * 2.3)}px rgba(43,232,160,.9)) drop-shadow(0 0 ${Math.round(gb * 1.15)}px rgba(47,217,217,.7))`;
      } else if (mode === 'emerge') {
        const grow = Math.min(1, elapsed / 1.0);
        scl = grow < 0.5 ? 2 * grow * grow : 1 - Math.pow(-2 * grow + 2, 2) / 2;
        ry = elapsed * Math.PI * 2;
        rx = D(8 * (1 - grow));
        rz = D(4 * (1 - grow));
        stageEl.style.filter = '';
      } else {
        if (now > cs.nextIdleAt) {
          cs.idleIdx = (cs.idleIdx + 1 + Math.floor(Math.random() * (IDLE_MOVES.length - 1))) % IDLE_MOVES.length;
          cs.nextIdleAt = now + (8 + Math.random() * 6) * 1000;
        }
        const r = IDLE_MOVES[cs.idleIdx](t, D);
        ry = r.ry; rx = r.rx; rz = r.rz;
        if (logo) { ry = 0.1 + (ry - 0.28) * 0.32; rx *= 0.5; rz *= 0.5; }  // stay near face-on
        cs.lastRy = ry;
        stageEl.style.filter = '';
      }
      group.rotation.set(rx, ry, rz);
      group.scale.setScalar(scl);
      renderer.render(scene, camera);
    }
    raf = requestAnimationFrame(frame);

    return {
      canvas: renderer.domElement,
      // Cancel the RAF, drop listeners, and free the WebGL context — a PWA
      // reuses the tab across login/logout, so leaking a GL context each time
      // would eventually hit the browser's context limit and blank the leaf.
      destroy() {
        if (disposed) return;
        disposed = true;
        cancelAnimationFrame(raf);
        clearTimeout(cs._settleTimer); clearTimeout(cs._resetTimer);
        stageEl.removeEventListener('click', onClick);
        try { if (geo) geo.dispose(); mat.dispose(); renderer.dispose(); } catch (e) {}
        try { const c = renderer.domElement; if (c && c.parentNode) c.parentNode.removeChild(c); } catch (e) {}
      },
    };
  }

  return { mount, supported, parseOBJToGeometry };
})();

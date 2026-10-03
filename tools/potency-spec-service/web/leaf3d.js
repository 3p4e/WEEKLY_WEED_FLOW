/* leaf3d.js — interactive 3D leaf mark (three.js r160, self-hosted).
   A port of Purely Plant's "Leaf 3D Interactive": idle float, click → a short
   eased spin (1.5–2.5 turns), THREE rapid clicks → wormhole implosion → emerge,
   and on a lively mount a spontaneous 3–4 turn whirl now and then. Hovering
   gives an organic, slightly random wobble rather than a rigid cursor tilt.
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

  // ── Per-theme leaf appearance ──────────────────────────────────────────
  // The mesh is the same; only its material, light rig and glow change per
  // skin so the 3D leaf belongs to whichever theme is active (a neon plasma
  // glow that pops on the dark shell would read as a harsh halo on the light
  // one). Each future skin adds a key here. baseGlow/wormholeGlow are
  // functions of the glow-blur px so a 30px header logo and the 280px splash
  // both scale correctly. Colors are three.js hex ints (0xRRGGBB).
  const THEMES = {
    dark: {
      mat: { color: 0x2ad98f, emissive: 0x139d68, emissiveIntensity: 0.72, metalness: 0.28, roughness: 0.34 },
      ambient: [0x2c5a4c, 1.45], key: [0xc9ffe8, 3.4], rim: [0x5fecec, 2.15], fill: [0x46f2b4, 1.2],
      baseGlow: (g) => `drop-shadow(0 0 ${g}px rgba(43,232,160,.72)) drop-shadow(0 0 ${Math.round(g * 0.5)}px rgba(47,217,217,.52))`,
      wormholeGlow: (g) => `drop-shadow(0 0 ${Math.round(g * 2.3)}px rgba(43,232,160,.9)) drop-shadow(0 0 ${Math.round(g * 1.15)}px rgba(47,217,217,.7))`,
    },
    light: {
      // Deeper emerald body (reads as a rich object on white, not washed out),
      // gentler emissive (no dark backdrop to glow against), and a soft
      // green/teal DROP shadow instead of a neon aura. Brighter near-white
      // key + neutral ambient so the leaf isn't lit only in green on a pale bg.
      mat: { color: 0x17A866, emissive: 0x0B7A46, emissiveIntensity: 0.40, metalness: 0.18, roughness: 0.42 },
      ambient: [0x9ec8b6, 1.55], key: [0xffffff, 3.1], rim: [0x2f9aa0, 1.65], fill: [0x2fa877, 1.05],
      baseGlow: (g) => `drop-shadow(0 ${Math.max(2, Math.round(g * 0.4))}px ${Math.round(g * 0.9)}px rgba(6,121,63,.30)) drop-shadow(0 0 ${Math.round(g * 0.5)}px rgba(15,111,118,.20))`,
      wormholeGlow: (g) => `drop-shadow(0 0 ${Math.round(g * 1.8)}px rgba(6,121,63,.55)) drop-shadow(0 0 ${Math.round(g * 0.9)}px rgba(15,111,118,.4))`,
    },
    suma: {
      // Protoss psi-crystal leaf: the plant-green brand body, but haloed in
      // psi-cyan + Khaydarin gold (the SUMA signature) instead of pure green —
      // teal rim + gold fill make it read as an energized crystal on the void.
      mat: { color: 0x22C98C, emissive: 0x10B981, emissiveIntensity: 0.66, metalness: 0.30, roughness: 0.32 },
      ambient: [0x1b3a4c, 1.4], key: [0xc9f7ff, 3.3], rim: [0x2ee6ff, 2.4], fill: [0xffcf6b, 1.1],
      baseGlow: (g) => `drop-shadow(0 0 ${g}px rgba(46,230,255,.6)) drop-shadow(0 0 ${Math.round(g * 0.5)}px rgba(255,207,107,.4))`,
      wormholeGlow: (g) => `drop-shadow(0 0 ${Math.round(g * 2.3)}px rgba(46,230,255,.9)) drop-shadow(0 0 ${Math.round(g * 1.15)}px rgba(255,207,107,.7))`,
    },
    masseffect: {
      // Mass Effect console leaf: an electric holographic-blue body haloed in bright
      // cyan-blue, with the amber of a Renegade interrupt in the fill — a hologram on the void.
      mat: { color: 0x33B8FF, emissive: 0x0E7FD6, emissiveIntensity: 0.78, metalness: 0.34, roughness: 0.30 },
      ambient: [0x123a57, 1.4], key: [0xd6f0ff, 3.4], rim: [0x5cd0ff, 2.4], fill: [0xf2a73c, 1.0],
      baseGlow: (g) => `drop-shadow(0 0 ${g}px rgba(51,184,255,.72)) drop-shadow(0 0 ${Math.round(g * 0.5)}px rgba(120,220,255,.5))`,
      wormholeGlow: (g) => `drop-shadow(0 0 ${Math.round(g * 2.3)}px rgba(51,184,255,.92)) drop-shadow(0 0 ${Math.round(g * 1.15)}px rgba(120,220,255,.7))`,
    },
  };
  function resolveThemeName(name) {
    if (name) return name;
    try { return document.documentElement.dataset.theme || 'dark'; } catch (e) { return 'dark'; }
  }
  // Parse "#rrggbb" or "r,g,b" or "rgb(...)" into an 0xRRGGBB int (null on fail).
  function toHexInt(s) {
    if (!s) return null;
    s = s.trim();
    let m = s.match(/^#?([0-9a-f]{6})$/i);
    if (m) return parseInt(m[1], 16);
    m = s.match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (m) return (+m[1] << 16) | (+m[2] << 8) | (+m[3]);
    return null;
  }
  function relLum(hex) {  // rough perceptual lightness 0..1 of an 0xRRGGBB int
    const r = (hex >> 16 & 255) / 255, g = (hex >> 8 & 255) / 255, b = (hex & 255) / 255;
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  // Build a leaf palette from the ACTIVE skin's CSS tokens — so every Carbon
  // skin (and any future one) gets a matching leaf with no per-skin config:
  // material = --primary, secondary glow = --blue, light-vs-dark glow style
  // chosen from --bg lightness.
  function deriveFromCSS() {
    const cs = getComputedStyle(document.documentElement);
    const primary = toHexInt(cs.getPropertyValue('--primary')) ?? 0x2ad98f;
    const blue = toHexInt(cs.getPropertyValue('--blue')) ?? primary;
    const bg = toHexInt(cs.getPropertyValue('--bg')) ?? 0x0e1f17;
    const pr = primary >> 16 & 255, pg = primary >> 8 & 255, pb = primary & 255;
    const br = blue >> 16 & 255, bg2 = blue >> 8 & 255, bb = blue & 255;
    const darker = (h, f) => ((Math.round((h >> 16 & 255) * f) << 16) | (Math.round((h >> 8 & 255) * f) << 8) | Math.round((h & 255) * f));
    const lightBg = relLum(bg) > 0.5;
    return {
      mat: { color: primary, emissive: darker(primary, lightBg ? 0.62 : 0.72),
             emissiveIntensity: lightBg ? 0.42 : 0.66, metalness: 0.26, roughness: lightBg ? 0.4 : 0.34 },
      ambient: lightBg ? [0x9aa8b0, 1.5] : [darker(primary, 0.22), 1.4],
      key: [lightBg ? 0xffffff : 0xd8ffee, lightBg ? 3.1 : 3.3],
      rim: [blue, lightBg ? 1.7 : 2.2], fill: [primary, 1.1],
      baseGlow: lightBg
        ? (g) => `drop-shadow(0 ${Math.max(2, Math.round(g * 0.4))}px ${Math.round(g * 0.9)}px rgba(${pr},${pg},${pb},.3)) drop-shadow(0 0 ${Math.round(g * 0.5)}px rgba(${br},${bg2},${bb},.2))`
        : (g) => `drop-shadow(0 0 ${g}px rgba(${pr},${pg},${pb},.62)) drop-shadow(0 0 ${Math.round(g * 0.5)}px rgba(${br},${bg2},${bb},.45))`,
      wormholeGlow: (g) => `drop-shadow(0 0 ${Math.round(g * 2.3)}px rgba(${pr},${pg},${pb},.9)) drop-shadow(0 0 ${Math.round(g * 1.15)}px rgba(${br},${bg2},${bb},.65))`,
    };
  }
  // A hand-tuned THEMES entry wins; every other skin derives from CSS.
  function paletteFor(name) {
    return THEMES[resolveThemeName(name)] || deriveFromCSS();
  }

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
    // Memoize the SUCCESS only. Caching the promise unconditionally meant one
    // transient blip during boot pinned a rejected promise for the rest of the
    // session, permanently downgrading the 3D leaf app-wide with no retry.
    if (!_objText) {
      _objText = fetch(url)
        .then(r => { if (!r.ok) throw new Error('leaf mesh ' + r.status); return r.text(); })
        .catch(e => { _objText = null; throw e; });   // let the next mount retry
    }
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
    const lively = !!opts.lively;                 // extra life: periodic self-spin + stronger hover
    const logo = size < 120 && !lively;           // lively small leaves keep their full idle motion
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
    renderer.domElement.style.display = 'block';
    stageEl.appendChild(renderer.domElement);

    // Theme-driven look. A hand-tuned THEMES entry (dark/light/suma) wins;
    // every other skin derives its leaf from the active CSS tokens. opts.theme
    // pins it (the splash keeps 'dark'); otherwise it follows <html data-theme>.
    let pal = paletteFor(opts.theme);

    // Brighter, higher-contrast rig so the leaf pops off the surface instead of
    // sinking into shadow: lifted ambient, a strong key, a punchy rim for edge
    // separation, and a brighter fill from below. Colors/intensities per theme.
    const ambient = new THREE.AmbientLight(pal.ambient[0], pal.ambient[1]); scene.add(ambient);
    const key = new THREE.DirectionalLight(pal.key[0], pal.key[1]); key.position.set(-0.7, 1.1, 1.3); scene.add(key);
    const rim = new THREE.DirectionalLight(pal.rim[0], pal.rim[1]); rim.position.set(1.1, 0.4, -0.9); scene.add(rim);
    const fill = new THREE.DirectionalLight(pal.fill[0], pal.fill[1]); fill.position.set(0.2, -1, 0.6); scene.add(fill);

    // Emissive base + low metalness (metal reads dark without an env map) so
    // more of the surface is diffusely lit and vividly coloured.
    const mat = new THREE.MeshStandardMaterial(pal.mat);
    renderer.domElement.style.filter = pal.baseGlow(gb);

    // Re-tint every material/light/glow to another skin's palette in place —
    // called by GF.leafFX.retintAll() when the user flips the theme, so live
    // leaves change skin without a remount (and without a GL-context churn).
    function applyTheme(name) {
      const p = paletteFor(name); if (!p) return;
      pal = p;
      mat.color.setHex(p.mat.color); mat.emissive.setHex(p.mat.emissive);
      mat.emissiveIntensity = p.mat.emissiveIntensity; mat.metalness = p.mat.metalness; mat.roughness = p.mat.roughness;
      mat.needsUpdate = true;
      ambient.color.setHex(p.ambient[0]); ambient.intensity = p.ambient[1];
      key.color.setHex(p.key[0]); key.intensity = p.key[1];
      rim.color.setHex(p.rim[0]); rim.intensity = p.rim[1];
      fill.color.setHex(p.fill[0]); fill.intensity = p.fill[1];
      if (cs.mode !== 'wormhole') renderer.domElement.style.filter = p.baseGlow(gb);
    }
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
        camera.position.set(0, 0, R / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.18);
        camera.lookAt(0, 0, 0);
      })
      .catch(e => { if (opts.onError) try { opts.onError(e); } catch (_) {} });

    const D = THREE.MathUtils.degToRad;
    const t0 = performance.now();
    const TAU = Math.PI * 2;
    const cs = { count: 0, mode: 'idle', modeStart: 0, spinFrom: 0.28, spinTurns: 1.5, spinDur: 1.8, lastRy: 0.28, idleIdx: Math.floor(Math.random() * IDLE_MOVES.length), nextIdleAt: t0 + (8 + Math.random() * 6) * 1000, nextSpinAt: lively ? t0 + (6 + Math.random() * 4) * 1000 : Infinity, _settleTimer: 0, _resetTimer: 0 };
    // Smoothed pose: idle/hover targets are eased toward, so a mode change never
    // snaps the leaf; spins and the wormhole drive the pose directly.
    const sm = { rx: 0, ry: 0.28, rz: 0, s: 1 };
    // Random phases per mount so two leaves on one page never wobble in step.
    const ph = Array.from({ length: 9 }, () => Math.random() * TAU);
    const wrap = (a) => (((a + Math.PI) % TAU) + TAU) % TAU - Math.PI;   // nearest equivalent angle in (-π, π]

    // Every tap both reveals the login card (onEnter — idempotent on the caller
    // side, so "back to leaf" then tapping re-reveals) AND drives the spin/
    // wormhole state machine (verbatim thresholds from the design).
    const onClick = () => {
      if (opts.onEnter) try { opts.onEnter(); } catch (_) {}
      if (cs.mode === 'wormhole') return;
      cs.count++;
      clearTimeout(cs._resetTimer);
      // 1 turn, then 2: whole revolutions, eased out, so a tap reads as a flick
      // rather than a motor and the leaf lands back on the pose it left.
      cs.spinTurns = Math.min(cs.count, 2);
      cs.spinDur = 0.9 + cs.spinTurns * 0.55;
      cs.spinFrom = cs.mode === 'spin' || cs.mode === 'autospin' ? cs.lastRy : sm.ry;
      cs.mode = 'spin';
      cs.modeStart = performance.now();
      if (cs.count >= 3) {
        setTimeout(() => {
          cs.mode = 'wormhole'; cs.modeStart = performance.now(); cs.spinFrom = cs.lastRy;
          setTimeout(() => {
            cs.mode = 'emerge'; cs.modeStart = performance.now();
            cs.count = 0;
            cs.idleIdx = Math.floor(Math.random() * IDLE_MOVES.length);
            setTimeout(() => { cs.mode = 'idle'; cs.modeStart = performance.now(); cs.lastRy = wrap(cs.lastRy); sm.ry = cs.lastRy; }, 1200);
          }, 2000);
        }, 600);
      }
    };
    stageEl.addEventListener('click', onClick);

    // Hover-follow (mouse/pen): the leaf tilts toward the cursor — the left/right
    // + up/down parallax the flat leaf logos used to have. Touch relies on the
    // idle float + tap-to-spin instead (no hover state to get stuck in).
    let hover = false, htx = 0, hty = 0, hx = 0, hy = 0;
    const onPEnter = (e) => { if (e.pointerType === 'touch') return; hover = true; };
    const onPLeave = () => { hover = false; htx = 0; hty = 0; if (lively) stageEl.style.transform = ''; };
    const onPMove = (e) => {
      if (e.pointerType === 'touch') return;
      const r = stageEl.getBoundingClientRect();
      if (!r.width) return;
      htx = ((e.clientX - r.left) / r.width - 0.5) * 1.2;   // yaw  (left/right)
      hty = -((e.clientY - r.top) / r.height - 0.5) * 0.9;  // pitch (up/down)
    };
    stageEl.addEventListener('pointerenter', onPEnter);
    stageEl.addEventListener('pointerleave', onPLeave);
    stageEl.addEventListener('pointermove', onPMove);

    let raf = 0;
    function frame(now) {
      if (disposed) return;
      raf = requestAnimationFrame(frame);
      const t = (now - t0) / 1000;
      let ry, rx, rz, scl = 1;
      const mode = cs.mode;
      const elapsed = (now - cs.modeStart) / 1000;

      if (mode === 'spin') {
        const p = Math.min(1, elapsed / cs.spinDur);
        const eased = 1 - Math.pow(1 - p, 3);                 // easeOutCubic: quick flick, gentle settle
        ry = cs.spinFrom + eased * TAU * cs.spinTurns;
        rx = D(6 + 6 * Math.cos(t * TAU * 0.8));
        rz = D(3 * Math.sin(t * TAU * 0.8));
        cs.lastRy = ry;
        if (p >= 1 && cs.count < 3) {
          cs.mode = 'idle'; cs.modeStart = now; cs.lastRy = wrap(ry); sm.ry = cs.lastRy;
          clearTimeout(cs._resetTimer); cs._resetTimer = setTimeout(() => { cs.count = 0; }, 1500);
        }
      } else if (mode === 'wormhole') {
        ry = cs.spinFrom + elapsed * (TAU * 6);
        rx = D(30 * Math.sin(elapsed * 12));
        rz = D(20 * Math.cos(elapsed * 8));
        const shrink = Math.max(0, 1 - elapsed / 1.6);
        scl = shrink * shrink;
        if (scl < 0.01) scl = 0;
        stageEl.style.filter = pal.wormholeGlow(gb);
      } else if (mode === 'emerge') {
        const grow = Math.min(1, elapsed / 1.0);
        scl = grow < 0.5 ? 2 * grow * grow : 1 - Math.pow(-2 * grow + 2, 2) / 2;
        ry = elapsed * TAU / 1.2;                          // exactly one turn over the emerge
        rx = D(8 * (1 - grow));
        rz = D(4 * (1 - grow));
        cs.lastRy = ry;
        stageEl.style.filter = '';
      } else if (mode === 'autospin') {
        // A spontaneous whirl of 3 or 4 turns on a timer — eased in and out, and
        // independent of the click/wormhole counter, so it never trips the implosion.
        const p = Math.min(1, elapsed / cs.autoDur);
        const eased = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;   // easeInOutCubic
        ry = cs.spinFrom + eased * TAU * cs.autoTurns;
        rx = D(5 * Math.sin(t * TAU * 0.5));
        rz = D(3 * Math.cos(t * TAU * 0.4));
        cs.lastRy = ry;
        if (p >= 1) { cs.mode = 'idle'; cs.modeStart = now; cs.lastRy = wrap(ry); sm.ry = cs.lastRy; }
        stageEl.style.filter = '';
      } else if (hover) {
        // Follow the cursor loosely (yaw = left/right, pitch = up/down) and add a
        // slow organic wobble — three incommensurate sines per axis with random
        // phases — so the leaf looks alive under the pointer instead of hinged to it.
        hx += (htx - hx) * 0.08;
        hy += (hty - hy) * 0.08;
        const hk = lively ? 1.4 : 0.8, w = t;
        const wy = 0.22 * Math.sin(w * 1.3 + ph[0]) + 0.13 * Math.sin(w * 2.9 + ph[1]) + 0.07 * Math.sin(w * 4.7 + ph[2]);
        const wx = 0.16 * Math.sin(w * 1.1 + ph[3]) + 0.09 * Math.sin(w * 3.3 + ph[4]) + 0.05 * Math.sin(w * 5.1 + ph[5]);
        const wz = 0.09 * Math.sin(w * 0.9 + ph[6]) + 0.05 * Math.sin(w * 2.3 + ph[7]);
        ry = 0.28 + hx * hk + wy; rx = hy * hk + wx; rz = wz;
        scl = (lively ? 1.12 : 1.04) + 0.02 * Math.sin(w * 1.7 + ph[8]);
        cs.lastRy = ry;
        if (lively) stageEl.style.transform = 'translate(' + (hx * 6).toFixed(1) + 'px,' + (-hy * 6).toFixed(1) + 'px)';
        stageEl.style.filter = '';
      } else {
        hx += (0 - hx) * 0.12; hy += (0 - hy) * 0.12;   // ease back to rest after hover
        if (lively) stageEl.style.transform = (Math.abs(hx) + Math.abs(hy) < 0.01) ? '' : ('translate(' + (hx * 7).toFixed(1) + 'px,' + (-hy * 7).toFixed(1) + 'px)');
        if (lively && now > cs.nextSpinAt) {   // kick off the next self-spin: 3 or 4 turns
          cs.mode = 'autospin'; cs.modeStart = now; cs.spinFrom = sm.ry;
          cs.autoTurns = 3 + (Math.random() < 0.5 ? 0 : 1);
          cs.autoDur = 0.6 + cs.autoTurns * 1.1;
          cs.nextSpinAt = now + (12 + Math.random() * 8) * 1000;
        }
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
      if (mode === 'idle' || (mode !== 'spin' && mode !== 'wormhole' && mode !== 'emerge' && mode !== 'autospin')) {
        sm.rx += (rx - sm.rx) * 0.1; sm.ry += (ry - sm.ry) * 0.1; sm.rz += (rz - sm.rz) * 0.1; sm.s += (scl - sm.s) * 0.1;
      } else { sm.rx = rx; sm.ry = ry; sm.rz = rz; sm.s = scl; }
      group.rotation.set(sm.rx, sm.ry, sm.rz);
      group.scale.setScalar(sm.s);
      renderer.render(scene, camera);
    }
    raf = requestAnimationFrame(frame);

    return {
      canvas: renderer.domElement,
      applyTheme,   // re-tint to another skin without a remount
      // Cancel the RAF, drop listeners, and free the WebGL context — a PWA
      // reuses the tab across login/logout, so leaking a GL context each time
      // would eventually hit the browser's context limit and blank the leaf.
      destroy() {
        if (disposed) return;
        disposed = true;
        cancelAnimationFrame(raf);
        clearTimeout(cs._settleTimer); clearTimeout(cs._resetTimer);
        stageEl.removeEventListener('click', onClick);
        stageEl.removeEventListener('pointerenter', onPEnter);
        stageEl.removeEventListener('pointerleave', onPLeave);
        stageEl.removeEventListener('pointermove', onPMove);
        try { if (geo) geo.dispose(); mat.dispose(); renderer.dispose(); } catch (e) {}
        try { const c = renderer.domElement; if (c && c.parentNode) c.parentNode.removeChild(c); } catch (e) {}
      },
    };
  }

  return { mount, supported, parseOBJToGeometry };
})();

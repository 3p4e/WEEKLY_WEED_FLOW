// GrowFlow UI kit — interactive app composition. Uses design-system components.
(function () {
const { GF_DEPARTMENTS, GF_HANDOFF, GF_TASK_TYPES, GF_ROLES, GF_ROLE_PERMS, GF_T, GF_PEOPLE, GF_PERSON, GF_TASKS } = window;
const DS = window.GrowFlowDesignSystem_7accb1;
const { Button, IconButton, Avatar, AvatarStack, Badge, Chip,
  Field, Input, Textarea, Select, Checkbox, Switch, Segmented,
  StatusPill, PriorityTag, TaskCard, KpiTile, BarRow,
  NavItem, DeptRow, DayPill, Modal, Toast, Leaf, GrowFlowLockup } = DS;
const PopSelect = window.PopSelect;
const Warbird = DS.Warbird || (() => null);

const I = (name, sz = 18) => {
  const n = window.lucide && lucide.icons[name];
  if (!n) return null;
  const kids = n.find(Array.isArray) || [];
  return React.createElement('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    kids.map(([t, a], i) => React.createElement(t, { key: i, ...a })));
};

// ─── Tweaks: three expressive whole-feel levers, driven by design-system tokens ───
const { useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakColor } = window;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "softness": "balanced",
  "accent": "#15A86B",
  "tempo": "lively",
  "logo": "leaf"
}/*EDITMODE-END*/;

// Softness — reshapes every corner radius + shadow at once (industrial ↔ pillowy).
const SOFTNESS = {
  crisp: { '--r-sm':'3px','--r-md':'5px','--r-lg':'7px','--r-xl':'9px','--r-2xl':'11px',
    '--sh-1':'0 1px 1px rgba(16,35,60,.05)','--sh-2':'0 2px 6px rgba(16,35,60,.07)','--sh-3':'0 6px 18px rgba(16,35,60,.12)' },
  balanced: {},
  pillowy: { '--r-sm':'12px','--r-md':'16px','--r-lg':'22px','--r-xl':'28px','--r-2xl':'34px',
    '--sh-1':'0 2px 6px rgba(16,35,60,.09)','--sh-2':'0 10px 26px rgba(16,35,60,.13)','--sh-3':'0 24px 64px rgba(16,35,60,.22)' },
};
// Tempo — re-times every interactive transition (snappy ↔ cinematic).
const TEMPO = {
  snappy: { '--dur-micro':'.05s','--dur-ui':'.08s','--dur-panel':'.13s' },
  lively: {},
  cinematic: { '--dur-micro':'.22s','--dur-ui':'.4s','--dur-panel':'.64s' },
};
// Accent — re-hues the whole brand from one chosen primary (green / blue / violet / amber).
function hexRgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function mix(h, f) { const [r,g,b] = hexRgb(h); const j = (c) => Math.round(c * (1 - f)); return `rgb(${j(r)},${j(g)},${j(b)})`; }
function accentVars(hex) {
  const [r,g,b] = hexRgb(hex);
  return {
    '--primary': hex,
    '--primary-hover': mix(hex, 0.14),
    '--primary-soft': `rgba(${r},${g},${b},.13)`,
    '--primary-fg': mix(hex, 0.28),
    '--focus-ring': `rgba(${r},${g},${b},.32)`,
    '--sh-brand': `0 6px 18px rgba(${r},${g},${b},.30)`,
  };
}
const FEEL_KEYS = ['--r-sm','--r-md','--r-lg','--r-xl','--r-2xl','--sh-1','--sh-2','--sh-3',
  '--primary','--primary-hover','--primary-soft','--primary-fg','--focus-ring','--sh-brand',
  '--dur-micro','--dur-ui','--dur-panel'];

function useFeel(tw) {
  React.useEffect(() => {
    const root = document.documentElement;
    FEEL_KEYS.forEach((k) => root.style.removeProperty(k));
    const merged = { ...(SOFTNESS[tw.softness] || {}), ...accentVars(tw.accent), ...(TEMPO[tw.tempo] || {}) };
    Object.entries(merged).forEach(([k, v]) => root.style.setProperty(k, v));
  }, [tw.softness, tw.accent, tw.tempo]);
}

function FeelTweaks({ tw, setTweak, lang }) {
  const L = lang === 'mk';
  return (
    <TweaksPanel title="Tweaks">
      <TweakSection label={L ? 'Мекост' : 'Softness'} />
      <TweakRadio label={L ? 'Форма' : 'Shape'} value={tw.softness}
        options={[{ value: 'crisp', label: L ? 'Остро' : 'Crisp' }, { value: 'balanced', label: L ? 'Средно' : 'Balanced' }, { value: 'pillowy', label: L ? 'Меко' : 'Pillowy' }]}
        onChange={(v) => setTweak('softness', v)} />
      <TweakSection label={L ? 'Бренд акцент' : 'Brand accent'} />
      <TweakColor label={L ? 'Примарна' : 'Primary'} value={tw.accent}
        options={['#15A86B', '#2A6FDB', '#7A5AE0', '#E8912A']}
        onChange={(v) => setTweak('accent', v)} />
      <TweakSection label={L ? 'Темпо' : 'Tempo'} />
      <TweakRadio label={L ? 'Движење' : 'Motion'} value={tw.tempo}
        options={[{ value: 'snappy', label: L ? 'Брзо' : 'Snappy' }, { value: 'lively', label: L ? 'Живо' : 'Lively' }, { value: 'cinematic', label: L ? 'Кино' : 'Cinematic' }]}
        onChange={(v) => setTweak('tempo', v)} />
      <TweakSection label={L ? 'Лого модел' : 'Logo model'} />
      <TweakRadio label={L ? 'Знак' : 'Mark'} value={tw.logo}
        options={[{ value: 'leaf', label: L ? 'Лист' : 'Leaf' }, { value: 'borg', label: L ? 'Борг' : 'Borg' }]}
        onChange={(v) => setTweak('logo', v)} />
    </TweaksPanel>
  );
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
const WEEK_LABELS = { en: ['Week 26', 'Week 27', 'Week 28'], mk: ['Недела 26', 'Недела 27', 'Недела 28'] };
const RISE = (i, dur = 0.55) => ({ animation: `gfRise ${dur}s cubic-bezier(.22,.61,.36,1) backwards`, animationDelay: (i * 0.09) + 's' });

// ─── OBJ → BufferGeometry (v + triangulated f only; no normals/mtl needed) ───
function parseOBJToGeometry(text, THREE) {
  const verts = [];
  const positions = [];
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.charCodeAt(0) === 118 && line.charCodeAt(1) === 32) { // "v "
      const p = line.split(/\s+/);
      verts.push(+p[1], +p[2], +p[3]);
    } else if (line.charCodeAt(0) === 102 && line.charCodeAt(1) === 32) { // "f "
      const p = line.split(/\s+/);
      const idx = [];
      for (let k = 1; k < p.length; k++) {
        if (!p[k]) continue;
        let vi = parseInt(p[k], 10);       // ignore /vt/vn if present
        if (vi < 0) vi = verts.length / 3 + vi + 1;
        idx.push(vi - 1);
      }
      for (let k = 1; k < idx.length - 1; k++) {  // fan triangulate
        const tri = [idx[0], idx[k], idx[k + 1]];
        for (let m = 0; m < 3; m++) {
          const b = tri[m] * 3;
          positions.push(verts[b], verts[b + 1], verts[b + 2]);
        }
      }
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  return geo;
}

// ─── CSS fallback: deep extruded stack (used only if WebGL is unavailable) ───
function LeafMarkCSS({ size = 210, phase = '' }) {
  const DEPTH = 26;
  const stepZ = (size * 0.17) / DEPTH; // thicker wall ≈ 17% of height
  const layers = Array.from({ length: DEPTH }, (_, i) => {
    const t = i / (DEPTH - 1);         // 0 = front face, 1 = deepest
    const bright = i === 0 ? 1.18 : 0.8 - t * 0.6;
    const sat = i === 0 ? 1.5 : 1.9;
    return (
      <span key={i} className="gf-splash-layer" style={{
        transform: `translateZ(${-i * stepZ}px)`,
        filter: `brightness(${bright}) saturate(${sat}) contrast(${1 + t * 0.2})`,
        zIndex: DEPTH - i,
      }} />
    );
  });
  return (
    <div className="gf-splash-stage" style={{ width: size, height: size * 1.166 }}>
      <div className={('gf-splash-wobble ' + phase).trim()}>
        <div className={('gf-splash-spin ' + phase).trim()}>{layers}</div>
      </div>
      <div className="gf-splash-shadow" style={{ width: size * 0.7, height: size * 0.124 }} />
    </div>
  );
}

// ─── Real 3D leaf — the uploaded solid mesh rendered in WebGL (Three.js) ───
// Idle: slow Y-sweep + cross-axis wobble. Click: burst-spin, then settle flat.
function LeafMark({ size = 210, phase = '' }) {
  const mountRef = React.useRef(null);
  const phaseRef = React.useRef(phase);
  phaseRef.current = phase;
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    const THREE = window.THREE;
    if (!THREE || !mountRef.current) { setFailed(true); return; }
    let renderer, raf, disposed = false;
    try {
      const width = size, height = Math.round(size * 1.166);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(32, width / height, 0.1, 6000);
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, preserveDrawingBuffer: true });
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      if ('outputColorSpace' in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.domElement.style.filter =
        'drop-shadow(0 0 26px rgba(43,232,160,.55)) drop-shadow(0 0 12px rgba(47,217,217,.4))';
      mountRef.current.appendChild(renderer.domElement);

      // Plasma-green material + Tal Shiar lighting (green key, cyan rim)
      scene.add(new THREE.AmbientLight(0x22403a, 1.15));
      const key = new THREE.DirectionalLight(0xa9ffdb, 2.3); key.position.set(-0.7, 1.1, 1.3); scene.add(key);
      const rim = new THREE.DirectionalLight(0x2fd9d9, 1.7); rim.position.set(1.1, 0.4, -0.9); scene.add(rim);
      const fill = new THREE.DirectionalLight(0x2be8a0, 0.85); fill.position.set(0.2, -1, 0.6); scene.add(fill);

      const mat = new THREE.MeshStandardMaterial({
        color: 0x1fb877, emissive: 0x0b6b45, emissiveIntensity: 0.5,
        metalness: 0.4, roughness: 0.32,
      });
      const group = new THREE.Group();
      scene.add(group);

      fetch('../../assets/pp-leaf-3d.obj').then((r) => r.text()).then((text) => {
        if (disposed) return;
        const geo = parseOBJToGeometry(text, THREE);
        geo.center();
        geo.computeVertexNormals();
        geo.computeBoundingSphere();
        const R = (geo.boundingSphere && geo.boundingSphere.radius) || 40;
        group.add(new THREE.Mesh(geo, mat));
        camera.position.set(0, 0, R / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.02);
        camera.lookAt(0, 0, 0);
      }).catch(() => { if (!disposed) setFailed(true); });

      const D = THREE.MathUtils.degToRad;
      const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const t0 = performance.now();
      let prev = '', burstStart = 0, settleStart = 0, settleFrom = 0, settleTo = 0, lastRy = 0.28;

      function frame(now) {
        raf = requestAnimationFrame(frame);
        const ph = phaseRef.current;
        const t = (now - t0) / 1000;
        let ry, rx, rz;
        if (reduce) {
          ry = 0.2; rx = D(6); rz = 0;
        } else if (ph === 'burst') {
          if (prev !== 'burst') burstStart = now;
          const p = (now - burstStart) / 1000;
          ry = 0.28 + p * (2 * Math.PI * 3.0);          // ~3 fast turns / sec
          rx = D(6 + 7 * Math.cos(t * 2 * Math.PI));
          rz = D(2.5 * Math.sin(t * 2 * Math.PI));
          lastRy = ry;
        } else if (ph === 'settle') {
          if (prev !== 'settle') {
            settleStart = now; settleFrom = lastRy;
            settleTo = Math.ceil(settleFrom / (2 * Math.PI)) * 2 * Math.PI; // forward to flat
          }
          const p = Math.min((now - settleStart) / 1000, 1);
          const e = 1 - Math.pow(1 - p, 3);
          ry = settleFrom + (settleTo - settleFrom) * e;
          rx = D(6) * (1 - e); rz = 0;
        } else {
          ry = 0.28 + 0.62 * (0.5 - 0.5 * Math.cos(t * 2 * Math.PI / 4.6)); // 16°→52° sweep
          rx = D(6.5 + 2.5 * Math.cos(t * 2 * Math.PI / 3.4));              // rock (period ≠ sweep)
          rz = D(1.2 * Math.sin(t * 2 * Math.PI / 3.4));                    // twist
          lastRy = ry;
        }
        group.rotation.set(rx, ry, rz);
        renderer.render(scene, camera);
        prev = ph;
      }
      raf = requestAnimationFrame(frame);
    } catch (e) {
      setFailed(true);
    }
    return () => {
      disposed = true;
      if (raf) cancelAnimationFrame(raf);
      if (renderer) {
        renderer.dispose();
        const el = renderer.domElement;
        if (el && el.parentNode) el.parentNode.removeChild(el);
      }
    };
  }, [size]);

  if (failed) return <LeafMarkCSS size={size} phase={phase} />;
  return (
    <div className="gf-splash-stage" style={{ width: size, height: size * 1.166 }}>
      <div ref={mountRef} style={{ width: size, height: size * 1.166 }} />
      <div className="gf-splash-shadow" style={{ width: size * 0.7, height: size * 0.124 }} />
    </div>
  );
}

// ─── Borgified leaf — GLB with baked neon-circuit materials, via <model-viewer> ───
function LeafMarkBorg({ size = 210, phase = '' }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Spin faster during the burst, normal idle otherwise.
    el.setAttribute('rotation-per-second', phase === 'burst' ? '900deg' : '26deg');
  }, [phase]);
  return (
    <div className="gf-splash-stage" style={{ width: size, height: size * 1.166 }}>
      <div style={{ width: size, height: size * 1.166,
        filter: 'drop-shadow(0 0 26px rgba(43,232,160,.55)) drop-shadow(0 0 12px rgba(47,217,217,.4))' }}>
        {React.createElement('model-viewer', {
          ref,
          src: '../../assets/PP_Leaf_Borg.glb',
          alt: 'Purely Plant Borg leaf mark',
          'auto-rotate': true,
          'auto-rotate-delay': 0,
          'rotation-per-second': '26deg',
          'interaction-prompt': 'none',
          'disable-zoom': true,
          'shadow-intensity': '0',
          exposure: '1.2',
          'environment-image': 'neutral',
          'camera-orbit': '25deg 80deg 108%',
          'field-of-view': '30deg',
          style: { width: '100%', height: '100%', background: 'transparent', pointerEvents: 'none' },
        })}
      </div>
      <div className="gf-splash-shadow" style={{ width: size * 0.7, height: size * 0.124 }} />
    </div>
  );
}

// ─────────────────────────────── Splash ───────────────────────────────
function Splash({ onDone, lang, logo }) {
  const [phase, setPhase] = React.useState('idle'); // idle | burst | settle

  function enter() {
    if (phase !== 'idle') return;
    setPhase('burst');
    setTimeout(() => setPhase('settle'), 1000);
    setTimeout(onDone, 2000);
  }

  const spinPhase = phase === 'idle' ? '' : phase;
  const leaving = phase === 'settle';
  return (
    <div className="gf-splash" style={{
      opacity: leaving ? 0 : 1,
      transform: leaving ? 'scale(1.14)' : 'scale(1)',
      transition: 'opacity 1s ease, transform 1s cubic-bezier(.3,.9,.4,1)',
    }} onClick={enter}>
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22,
        transform: leaving ? 'scale(1.06)' : 'scale(1)',
        transition: 'transform 1s cubic-bezier(.3,.9,.4,1)',
      }}>
        {logo === 'borg' ? <LeafMarkBorg size={210} phase={spinPhase} /> : <LeafMark size={210} phase={spinPhase} />}
        <div style={RISE(0, 0.5)}>
          <GrowFlowLockup size="lg" onDark leaf={false} match />
        </div>
        <div style={{ ...RISE(2, 0.5), fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,.4)', letterSpacing: '.02em' }}>
          {lang === 'mk' ? 'Кликни за да продолжиш' : 'Tap the leaf to enter'}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────── Login ───────────────────────────────
function Login({ onSignIn, lang, logo }) {
  const [mode, setMode] = React.useState('signin');
  const [user, setUser] = React.useState('qcm.blani');
  const [pass, setPass] = React.useState('password');
  const [resetUser, setResetUser] = React.useState('qcm.blani');
  const [error, setError] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const t = GF_T[lang];

  async function submitSignIn(e) {
    e && e.preventDefault();
    if (!user.trim() || !pass.trim()) { setError(lang === 'mk' ? 'Внесете корисничко име и лозинка.' : 'Enter a username and password.'); return; }
    setError(null); setBusy(true);
    // Mock/demo build (public design review): no backend behind this URL —
    // accept any credentials and enter on the kit's seed dataset.
    if (window.GF_MOCK) { setTimeout(() => { setBusy(false); onSignIn(); }, 380); return; }
    try {
      await window.GF_API.login(user.trim(), pass);
      const { meId } = await window.GF_REAL.loadRealData();
      setBusy(false); onSignIn(meId);
    } catch (err) {
      setBusy(false);
      setError(err.message === 'unauthorized' || /invalid/i.test(err.message || '')
        ? (lang === 'mk' ? 'Погрешно корисничко име или лозинка.' : 'Incorrect username or password.')
        : (err.message || (lang === 'mk' ? 'Најавувањето не успеа.' : 'Sign-in failed.')));
    }
  }
  function submitForgot(e) {
    e && e.preventDefault();
    if (!resetUser.trim()) return;
    setBusy(true);
    setTimeout(() => { setBusy(false); setMode('sent'); }, 420);
  }

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', background: 'radial-gradient(120% 80% at 20% 0%, #0c2419 0%, var(--navy-900) 55%)' }}>
      <div aria-hidden style={{ position: 'absolute', inset: 0, opacity: .5, backgroundImage: 'radial-gradient(circle at 15% 20%, rgba(43,232,160,.16), transparent 42%), radial-gradient(circle at 85% 82%, rgba(47,217,217,.14), transparent 46%)' }} />
      <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: .4, mixBlendMode: 'overlay', background: 'var(--scanlines), var(--plasma-grid)' }} />
      <div aria-hidden style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', pointerEvents: 'none' }}><Warbird size={620} variant="ghost" glow={false} /></div>
      <div style={{ position: 'relative', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
            <div style={RISE(0)}>{logo === 'borg' ? <LeafMarkBorg size={150} /> : <LeafMark size={150} />}</div>
            <div style={RISE(1)}><GrowFlowLockup size="lg" onDark leaf={false} match /></div>
          </div>

          <div style={{ ...RISE(3), background: 'var(--surface)', border: '1px solid var(--border-strong)', borderRadius: 'var(--r-2xl)', boxShadow: 'var(--sh-3)', padding: 26, width: 340, display: 'flex', flexDirection: 'column', gap: 14, position: 'relative', overflow: 'hidden' }}>
            <span aria-hidden style={{ position: 'absolute', top: 0, left: 24, right: 24, height: 2, background: 'var(--hairline-plasma)' }} />
            {mode === 'signin' && (
              <form onSubmit={submitSignIn} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <Field label={lang === 'mk' ? 'Корисничко име' : 'Username'}>
                  <Input value={user} onChange={(e) => setUser(e.target.value)} placeholder="qcm.blani" />
                </Field>
                <Field label={lang === 'mk' ? 'Лозинка' : 'Password'}>
                  <Input type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="••••••••" />
                </Field>
                {error && <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: 'var(--red-soft)', color: 'var(--red-700)', fontSize: 'var(--fs-12)', fontWeight: 700, borderRadius: 'var(--r-sm)', padding: '8px 11px' }}>{I('CircleAlert', 15)}{error}</div>}
                <Button type="submit" full size="lg" disabled={busy}>{busy ? (lang === 'mk' ? 'Најавување…' : 'Signing in…') : t.signin}</Button>
                <span onClick={() => { setError(null); setMode('forgot'); }} style={{ alignSelf: 'center', fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--primary-fg)', cursor: 'pointer' }}>
                  {lang === 'mk' ? 'Заборавена лозинка?' : 'Forgot password?'}
                </span>
              </form>
            )}

            {mode === 'forgot' && (
              <form onSubmit={submitForgot} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <div style={{ fontWeight: 800, fontSize: 'var(--fs-15)', marginBottom: 4 }}>{lang === 'mk' ? 'Барање нова лозинка' : 'Request a password reset'}</div>
                  <p style={{ margin: 0, fontSize: 'var(--fs-12)', color: 'var(--text-body)', lineHeight: 1.5 }}>
                    {lang === 'mk'
                      ? 'Нема самопослужување — администратор ќе издаде нова привремена лозинка на вашата сметка.'
                      : 'Accounts are provisioned — no self-service reset. An administrator will issue a new one-time password to your account.'}
                  </p>
                </div>
                <Field label={lang === 'mk' ? 'Корисничко име' : 'Username'}>
                  <Input value={resetUser} onChange={(e) => setResetUser(e.target.value)} placeholder="qcm.blani" autoFocus />
                </Field>
                <div style={{ display: 'flex', gap: 10 }}>
                  <Button variant="secondary" type="button" full onClick={() => setMode('signin')}>{lang === 'mk' ? 'Назад' : 'Back'}</Button>
                  <Button type="submit" full disabled={busy}>{busy ? (lang === 'mk' ? 'Испраќање…' : 'Sending…') : (lang === 'mk' ? 'Испрати барање' : 'Send request')}</Button>
                </div>
              </form>
            )}

            {mode === 'sent' && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 12, padding: '6px 0 2px' }}>
                <span style={{ width: 46, height: 46, borderRadius: 999, background: 'var(--green-100)', color: 'var(--green-700)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I('Check', 22)}</span>
                <div style={{ fontWeight: 800, fontSize: 'var(--fs-15)' }}>{lang === 'mk' ? 'Барањето е испратено' : 'Request sent'}</div>
                <p style={{ margin: 0, fontSize: 'var(--fs-12)', color: 'var(--text-body)', lineHeight: 1.5 }}>
                  {lang === 'mk'
                    ? `Администратор ќе издаде нова привремена лозинка за „${resetUser}“ и ќе ве извести лично.`
                    : `An administrator will issue a new one-time password for "${resetUser}" and notify you directly.`}
                </p>
                <Button variant="secondary" full onClick={() => setMode('signin')}>{lang === 'mk' ? 'Назад кон најава' : 'Back to sign in'}</Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────── Sidebar ───────────────────────────────
function Sidebar({ view, setView, lang, me, tasks, deptFilter, setDeptFilter }) {
  const t = GF_T[lang];
  const L = lang === 'mk';
  const nav = [
    { id: 'myweek', icon: 'LayoutGrid', label: t.myweek },
    { id: 'planning', icon: 'CalendarRange', label: L ? 'Планирање' : 'Planning' },
    { id: 'board', icon: 'Columns3', label: t.board },
    { id: 'timeline', icon: 'CalendarRange', label: t.timeline },
    { id: 'coord', icon: 'GitBranch', label: t.coord },
    { id: 'dash', icon: 'ChartColumn', label: t.dash },
    { id: 'team', icon: 'Users', label: t.team },
    { id: 'report', icon: 'Sparkles', label: 'AI Report' },
    { id: 'qclab', icon: 'FlaskConical', label: L ? 'QC лаб' : 'QC Lab' },
    { id: 'analytics', icon: 'ChartPie', label: L ? 'Аналитика' : 'Analytics' },
    { id: 'audit', icon: 'ScrollText', label: L ? 'Дневник' : 'Audit' },
    { id: 'import', icon: 'Upload', label: L ? 'Увоз' : 'Import' },
    { id: 'access', icon: 'ShieldCheck', label: L ? 'Пристап' : 'Access' },
    { id: 'governance', icon: 'GitPullRequestArrow', label: L ? 'Управување' : 'Governance' },
    { id: 'settings', icon: 'Settings', label: t.settings },
  ];
  return (
    <aside style={{ width: 250, flexShrink: 0, background: 'var(--surface)', borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '18px 18px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Warbird size={26} variant="line" />
        <GrowFlowLockup size="md" leaf={false} />
      </div>
      <nav style={{ padding: '2px 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {nav.map((n) => <NavItem key={n.id} icon={I(n.icon)} label={n.label} active={view === n.id} onClick={() => setView(n.id)} />)}
      </nav>
      <div style={{ height: 1, background: 'var(--line-2)', margin: '14px 18px' }} />
      <div style={{ padding: '0 16px', marginBottom: 8 }}><span className="eyebrow">{t.depts}</span></div>
      <div style={{ padding: '0 12px', display: 'flex', flexDirection: 'column', gap: 1, overflowY: 'auto', flex: 1 }}>
        {GF_DEPARTMENTS.map((d) => <DeptRow key={d.id} color={d.color} name={lang === 'mk' ? d.mk : d.name} count={(tasks || []).filter((x) => x.dept === d.id).length} active={deptFilter === d.id} onClick={() => { setDeptFilter(deptFilter === d.id ? null : d.id); if (view !== 'myweek' && view !== 'board') setView('myweek'); }} />)}
      </div>
      <div onClick={() => setView('settings')} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, margin: 12, borderRadius: 'var(--r-md)', background: 'var(--surface-2)', cursor: 'pointer' }}>
        <Avatar name={me.name} size={34} color={me.color} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 'var(--fs-13)' }}>{me.name}</div>
          <div style={{ fontSize: 'var(--fs-11)', color: 'var(--text-body)', fontWeight: 600 }}>{GF_ROLES[me.role] ? GF_ROLES[me.role][lang] : me.roleLabel}</div>
        </div>
      </div>
    </aside>
  );
}

// ─────────────────────────────── Header ───────────────────────────────
function Header({ lang, setLang, theme, setTheme, onNew, onVoice, onOpenReport, onWorklog, onAssistant, me, query, setQuery, weekIdx, setWeekIdx }) {
  const t = GF_T[lang];
  return (
    <header style={{ height: 64, display: 'flex', alignItems: 'center', gap: 14, padding: '0 22px', background: 'var(--surface)', borderBottom: '1px solid var(--line)', flexShrink: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, maxWidth: 380, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '0 13px' }}>
        <span style={{ color: 'var(--text-muted)', display: 'inline-flex' }}>{I('Search', 16)}</span>
        <input id="gf-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.search} style={{ border: 'none', background: 'none', outline: 'none', padding: '10px 0', fontSize: 'var(--fs-13)', fontWeight: 500, width: '100%', fontFamily: 'inherit', color: 'var(--text-strong)' }} />
        {query && <span onClick={() => setQuery('')} style={{ cursor: 'pointer', color: 'var(--text-muted)', display: 'inline-flex' }}>{I('X', 14)}</span>}
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '3px 4px' }} title={['Jun 26 – Jul 2', 'Jul 3 – Jul 9', 'Jul 10 – Jul 16'][weekIdx]}>
        <IconButton size="sm" variant="ghost" disabled={weekIdx === 0} onClick={() => weekIdx > 0 && setWeekIdx(weekIdx - 1)}>{I('ChevronLeft', 16)}</IconButton>
        <span style={{ fontSize: 'var(--fs-12)', fontWeight: 700, minWidth: 92, textAlign: 'center', color: 'var(--text-strong)' }}>{WEEK_LABELS[lang][weekIdx]}</span>
        <IconButton size="sm" variant="ghost" disabled={weekIdx === 2} onClick={() => weekIdx < 2 && setWeekIdx(weekIdx + 1)}>{I('ChevronRight', 16)}</IconButton>
      </div>
      <Segmented options={[{ value: 'en', label: 'EN' }, { value: 'mk', label: 'МК' }]} value={lang} onChange={setLang} />
      <Button variant="primary" size="sm" icon={I('Plus', 16)} onClick={onNew}>{t.newtask}</Button>
      <Button variant="orange" size="sm" icon={I('Mic', 16)} onClick={onVoice}>{t.voice}</Button>
      <IconButton onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{I(theme === 'dark' ? 'Sun' : 'Moon', 18)}</IconButton>
      <IconButton onClick={onWorklog} title={lang === 'mk' ? 'Работни сесии' : 'Work sessions'}>{I('Clock', 18)}</IconButton>
      <IconButton active badge="3" onClick={onAssistant}>{I('Sparkles', 18)}</IconButton>
    </header>
  );
}

// ─────────────────────────────── Week strip ───────────────────────────────
function WeekStrip({ lang, day, setDay, weekIdx, setWeekIdx, tasks }) {
  const t = GF_T[lang];
  const counts = { Mon: 0, Tue: 0, Wed: 0, Thu: 0, Fri: 0 };
  (tasks || []).forEach((x) => (x.days || [x.day]).forEach((d) => { if (counts[d] != null) counts[d] += 1; }));
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '18px 24px 6px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800, letterSpacing: '-.01em' }}>{WEEK_LABELS[lang][weekIdx]}</span>
        <span style={{ fontSize: 'var(--fs-13)', color: 'var(--text-body)', fontWeight: 600 }}>{['Jun 26 – Jul 2', 'Jul 3 – Jul 9', 'Jul 10 – Jul 16'][weekIdx]}</span>
        {weekIdx === 1 && <Badge tone="green">{t.thisweek}</Badge>}
        <div style={{ flex: 1 }} />
        <IconButton size="sm" variant="ghost" disabled={weekIdx === 0} onClick={() => weekIdx > 0 && setWeekIdx(weekIdx - 1)}>{I('ChevronLeft', 18)}</IconButton>
        <IconButton size="sm" variant="ghost" disabled={weekIdx === 2} onClick={() => weekIdx < 2 && setWeekIdx(weekIdx + 1)}>{I('ChevronRight', 18)}</IconButton>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '8px 24px 4px' }}>
        {DAYS.map((d) => <DayPill key={d} day={lang === 'mk' ? ({Mon:'Пон',Tue:'Вто',Wed:'Сре',Thu:'Чет',Fri:'Пет'}[d]) : d} count={counts[d]} active={d === day} onClick={() => setDay(d === day ? null : d)} />)}
      </div>
    </div>
  );
}

// ─────────────────────────────── My Week ───────────────────────────────
function MyWeek({ lang, day, setDay, weekIdx, setWeekIdx, tasks, query, onCycle, onCheck, onNew, onEdit, onDelete, onOpen, canEdit, canDelete }) {
  const t = GF_T[lang];
  const [openId, setOpenId] = React.useState('T-4KZ9');
  const q = query.trim().toLowerCase();
  let shown = day ? tasks.filter((x) => x.day === day) : tasks;
  if (q) shown = shown.filter((x) => x.title.toLowerCase().includes(q) || (x.refCode || '').toLowerCase().includes(q) || (x.type || '').toLowerCase().includes(q));
  const done = shown.filter((x) => x.status === 'done').length;
  return (
    <div style={{ overflowY: 'auto', height: '100%' }}>
      <WeekStrip lang={lang} day={day} setDay={setDay} weekIdx={weekIdx} setWeekIdx={setWeekIdx} tasks={tasks} />
      <div style={{ margin: '12px 24px 4px', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', display: 'flex', alignItems: 'center', gap: 26, padding: '13px 18px', flexWrap: 'wrap' }}>
        {[[tasks.length + '', t.total], [done + '', STATUS_LABEL(lang, 'done')], [tasks.filter((x) => x.status === 'working').length + '', t.working], [tasks.filter((x) => x.status === 'stuck').length + '', t.stuck], ['Wed', t.busiest]].map(([v, l], i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 'var(--fs-19)', fontWeight: 800, letterSpacing: '-.02em' }}>{v}</span>
            <span style={{ fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-body)' }}>{l}</span>
          </div>
        ))}
      </div>
      <div style={{ padding: '10px 24px 40px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 2px 6px' }}>
          <span style={{ fontSize: 'var(--fs-17)', fontWeight: 800 }}>{day ? day : (lang === 'mk' ? 'Оваа недела' : 'This week')}</span>
          <Badge tone="neutral">{shown.length}</Badge>
        </div>
        {shown.length === 0 && (
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontWeight: 600, border: '1px dashed var(--line)', borderRadius: 'var(--r-lg)' }}>
            {q ? `${t.noresults} "${query}"` : t.notasks}
          </div>
        )}
        {shown.map((task) => (
          <div key={task.id} style={{ position: 'relative' }} className="gf-mw-card">
            <TaskCard task={{ ...task, deps: task._depObjs || [] }} lang={lang} expanded={openId === task.id} onToggle={() => setOpenId(openId === task.id ? null : task.id)}
              onStatusClick={() => onCycle(task.id)} onCheck={() => onCheck(task.id)}
              handoffTo={GF_HANDOFF[task.dept] ? DEPT_NAME(GF_HANDOFF[task.dept], lang) : null}
              onEdit={() => onEdit(task)} onAdvance={() => onCycle(task.id)}
              onDelete={() => onDelete(task.id)} canEdit={canEdit(task)} canDelete={canDelete} />
            <button onClick={(e) => { e.stopPropagation(); onOpen && onOpen(task); }} title={lang === 'mk' ? 'Отвори детали' : 'Open details'}
              style={{ position: 'absolute', top: 12, right: 12, width: 28, height: 28, borderRadius: 'var(--r-sm)', border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--text-muted)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', opacity: 0, transition: 'opacity var(--dur-1) var(--ease-out)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--primary)'; e.currentTarget.style.borderColor = 'var(--primary)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--line)'; }}>
              {I('Maximize2', 14)}
            </button>
          </div>
        ))}
        <div onClick={onNew} style={{ display: 'flex', gap: 10, alignItems: 'center', background: 'var(--surface)', border: '1px dashed var(--line)', borderRadius: 'var(--r-md)', padding: '12px 15px', cursor: 'pointer', color: 'var(--text-muted)', fontWeight: 600, fontSize: 'var(--fs-13)' }}>
          {I('Plus', 16)} {t.addtask}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────── Board ───────────────────────────────
function Board({ lang, tasks, query, onDrop, onOpen }) {
  const [overCol, setOverCol] = React.useState(null);
  const q = query.trim().toLowerCase();
  const filtered = q ? tasks.filter((x) => x.title.toLowerCase().includes(q)) : tasks;
  const cols = [
    { id: 'pending', label: STATUS_LABEL(lang, 'pending'), dot: 'var(--st-pending)' },
    { id: 'working', label: STATUS_LABEL(lang, 'working'), dot: 'var(--st-working)' },
    { id: 'review', label: STATUS_LABEL(lang, 'review'), dot: 'var(--st-review)' },
    { id: 'stuck', label: STATUS_LABEL(lang, 'stuck'), dot: 'var(--st-stuck)' },
    { id: 'done', label: STATUS_LABEL(lang, 'done'), dot: 'var(--st-done)' },
  ];
  return (
    <div style={{ overflow: 'auto', height: '100%', padding: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(200px, 1fr))', gap: 14, minWidth: 'min-content' }}>
        {cols.map((c) => {
          const items = filtered.filter((x) => x.status === c.id);
          return (
            <div key={c.id}
              onDragOver={(e) => { e.preventDefault(); setOverCol(c.id); }}
              onDragLeave={() => setOverCol((v) => (v === c.id ? null : v))}
              onDrop={(e) => { e.preventDefault(); const id = e.dataTransfer.getData('text/task'); setOverCol(null); if (id) onDrop(id, c.id); }}
              style={{ background: overCol === c.id ? 'var(--primary-soft)' : 'var(--surface-2)', border: '1px solid ' + (overCol === c.id ? 'var(--primary)' : 'var(--line)'), borderRadius: 'var(--r-lg)', padding: 12, minHeight: 200, transition: 'background var(--dur-ui), border-color var(--dur-ui)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '0 2px' }}>
                <span style={{ width: 9, height: 9, borderRadius: 999, background: c.dot }} />
                <span style={{ fontWeight: 700, fontSize: 'var(--fs-13)' }}>{c.label}</span>
                <Badge tone="neutral">{items.length}</Badge>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {items.length === 0 && <div style={{ padding: 14, textAlign: 'center', color: 'var(--text-faint)', fontSize: 'var(--fs-12)' }}>—</div>}
                {items.map((x) => (
                  <div key={x.id} draggable onClick={() => onOpen(x)}
                    onDragStart={(e) => { e.dataTransfer.setData('text/task', x.id); e.currentTarget.style.opacity = '.4'; }}
                    onDragEnd={(e) => { e.currentTarget.style.opacity = '1'; }}
                    style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderLeft: '3px solid ' + x.color, borderRadius: 'var(--r-md)', padding: 11, boxShadow: 'var(--sh-1)', cursor: 'grab', transition: 'opacity var(--dur-ui), box-shadow var(--dur-ui)' }}
                    onMouseEnter={(e) => e.currentTarget.style.boxShadow = 'var(--sh-2)'} onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'var(--sh-1)'}>
                    <div style={{ fontSize: 'var(--fs-10)', fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 5 }}>{DEPT_NAME(x.dept, lang)}</div>
                    <div style={{ fontSize: 'var(--fs-13)', fontWeight: 700, marginBottom: 9, lineHeight: 1.3 }}>{x.title}</div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <AvatarStack people={x.people} size={24} />
                      <PriorityTag priority={x.priority} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────── Dashboard ───────────────────────────────
function Dashboard({ lang, tasks }) {
  const t = GF_T[lang];
  const byStatus = ['done', 'working', 'review', 'stuck', 'pending'];
  const countBy = (s) => tasks.filter((x) => x.status === s).length;
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 16 }}>
        <KpiTile value={Math.round((countBy('done') / tasks.length) * 100) + '%'} label={t.completion} tone="green" icon={I('TrendingUp', 18)} />
        <KpiTile value={tasks.length} label={t.total} icon={I('ListChecks', 18)} />
        <KpiTile value={countBy('working')} label={t.working} tone="orange" icon={I('Loader', 18)} />
        <KpiTile value={countBy('stuck')} label={t.stuck} tone="red" icon={I('OctagonAlert', 18)} />
        <KpiTile value="Wed" label={t.busiest} tone="violet" icon={I('CalendarClock', 18)} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Panel title={lang === 'mk' ? 'По статус' : 'Completion by status'}>
          {byStatus.map((s) => <BarRow key={s} label={STATUS_LABEL(lang, s)} value={countBy(s)} max={tasks.length} color={STATUS_COLOR(s)} />)}
        </Panel>
        <Panel title={lang === 'mk' ? 'По оддел' : 'By department'}>
          {GF_DEPARTMENTS.map((d) => ({ d, n: tasks.filter((x) => x.dept === d.id).length })).filter((o) => o.n > 0).sort((a, b) => b.n - a.n).slice(0, 6).map(({ d, n }) => <BarRow key={d.id} label={lang === 'mk' ? d.mk : d.name} value={n} max={Math.max(...GF_DEPARTMENTS.map((z) => tasks.filter((x) => x.dept === z.id).length), 1)} dot={d.color} color={d.color} />)}
        </Panel>
        <Panel title={lang === 'mk' ? 'Оптоварување' : 'Workload'}>
          {[...GF_PEOPLE].sort((a, b) => b.active - a.active).slice(0, 4).map((p) => (
            <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Avatar name={p.name} size={30} />
              <div style={{ flex: 1 }}><div style={{ fontSize: 'var(--fs-13)', fontWeight: 700 }}>{p.name}</div><div style={{ fontSize: 'var(--fs-11)', color: 'var(--text-muted)', fontWeight: 600 }}>{GF_ROLES[p.role] ? GF_ROLES[p.role][lang] : p.roleLabel}</div></div>
              <Badge tone="neutral">{p.active}</Badge>
            </div>
          ))}
        </Panel>
        <Panel title={lang === 'mk' ? 'Блокери' : 'Blockers'}>
          {tasks.filter((x) => x.status === 'stuck').length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: 'var(--fs-13)', fontWeight: 600 }}>{lang === 'mk' ? 'Нема блокери 🎉' : 'None 🎉'}</div>}
          {tasks.filter((x) => x.status === 'stuck').map((x) => (
            <div key={x.id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', background: 'var(--red-soft)', borderRadius: 'var(--r-md)', padding: 12 }}>
              <span style={{ color: 'var(--red)', display: 'inline-flex', marginTop: 1 }}>{I('OctagonAlert', 16)}</span>
              <div><div style={{ fontSize: 'var(--fs-13)', fontWeight: 700, color: 'var(--red-700)' }}>{x.title}</div><div style={{ fontSize: 'var(--fs-12)', color: 'var(--red-700)', opacity: .85, marginTop: 2 }}>{x.blocker}</div></div>
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}
function Panel({ title, children }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', padding: 18, boxShadow: 'var(--sh-1)' }}>
      <div style={{ fontSize: 'var(--fs-14)', fontWeight: 800, marginBottom: 14 }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>{children}</div>
    </div>
  );
}

function STATUS_LABEL(lang, s) { return DS.STATUS[s][lang === 'mk' ? 'labelMk' : 'label']; }
function STATUS_COLOR(s) { return DS.STATUS[s].dot; }
window.STATUS_LABEL = STATUS_LABEL; window.STATUS_COLOR = STATUS_COLOR;
function DEPT_NAME(id, lang) { const d = GF_DEPARTMENTS.find((x) => x.id === id); return d ? (lang === 'mk' ? d.mk : d.name) : id; }

// ─────────────────────────────── Voice modal ───────────────────────────────
function VoiceModal({ onClose, onConfirm, lang }) {
  const L = lang === 'mk';
  const [stage, setStage] = React.useState('recording'); // recording | parsing | parsed
  const [live, setLive] = React.useState(true);
  const [transcript, setTranscript] = React.useState('');
  const bars = Array.from({ length: 22 }, (_, i) => 8 + Math.abs(Math.sin(i * 0.9)) * 40);
  const fullText = L
    ? 'Валидирај го HPLC методот за јачина за серија F27, висок приоритет, рок четврток.'
    : 'Validate the HPLC potency method for batch F27, high priority, due Thursday.';

  // stream transcript while recording
  React.useEffect(() => {
    if (stage !== 'recording' || !live) return;
    const words = fullText.split(' ');
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setTranscript(words.slice(0, i).join(' '));
      if (i >= words.length) clearInterval(id);
    }, 130);
    return () => clearInterval(id);
  }, [stage, live]);

  function parse() {
    setStage('parsing');
    setTimeout(() => setStage('parsed'), 1400);
  }

  const fields = [
    { l: L ? 'Наслов' : 'Title', v: L ? 'Валидирај HPLC метод' : 'Validate HPLC method', c: 96 },
    { l: L ? 'Оддел' : 'Department', v: L ? 'Контрола на квалитет' : 'Quality Control', c: 92 },
    { l: L ? 'Приоритет' : 'Priority', v: L ? 'Критичен' : 'Critical', c: 88 },
    { l: L ? 'Рок' : 'Due', v: L ? 'Четврток' : 'Thursday', c: 79 },
    { l: L ? 'Реф.' : 'Ref', v: 'PP-QC-012', c: 71 },
  ];
  const cColor = (c) => c >= 90 ? 'var(--green-600)' : c >= 78 ? 'var(--amber)' : 'var(--orange)';

  const footer = stage === 'parsed'
    ? <React.Fragment>
        <Button variant="secondary" onClick={() => { setStage('recording'); setTranscript(''); setLive(true); }}>{I('RotateCcw', 15)}{L ? 'Повтори' : 'Redo'}</Button>
        <Button onClick={onConfirm}>{I('Check', 15)}{L ? 'Создади задача' : 'Create task'}</Button>
      </React.Fragment>
    : stage === 'recording'
    ? <React.Fragment>
        <Button variant="secondary" onClick={() => setLive(!live)}>{live ? (L ? 'Паузирај' : 'Pause') : (L ? 'Продолжи' : 'Resume')}</Button>
        <Button onClick={parse} disabled={!transcript}>{I('Sparkles', 15)}{L ? 'Парсирај со AI' : 'Parse with AI'}</Button>
      </React.Fragment>
    : null;

  return (
    <Modal dark title={L ? 'Кажете ја задачата' : 'Speak your task'} onClose={onClose} width={460} footer={footer}>
      {stage === 'recording' && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, padding: '10px 0 4px' }}>
          <div style={{ position: 'relative', width: 118, height: 118, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ position: 'absolute', inset: 0, borderRadius: 999, background: 'rgba(255,122,26,.14)' }} />
            <span style={{ position: 'absolute', inset: 15, borderRadius: 999, background: 'rgba(255,122,26,.22)' }} />
            <button onClick={() => setLive(!live)} style={{ width: 78, height: 78, borderRadius: 999, background: 'var(--orange)', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', cursor: 'pointer', boxShadow: '0 10px 30px rgba(255,122,26,.5)' + (live ? ', 0 0 0 14px rgba(255,122,26,.12)' : '') }}>{I(live ? 'Mic' : 'Play', 30)}</button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 46 }}>
            {bars.map((h, i) => <span key={i} style={{ width: 4, borderRadius: 4, background: 'var(--orange)', height: live ? h : 8, transition: 'height .2s' }} />)}
          </div>
          <div style={{ minHeight: 44, fontSize: 'var(--fs-15)', fontWeight: 600, lineHeight: 1.5, textAlign: 'center', color: transcript ? 'var(--text-strong)' : 'var(--text-muted)', maxWidth: 380 }}>
            {transcript ? `“${transcript}${live ? '…' : ''}”` : (L ? 'Слушам…' : 'Listening…')}
          </div>
        </div>
      )}
      {stage === 'parsing' && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '40px 0' }}>
          <span style={{ color: 'var(--primary)', display: 'inline-flex', animation: 'gfSpin 1s linear infinite' }}>{I('LoaderCircle', 40)}</span>
          <div style={{ fontSize: 'var(--fs-14)', fontWeight: 700, color: 'var(--text-strong)' }}>{L ? 'AI ги извлекува полињата…' : 'AI is extracting fields…'}</div>
          <div style={{ fontSize: 'var(--fs-12)', fontWeight: 600, color: 'var(--text-muted)' }}>{L ? 'Наслов · Оддел · Приоритет · Рок' : 'Title · Department · Priority · Due'}</div>
        </div>
      )}
      {stage === 'parsed' && (
        <div style={{ padding: '4px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, fontSize: 'var(--fs-12)', fontWeight: 600, color: 'var(--text-muted)' }}>
            <span style={{ color: 'var(--primary)', display: 'inline-flex' }}>{I('Sparkles', 15)}</span>
            {L ? 'Извлечено од: ' : 'Parsed from: '}<span style={{ fontStyle: 'italic' }}>“{fullText}”</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {fields.map((f) => (
              <div key={f.l} style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '10px 13px' }}>
                <div style={{ width: 84, flexShrink: 0, fontSize: 'var(--fs-10)', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.03em' }}>{f.l}</div>
                <div style={{ flex: 1, fontSize: 'var(--fs-13)', fontWeight: 700, color: 'var(--text-strong)' }}>{f.v}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 40, height: 4, borderRadius: 999, background: 'var(--line)', overflow: 'hidden' }}><span style={{ display: 'block', height: '100%', width: `${f.c}%`, background: cColor(f.c) }} /></span>
                  <span style={{ fontSize: 'var(--fs-10)', fontWeight: 800, color: cColor(f.c), width: 28 }}>{f.c}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
}

// ─────────────────────────────── Add / Edit task ───────────────────────────────
function AddTaskModal({ onClose, onCreate, lang, editTask }) {
  const L = lang === 'mk';
  const isEdit = !!editTask;
  const [title, setTitle] = React.useState(editTask ? editTask.title : '');
  const [desc, setDesc] = React.useState(editTask ? (editTask.desc || '') : '');
  const [pri, setPri] = React.useState(editTask ? editTask.priority : 'high');
  const [dept, setDept] = React.useState(editTask ? editTask.dept : GF_DEPARTMENTS[0].id);
  const [type, setType] = React.useState(editTask ? (editTask.type || 'validation') : 'validation');
  const [owner, setOwner] = React.useState(editTask ? editTask.owner : GF_PEOPLE[0].id);
  const [helpers, setHelpers] = React.useState(editTask ? (editTask.helpers || []) : []);
  const [days, setDays] = React.useState(editTask ? (editTask.days || []) : ['Mon']);
  const [est, setEst] = React.useState(editTask ? (editTask.sessionHours != null ? String(editTask.sessionHours) : '') : '');
  const [rec, setRec] = React.useState(editTask ? (editTask.recurrence || '') : '');
  const [due, setDue] = React.useState(editTask ? (editTask.due || '') : '');
  const [ref, setRef] = React.useState(editTask ? (editTask.ref || '') : '');
  const [tags, setTags] = React.useState(editTask ? (editTask.tags || []).join(', ') : '');
  const [err, setErr] = React.useState(false);
  const priLabel = { critical: L ? 'Критично' : 'Critical', high: L ? 'Високо' : 'High', medium: L ? 'Средно' : 'Medium', low: L ? 'Ниско' : 'Low' };
  const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const dayLabel = { Mon: L ? 'Пон' : 'Mon', Tue: L ? 'Вто' : 'Tue', Wed: L ? 'Сре' : 'Wed', Thu: L ? 'Чет' : 'Thu', Fri: L ? 'Пет' : 'Fri' };
  const recLabel = { '': L ? 'Без' : 'None', daily: L ? 'Дневно' : 'Daily', weekly: L ? 'Неделно' : 'Weekly', monthly: L ? 'Месечно' : 'Monthly' };
  const toggleHelper = (id) => setHelpers((hs) => hs.includes(id) ? hs.filter((x) => x !== id) : [...hs, id]);
  const toggleDay = (d) => setDays((ds) => ds.includes(d) ? ds.filter((x) => x !== d) : [...ds, d]);
  function submit() {
    if (!title.trim()) { setErr(true); return; }
    onCreate({ id: editTask && editTask.id, title: title.trim(), desc: desc.trim(), priority: pri, dept, type, owner,
      helpers: helpers.filter((h) => h !== owner), days: days.length ? days : ['Mon'],
      sessionHours: est.trim() ? parseFloat(est) : null, recurrence: rec || null,
      due: due || null, ref: ref.trim() || null, tags: tags.split(',').map((s) => s.trim()).filter(Boolean) });
  }
  return (
    <Modal title={isEdit ? (L ? 'Уреди задача' : 'Edit task') : (L ? 'Нова задача' : 'Add a task')} onClose={onClose} width={520}
      footer={<React.Fragment><Button variant="secondary" onClick={onClose}>{L ? 'Откажи' : 'Cancel'}</Button><Button onClick={submit}>{isEdit ? (L ? 'Зачувај' : 'Save changes') : (L ? 'Креирај' : 'Create task')}</Button></React.Fragment>}>
      <Field label={L ? 'Наслов' : 'Task title'} required hint={err ? (L ? 'Задолжително поле' : 'This field is required') : null}>
        <Input placeholder={L ? 'Валидирај HPLC метод…' : 'Validate HPLC method…'} autoFocus value={title}
          onChange={(e) => { setTitle(e.target.value); if (err) setErr(false); }} style={err ? { borderColor: 'var(--red)' } : {}} />
      </Field>
      <Field label={L ? 'Опис' : 'Description'}><Textarea placeholder={L ? 'Додади детали…' : 'Add detail…'} value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Field label={L ? 'Оддел' : 'Department'}><PopSelect value={dept} onChange={setDept} title={L ? 'Оддел' : 'Department'} options={GF_DEPARTMENTS.map((d) => ({ value: d.id, label: L ? d.mk : d.name, color: d.color }))} /></Field>
        <Field label={L ? 'Носител' : 'Owner'}><PopSelect value={owner} onChange={setOwner} title={L ? 'Носител' : 'Owner'} options={GF_PEOPLE.map((p) => ({ value: p.id, label: p.name, color: p.color }))} /></Field>
      </div>
      <Field label={L ? 'Соработници (Одговорни)' : 'Helpers (Responsible)'}>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          {GF_PEOPLE.filter((p) => p.id !== owner).map((p) => <Chip key={p.id} selected={helpers.includes(p.id)} onClick={() => toggleHelper(p.id)}>{p.name.split(' ')[0]}</Chip>)}
        </div>
      </Field>
      <Field label={L ? 'Тип' : 'Type'}>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          {Object.entries(GF_TASK_TYPES).map(([k, v]) => <Chip key={k} selected={type === k} onClick={() => setType(k)}>{v[lang]}</Chip>)}
        </div>
      </Field>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Field label={L ? 'Рок' : 'Due date'}><Input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></Field>
        <Field label={L ? 'Реф. код' : 'Ref code'}><Input placeholder="PP-QC-012" value={ref} onChange={(e) => setRef(e.target.value)} /></Field>
      </div>
      <Field label={L ? 'Закажи за денови' : 'Schedule for days'}>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          {WEEKDAYS.map((d) => <Chip key={d} selected={days.includes(d)} onClick={() => toggleDay(d)}>{dayLabel[d]}</Chip>)}
        </div>
      </Field>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Field label={L ? 'Проценети часови' : 'Estimated hours'}><Input type="number" min="0" step="0.5" placeholder="0" value={est} onChange={(e) => setEst(e.target.value)} /></Field>
        <Field label={L ? 'Повторување' : 'Recurrence'}><PopSelect value={rec} onChange={setRec} title={L ? 'Повторување' : 'Recurrence'} options={['', 'daily', 'weekly', 'monthly'].map((r) => ({ value: r, label: recLabel[r] }))} /></Field>
      </div>
      <Field label={L ? 'Приоритет' : 'Priority'}>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          {['critical', 'high', 'medium', 'low'].map((p) => <Chip key={p} selected={pri === p} onClick={() => setPri(p)}>{priLabel[p]}</Chip>)}
        </div>
      </Field>
      <Field label={L ? 'Ознаки (одвоени со запирка)' : 'Tags (comma-separated)'}><Input placeholder="potency, batch-F27" value={tags} onChange={(e) => setTags(e.target.value)} /></Field>
    </Modal>
  );
}

// ─────────────────────────────── User profile / edit modal ───────────────────────────────
const AVATAR_COLORS = ['#2F6BFF', '#15A86B', '#E0603A', '#7A5BE0', '#0891B2', '#D4A017', '#DB2777', '#0EA5A5', '#F97316', '#6366F1'];
function UserModal({ person, lang, onClose, canManage, isActive, onSetActive, onSave, onRemove }) {
  const L = lang === 'mk';
  const isNew = !person;
  const [editing, setEditing] = React.useState(isNew);
  const [name, setName] = React.useState(person ? person.name : '');
  const [role, setRole] = React.useState(person ? person.role : 'operator');
  const [dept, setDept] = React.useState(person ? person.dept : GF_DEPARTMENTS[0].id);
  const [color, setColor] = React.useState(person ? person.color : AVATAR_COLORS[0]);
  const [err, setErr] = React.useState(false);

  if (editing) {
    const save = () => { if (!name.trim()) { setErr(true); return; } onSave({ id: person && person.id, name: name.trim(), role, dept, color }); };
    return (
      <Modal title={isNew ? (L ? 'Нов член' : 'Add member') : (L ? 'Уреди член' : 'Edit member')} onClose={onClose} width={460}
        footer={<React.Fragment>{!isNew && <Button variant="secondary" onClick={() => setEditing(false)}>{L ? 'Откажи' : 'Cancel'}</Button>}<Button onClick={save}>{isNew ? (L ? 'Додади' : 'Add member') : (L ? 'Зачувај' : 'Save')}</Button></React.Fragment>}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
          <Avatar name={name || '?'} size={54} color={color} />
          <div style={{ fontSize: 'var(--fs-13)', fontWeight: 600, color: 'var(--text-muted)' }}>{L ? 'Преглед на аватар' : 'Avatar preview'}</div>
        </div>
        <Field label={L ? 'Име' : 'Full name'} required hint={err ? (L ? 'Задолжително' : 'Required') : null}>
          <Input placeholder={L ? 'на пр. Ана Николова' : 'e.g. Ana Nikolova'} autoFocus value={name} onChange={(e) => { setName(e.target.value); if (err) setErr(false); }} style={err ? { borderColor: 'var(--red)' } : {}} />
        </Field>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label={L ? 'Улога' : 'Role'}><PopSelect value={role} onChange={setRole} title={L ? 'Улога' : 'Role'} options={Object.keys(GF_ROLES).map((r) => ({ value: r, label: GF_ROLES[r][lang] }))} /></Field>
          <Field label={L ? 'Оддел' : 'Department'}><PopSelect value={dept} onChange={setDept} title={L ? 'Оддел' : 'Department'} options={GF_DEPARTMENTS.map((d) => ({ value: d.id, label: L ? d.mk : d.name, color: d.color }))} /></Field>
        </div>
        <Field label={L ? 'Боја на аватар' : 'Avatar color'}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {AVATAR_COLORS.map((c) => <span key={c} onClick={() => setColor(c)} style={{ width: 26, height: 26, borderRadius: 999, background: c, cursor: 'pointer', boxShadow: color === c ? '0 0 0 3px var(--surface), 0 0 0 5px ' + c : 'none' }} />)}
          </div>
        </Field>
      </Modal>
    );
  }

  const pdept = GF_DEPARTMENTS.find((d) => d.id === person.dept) || {};
  const perms = GF_ROLE_PERMS(person.role);
  const permRows = [
    [L ? 'Создавање задачи' : 'Create tasks', perms.create],
    [L ? 'Уреди сите' : 'Edit any task', perms.editAny],
    [L ? 'Избриши сите' : 'Delete any task', perms.deleteAny],
    [L ? 'Статус: сите' : 'Change any status', perms.status === 'any'],
    [L ? 'Преглед на тим' : 'View team', perms.team],
  ];
  return (
    <Modal title={L ? 'Профил' : 'Team member'} onClose={onClose} width={460}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
        <Avatar name={person.name} size={54} color={person.color} />
        <div>
          <div style={{ fontSize: 'var(--fs-19)', fontWeight: 800 }}>{person.name}</div>
          <div style={{ fontSize: 'var(--fs-13)', fontWeight: 600, color: 'var(--text-body)' }}>{GF_ROLES[person.role] ? GF_ROLES[person.role][lang] : person.role}</div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 6, fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-muted)' }}>
            <span style={{ width: 9, height: 9, borderRadius: 999, background: pdept.color }} />{L ? pdept.mk : pdept.name}
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 18 }}>
        <div style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '12px 14px' }}>
          <div style={{ fontSize: 'var(--fs-28)', fontWeight: 800, color: 'var(--primary)' }}>{person.active}</div>
          <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-muted)' }}>{L ? 'Активни задачи' : 'Active tasks'}</div>
        </div>
        <div style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '12px 14px' }}>
          <div style={{ fontSize: 'var(--fs-28)', fontWeight: 800, color: 'var(--st-done)' }}>{person.done}</div>
          <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-muted)' }}>{L ? 'Завршени' : 'Completed'}</div>
        </div>
      </div>
      <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, letterSpacing: '.04em', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>{L ? 'Дозволи' : 'Permissions'}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {permRows.map(([label, on]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 0', fontSize: 'var(--fs-13)', fontWeight: 600, color: on ? 'var(--text-strong)' : 'var(--text-faint)' }}>
            <span style={{ color: on ? 'var(--st-done)' : 'var(--text-faint)' }}>{I(on ? 'Check' : 'Minus', 16)}</span>{label}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 20, flexWrap: 'wrap' }}>
        {isActive
          ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--st-done)', background: 'var(--st-done-soft)', borderRadius: 999, padding: '8px 13px' }}>{I('Check', 15)}{L ? 'Активен корисник' : 'Active user'}</span>
          : <Button variant="secondary" onClick={() => { onSetActive(person.id); onClose(); }}>{I('UserCheck', 15)}&nbsp;{L ? 'Постави како активен' : 'Set as active'}</Button>}
        <div style={{ flex: 1 }} />
        {canManage && <Button variant="secondary" onClick={() => setEditing(true)}>{L ? 'Уреди' : 'Edit'}</Button>}
        {canManage && !isActive && <Button variant="secondary" onClick={() => { onRemove(person.id); onClose(); }} style={{ color: 'var(--red)' }}>{L ? 'Отстрани' : 'Remove'}</Button>}
      </div>
    </Modal>
  );
}

// ─────────────────────────────── Worklog modal ───────────────────────────────
function WorklogModal({ lang, onClose }) {
  const L = lang === 'mk';
  const classes = {
    regular:  { label: L ? 'Редовно' : 'Regular',  bg: 'var(--st-done-soft)', fg: 'var(--st-done)' },
    overtime: { label: L ? 'Прекувремено' : 'Overtime', bg: 'var(--orange-soft)', fg: 'var(--orange-700)' },
    night:    { label: L ? 'Ноќна' : 'Night',    bg: 'var(--av-violet-soft, #ECE6FB)', fg: '#7A5BE0' },
    weekend:  { label: L ? 'Викенд' : 'Weekend',  bg: 'var(--st-stuck-soft)', fg: 'var(--st-stuck)' },
  };
  const sessions = [
    { day: 'Mon', who: 'blagoj', task: 'T-4KZ9', from: '08:00', to: '11:30', h: 3.5, cls: 'regular' },
    { day: 'Mon', who: 'ivo', task: 'T-2M1P', from: '18:00', to: '20:00', h: 2, cls: 'overtime' },
    { day: 'Tue', who: 'blagoj', task: 'T-4KZ9', from: '22:00', to: '01:00', h: 3, cls: 'night' },
    { day: 'Wed', who: 'goran', task: 'T-9F3B', from: '09:00', to: '11:00', h: 2, cls: 'regular' },
    { day: 'Sat', who: 'elena', task: 'T-7B2N', from: '10:00', to: '13:00', h: 3, cls: 'weekend' },
  ];
  const total = sessions.reduce((s, x) => s + x.h, 0);
  return (
    <Modal title={L ? 'Работни сесии' : 'Work sessions'} onClose={onClose} width={560}
      footer={<div style={{ marginRight: 'auto', fontSize: 'var(--fs-13)', fontWeight: 700, color: 'var(--text-body)' }}>{L ? 'Вкупно' : 'Total'}: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-strong)' }}>{total.toFixed(1)}h</span></div>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {sessions.map((s, i) => {
          const c = classes[s.cls]; const p = GF_PERSON(s.who);
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: 'var(--surface-2)', border: '1px solid var(--line-2)', borderRadius: 'var(--r-sm)', fontSize: 'var(--fs-12)' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', width: 30 }}>{s.day}</span>
              <Avatar name={p.name} size={24} color={p.color} />
              <span style={{ fontWeight: 700, flex: 1 }}>{p.name}</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-body)' }}>{s.from}–{s.to}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{s.h}h</span>
              <span style={{ fontSize: 'var(--fs-10)', fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', padding: '2px 8px', borderRadius: 999, background: c.bg, color: c.fg, whiteSpace: 'nowrap' }}>{c.label}</span>
            </div>
          );
        })}
      </div>
    </Modal>
  );
}

// ─────────────────────────────── Task detail (from Board) ───────────────────────────────
// Type-driven subtask step templates → meaningful checklist labels
const SUBTASK_TEMPLATES = {
  validation: [['Equilibrate column & prep mobile phase','Еквилибрирај колона и подготви мобилна фаза'],['Run system suitability','Изврши системска подобност'],['Linearity across levels','Линеарност по нивоа'],['Precision / repeatability','Прецизност / повторливост'],['Compile validation report','Состави извештај за валидација']],
  lab: [['Draw samples per formula','Земи мостри по формула'],['Run pass/fail gates','Изврши порти за помин/пад'],['Record disposition','Запиши диспозиција'],['Log to LIMS','Запиши во LIMS']],
  sop: [['Draft revision','Нацрт ревизија'],['Internal review','Внатрешен преглед'],['QA approval','Одобрување од КО'],['Publish & train','Објави и обучи']],
  capa: [['Root-cause analysis','Анализа на основна причина'],['Define action plan','Дефинирај акционен план'],['Implement corrective action','Спроведи корективна акција'],['Verify effectiveness','Потврди ефективност']],
  _default: [['Prepare','Подготви'],['Execute','Изврши'],['Verify','Потврди'],['Sign off','Потпиши']],
};
function buildSubs(task) {
  const n = task.subCount || 0;
  const tpl = SUBTASK_TEMPLATES[task.type] || SUBTASK_TEMPLATES._default;
  return Array.from({ length: n }, (_, i) => tpl[i % tpl.length]);
}

function DetailSection({ icon, title, right, children }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
        <span style={{ color: 'var(--text-muted)', display: 'inline-flex' }}>{I(icon, 15)}</span>
        <div style={{ fontSize: 'var(--fs-11)', fontWeight: 800, letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>{title}</div>
        <div style={{ flex: 1 }} />
        {right}
      </div>
      {children}
    </div>
  );
}

function TaskDetailModal({ task, lang, allTasks, canEdit, onClose, onCycle, onCheck }) {
  const L = lang === 'mk';
  const initialSubs = React.useMemo(() => buildSubs(task).map((s, i) => ({ label: s[L ? 1 : 0], done: i < (task.subDone || 0) })), [task.id, L]);
  const [subs, setSubs] = React.useState(initialSubs);
  React.useEffect(() => { setSubs(buildSubs(task).map((s, i) => ({ label: s[L ? 1 : 0], done: i < (task.subDone || 0) }))); }, [task.id, L]);
  const [notes, setNotes] = React.useState(task.notes || []);
  const [draft, setDraft] = React.useState('');
  const [ack, setAck] = React.useState(task.ack || null); // 'accepted' | 'declined' | null
  if (!task) return null;

  const doneCount = subs.filter((s) => s.done).length;
  const owner = GF_PERSON(task.owner);
  const helpers = (task.helpers || []).map(GF_PERSON);
  const deps = (task.deps || []).map((id) => (allTasks || []).find((t) => t.id === id)).filter(Boolean);
  const typeLabel = GF_TASK_TYPES[task.type] ? GF_TASK_TYPES[task.type][lang] : task.type;
  const chip = (label, val, tone) => (
    <div style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '8px 11px', minWidth: 0 }}>
      <div style={{ fontSize: 'var(--fs-10)', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 'var(--fs-13)', fontWeight: 700, color: tone || 'var(--text-strong)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{val}</div>
    </div>
  );

  function toggleSub(i) {
    if (!canEdit) return;
    setSubs((s) => s.map((x, j) => j === i ? { ...x, done: !x.done } : x));
  }
  function addNote() {
    const n = draft.trim();
    if (!n) return;
    setNotes((ns) => [...ns, { d: L ? 'Денес' : 'Today', n }]);
    setDraft('');
  }

  return (
    <Modal title={task.title} onClose={onClose} width={560}>
      {/* status + priority + assignment ack */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <StatusPill status={task.status} lang={lang} onClick={canEdit ? () => onCycle(task.id) : undefined} />
        <PriorityTag priority={task.priority} />
        {task.overdue && <Badge tone="red">{I('CalendarClock', 12)}{L ? 'Задоцнета' : 'Overdue'}</Badge>}
        <div style={{ flex: 1 }} />
        {ack === 'accepted' && <Badge tone="green">{I('Check', 12)}{L ? 'Прифатена' : 'Accepted'}</Badge>}
        {ack === 'declined' && <Badge tone="red">{I('X', 12)}{L ? 'Одбиена' : 'Declined'}</Badge>}
      </div>

      {/* blocker banner */}
      {task.status === 'stuck' && task.blocker && (
        <div style={{ marginTop: 14, display: 'flex', gap: 9, alignItems: 'flex-start', background: 'color-mix(in srgb, var(--red) 10%, var(--surface))', border: '1px solid color-mix(in srgb, var(--red) 35%, var(--line))', borderRadius: 'var(--r-md)', padding: '11px 13px' }}>
          <span style={{ color: 'var(--red)', display: 'inline-flex', flexShrink: 0, marginTop: 1 }}>{I('OctagonAlert', 16)}</span>
          <div>
            <div style={{ fontSize: 'var(--fs-11)', fontWeight: 800, color: 'var(--red)', textTransform: 'uppercase', letterSpacing: '.04em' }}>{L ? 'Блокатор' : 'Blocker'}</div>
            <div style={{ fontSize: 'var(--fs-13)', fontWeight: 600, color: 'var(--text-strong)', marginTop: 2 }}>{task.blocker}</div>
          </div>
        </div>
      )}

      {/* meta grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 14 }}>
        {chip(L ? 'Реф.' : 'Ref', task.ref || '—')}
        {chip(L ? 'Тип' : 'Type', typeLabel)}
        {chip(L ? 'Оддел' : 'Dept', DEPT_NAME(task.dept, lang))}
        {chip(L ? 'Рок' : 'Due', task.due || '—', task.overdue ? 'var(--red)' : null)}
      </div>

      {task.description && <div style={{ marginTop: 14, fontSize: 'var(--fs-13)', lineHeight: 1.55, color: 'var(--text-body)' }}>{task.description}</div>}

      {/* people / RACI */}
      <DetailSection icon="Users" title={L ? 'Луѓе' : 'People'}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 999, padding: '4px 12px 4px 4px' }}>
            <Avatar name={owner.name} color={owner.color} size={26} />
            <div><div style={{ fontSize: 'var(--fs-12)', fontWeight: 700 }}>{owner.name}</div><div style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: 'var(--primary)' }}>{L ? 'Носител' : 'Owner'}</div></div>
          </div>
          {helpers.map((h) => (
            <div key={h.name} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 999, padding: '4px 12px 4px 4px' }}>
              <Avatar name={h.name} color={h.color} size={26} />
              <div><div style={{ fontSize: 'var(--fs-12)', fontWeight: 700 }}>{h.name}</div><div style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: 'var(--text-muted)' }}>{L ? 'Помош' : 'Helper'}</div></div>
            </div>
          ))}
        </div>
      </DetailSection>

      {/* subtasks / steps */}
      {subs.length > 0 && (
        <DetailSection icon="ListChecks" title={L ? 'Чекори' : 'Steps'} right={<div style={{ fontSize: 'var(--fs-11)', fontWeight: 800, color: 'var(--text-muted)' }}>{doneCount}/{subs.length}</div>}>
          <div style={{ height: 5, borderRadius: 999, background: 'var(--surface-2)', overflow: 'hidden', marginBottom: 10 }}>
            <div style={{ height: '100%', width: `${(doneCount / subs.length) * 100}%`, background: 'var(--primary)', borderRadius: 999, transition: 'width var(--dur-2) var(--ease-out)' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {subs.map((s, i) => (
              <button key={i} onClick={() => toggleSub(i)} disabled={!canEdit} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 9px', borderRadius: 'var(--r-sm)', border: 'none', background: 'transparent', cursor: canEdit ? 'pointer' : 'default', textAlign: 'left', width: '100%' }} onMouseEnter={(e) => canEdit && (e.currentTarget.style.background = 'var(--surface-2)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                <span style={{ width: 19, height: 19, flexShrink: 0, borderRadius: 6, border: `2px solid ${s.done ? 'var(--primary)' : 'var(--line-strong, var(--line))'}`, background: s.done ? 'var(--primary)' : 'transparent', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{s.done && I('Check', 12)}</span>
                <span style={{ fontSize: 'var(--fs-13)', fontWeight: 600, color: s.done ? 'var(--text-muted)' : 'var(--text-strong)', textDecoration: s.done ? 'line-through' : 'none' }}>{s.label}</span>
              </button>
            ))}
          </div>
        </DetailSection>
      )}

      {/* dependencies */}
      {deps.length > 0 && (
        <DetailSection icon="GitBranch" title={L ? 'Зависности' : 'Dependencies'}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {deps.map((d) => (
              <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '9px 11px' }}>
                <span style={{ fontSize: 'var(--fs-10)', fontWeight: 800, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{d.id}</span>
                <span style={{ flex: 1, fontSize: 'var(--fs-12)', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.title}</span>
                <StatusPill status={d.status} lang={lang} />
              </div>
            ))}
          </div>
        </DetailSection>
      )}

      {/* progress notes */}
      <DetailSection icon="MessageSquareText" title={L ? 'Белешки за напредок' : 'Progress notes'}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {notes.length === 0 && <div style={{ fontSize: 'var(--fs-12)', color: 'var(--text-muted)', fontWeight: 600 }}>{L ? 'Сè уште нема белешки.' : 'No notes yet.'}</div>}
          {notes.map((n, i) => (
            <div key={i} style={{ display: 'flex', gap: 10 }}>
              <div style={{ width: 44, flexShrink: 0, fontSize: 'var(--fs-10)', fontWeight: 800, color: 'var(--text-muted)', paddingTop: 2, textTransform: 'uppercase' }}>{n.d}</div>
              <div style={{ fontSize: 'var(--fs-13)', fontWeight: 600, color: 'var(--text-body)', borderLeft: '2px solid var(--line)', paddingLeft: 10 }}>{n.n}</div>
            </div>
          ))}
          {canEdit && (
            <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
              <Input placeholder={L ? 'Додади белешка…' : 'Add a note…'} value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addNote()} />
              <Button variant="secondary" onClick={addNote}>{I('Plus', 15)}</Button>
            </div>
          )}
        </div>
      </DetailSection>

      {/* assignment lifecycle footer */}
      {!ack && canEdit && (
        <div style={{ display: 'flex', gap: 9, marginTop: 18, paddingTop: 16, borderTop: '1px solid var(--line)' }}>
          <Button variant="primary" onClick={() => setAck('accepted')} style={{ flex: 1 }}>{I('Check', 15)}{L ? 'Прифати задача' : 'Accept task'}</Button>
          <Button variant="ghost" onClick={() => setAck('declined')} style={{ flex: 1 }}>{I('X', 15)}{L ? 'Одбиј' : 'Decline'}</Button>
        </div>
      )}
    </Modal>
  );
}

// ─────────────────────────────── Assistant panel ───────────────────────────────
function AssistantPanel({ lang, tasks, onClose, onOpenTask }) {
  const L = lang === 'mk';
  const stuck = tasks.filter((x) => x.status === 'stuck');
  const overdue = tasks.filter((x) => x.overdue);
  const suggestions = L
    ? ['Што е блокирано оваа недела?', 'Резимирај ги задачите на QC', 'Кои задачи се задоцнети?']
    : ['What is blocked this week?', 'Summarize QC tasks', 'Which tasks are overdue?'];
  const [msgs, setMsgs] = React.useState([
    { role: 'ai', text: L ? 'Здраво! Јас сум GrowFlow асистентот. Прашај ме за задачите, блокадите или планот за неделата.' : "Hi! I'm the GrowFlow assistant. Ask me about tasks, blockers, or this week's plan." },
  ]);
  const [input, setInput] = React.useState('');
  const [typing, setTyping] = React.useState(false);
  const [mode, setMode] = React.useState('ask'); // ask | draft
  const [tone, setTone] = React.useState('formal');
  const [purpose, setPurpose] = React.useState('handoff');
  const [drafting, setDrafting] = React.useState(false);
  const [draftOut, setDraftOut] = React.useState('');
  const [copied, setCopied] = React.useState(false);
  const tones = [
    { id: 'formal', en: 'Formal', mk: 'Формален' },
    { id: 'friendly', en: 'Friendly', mk: 'Пријателски' },
    { id: 'direct', en: 'Direct', mk: 'Директен' },
    { id: 'concise', en: 'Concise', mk: 'Концизен' },
  ];
  const purposes = [
    { id: 'handoff', en: 'Dept handoff note', mk: 'Белешка за предавање' },
    { id: 'escalate', en: 'Blocker escalation', mk: 'Ескалација на блокада' },
    { id: 'update', en: 'Weekly status update', mk: 'Неделен статус' },
    { id: 'reminder', en: 'Task reminder', mk: 'Потсетник за задача' },
  ];
  function composeDraft() {
    const stuckOne = stuck[0];
    const map = {
      handoff: {
        formal: 'Please be advised that batch F27 has completed post-curing and is ready for QC intake. Kindly confirm receipt and schedule sampling at your earliest convenience.',
        friendly: "Hi team — F27 just wrapped post-curing and it's all yours for QC intake! Let me know when you can slot in the sampling. Thanks!",
        direct: 'F27 is done post-curing. QC intake needed now. Confirm receipt and sampling slot.',
        concise: 'F27 ready for QC intake. Confirm + schedule sampling.',
      },
      escalate: {
        formal: `The following task is blocked and requires attention: "${stuckOne ? stuckOne.title : 'QC water verdict'}". ${stuckOne && stuckOne.blocker ? stuckOne.blocker + ' ' : ''}Please advise on resolution to avoid downstream delay.`,
        friendly: `Quick heads-up — we're stuck on "${stuckOne ? stuckOne.title : 'the QC water verdict'}" and it's holding things up. Could you help us get it moving?`,
        direct: `Blocked: "${stuckOne ? stuckOne.title : 'QC water verdict'}". Need resolution today — downstream tasks are waiting.`,
        concise: `Blocker: ${stuckOne ? stuckOne.title : 'QC water verdict'}. Needs resolution today.`,
      },
      update: {
        formal: `This week the team has ${tasks.filter((t) => t.status === 'done').length} completed and ${stuck.length} blocked task(s). Priorities remain on schedule with the exception of the noted QC blocker.`,
        friendly: `Week in review: ${tasks.filter((t) => t.status === 'done').length} done and ${stuck.length} blocked — mostly on track apart from the QC snag we're clearing.`,
        direct: `Status: ${tasks.filter((t) => t.status === 'done').length} done, ${stuck.length} blocked. On track except QC blocker.`,
        concise: `${tasks.filter((t) => t.status === 'done').length} done · ${stuck.length} blocked · QC blocker open.`,
      },
      reminder: {
        formal: 'This is a courtesy reminder that your assigned task is due Thursday. Please ensure progress notes are recorded ahead of the deadline.',
        friendly: 'Friendly nudge — your task is due Thursday! Drop a progress note when you get a sec 🙂',
        direct: 'Reminder: task due Thursday. Log progress before then.',
        concise: 'Due Thursday. Log progress.',
      },
    };
    const mkMap = {
      handoff: 'Серијата F27 е завршена по сушење и е подготвена за прием во КК. Ве молиме потврдете прием и закажете земање мостри.',
      escalate: `Задачата „${stuckOne ? stuckOne.title : 'вердикт за QC вода'}" е блокирана и бара внимание. Ве молиме за решение за да избегнеме доцнење.`,
      update: `Оваа недела: ${tasks.filter((t) => t.status === 'done').length} завршени, ${stuck.length} блокирани. На тек, освен блокадата во КК.`,
      reminder: 'Потсетник: вашата задача е со рок четврток. Запишете белешка за напредок пред рокот.',
    };
    return L ? mkMap[purpose] : map[purpose][tone];
  }
  function generate() {
    setDrafting(true); setDraftOut(''); setCopied(false);
    setTimeout(() => { setDrafting(false); setDraftOut(composeDraft()); }, 900);
  }
  const bodyRef = React.useRef(null);
  React.useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight; }, [msgs, typing]);

  function answer(q) {
    const ql = q.toLowerCase();
    if (ql.includes('block') || ql.includes('блок') || ql.includes('stuck')) {
      if (!stuck.length) return L ? 'Нема блокирани задачи. 🎉' : 'Nothing is blocked right now.';
      return (L ? 'Блокирани задачи:\n' : 'Blocked tasks:\n') + stuck.map((x) => `• ${x.title}${x.blocker ? ' — ' + x.blocker : ''}`).join('\n');
    }
    if (ql.includes('overdue') || ql.includes('задоцн') || ql.includes('доцн')) {
      if (!overdue.length) return L ? 'Нема задоцнети задачи.' : 'No overdue tasks.';
      return (L ? 'Задоцнети:\n' : 'Overdue:\n') + overdue.map((x) => `• ${x.title} (${x.due})`).join('\n');
    }
    if (ql.includes('qc') || ql.includes('quality') || ql.includes('квалит')) {
      const qc = tasks.filter((x) => x.dept === 'qc' || x.dept === 'qa');
      return (L ? `${qc.length} задачи во QC/QA:\n` : `${qc.length} QC/QA tasks:\n`) + qc.map((x) => `• ${x.title} — ${STATUS_LABEL(lang, x.status)}`).join('\n');
    }
    const done = tasks.filter((x) => x.status === 'done').length;
    return L
      ? `Оваа недела: ${tasks.length} задачи, ${done} завршени, ${stuck.length} блокирани. Најголем ризик е блокадата во QC.`
      : `This week: ${tasks.length} tasks, ${done} done, ${stuck.length} blocked. Biggest risk is the QC blocker.`;
  }
  function send(q) {
    const text = (q ?? input).trim(); if (!text) return;
    setMsgs((m) => [...m, { role: 'user', text }]); setInput(''); setTyping(true);
    setTimeout(() => { setTyping(false); setMsgs((m) => [...m, { role: 'ai', text: answer(text) }]); }, 700);
  }
  return (
    <React.Fragment>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(22,35,59,.35)', backdropFilter: 'blur(3px)', zIndex: 640, animation: 'gfFade .2s ease' }} />
      <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 400, maxWidth: '92vw', background: 'var(--surface)', borderLeft: '1px solid var(--line)', boxShadow: 'var(--sh-3)', zIndex: 650, display: 'flex', flexDirection: 'column', animation: 'gfSlideIn .26s cubic-bezier(.22,.61,.36,1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 18px', borderBottom: '1px solid var(--line)' }}>
          <span style={{ width: 32, height: 32, borderRadius: 999, background: 'var(--violet-soft)', color: 'var(--violet-700)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I('Sparkles', 17)}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 'var(--fs-15)' }}>{L ? 'Асистент' : 'Assistant'}</div>
            <div style={{ fontSize: 'var(--fs-11)', color: 'var(--text-muted)', fontWeight: 600 }}>{L ? 'Прашај за твојата недела' : 'Ask about your week'}</div>
          </div>
          <IconButton size="sm" variant="ghost" onClick={onClose}>{I('X', 18)}</IconButton>
        </div>
        <div style={{ display: 'flex', gap: 4, padding: '8px 14px 0', borderBottom: '1px solid var(--line)' }}>
          {[['ask', L ? 'Прашај' : 'Ask', 'MessageCircle'], ['draft', L ? 'Состави' : 'Draft', 'PenLine']].map(([id, label, icon]) => (
            <button key={id} onClick={() => setMode(id)} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 14px', border: 'none', background: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 'var(--fs-13)', fontWeight: 700, color: mode === id ? 'var(--primary)' : 'var(--text-muted)', borderBottom: `2px solid ${mode === id ? 'var(--primary)' : 'transparent'}`, marginBottom: -1 }}>{I(icon, 15)}{label}</button>
          ))}
        </div>
        {mode === 'ask' && (<React.Fragment>
        <div ref={bodyRef} style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {msgs.map((m, i) => (
            <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%', background: m.role === 'user' ? 'var(--primary)' : 'var(--surface-2)', color: m.role === 'user' ? '#fff' : 'var(--text-strong)', border: m.role === 'user' ? 'none' : '1px solid var(--line)', borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px', padding: '10px 13px', fontSize: 'var(--fs-13)', fontWeight: 500, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{m.text}</div>
          ))}
          {typing && <div style={{ alignSelf: 'flex-start', display: 'flex', gap: 4, padding: '12px 14px', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: '14px 14px 14px 4px' }}>
            {[0, 1, 2].map((i) => <span key={i} style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--text-muted)', animation: `gfBounce 1s ${i * 0.15}s infinite` }} />)}
          </div>}
        </div>
        <div style={{ padding: '10px 14px', borderTop: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {suggestions.map((s) => <button key={s} onClick={() => send(s)} style={{ fontSize: 'var(--fs-11)', fontWeight: 600, padding: '5px 10px', borderRadius: 999, border: '1px solid var(--line)', background: 'var(--surface-2)', color: 'var(--text-body)', cursor: 'pointer', fontFamily: 'inherit' }}>{s}</button>)}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} placeholder={L ? 'Напиши прашање…' : 'Type a question…'} style={{ flex: 1, border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: '10px 12px', fontSize: 'var(--fs-13)', outline: 'none', background: 'var(--surface-2)', fontFamily: 'inherit', color: 'var(--text-strong)' }} />
            <IconButton onClick={() => send()}>{I('Send', 18)}</IconButton>
          </div>
        </div>
        </React.Fragment>)}
        {mode === 'draft' && (
          <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <div style={{ fontSize: 'var(--fs-11)', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 8 }}>{L ? 'Намена' : 'Purpose'}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {purposes.map((p) => (
                  <button key={p.id} onClick={() => { setPurpose(p.id); setDraftOut(''); }} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 12px', borderRadius: 'var(--r-md)', border: `1px solid ${purpose === p.id ? 'var(--primary)' : 'var(--line)'}`, background: purpose === p.id ? 'color-mix(in srgb, var(--primary) 8%, var(--surface))' : 'var(--surface-2)', cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left' }}>
                    <span style={{ width: 16, height: 16, borderRadius: 999, border: `2px solid ${purpose === p.id ? 'var(--primary)' : 'var(--line-strong, var(--line))'}`, background: purpose === p.id ? 'var(--primary)' : 'transparent', flexShrink: 0 }} />
                    <span style={{ fontSize: 'var(--fs-13)', fontWeight: 700, color: 'var(--text-strong)' }}>{L ? p.mk : p.en}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 'var(--fs-11)', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 8 }}>{L ? 'Тон' : 'Tone'}</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {tones.map((tn) => (
                  <button key={tn.id} onClick={() => { setTone(tn.id); if (draftOut) setDraftOut(''); }} disabled={L} style={{ fontSize: 'var(--fs-12)', fontWeight: 700, padding: '7px 13px', borderRadius: 999, border: `1px solid ${tone === tn.id ? 'var(--primary)' : 'var(--line)'}`, background: tone === tn.id ? 'var(--primary)' : 'var(--surface-2)', color: tone === tn.id ? '#fff' : 'var(--text-body)', cursor: L ? 'default' : 'pointer', opacity: L ? 0.5 : 1, fontFamily: 'inherit' }}>{L ? tn.mk : tn.en}</button>
                ))}
              </div>
            </div>
            <Button variant="primary" onClick={generate} style={{ width: '100%' }}>{drafting ? <span style={{ display: 'inline-flex', animation: 'gfSpin 1s linear infinite' }}>{I('LoaderCircle', 16)}</span> : I('Sparkles', 16)}{drafting ? (L ? 'Составувам…' : 'Drafting…') : (L ? 'Состави порака' : 'Draft message')}</Button>
            {draftOut && (
              <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--r-md)', overflow: 'hidden' }}>
                <div style={{ padding: '13px 14px', fontSize: 'var(--fs-13)', fontWeight: 500, lineHeight: 1.6, color: 'var(--text-strong)', whiteSpace: 'pre-wrap', background: 'var(--surface)' }}>{draftOut}</div>
                <div style={{ display: 'flex', gap: 6, padding: '8px 10px', borderTop: '1px solid var(--line)', background: 'var(--surface-2)' }}>
                  <button onClick={() => { navigator.clipboard && navigator.clipboard.writeText(draftOut); setCopied(true); setTimeout(() => setCopied(false), 1600); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--fs-12)', fontWeight: 700, padding: '6px 11px', borderRadius: 'var(--r-sm)', border: '1px solid var(--line)', background: 'var(--surface)', color: copied ? 'var(--green-600)' : 'var(--text-body)', cursor: 'pointer', fontFamily: 'inherit' }}>{I(copied ? 'Check' : 'Copy', 14)}{copied ? (L ? 'Копирано' : 'Copied') : (L ? 'Копирај' : 'Copy')}</button>
                  <button onClick={generate} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--fs-12)', fontWeight: 700, padding: '6px 11px', borderRadius: 'var(--r-sm)', border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--text-body)', cursor: 'pointer', fontFamily: 'inherit' }}>{I('RefreshCw', 14)}{L ? 'Преработи' : 'Rewrite'}</button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </React.Fragment>
  );
}

// ─────────────────────────────── Toasts ───────────────────────────────
function ToastStack({ toasts, onClose }) {
  return (
    <div style={{ position: 'fixed', bottom: 22, right: 22, zIndex: 700, display: 'flex', flexDirection: 'column', gap: 10 }}>
      {toasts.map((t) => (
        <Toast key={t.id} tone={t.tone} icon={I(t.icon, 16)} onClose={() => onClose(t.id)}>{t.text}</Toast>
      ))}
    </div>
  );
}

const STATUS_CYCLE = ['pending', 'working', 'review', 'stuck', 'postponed', 'done'];
let taskSeq = 100;

// ─────────────────────────────── App ───────────────────────────────
function App() {
  const [authed, setAuthed] = React.useState(false);
  const [stage, setStage] = React.useState('splash'); // splash | login
  const [view, setView] = React.useState('myweek');
  const [lang, setLang] = React.useState('en');
  const [theme, setTheme] = React.useState('light');
  const [day, setDay] = React.useState(null);
  const [weekIdx, setWeekIdx] = React.useState(1);
  const [query, setQuery] = React.useState('');
  const [deptFilter, setDeptFilter] = React.useState(null);
  const [modal, setModal] = React.useState(null);
  const [detailTask, setDetailTask] = React.useState(null);
  const [editTask, setEditTask] = React.useState(null);
  const [userPerson, setUserPerson] = React.useState(null);
  const [assistant, setAssistant] = React.useState(false);
  const [currentUser, setCurrentUser] = React.useState('blagoj');
  const [peopleVer, setPeopleVer] = React.useState(0);
  const me = GF_PEOPLE.find((p) => p.id === currentUser) || GF_PEOPLE[0];
  const myPerms = GF_ROLE_PERMS(me.role);
  const ownsTask = React.useCallback((t) => !!t && (t.owner === currentUser || (t.helpers || []).includes(currentUser)), [currentUser]);
  const canStatus = React.useCallback((t) => myPerms.status === 'any' || (myPerms.status === 'own' && ownsTask(t)), [myPerms, ownsTask]);
  const denyToast = React.useCallback(() => pushToast('error', (lang === 'mk' ? 'Немате дозвола (улога: ' : 'Not permitted for your role (') + (GF_ROLES[me.role] ? GF_ROLES[me.role][lang] : me.role) + ')', 'Lock'), [lang, me]);
  const [tasks, setTasks] = React.useState(() => GF_TASKS.map((t) => ({ ...t, color: (GF_DEPARTMENTS.find((d) => d.id === t.dept) || {}).color })));
  const [toasts, setToasts] = React.useState([]);
  const [handoffs, setHandoffs] = React.useState([
    { from: 'Cultivation', to: 'Production', item: 'Batch F27 — harvest lot ready for intake', status: 'pending', by: 'Marko I' },
    { from: 'Production', to: 'Quality Control', item: 'Batch F26 — post-cure samples staged', status: 'done', by: 'Ivo K' },
    { from: 'Quality Control', to: 'Quality Assurance', item: 'Potency results for F25 awaiting QP review', status: 'working', by: 'Blagoj N' },
    { from: 'Quality Assurance', to: 'Logistics', item: 'F24 release memo — cleared for shipment', status: 'done', by: 'Ana P' },
  ]);
  const [notifs, setNotifs] = React.useState({ stuck: true, report: true, handoff: false });
  const [aiBackend, setAiBackend] = React.useState('claude');
  const [tw, setTweak] = useTweaks(TWEAK_DEFAULTS);
  useFeel(tw);
  const panel = <FeelTweaks tw={tw} setTweak={setTweak} lang={lang} />;

  const pushToast = React.useCallback((tone, text, icon = 'Check') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((ts) => [...ts, { id, tone, text, icon }]);
    setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), 3600);
  }, []);
  const closeToast = (id) => setToasts((ts) => ts.filter((t) => t.id !== id));

  const cycleStatus = React.useCallback((id) => {
    setTasks((ts) => ts.map((x) => {
      if (x.id !== id) return x;
      if (!canStatus(x)) { denyToast(); return x; }
      const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(x.status) + 1) % STATUS_CYCLE.length];
      pushToast(next === 'done' ? 'success' : next === 'stuck' ? 'error' : 'info', `${x.title} → ${STATUS_LABEL(lang, next)}`, next === 'done' ? 'CheckCheck' : next === 'stuck' ? 'OctagonAlert' : 'Loader');
      window.GF_REAL.persistStatus(id, next).catch((e) => pushToast('error', (lang === 'mk' ? 'Не се зачува: ' : 'Not saved: ') + e.message, 'CircleAlert'));
      const updated = { ...x, status: next, overdue: next === 'done' ? false : x.overdue };
      setDetailTask((d) => (d && d.id === id ? updated : d));
      return updated;
    }));
  }, [lang, pushToast, canStatus, denyToast]);

  const toggleDone = React.useCallback((id) => {
    setTasks((ts) => ts.map((x) => {
      if (x.id !== id) return x;
      if (!canStatus(x)) { denyToast(); return x; }
      const done = x.status !== 'done';
      if (done) pushToast('success', `${x.title} marked done`, 'CheckCheck');
      window.GF_REAL.persistStatus(id, done ? 'done' : 'pending').catch((e) => pushToast('error', (lang === 'mk' ? 'Не се зачува: ' : 'Not saved: ') + e.message, 'CircleAlert'));
      const updated = { ...x, status: done ? 'done' : 'pending' };
      setDetailTask((d) => (d && d.id === id ? updated : d));
      return updated;
    }));
  }, [pushToast, canStatus, denyToast]);

  const dropOnColumn = React.useCallback((id, status) => {
    setTasks((ts) => ts.map((x) => {
      if (x.id !== id || x.status === status) return x;
      pushToast('info', `${x.title} moved to ${STATUS_LABEL(lang, status)}`, 'Move');
      return { ...x, status };
    }));
  }, [lang, pushToast]);

  const createTask = React.useCallback(({ id, title, priority, dept, type, owner, helpers, days, sessionHours, recurrence, due, ref, desc, tags }) => {
    const color = (GF_DEPARTMENTS.find((d) => d.id === dept) || {}).color;
    const hp = helpers || [];
    const uiVals = { title, priority, dept, type, helpers: hp, days, recurrence, due, ref, desc, tags };
    const saveErr = (e) => pushToast('error', (lang === 'mk' ? 'Не се зачува: ' : 'Not saved: ') + e.message, 'CircleAlert');
    if (id) {
      window.GF_REAL.persistEdit(id, uiVals).catch(saveErr);
      setTasks((ts) => ts.map((x) => {
        if (x.id !== id) return x;
        // Persist Responsible changes: diff new helpers against the previous
        // set (only known here, inside the updater) → assign/unassign calls.
        const prev = x.helpers || [];
        if (!window.GF_MOCK) {
          hp.filter((w) => !prev.includes(w)).forEach((w) => window.GF_API.assign(id, w).catch(saveErr));
          prev.filter((w) => !hp.includes(w)).forEach((w) => window.GF_API.unassign(id, w).catch(saveErr));
        }
        return { ...x, title, priority, pr: priority, dept, type, owner, helpers: hp, days: days || x.days, day: (days && days[0]) || x.day, sessionHours, recurrence, due, ref, refCode: ref, desc, description: desc, tags, color,
          people: [owner, ...hp].map((pid) => { const p = GF_PERSON(pid); return { name: p.name, color: p.color }; }) };
      }));
      pushToast('success', `"${title}" updated`, 'Check');
      return;
    }
    // Optimistic local card now; swap in the real (server-id'd) row when the
    // POST lands so later status changes PATCH a real task id.
    taskSeq += 1;
    const tempId = `T-${taskSeq}`;
    const newTask = { id: tempId, title, status: 'pending', priority, pr: priority, dept, type, owner, helpers: hp, due, ref, refCode: ref, desc, description: desc,
      sessionHours, recurrence, tags: tags || [], day: (days && days[0]) || 'Mon', days: days && days.length ? days : ['Mon'], weekIdx, color,
      people: [owner, ...hp].map((pid) => { const p = GF_PERSON(pid); return { name: p.name, color: p.color }; }) };
    setTasks((ts) => [newTask, ...ts]);
    pushToast('success', `"${title}" created`, 'Plus');
    window.GF_REAL.persistCreate(uiVals)
      .then((real) => real && setTasks((ts) => ts.map((x) => x.id === tempId ? { ...x, ...real, weekIdx: x.weekIdx } : x)))
      .catch((e) => { saveErr(e); setTasks((ts) => ts.filter((x) => x.id !== tempId)); });
  }, [pushToast, weekIdx, lang]);

  const saveUser = React.useCallback(({ id, name, role, dept, color }) => {
    if (id) {
      const p = GF_PEOPLE.find((x) => x.id === id);
      if (p) { p.name = name; p.role = role; p.dept = dept; p.color = color; }
      pushToast('success', (lang === 'mk' ? 'Зачувано: ' : 'Saved: ') + name, 'Check');
    } else {
      const nid = name.toLowerCase().replace(/[^a-z]+/g, '-').slice(0, 12) + '-' + Math.random().toString(36).slice(2, 5);
      GF_PEOPLE.push({ id: nid, name, role, dept, color, active: 0, done: 0 });
      pushToast('success', (lang === 'mk' ? 'Додаден член: ' : 'Member added: ') + name, 'UserPlus');
    }
    setPeopleVer((v) => v + 1);
  }, [pushToast, lang]);

  const removeUser = React.useCallback((id) => {
    if (!myPerms.team) { denyToast(); return; }
    if (GF_PEOPLE.length <= 1) return;
    const idx = GF_PEOPLE.findIndex((x) => x.id === id);
    if (idx >= 0) { const nm = GF_PEOPLE[idx].name; GF_PEOPLE.splice(idx, 1); pushToast('info', (lang === 'mk' ? 'Отстранет: ' : 'Removed: ') + nm, 'Trash2'); }
    if (currentUser === id) setCurrentUser(GF_PEOPLE[0].id);
    setPeopleVer((v) => v + 1);
  }, [myPerms, denyToast, pushToast, lang, currentUser]);

  const setActiveUser = React.useCallback((id) => {
    setCurrentUser(id);
    const p = GF_PEOPLE.find((x) => x.id === id);
    if (p) pushToast('success', (lang === 'mk' ? 'Активен: ' : 'Now acting as ') + p.name, 'UserCheck');
  }, [pushToast, lang]);

  const deleteTask = React.useCallback((id) => {
    if (!myPerms.deleteAny) { denyToast(); return; }
    // Soft-delete: the backend archives (is_archived) rather than hard-deleting.
    window.GF_REAL.persistArchive(id).catch((e) => pushToast('error', (lang === 'mk' ? 'Не се зачува: ' : 'Not saved: ') + e.message, 'CircleAlert'));
    setTasks((ts) => ts.filter((x) => x.id !== id));
    pushToast('info', lang === 'mk' ? 'Задачата е архивирана' : 'Task archived', 'Trash2');
  }, [myPerms, denyToast, pushToast, lang]);

  const advanceHandoff = React.useCallback((i) => {
    setHandoffs((hs) => hs.map((h, idx) => {
      if (idx !== i) return h;
      const seq = ['pending', 'working', 'review', 'done'];
      const next = seq[Math.min(seq.indexOf(h.status) + 1, seq.length - 1)];
      pushToast(next === 'done' ? 'success' : 'info', `${h.from} → ${h.to}: ${STATUS_LABEL(lang, next)}`, next === 'done' ? 'CheckCheck' : 'Loader');
      return { ...h, status: next };
    }));
  }, [lang, pushToast]);

  const toggleNotif = React.useCallback((key) => setNotifs((n) => ({ ...n, [key]: !n[key] })), []);

  React.useEffect(() => { document.documentElement.setAttribute('data-theme', theme); }, [theme]);

  React.useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target.tagName || '').toUpperCase();
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); const el = document.getElementById('gf-search'); if (el) el.focus(); return; }
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) { if (e.key === 'Escape') e.target.blur(); return; }
      if (e.key === 'n' && stage === 'app') { e.preventDefault(); setModal('add'); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [stage]);

  if (stage === 'splash') return <React.Fragment><Splash onDone={() => setStage('login')} lang={lang} logo={tw.logo} />{panel}</React.Fragment>;
  if (!authed) return <React.Fragment><Login onSignIn={(meId) => {
    // loadRealData() (awaited in submitSignIn before this fires) mutated
    // GF_TASKS/GF_PEOPLE/GF_DEPARTMENTS in place — re-derive `tasks` state
    // from them now (the useState lazy initializer above only ran once, at
    // first mount, against the mock seed) and adopt the real signed-in user.
    setTasks(GF_TASKS.map((t) => ({ ...t, color: (GF_DEPARTMENTS.find((d) => d.id === t.dept) || {}).color })));
    setPeopleVer((v) => v + 1);
    if (meId) setCurrentUser(meId);
    setAuthed(true);
    const me2 = GF_PEOPLE.find((p) => p.id === meId) || GF_PEOPLE[0];
    pushToast('success', (lang === 'mk' ? 'Најавен како ' : 'Signed in as ') + (me2 ? me2.name : ''));
  }} lang={lang} logo={tw.logo} />{panel}</React.Fragment>;

  const weekTasks = tasks.filter((x) => x.weekIdx === weekIdx);
  const scoped = deptFilter ? weekTasks.filter((x) => x.dept === deptFilter) : weekTasks;

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%' }}>
      <Sidebar view={view} setView={setView} lang={lang} me={me} tasks={tasks} deptFilter={deptFilter} setDeptFilter={setDeptFilter} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Header lang={lang} setLang={setLang} theme={theme} setTheme={setTheme} onNew={() => setModal('add')} onVoice={() => setModal('voice')}
          onOpenReport={() => setView('report')} onWorklog={() => setModal('worklog')} onAssistant={() => setAssistant(true)} me={me} query={query} setQuery={setQuery} weekIdx={weekIdx} setWeekIdx={setWeekIdx} />
        <div style={{ flex: 1, minHeight: 0, background: 'var(--bg)', backgroundImage: 'var(--plasma-grid)', display: 'flex', flexDirection: 'column' }}>
          {deptFilter && (view === 'myweek' || view === 'board') && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '9px 24px', background: 'var(--surface)', borderBottom: '1px solid var(--line)' }}>
              <span style={{ fontSize: 'var(--fs-12)', fontWeight: 600, color: 'var(--text-muted)' }}>{lang === 'mk' ? 'Филтрирано по:' : 'Filtered by:'}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-strong)', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 999, padding: '4px 6px 4px 11px' }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: (GF_DEPARTMENTS.find((d) => d.id === deptFilter) || {}).color }} />
                {(() => { const d = GF_DEPARTMENTS.find((x) => x.id === deptFilter) || {}; return lang === 'mk' ? d.mk : d.name; })()}
                <button onClick={() => setDeptFilter(null)} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, borderRadius: 999, border: 'none', background: 'var(--line)', color: 'var(--text-body)', cursor: 'pointer' }}>{I('X', 12)}</button>
              </span>
            </div>
          )}
          <div style={{ flex: 1, minHeight: 0 }}>
          {view === 'myweek' && <MyWeek lang={lang} day={day} setDay={setDay} weekIdx={weekIdx} setWeekIdx={setWeekIdx} tasks={scoped} query={query} onCycle={cycleStatus} onCheck={toggleDone} onNew={() => setModal('add')} onEdit={setEditTask} onDelete={deleteTask} onOpen={setDetailTask} canEdit={(tk) => myPerms.editAny || ownsTask(tk)} canDelete={myPerms.deleteAny} />}
          {view === 'board' && <Board lang={lang} tasks={scoped} query={query} onDrop={dropOnColumn} onOpen={setDetailTask} />}
          {view === 'dash' && <Dashboard lang={lang} tasks={weekTasks} />}
          {view === 'timeline' && <window.GFScreens.Timeline lang={lang} tasks={weekTasks} />}
          {view === 'coord' && <window.GFScreens.Coordination lang={lang} handoffs={handoffs} onAdvance={advanceHandoff} />}
          {view === 'team' && <window.GFScreens.Team lang={lang} onOpenPerson={setUserPerson} onAdd={() => setUserPerson({ __new: true })} canManage={myPerms.team} currentUser={currentUser} peopleVer={peopleVer} />}
          {view === 'report' && <window.GFScreens.AIReport lang={lang} tasks={weekTasks} onToast={pushToast} />}
          {view === 'settings' && <window.GFScreens.Settings lang={lang} setLang={setLang} theme={theme} setTheme={setTheme} notifs={notifs} onToggleNotif={toggleNotif} aiBackend={aiBackend} setAiBackend={setAiBackend} currentUser={currentUser} setCurrentUser={setCurrentUser} myPerms={myPerms} />}
          {view === 'audit' && <window.GFScreens.AuditTrail lang={lang} />}
          {view === 'import' && <window.GFScreens.ImportView lang={lang} onToast={pushToast} />}
          {view === 'analytics' && <window.GFScreens.Analytics lang={lang} />}
          {view === 'planning' && <window.GFScreens.Planning lang={lang} onToast={pushToast} />}
          {view === 'qclab' && <window.GFScreens.QCLab lang={lang} onToast={pushToast} />}
          {view === 'access' && <window.GFScreens.Access lang={lang} onToast={pushToast} />}
          {view === 'governance' && <window.GFScreens.Governance lang={lang} onToast={pushToast} />}
          </div>
        </div>
      </div>
      {modal === 'voice' && <VoiceModal onClose={() => setModal(null)} onConfirm={() => { setModal(null); createTask({ title: 'Validate HPLC method for potency (voice)', priority: 'critical', dept: 'qc', type: 'Validation' }); pushToast('success', 'Task created from voice capture', 'Mic'); }} lang={lang} />}
      {modal === 'add' && <AddTaskModal onClose={() => setModal(null)} onCreate={(vals) => { setModal(null); createTask(vals); }} lang={lang} />}
      {editTask && <AddTaskModal editTask={editTask} onClose={() => setEditTask(null)} onCreate={(vals) => { setEditTask(null); createTask(vals); }} lang={lang} />}
      {userPerson && <UserModal person={userPerson.__new ? null : userPerson} lang={lang} onClose={() => setUserPerson(null)} canManage={myPerms.team} isActive={userPerson && userPerson.id === currentUser} onSetActive={setActiveUser} onSave={(v) => { saveUser(v); setUserPerson(null); }} onRemove={removeUser} />}
      {modal === 'worklog' && <WorklogModal lang={lang} onClose={() => setModal(null)} />}
      {detailTask && <TaskDetailModal task={detailTask} lang={lang} allTasks={tasks} canEdit={canStatus(detailTask)} onClose={() => setDetailTask(null)} onCycle={cycleStatus} onCheck={toggleDone} />}
      {assistant && <AssistantPanel lang={lang} tasks={tasks} onClose={() => setAssistant(false)} />}
      <ToastStack toasts={toasts} onClose={closeToast} />
      {panel}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
})();

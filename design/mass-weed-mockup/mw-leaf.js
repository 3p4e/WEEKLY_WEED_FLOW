// MASS WEED — reusable 3D leaf logo, cyan HUD theme.
// Usage: <div class="mw-leaf" data-mw-leaf data-size="hero|mini"></div>
// then include this script once (module) after mass-weed.css.

// Load model-viewer as a module via an injected tag (avoids bundler npm resolution).
(function ensureModelViewer(){
  const SRC = 'https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js';
  if (document.querySelector('script[data-mw-modelviewer]')) return;
  const s = document.createElement('script');
  s.type = 'module';
  s.src = SRC;
  s.setAttribute('data-mw-modelviewer', '');
  document.head.appendChild(s);
})();

// Path from a mass-weed/ page up to /assets
const GLB = '../assets/PP_Leaf_3D.glb';

// Mass Weed palette — cyan alloy hull with plasma-cyan energy in the veins
const MW = {
  base:     [0.055, 0.176, 0.290, 1.0], // deep hull blue
  metal:    0.82,
  rough:    0.28,
  emissive: [0.14, 0.62, 0.86],         // cyan plasma glow
  exposure: 1.05,
};

function themeLeaf(mv) {
  try {
    const mats = mv.model && mv.model.materials;
    if (!mats || !mats.length) return;
    mats.forEach(m => {
      const pm = m.pbrMetallicRoughness;
      pm.setBaseColorFactor(MW.base);
      pm.setMetallicFactor(MW.metal);
      pm.setRoughnessFactor(MW.rough);
      m.setEmissiveFactor(MW.emissive);
    });
  } catch (e) {}
  // living plasma breathe on the emissive/exposure
  let t = 0;
  clearInterval(mv._mwShimmer);
  mv._mwShimmer = setInterval(() => {
    t += 0.08;
    const e = MW.exposure * (1 + 0.12 * Math.sin(t * 2.2));
    mv.setAttribute('exposure', e.toFixed(3));
    try {
      const p = 0.5 + 0.5 * Math.sin(t * 2.2);
      mv.model.materials.forEach(m => m.setEmissiveFactor([
        MW.emissive[0] * (0.7 + 0.6 * p),
        MW.emissive[1] * (0.7 + 0.6 * p),
        MW.emissive[2] * (0.7 + 0.6 * p),
      ]));
    } catch (e) {}
  }, 60);
}

function mountLeaf(host) {
  const size = host.dataset.size || 'hero';
  const spin = host.dataset.spin || (size === 'mini' ? '18deg' : '26deg');
  host.innerHTML =
    '<span class="mw-leaf__aura"></span>' +
    '<span class="mw-leaf__ring"></span>' +
    '<span class="mw-leaf__scan"></span>';
  const mv = document.createElement('model-viewer');
  mv.setAttribute('src', GLB);
  mv.setAttribute('alt', 'Mass Weed leaf mark');
  mv.setAttribute('camera-controls', '');
  mv.setAttribute('touch-action', 'pan-y');
  mv.setAttribute('auto-rotate', '');
  mv.setAttribute('auto-rotate-delay', '0');
  mv.setAttribute('rotation-per-second', spin);
  mv.setAttribute('interaction-prompt', 'none');
  mv.setAttribute('shadow-intensity', '0');
  mv.setAttribute('tone-mapping', 'commerce');
  mv.setAttribute('exposure', String(MW.exposure));
  mv.setAttribute('environment-image', 'neutral');
  mv.setAttribute('camera-orbit', '30deg 74deg 100%');
  mv.setAttribute('field-of-view', '30deg');
  mv.setAttribute('disable-zoom', '');
  host.appendChild(mv);
  mv.addEventListener('load', () => themeLeaf(mv));
}

function boot() {
  document.querySelectorAll('[data-mw-leaf]').forEach(mountLeaf);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();

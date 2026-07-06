// Build a self-contained, CSP-safe static preview of the GrowFlow redesign.
// Vendors React/ReactDOM/lucide as local UMD, esbuild-transpiles the kit JSX
// (kept as classic scripts so the window.GF_* global model is preserved),
// self-hosts fonts, and drops all CDN/3D deps (the splash falls back to its
// CSS/PNG leaf when window.THREE is absent). Output: ./preview_dist
import { rmSync, mkdirSync, cpSync, readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import esbuild from 'esbuild';

const ROOT = dirname(fileURLToPath(import.meta.url));
const OUT = join(ROOT, 'preview_dist');
const NM = join(ROOT, 'node_modules');
const R = (...p) => join(ROOT, ...p);
const O = (...p) => join(OUT, ...p);

rmSync(OUT, { recursive: true, force: true });
for (const d of ['', 'vendor', 'design', 'design/tokens', 'kit', 'fonts', 'assets']) mkdirSync(O(d), { recursive: true });

// 1) Vendor UMD (production) — no CDN
cpSync(join(NM, 'react/umd/react.production.min.js'), O('vendor/react.js'));
cpSync(join(NM, 'react-dom/umd/react-dom.production.min.js'), O('vendor/react-dom.js'));
cpSync(join(NM, 'lucide/dist/umd/lucide.min.js'), O('vendor/lucide.js'));

// 2) Assets (brand bitmaps + svg + comfortaa woff2 live under public/assets)
cpSync(R('public/assets'), O('assets'), { recursive: true });

// 3) Design-system CSS — copy tokens + brand, strip the Google Fonts @import
//    (we self-host), and rewrite ../assets -> /assets so paths resolve flat.
const fixCss = (s) => s
  .replace(/@import\s+url\(['"]https:\/\/fonts\.googleapis[^)]*\);?/g, '')
  .replace(/\.\.\/assets\//g, '/assets/')
  .replace(/\.\.\/fonts\//g, '/fonts/')
  // brand.css uses bare `url('assets/...')` (no ../) — flatten those too, or
  // they resolve under /design/assets and 404.
  .replace(/url\((['"]?)assets\//g, 'url($1/assets/');
for (const f of readdirSync(R('src/design/tokens'))) {
  writeFileSync(O('design/tokens', f), fixCss(readFileSync(R('src/design/tokens', f), 'utf8')));
}
writeFileSync(O('design/brand.css'), fixCss(readFileSync(R('src/design/brand.css'), 'utf8')));
// styles.css entry: import tokens + brand + our self-hosted fonts
writeFileSync(O('design/styles.css'),
  `@import url("tokens/colors.css");\n@import url("tokens/typography.css");\n@import url("tokens/layout.css");\n@import url("tokens/base.css");\n@import url("brand.css");\n@import url("/fonts.css");\n`);

// 4) Self-host fonts. latin + latin-ext + cyrillic (where @fontsource ships it).
const URANGE = {
  latin: 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD',
  'latin-ext': 'U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF',
  cyrillic: 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116',
};
const FAMILIES = [
  { pkg: 'saira', family: 'Saira', weights: [400, 500, 600, 700, 800] },
  { pkg: 'orbitron', family: 'Orbitron', weights: [500, 600, 700, 800, 900] },
  { pkg: 'rajdhani', family: 'Rajdhani', weights: [500, 600, 700] },
  { pkg: 'geist-mono', family: 'Geist Mono', weights: [400, 500, 600] },
];
let fontCss = '/* self-hosted @fontsource subsets — CSP-safe, no CDN */\n';
for (const { pkg, family, weights } of FAMILIES) {
  const filesDir = join(NM, '@fontsource', pkg, 'files');
  for (const w of weights) {
    for (const subset of ['latin', 'latin-ext', 'cyrillic']) {
      const fn = `${pkg}-${subset}-${w}-normal.woff2`;
      if (!existsSync(join(filesDir, fn))) continue;
      cpSync(join(filesDir, fn), O('fonts', fn));
      fontCss += `@font-face{font-family:'${family}';font-style:normal;font-weight:${w};font-display:swap;`
        + `src:url('/fonts/${fn}') format('woff2');unicode-range:${URANGE[subset]};}\n`;
    }
  }
}
// Comfortaa (brand) is shipped as woff2 in assets already — reference those.
for (const [sub, file] of [['latin', 'comfortaa-600-latin.woff2'], ['latin-ext', 'comfortaa-600-latin-ext.woff2'], ['cyrillic', 'comfortaa-600-cyrillic.woff2']]) {
  fontCss += `@font-face{font-family:'Comfortaa';font-style:normal;font-weight:600;font-display:swap;`
    + `src:url('/assets/${file}') format('woff2');unicode-range:${URANGE[sub]};}\n`;
}
writeFileSync(O('fonts.css'), fontCss);

// 5) Kit JS. ds_bundle is already plain JS (React.createElement). data/screens/
//    app/tweaks are JSX — transpile with esbuild (no bundle: keep classic-script
//    globals intact), and flatten ../../assets -> /assets in string literals.
// The DS compiler swept a full copy of the demo app into ds_bundle AND left an
// auto-mount at the tail (createRoot(#root).render(<App/>)). We only want the
// component namespace from it — app.js is the sole real mounter — so neutralize
// any root auto-mount so it doesn't render a globals-less demo and throw.
{
  let dsb = readFileSync(R('src/kit/ds_bundle.js'), 'utf8');
  dsb = dsb.replace(/ReactDOM\.createRoot\(\s*document\.getElementById\(['"]root['"]\)\s*\)\.render\([^;]*\);/g,
    '/* auto-mount stripped: app.js mounts the wired app */');
  writeFileSync(O('kit/ds_bundle.js'), dsb);
}
for (const f of ['data.js', 'screens.js', 'app.js', 'tweaks-panel.js']) {
  const src = readFileSync(R('src/kit', f), 'utf8').replace(/\.\.\/\.\.\/assets\//g, '/assets/');
  const { code } = esbuild.transformSync(src, { loader: 'jsx', jsx: 'transform', format: 'iife', target: 'es2019' });
  writeFileSync(O('kit', f), code);
}

// 6) Splash keyframes/styles lifted from the kit index.html <head> (asset paths flattened)
const splashCss = readFileSync(R('src/kit/splash.css'), 'utf8');
writeFileSync(O('splash.css'), splashCss);

// 7) index.html — local CSS + vendor UMD + kit classic scripts; no CDN/babel/three.
writeFileSync(O('index.html'), `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GrowFlow — Weekly Weed Flow</title>
<link rel="icon" href="/assets/wwf-icon-192.png">
<link rel="stylesheet" href="/design/styles.css">
<link rel="stylesheet" href="/splash.css">
</head><body>
<div id="root"></div>
<script src="/vendor/react.js"></script>
<script src="/vendor/react-dom.js"></script>
<script src="/vendor/lucide.js"></script>
<script src="/kit/data.js"></script>
<script src="/kit/ds_bundle.js"></script>
<script src="/kit/tweaks-panel.js"></script>
<script src="/kit/screens.js"></script>
<script src="/kit/app.js"></script>
</body></html>\n`);

console.log('preview_dist built:', readdirSync(OUT).join(', '));

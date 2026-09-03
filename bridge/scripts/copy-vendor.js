// Copies the browser bundles of xterm.js out of node_modules into public/vendor
// so the UI is served entirely same-origin (no CDN, works offline / behind the
// facility proxy). Runs on `npm install`.
import { mkdirSync, copyFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const nm = join(root, 'node_modules');
const out = join(root, 'public', 'vendor');
mkdirSync(out, { recursive: true });

const files = [
  ['@xterm/xterm/lib/xterm.js', 'xterm.js'],
  ['@xterm/xterm/css/xterm.css', 'xterm.css'],
  ['@xterm/addon-fit/lib/addon-fit.js', 'addon-fit.js'],
  ['@xterm/addon-web-links/lib/addon-web-links.js', 'addon-web-links.js'],
];
for (const [src, dst] of files) {
  const from = join(nm, src);
  if (!existsSync(from)) { console.warn(`copy-vendor: missing ${src}`); continue; }
  copyFileSync(from, join(out, dst));
}
console.log(`copy-vendor: ${files.length} files -> public/vendor`);

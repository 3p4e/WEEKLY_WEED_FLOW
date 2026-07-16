// Convert a CSS declaration string into a React style object, so inline styles
// from the prototype can be ported nearly verbatim as style={css('...')}.
export function css(str) {
  const o = {};
  String(str)
    .split(';')
    .forEach((decl) => {
      const i = decl.indexOf(':');
      if (i < 0) return;
      const key = decl.slice(0, i).trim();
      const val = decl.slice(i + 1).trim();
      if (!key) return;
      o[key.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = val;
    });
  return o;
}

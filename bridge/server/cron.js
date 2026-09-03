// Minimal 5-field cron (minute hour day-of-month month day-of-week), local time.
// Supports *, lists (1,2), ranges (1-5), steps (*/15, 1-30/5), and names for
// months/weekdays. Enough for "every night at 02:00" and "weekdays 09:00".
const NAMES = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12, sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
const RANGES = [[0, 59], [0, 23], [1, 31], [1, 12], [0, 7]];
export const PRESETS = { '@hourly': '0 * * * *', '@daily': '0 2 * * *', '@weekdays': '0 9 * * 1-5', '@weekly': '0 9 * * 1' };

function field(spec, [lo, hi]) {
  const set = new Set();
  for (const part of spec.split(',')) {
    const m = /^(\*|[a-z0-9]+(?:-[a-z0-9]+)?)(?:\/(\d+))?$/i.exec(part.trim());
    if (!m) throw new Error(`bad cron field "${spec}"`);
    const step = m[2] ? Number(m[2]) : 1;
    let a = lo, b = hi;
    if (m[1] !== '*') {
      const [x, y] = m[1].split('-').map((v) => (NAMES[v.toLowerCase()] ?? Number(v)));
      if (Number.isNaN(x) || (y !== undefined && Number.isNaN(y))) throw new Error(`bad cron value "${part}"`);
      a = x; b = y === undefined ? (m[2] ? hi : x) : y;
    }
    if (a < lo || b > hi || a > b || step < 1) throw new Error(`cron value out of range "${part}"`);
    for (let v = a; v <= b; v += step) set.add(v === 7 && hi === 7 ? 0 : v);
  }
  return set;
}

export function parseCron(expr) {
  const src = PRESETS[String(expr).trim()] || String(expr).trim();
  const parts = src.split(/\s+/);
  if (parts.length !== 5) throw new Error('cron needs 5 fields: minute hour day month weekday');
  const [min, hour, dom, mon, dow] = parts.map((p, i) => field(p, RANGES[i]));
  return { src, min, hour, dom, mon, dow, domAny: parts[2] === '*', dowAny: parts[4] === '*' };
}

export function matches(c, d) {
  if (!c.min.has(d.getMinutes()) || !c.hour.has(d.getHours()) || !c.mon.has(d.getMonth() + 1)) return false;
  const domOk = c.dom.has(d.getDate()), dowOk = c.dow.has(d.getDay());
  if (!c.domAny && !c.dowAny) return domOk || dowOk; // classic cron: either day field
  return (c.domAny || domOk) && (c.dowAny || dowOk);
}

export function nextRun(expr, from = new Date()) {
  const c = typeof expr === 'string' ? parseCron(expr) : expr;
  const d = new Date(from); d.setSeconds(0, 0); d.setMinutes(d.getMinutes() + 1);
  for (let i = 0; i < 366 * 24 * 60; i++) { if (matches(c, d)) return d; d.setMinutes(d.getMinutes() + 1); }
  return null;
}

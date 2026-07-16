// Language-aware label helpers for the Production module.
import { DEPTS, STATUS, PRIORITY, DAYS, DAYS_MK, I18N, dep } from './data.js';

export const makeLabels = (lang) => ({
  t: (k) => (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k,
  depName: (id) => {
    const d = dep(id);
    return lang === 'mk' ? d.mk : d.name;
  },
  statusLabel: (s) => (STATUS[s] ? STATUS[s][lang] : s),
  prLabel: (p) => (PRIORITY[p] ? PRIORITY[p][lang] : p),
  dayLabel: (d) => {
    const i = DAYS.indexOf(d);
    return lang === 'mk' && i >= 0 ? DAYS_MK[i] : d;
  },
});

// Lightweight bilingual (EN / МК) helper shared by both modules.
// The prototype stores strings as { en, mk } objects or via a flat dictionary;
// `t()` resolves either against the active language.

import { useSyncExternalStore } from 'react';

const LANG_KEY = 'gf_lang';
let lang = localStorage.getItem(LANG_KEY) || 'en';
const listeners = new Set();

export function getLang() {
  return lang;
}
export function setLang(l) {
  lang = l === 'mk' ? 'mk' : 'en';
  localStorage.setItem(LANG_KEY, lang);
  listeners.forEach((fn) => fn());
}
function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// React hook: re-renders subscribers when the language changes.
export function useLang() {
  return useSyncExternalStore(subscribe, getLang);
}

// Resolve a { en, mk } pair (or plain string) against the active language.
export function tr(value, l = lang) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  return value[l] ?? value.en ?? '';
}

// Flat dictionary translate, used for static UI chrome labels.
export function makeT(dict) {
  return (key, l = lang) => {
    const entry = dict[key];
    if (!entry) return key;
    return typeof entry === 'string' ? entry : entry[l] ?? entry.en ?? key;
  };
}

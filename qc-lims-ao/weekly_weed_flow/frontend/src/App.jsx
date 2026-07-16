import React, { useEffect, useState } from 'react';
import { api, getToken, setToken } from './api.js';
import { I18N } from './i18n.js';
import Board from './Board.jsx';
import AiPanel from './AiPanel.jsx';

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [lang, setLang] = useState(localStorage.getItem('wwf_lang') || 'en');
  const t = I18N[lang];

  useEffect(() => {
    if (!getToken()) { setBooting(false); return; }
    api.me().then(setUser).catch(() => setToken('')).finally(() => setBooting(false));
  }, []);

  function chooseLang(l) { setLang(l); localStorage.setItem('wwf_lang', l); }
  function logout() { setToken(''); setUser(null); }

  if (booting) return <div className="login-wrap"><div className="muted" style={{ color: '#fff' }}>…</div></div>;
  if (!user) return <Login t={t} onAuthed={setUser} />;
  if (user.must_change_password) return <ForceChange t={t} onDone={() => api.me().then(setUser)} />;
  return <Shell t={t} lang={lang} chooseLang={chooseLang} user={user} logout={logout} />;
}

function Login({ t, onAuthed }) {
  const [email, setEmail] = useState(''); const [pw, setPw] = useState('');
  const [remember, setRemember] = useState(false); const [err, setErr] = useState('');
  async function submit(e) {
    e.preventDefault(); setErr('');
    try { const r = await api.login(email, pw, remember); setToken(r.access_token); onAuthed(r.user); }
    catch { setErr('Invalid credentials'); }
  }
  return (
    <div className="login-wrap"><form className="login-card" onSubmit={submit}>
      <h1>WEEKLY WEED FLOW</h1>
      <div className="muted" style={{ fontSize: 12 }}>Accounts are created by your administrator or department head.</div>
      <div className="field"><label>{t.email}</label><input value={email} onChange={(e) => setEmail(e.target.value)} autoFocus /></div>
      <div className="field"><label>{t.password}</label><input type="password" value={pw} onChange={(e) => setPw(e.target.value)} /></div>
      <label className="row" style={{ marginTop: 10, fontSize: 13 }}>
        <input type="checkbox" style={{ width: 'auto' }} checked={remember} onChange={(e) => setRemember(e.target.checked)} /> {t.remember}
      </label>
      {err && <div className="err">{err}</div>}
      <button className="btn btn-primary" style={{ width: '100%', marginTop: 14 }}>{t.signin}</button>
    </form></div>
  );
}

function ForceChange({ t, onDone }) {
  const [a, setA] = useState(''); const [b, setB] = useState(''); const [err, setErr] = useState('');
  async function submit(e) {
    e.preventDefault(); setErr('');
    if (a.length < 12) return setErr('Password must be at least 12 characters.');
    if (a !== b) return setErr('Passwords do not match.');
    try { await api.changePassword(a); onDone(); } catch (x) { setErr(x.message); }
  }
  return (
    <div className="login-wrap"><form className="login-card" onSubmit={submit}>
      <h1>{t.force_title}</h1><div className="muted" style={{ fontSize: 12 }}>{t.force_sub}</div>
      <div className="field"><label>{t.new_pw}</label><input type="password" value={a} onChange={(e) => setA(e.target.value)} autoFocus /></div>
      <div className="field"><label>{t.confirm_pw}</label><input type="password" value={b} onChange={(e) => setB(e.target.value)} /></div>
      {err && <div className="err">{err}</div>}
      <button className="btn btn-primary" style={{ width: '100%', marginTop: 14 }}>{t.save_continue}</button>
    </form></div>
  );
}

function Shell({ t, lang, chooseLang, user, logout }) {
  const [depts, setDepts] = useState([]); const [dept, setDept] = useState(null);
  useEffect(() => { api.departments().then(setDepts).catch(() => {}); }, []);
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">WEEKLY WEED FLOW<small>Purely Plant · {t.brand_sub}</small></div>
        <div className="side-label">{t.departments}</div>
        <div className={'dept' + (dept === null ? ' on' : '')} onClick={() => setDept(null)}>{t.all_depts}</div>
        {depts.map((d) => (
          <div key={d.id} className={'dept' + (dept === d.id ? ' on' : '')} onClick={() => setDept(d.id)}>{d.name}</div>
        ))}
        <div className="usercard">
          <div style={{ fontWeight: 700, color: '#fff' }}>{user.full_name}</div>
          <div className="muted" style={{ color: '#8aa093' }}>{user.function_role || user.role}</div>
          <button className="btn" style={{ marginTop: 8, width: '100%' }} onClick={logout}>{t.logout}</button>
        </div>
      </aside>
      <div className="main">
        <header className="header">
          <strong>Task Manager</strong><div style={{ flex: 1 }} />
          <div className="lang">
            <span className={lang === 'en' ? 'on' : ''} onClick={() => chooseLang('en')}>EN</span>
            <span className={lang === 'mk' ? 'on' : ''} onClick={() => chooseLang('mk')}>МК</span>
          </div>
        </header>
        <div className="workspace">
          <Board t={t} dept={dept} />
          <AiPanel t={t} />
        </div>
      </div>
    </div>
  );
}

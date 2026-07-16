// GrowFlow Unified shell — sidebar, header, mode switch (Production ⇄ QC Lab),
// settings + login modals. Ported from "GrowFlow Unified.html" (window.APP).
import { useState, useCallback, useEffect } from 'react';
import { Icon } from './lib/icons.jsx';
import { Avatar, ToastProvider, useToast, Modal } from './lib/ui.jsx';
import { useLang, setLang as setGlobalLang } from './lib/i18n.js';
import { api, isAuthed } from './api/client.js';
import { useProduction } from './production/useProduction.js';
import { ProductionWorkspace, ProductionSidebar } from './production/ProductionWorkspace.jsx';
import { PEOPLE as GF_PEOPLE } from './production/data.js';
import { makeLabels } from './production/labels.js';
import { useQC } from './qc/useQC.js';
import { QcSidebar, QcWorkspace } from './qc/QcModule.jsx';
import { PEOPLE as QC_PEOPLE } from './qc/data.js';

const API_KEY = 'api_base';
const MODE_KEY = 'app_mode';
const USER_KEY = 'gf_user';

function Shell() {
  const toast = useToast();
  const lang = useLang();
  const [mode, setMode] = useState(() => localStorage.getItem(MODE_KEY) || 'prod');
  const [apiBase, setApiBase] = useState(() => localStorage.getItem(API_KEY) || '');
  const [prodUser, setProdUser] = useState(() => localStorage.getItem(USER_KEY) || 'marko');
  const [authed, setAuthed] = useState(() => isAuthed());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);

  const prod = useProduction();
  const qc = useQC({ apiBase, authed, onToast: toast });
  const prodLabels = makeLabels(lang);

  const switchMode = useCallback((m) => {
    setMode(m);
    localStorage.setItem(MODE_KEY, m);
  }, []);

  const onSearch = (e) => {
    if (mode === 'prod') prod.setSearch(e.target.value);
  };

  // keyboard: ⌘/Ctrl-K focus search, Esc closes drawer
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('search-input')?.focus();
      }
      if (e.key === 'Escape') setSidebarOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const activeUser = mode === 'prod' ? GF_PEOPLE[prodUser] : QC_PEOPLE.elena;

  return (
    <div id="app">
      <div className={`sidebar-overlay ${sidebarOpen ? 'open' : ''}`} onClick={() => setSidebarOpen(false)} />
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="brand">
          <div className="brand-mark">
            <svg className="icon" viewBox="0 0 20 20" style={{ stroke: '#fff', width: 20, height: 20 }}>
              <path d="M4 16c8 0 12-4 12-12C8 4 4 8 4 16zM4 16c1.5-4 3.5-6 6-7.5" />
            </svg>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div className="brand-name">Grow<b>Flow</b></div>
            <span className="pp-wordmark pp-wordmark--sm" title="Purely Plant GmbH" style={{ marginTop: 1 }} />
          </div>
        </div>

        {/* Mode switch */}
        <div className="mode-switch">
          <span className={mode === 'prod' ? 'on' : ''} onClick={() => switchMode('prod')}>Production</span>
          <span className={mode === 'qc' ? 'on' : ''} onClick={() => switchMode('qc')}>QC Lab</span>
        </div>

        {mode === 'prod' ? (
          <ProductionSidebar store={prod} lang={lang} onToast={toast} />
        ) : (
          <QcSidebar qc={qc} lang={lang} />
        )}

        <div style={{ flex: 1 }} />
        <div className="mode-divider" />
        {mode === 'qc' && (
          <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
            <div className="row" style={{ gap: 7, fontSize: 11, fontWeight: 600, color: 'var(--ink-2)' }}>
              <span className="dot" style={{ background: 'var(--green)' }} />EU GMP Annex 11
            </div>
            <div className="row" style={{ gap: 7, fontSize: 11, fontWeight: 600, color: 'var(--ink-2)' }}>
              <span className="dot" style={{ background: 'var(--blue)' }} />MK GMP
            </div>
          </div>
        )}
        <div className="user-card">
          <Avatar person={activeUser} size={34} />
          <div style={{ minWidth: 0 }}>
            <div className="nm">{activeUser?.name}</div>
            <div className="rl">{activeUser?.roleLabel || activeUser?.role || ''}</div>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="header">
          <button className="btn-ghost hamburger" onClick={() => setSidebarOpen((o) => !o)}>
            <Icon name="menu" />
          </button>
          <h2 style={{ fontSize: 17, fontWeight: 800, letterSpacing: '-.5px' }}>
            Grow<span style={{ color: 'var(--orange)' }}>Flow</span>
            <span style={{ color: 'var(--ink-3)', fontWeight: 600, fontSize: 13, marginLeft: 8 }}>{mode === 'qc' ? 'QC Lab' : ''}</span>
          </h2>
          <div className="search" style={{ marginLeft: 16 }}>
            <Icon name="search" />
            <input id="search-input" placeholder={mode === 'prod' ? prodLabels.t('search') : lang === 'mk' ? 'Барај примероци, серии, CoA…' : 'Search samples, batches, CoA…'} onChange={onSearch} />
          </div>
          <div className="spacer" />
          <div className="lang-toggle">
            <span className={lang === 'en' ? 'on' : ''} onClick={() => setGlobalLang('en')}>EN</span>
            <span className={lang === 'mk' ? 'on' : ''} onClick={() => setGlobalLang('mk')}>МК</span>
          </div>
          {mode === 'prod' && (
            <button className="btn btn-orange" onClick={() => toast(prodLabels.t('voice_task') + ' — Web Speech API', 'info')}>
              <Icon name="mic" stroke="#fff" /><span>{prodLabels.t('voice_task')}</span>
            </button>
          )}
          {mode === 'qc' && (
            <button className="btn btn-orange btn-sm" onClick={() => qc.navigate('search')}>
              <Icon name="sparkle" stroke="#fff" />AI
            </button>
          )}
          {mode === 'prod' && (
            <button className="btn btn-sm" onClick={() => prod.goToday()}>{prodLabels.t('today')}</button>
          )}
          {apiBase && (
            <button className="btn btn-sm" onClick={() => (authed ? (api.logout(), setAuthed(false), toast('Logged out', 'info')) : setLoginOpen(true))}>
              <Icon name={authed ? 'shield' : 'lock'} className="icon" stroke={authed ? 'var(--green)' : undefined} />
              {authed ? (qc.online ? 'Live' : 'Auth') : 'Log in'}
            </button>
          )}
          <button className="icon-btn" onClick={() => setSettingsOpen(true)} title="Settings">
            <Icon name="settings" />
          </button>
          <div id="header-avatar"><Avatar person={activeUser} size={38} ring /></div>
        </header>

        {mode === 'prod' ? (
          <ProductionWorkspace store={prod} lang={lang} onToast={toast} />
        ) : (
          <div className="workspace" id="content" style={{ overflow: 'auto' }}>
            <QcWorkspace qc={qc} lang={lang} onToast={toast} />
          </div>
        )}
      </div>

      {/* Settings */}
      <Modal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        title="Settings"
        maxWidth={440}
        footer={
          <>
            <button className="btn" onClick={() => setSettingsOpen(false)}>Cancel</button>
            <button
              className="btn btn-primary"
              onClick={() => {
                const base = document.getElementById('set-api-base').value.trim();
                const l = document.getElementById('set-lang').value;
                const u = document.getElementById('set-user').value;
                setApiBase(base);
                localStorage.setItem(API_KEY, base);
                setProdUser(u);
                localStorage.setItem(USER_KEY, u);
                setGlobalLang(l);
                setSettingsOpen(false);
                toast('Settings saved ✓', 'success');
              }}
            >
              Save
            </button>
          </>
        }
      >
        <div className="field">
          <label>Backend API URL</label>
          <input id="set-api-base" defaultValue={apiBase} placeholder="leave blank for offline demo" />
        </div>
        <div className="field">
          <label>Language</label>
          <select id="set-lang" defaultValue={lang}>
            <option value="en">English</option>
            <option value="mk">Македонски</option>
          </select>
        </div>
        <div className="field">
          <label>Active user (Production)</label>
          <select id="set-user" defaultValue={prodUser}>
            {Object.entries(GF_PEOPLE).map(([k, v]) => (
              <option key={k} value={k}>{v.name} — {v.roleLabel}</option>
            ))}
          </select>
        </div>
        <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 4, lineHeight: 1.5 }}>
          Leave the API URL blank to run on offline seed data. Set it to your{' '}
          <b>QC_LIMS_Ao backend</b> (e.g. its origin) to load live samples, OOS and audit records.
        </div>
      </Modal>

      {/* Login */}
      <Modal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        title="Sign in"
        maxWidth={380}
        footer={
          <>
            <button className="btn" onClick={() => setLoginOpen(false)}>Cancel</button>
            <button
              className="btn btn-primary"
              onClick={async () => {
                const email = document.getElementById('login-email').value.trim();
                const password = document.getElementById('login-pass').value;
                try {
                  await api.login(email, password);
                  setAuthed(true);
                  setLoginOpen(false);
                  toast('Signed in ✓', 'success');
                } catch (err) {
                  toast(err.offline ? 'Backend unreachable' : 'Invalid credentials', 'error');
                }
              }}
            >
              Sign in
            </button>
          </>
        }
      >
        <div className="field">
          <label>Email</label>
          <input id="login-email" defaultValue="elena@purelyplant.eu" placeholder="you@purelyplant.eu" />
        </div>
        <div className="field">
          <label>Password</label>
          <input id="login-pass" type="password" defaultValue="Password123!" />
        </div>
        <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 4, lineHeight: 1.5 }}>
          Seeded demo accounts (see backend seed) — e.g. <b>elena@purelyplant.eu</b> / <b>Password123!</b>.
        </div>
      </Modal>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}

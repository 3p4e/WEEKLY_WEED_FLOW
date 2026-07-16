import { useEffect, useState } from "react";
import { ArrowLeft, KeyRound, LockOpen, LogIn, Send } from "lucide-react";
import { login, resetRequest, resetConfirm } from "../api/planner";
import type { Lang, UserOut } from "../types/models";
import "../styles/suma-auth.css";

/* ── Color-scheme picker ──────────────────────────────────────────────────
   The login screen offers language + color-scheme options (the design's
   purpose). The 6 schemes map to [data-theme] in suma-auth.css. `key` drives
   the CSS; `label` is a neutral, professional tooltip (no game lore). */
const THEME_KEY = "suma-theme";
const THEMES: { key: string; label: string; dot: string }[] = [
  { key: "protoss", label: "Cyan", dot: "#2ee6ff" },
  { key: "terran", label: "Teal", dot: "#38c8d2" },
  { key: "aiur", label: "Gold", dot: "#ffcf6b" },
  { key: "verdant", label: "Green", dot: "#34d399" },
  { key: "zerg", label: "Violet", dot: "#c061f0" },
  { key: "swann", label: "Amber", dot: "#ff8a2a" },
];
function loadTheme(): string {
  try {
    const v = localStorage.getItem(THEME_KEY);
    if (v && THEMES.some((x) => x.key === v)) return v;
  } catch { /* ignore */ }
  return "protoss";
}

const LAST_USER = "gf_last_user";

type View = "login" | "forgot" | "reset";

export function Login({
  onLogin, lang, onToggleLang, locked = false,
}: {
  t: (k: string) => string; onLogin: (u: UserOut) => void;
  lang: Lang; onToggleLang: (l: Lang) => void; locked?: boolean;
}) {
  const L = (en: string, mk: string) => (lang === "mk" ? mk : en);
  const [theme, setTheme] = useState<string>(loadTheme);
  const [view, setView] = useState<View>("login");
  const [pop, setPop] = useState(0);       // re-key the card to replay the entrance
  const [gag, setGag] = useState(0);       // click-the-leaf shatter gag
  const [username, setUsername] = useState(() => {
    try { return localStorage.getItem(LAST_USER) || ""; } catch { return ""; }
  });
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // forgot / reset
  const [code, setCode] = useState("");
  const [newPw, setNewPw] = useState("");

  useEffect(() => {
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  }, [theme]);

  const go = (v: View) => { setError(null); setPop((p) => p + 1); setView(v); };

  async function doLogin() {
    setBusy(true); setError(null);
    try {
      const tok = await login(username.trim(), password);
      try { localStorage.setItem(LAST_USER, username.trim()); } catch { /* ignore */ }
      onLogin(tok.user);
    } catch { setError(L("Invalid credentials", "Невалидни акредитиви")); } finally { setBusy(false); }
  }
  async function doForgot() {
    setBusy(true); setError(null); setNote(null);
    try {
      const r = await resetRequest(username.trim());
      if (r.delivery === "shown" && r.code) {
        setCode(r.code);
        setNote(L(`Your reset code: ${r.code}`, `Вашиот код: ${r.code}`));
      } else {
        setNote(L("If the account exists, a reset code was sent.", "Ако сметката постои, испратен е код."));
      }
      go("reset");
    } catch { setError(L("Could not request a code", "Не може да се побара код")); } finally { setBusy(false); }
  }
  async function doReset() {
    setBusy(true); setError(null);
    try {
      await resetConfirm(username.trim(), code.trim(), newPw);
      setNote(L("Password updated — sign in.", "Лозинката е ажурирана — најавете се."));
      setPassword(""); setNewPw(""); setCode(""); go("login");
    } catch { setError(L("Invalid or expired code", "Невалиден или истечен код")); } finally { setBusy(false); }
  }

  const sub =
    view === "forgot" || view === "reset" ? L("Reset access", "Ресетирање пристап")
      : locked ? L("Session locked", "Сесијата е заклучена")
        : L("Weekly Planner · Tasks", "Неделен Планер · Задачи");

  return (
    <div className="suma-auth au-root" data-theme={theme}>
      {/* color-scheme picker */}
      <div className="au-theme" role="group" aria-label={L("Color scheme", "Шема на бои")}>
        <span className="au-theme-lbl">{L("Scheme", "Шема")}</span>
        {THEMES.map((th) => (
          <button
            key={th.key}
            type="button"
            className={`au-th${theme === th.key ? " on" : ""}`}
            style={{ background: th.dot }}
            title={th.label}
            aria-label={th.label}
            aria-pressed={theme === th.key}
            onClick={() => setTheme(th.key)}
          />
        ))}
      </div>

      {/* persistent brand hero */}
      <div className="au-hero">
        <div
          className={`au-leaf${gag ? " gag" : ""}`}
          key={`leaf-${gag}`}
          onClick={() => setGag((g) => g + 1)}
          title="GrowFlow"
        >
          <div className="au-leaf-img" />
          <span className="au-ember" />
          <div className="au-smoke"><i /><i /><i /><i /></div>
        </div>
        <div className="au-brand">Grow<b>Flow</b></div>
        <div className="au-sep" />
        <div className="au-wordmark" />
        <div className="au-sub" key={sub}>{sub}</div>

        {/* swappable card slot */}
        <div className="au-slot">
          <div className="au-card" key={`${view}-${pop}`}>
            {view === "login" && (
              <form className="au-box" onSubmit={(e) => { e.preventDefault(); if (username && password) void doLogin(); }}>
                <label className="au-flabel">{L("User", "Корисник")}</label>
                <input
                  className="au-field" autoFocus value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={L("Username", "Корисничко име")}
                  autoComplete="username"
                />
                <label className="au-flabel">{L("Password", "Лозинка")}</label>
                <input
                  className="au-field" type="password" value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <div className="au-err">{error || ""}</div>
                {note && <div className="au-ok">{note}</div>}
                <button className="au-btn" type="submit" disabled={busy || !username || !password}>
                  {busy ? "…" : (<>{locked ? <LockOpen size={15} /> : <LogIn size={15} />}{locked ? L("Unlock", "Отклучи") : L("Sign in", "Најави се")}</>)}
                </button>
                <button className="au-ghost" type="button" onClick={() => go("forgot")}>
                  <KeyRound size={13} /> {L("Forgot password?", "Заборавена лозинка?")}
                </button>
                <div className="au-hint">
                  {L("Accounts are created by your administrator or department head.",
                    "Сметките ги креира администраторот или раководителот.")}
                </div>
              </form>
            )}

            {view === "forgot" && (
              <form className="au-box" onSubmit={(e) => { e.preventDefault(); if (username) void doForgot(); }}>
                <div className="au-hint" style={{ marginTop: 0, marginBottom: 6, textAlign: "left" }}>
                  {L("Enter your username or email to get a reset code.",
                    "Внесете корисничко име или е-пошта за код.")}
                </div>
                <label className="au-flabel">{L("Username or email", "Корисничко име или е-пошта")}</label>
                <input
                  className="au-field" autoFocus value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={L("Username or email", "Корисничко име или е-пошта")}
                />
                <div className="au-err">{error || ""}</div>
                <button className="au-btn" type="submit" disabled={busy || !username}>
                  {busy ? "…" : (<><Send size={14} /> {L("Send reset code", "Испрати код")}</>)}
                </button>
                <button className="au-ghost" type="button" onClick={() => go("login")}>
                  <ArrowLeft size={13} /> {L("Back", "Назад")}
                </button>
              </form>
            )}

            {view === "reset" && (
              <form className="au-box" onSubmit={(e) => { e.preventDefault(); if (code && newPw.length >= 10) void doReset(); }}>
                {note && <div className="au-ok">{note}</div>}
                <label className="au-flabel">{L("6-digit code", "6-цифрен код")}</label>
                <input
                  className="au-field" autoFocus value={code}
                  onChange={(e) => setCode(e.target.value)}
                  inputMode="numeric" placeholder="••••••"
                />
                <label className="au-flabel">{L("New password (min 10)", "Нова лозинка (мин. 10)")}</label>
                <input
                  className="au-field" type="password" value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  placeholder="••••••••••" autoComplete="new-password"
                />
                <div className="au-err">{error || ""}</div>
                <button className="au-btn" type="submit" disabled={busy || !code || newPw.length < 10}>
                  {busy ? "…" : (<><KeyRound size={14} /> {L("Set new password", "Постави лозинка")}</>)}
                </button>
                <button className="au-ghost" type="button" onClick={() => go("login")}>
                  <ArrowLeft size={13} /> {L("Back", "Назад")}
                </button>
              </form>
            )}
          </div>
        </div>

        {/* language toggle */}
        <div className="au-toggle" role="group" aria-label={L("Language", "Јазик")}>
          <span className={lang === "en" ? "on" : ""} onClick={() => onToggleLang("en")}>EN</span>
          <span className={lang === "mk" ? "on" : ""} onClick={() => onToggleLang("mk")}>МК</span>
        </div>
      </div>
    </div>
  );
}

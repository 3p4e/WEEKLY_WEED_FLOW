import { useCallback, useEffect, useState } from "react";
import { PlannerShell, type ViewId } from "./PlannerShell";
import { Login } from "./views/Login";
import { ChangePassword } from "./views/ChangePassword";
import { MyWeekView } from "./views/MyWeekView";
import { BoardView } from "./views/BoardView";
import { TreeView } from "./views/TreeView";
import { WeeklySummary } from "./views/WeeklySummary";
import { ExecutiveDashboard } from "./views/ExecutiveDashboard";
import { AdminConsole } from "./views/AdminConsole";
import { SettingsView } from "./views/SettingsView";
import { AiDrawer } from "./views/AiDrawer";
import { getToken } from "./api/client";
import { listDepartments, listUsers, logout, me } from "./api/planner";
import { makeT } from "./i18n";
import { addWeeks, mondayOf } from "./views/status";
import type { Lang, PlannerDepartment, UserOut } from "./types/models";

export function App() {
  const [lang, setLang] = useState<Lang>("en");
  const [user, setUser] = useState<UserOut | null>(null);
  const [departments, setDepartments] = useState<PlannerDepartment[]>([]);
  const [users, setUsers] = useState<UserOut[]>([]);
  const [view, setView] = useState<ViewId>("myweek");
  const [weekStart, setWeekStart] = useState<string>(mondayOf(new Date()));
  const [booting, setBooting] = useState(true);
  const [aiOpen, setAiOpen] = useState(false);
  const [locked, setLocked] = useState(false);

  const t = makeT(lang);

  // Inactivity session-lock (GMP: 15-min auto-logout → branded lock screen).
  useEffect(() => {
    if (!user) return;
    let timer = 0;
    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => { logout(); setUser(null); setLocked(true); }, 15 * 60 * 1000);
    };
    const evts = ["mousemove", "keydown", "click", "scroll"];
    evts.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => { window.clearTimeout(timer); evts.forEach((e) => window.removeEventListener(e, reset)); };
  }, [user]);

  const loadRefData = useCallback(async () => {
    const [depts, allUsers] = await Promise.all([listDepartments(), listUsers()]);
    setDepartments(depts);
    setUsers(allUsers);
  }, []);

  // Restore session from a stored token on first load.
  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          const u = await me();
          setUser(u);
          if (!u.must_change_password) await loadRefData();
        } catch {
          setUser(null);
        }
      }
      setBooting(false);
    })();
  }, [loadRefData]);

  async function handleLogin(u: UserOut) {
    setUser(u);
    if (u.must_change_password) return; // forced-change gate handles the rest
    try {
      await loadRefData();
    } catch {
      /* ref data load failure surfaces as empty pickers; views show empty state */
    }
  }

  async function handlePasswordChanged(u: UserOut) {
    setUser(u);
    try {
      await loadRefData();
    } catch {
      /* ignore */
    }
  }

  function handleLogout() {
    logout();
    setUser(null);
    setView("myweek");
  }

  if (booting) return null;
  if (!user)
    return (
      <Login
        t={t}
        onLogin={(u) => { setLocked(false); void handleLogin(u); }}
        lang={lang}
        onToggleLang={setLang}
        locked={locked}
      />
    );
  if (user.must_change_password)
    return <ChangePassword t={t} forced onDone={handlePasswordChanged} />;

  return (
    <>
      <PlannerShell
        current={view}
        onNavigate={setView}
        user={user}
        lang={lang}
        onToggleLang={() => setLang((l) => (l === "en" ? "mk" : "en"))}
        t={t}
        weekStart={weekStart}
        onWeekStep={(delta) => setWeekStart((w) => addWeeks(w, delta))}
        onToday={() => setWeekStart(mondayOf(new Date()))}
        onLogout={handleLogout}
        onOpenAi={() => setAiOpen(true)}
      >
        {view === "myweek" && (
          <MyWeekView currentUser={user} departments={departments} users={users} weekStart={weekStart} lang={lang} t={t} />
        )}
        {view === "board" && (
          <BoardView currentUser={user} departments={departments} users={users} weekStart={weekStart} lang={lang} t={t} />
        )}
        {view === "tree" && <TreeView t={t} lang={lang} />}
        {view === "reports" && <WeeklySummary t={t} lang={lang} user={user} departments={departments} />}
        {view === "executive" && <ExecutiveDashboard weekStart={weekStart} lang={lang} t={t} />}
        {view === "admin" && <AdminConsole t={t} user={user} />}
        {view === "settings" && <SettingsView t={t} user={user} departments={departments} />}
      </PlannerShell>
      <AiDrawer open={aiOpen} onClose={() => setAiOpen(false)} t={t} />
    </>
  );
}

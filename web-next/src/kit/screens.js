// GrowFlow UI kit — Team, Timeline, Coordination, AI Report, Settings screens.
(function () {
const { GF_DEPARTMENTS, GF_HANDOFF, GF_TASK_TYPES, GF_ROLES, GF_ROLE_PERMS, GF_T, GF_PEOPLE, GF_PERSON, GF_TASKS } = window;
const DS2 = window.GrowFlowDesignSystem_7accb1;
const { Avatar, AvatarStack, Badge, Button, IconButton, Switch, Segmented, Select, Field, KpiTile, BarRow, Leaf, PriorityTag } = DS2;
const PopSelect = window.PopSelect;
const I2 = (name, sz = 18) => {
  const n = window.lucide && lucide.icons[name];
  if (!n) return null;
  const kids = n.find(Array.isArray) || [];
  return React.createElement('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    kids.map(([t, a], i) => React.createElement(t, { key: i, ...a })));
};
function Panel2({ title, right = null, children, style = {} }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', padding: 18, boxShadow: 'var(--sh-1)', ...style }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ fontSize: 'var(--fs-14)', fontWeight: 800 }}>{title}</div>
        {right}
      </div>
      {children}
    </div>
  );
}

function Team({ lang, onOpenPerson, onAdd, canManage, currentUser, peopleVer }) {
  const t = GF_T[lang];
  const deptName = (id) => { const d = GF_DEPARTMENTS.find((x) => x.id === id); return d ? (lang === 'mk' ? d.mk : d.name) : id; };
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800 }}>{t.team}</span>
        <Badge tone="neutral">{GF_PEOPLE.length}</Badge>
        <div style={{ flex: 1 }} />
        {canManage
          ? <Button onClick={onAdd}>{I2('Plus', 15)}&nbsp;{lang === 'mk' ? 'Додади член' : 'Add member'}</Button>
          : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-muted)' }}>{I2('Shield', 14)}{lang === 'mk' ? 'Само преглед' : 'View only'}</span>}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 14 }}>
        {GF_PEOPLE.map((p) => (
          <div key={p.name} onClick={() => onOpenPerson && onOpenPerson(p)} style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', padding: 16, boxShadow: 'var(--sh-1)', display: 'flex', flexDirection: 'column', gap: 12, cursor: 'pointer', transition: 'box-shadow var(--dur-ui), transform var(--dur-ui)' }}
            onMouseEnter={(e) => { e.currentTarget.style.boxShadow = 'var(--sh-2)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'var(--sh-1)'; e.currentTarget.style.transform = 'none'; }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Avatar name={p.name} size={42} color={p.color} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 'var(--fs-14)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}{p.id === currentUser && <span style={{ marginLeft: 7, fontSize: 'var(--fs-10)', fontWeight: 800, color: 'var(--primary)', background: 'var(--primary-soft)', borderRadius: 999, padding: '2px 7px', verticalAlign: 'middle' }}>{lang === 'mk' ? 'ВИЕ' : 'YOU'}</span>}</div>
                <div style={{ fontSize: 'var(--fs-12)', color: 'var(--text-body)', fontWeight: 600 }}>{(GF_ROLES[p.role] ? GF_ROLES[p.role][lang] : p.roleLabel)}</div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: p.color }} />
              <span style={{ fontSize: 'var(--fs-12)', fontWeight: 600, color: 'var(--text-body)' }}>{deptName(p.dept)}</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1, background: 'var(--surface-2)', borderRadius: 'var(--r-sm)', padding: '8px 10px', textAlign: 'center' }}>
                <div style={{ fontWeight: 800, fontSize: 'var(--fs-17)' }}>{p.active}</div>
                <div style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.03em' }}>{t.working}</div>
              </div>
              <div style={{ flex: 1, background: 'var(--green-100)', borderRadius: 'var(--r-sm)', padding: '8px 10px', textAlign: 'center' }}>
                <div style={{ fontWeight: 800, fontSize: 'var(--fs-17)', color: 'var(--green-700)' }}>{p.done}</div>
                <div style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: 'var(--green-700)', textTransform: 'uppercase', letterSpacing: '.03em' }}>Done</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Timeline({ lang, tasks }) {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const daysMk = { Mon: 'Пон', Tue: 'Вто', Wed: 'Сре', Thu: 'Чет', Fri: 'Пет' };
  return (
    <div style={{ overflow: 'auto', height: '100%', padding: 24 }}>
      <div style={{ fontSize: 'var(--fs-22)', fontWeight: 800, marginBottom: 16 }}>{GF_T[lang].timeline}</div>
      <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', overflow: 'hidden', minWidth: 760 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '160px repeat(5, 1fr)', borderBottom: '1px solid var(--line)' }}>
          <div style={{ padding: '12px 16px', fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.03em' }}>{GF_T[lang].depts}</div>
          {days.map((d) => <div key={d} style={{ padding: '12px 8px', textAlign: 'center', fontSize: 'var(--fs-12)', fontWeight: 700, borderLeft: '1px solid var(--line)' }}>{lang === 'mk' ? daysMk[d] : d}</div>)}
        </div>
        {GF_DEPARTMENTS.map((d) => (
          <div key={d.id} style={{ display: 'grid', gridTemplateColumns: '160px repeat(5, 1fr)', borderBottom: '1px solid var(--line-2)' }}>
            <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--fs-13)', fontWeight: 700 }}>
              <span style={{ width: 9, height: 9, borderRadius: 999, background: d.color, flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{lang === 'mk' ? d.mk : d.name}</span>
            </div>
            {days.map((day) => {
              const items = tasks.filter((x) => x.dept === d.id && x.day === day);
              return (
                <div key={day} style={{ borderLeft: '1px solid var(--line-2)', padding: 6, display: 'flex', flexDirection: 'column', gap: 4, minHeight: 52 }}>
                  {items.map((x) => (
                    <div key={x.id} title={x.title} style={{
                      fontSize: 'var(--fs-10)', fontWeight: 700, padding: '4px 7px', borderRadius: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      background: DS2.STATUS[x.status].bg, color: DS2.STATUS[x.status].fg,
                    }}>{x.title}</div>
                  ))}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function Coordination({ lang, handoffs, onAdvance }) {
  const t = GF_T[lang];
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24 }}>
      <div style={{ fontSize: 'var(--fs-22)', fontWeight: 800, marginBottom: 4 }}>{t.coord}</div>
      <p style={{ margin: '0 0 18px', fontSize: 'var(--fs-13)', color: 'var(--text-body)', fontWeight: 500 }}>
        {lang === 'mk' ? 'Предавање меѓу оддели — што чека кого. Кликни за да напредуваш статус.' : 'Cross-department handoffs — what\u2019s waiting on whom. Click a status to advance it.'}
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {handoffs.map((h, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', padding: '14px 16px', boxShadow: 'var(--sh-1)', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-body)' }}>
              <span>{h.from}</span>{I2('ArrowRight', 15)}<span style={{ color: 'var(--text-strong)' }}>{h.to}</span>
            </div>
            <div style={{ flex: 1, minWidth: 220, fontSize: 'var(--fs-13)', fontWeight: 600 }}>{h.item}</div>
            <Avatar name={h.by} size={26} />
            <DS2.StatusPill status={h.status} lang={lang} onClick={() => onAdvance(i)} />
          </div>
        ))}
      </div>
    </div>
  );
}

function AIReport({ lang, tasks, onToast }) {
  const L = lang === 'mk';
  const STATUS_LABEL = window.STATUS_LABEL, STATUS_COLOR = window.STATUS_COLOR;
  const T = tasks || GF_TASKS;
  const statuses = ['done', 'working', 'review', 'stuck', 'postponed', 'pending'];
  const statusCount = (s) => T.filter((x) => x.status === s).length;
  const total = T.length || 1;
  const donePct = Math.round((statusCount('done') / total) * 100);
  // weekday activity (sum of session hours by first day)
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const dayMk = { Mon: 'Пон', Tue: 'Вто', Wed: 'Сре', Thu: 'Чет', Fri: 'Пет' };
  const dayHours = days.map((d) => T.filter((x) => (x.days || [x.day]).includes(d)).reduce((s, x) => s + (x.sessionHours || 1.5), 0));
  const maxH = Math.max(...dayHours, 1);
  const busiest = days[dayHours.indexOf(maxH)];
  // dept breakdown
  const deptRows = GF_DEPARTMENTS.map((d) => ({ d, n: T.filter((x) => x.dept === d.id).length })).filter((o) => o.n > 0).sort((a, b) => b.n - a.n);
  const maxDept = Math.max(...deptRows.map((o) => o.n), 1);
  const [mode, setMode] = React.useState('report');
  const [submitted, setSubmitted] = React.useState(false);
  const isPlan = mode === 'plan';
  const download = (filename, text, mime) => {
    const blob = new Blob([text], { type: mime + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click();
    document.body.removeChild(a); setTimeout(() => URL.revokeObjectURL(url), 1000);
    if (onToast) onToast('success', (L ? 'Извезено: ' : 'Exported ') + filename, 'Download');
  };
  const exportJSON = () => download('weekly-' + mode + '.json', JSON.stringify({ generated: new Date().toISOString(), mode, summary: statuses.map((s) => ({ status: s, count: statusCount(s) })), tasks: T }, null, 2), 'application/json');
  const exportCSV = () => {
    const head = ['id', 'title', 'dept', 'owner', 'status', 'priority', 'due', 'ref', 'hours'];
    const rows = T.map((x) => [x.id, x.title, x.dept, x.owner, x.status, x.pr || x.priority, x.due || '', x.ref || x.refCode || '', x.sessionHours || ''].map((v) => '"' + String(v).replace(/"/g, '""') + '"').join(','));
    download('weekly-' + mode + '.csv', '\uFEFF' + [head.join(','), ...rows].join('\r\n'), 'text/csv');
  };
  const exportMD = () => {
    const lines = ['# GrowFlow Weekly ' + (isPlan ? 'Plan' : 'Report'), '', '_Generated ' + new Date().toLocaleDateString() + ' — informational draft, not an official record_', '', '## Summary', ...statuses.map((s) => '- **' + STATUS_LABEL(lang, s) + '**: ' + statusCount(s)), '', '## Tasks'];
    T.forEach((x) => lines.push('- `' + x.id + '` ' + x.title + ' — ' + STATUS_LABEL(lang, x.status) + (x.ref ? ' (' + x.ref + ')' : '')));
    download('weekly-' + mode + '.md', lines.join('\n'), 'text/markdown');
  };
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 820 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <span style={{ width: 34, height: 34, borderRadius: 999, background: 'var(--violet-soft)', color: 'var(--violet-700)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I2('Sparkles', 18)}</span>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800 }}>{isPlan ? (L ? 'Неделен план' : 'Weekly Plan') : (L ? 'Неделен извештај' : 'Weekly Report')}</span>
        <div style={{ flex: 1 }} />
        <Segmented options={[{ value: 'report', label: L ? 'Извештај' : 'Report' }, { value: 'plan', label: L ? 'План' : 'Plan' }]} value={mode} onChange={(v) => { setMode(v); setSubmitted(false); }} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-muted)' }}>{L ? 'Извези:' : 'Export:'}</span>
        <Button variant="secondary" onClick={exportJSON}>{I2('FileJson', 14)}&nbsp;JSON</Button>
        <Button variant="secondary" onClick={exportCSV}>{I2('Sheet', 14)}&nbsp;CSV</Button>
        <Button variant="secondary" onClick={exportMD}>{I2('FileText', 14)}&nbsp;Markdown</Button>
        <div style={{ flex: 1 }} />
        {submitted
          ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--st-done)', background: 'var(--st-done-soft)', borderRadius: 999, padding: '8px 14px' }}>{I2('CheckCheck', 15)}{isPlan ? (L ? 'Планот е поднесен' : 'Plan submitted') : (L ? 'Извештајот е поднесен' : 'Report submitted')}</span>
          : <Button onClick={() => { setSubmitted(true); if (onToast) onToast('success', (isPlan ? (L ? 'Планот е поднесен' : 'Plan submitted') : (L ? 'Извештајот е поднесен' : 'Report submitted')), 'CheckCheck'); }}>{I2('Send', 15)}&nbsp;{L ? 'Поднеси нацрт' : 'Submit draft'}</Button>}
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        <KpiTile value={donePct + '%'} label={GF_T[lang].completion} tone="green" icon={I2('TrendingUp', 16)} />
        <KpiTile value={total} label={GF_T[lang].total} icon={I2('ListChecks', 16)} />
        <KpiTile value={statusCount('stuck')} label={GF_T[lang].stuck} tone="red" icon={I2('OctagonAlert', 16)} />
        <KpiTile value={L ? dayMk[busiest] : busiest} label={GF_T[lang].busiest} tone="violet" icon={I2('CalendarClock', 16)} />
      </div>

      {/* Status band */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18, marginBottom: 14 }}>
        <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 12 }}>{L ? 'Распределба по статус' : 'Status distribution'}</div>
        <div style={{ display: 'flex', height: 16, borderRadius: 999, overflow: 'hidden', background: 'var(--surface-3)' }}>
          {statuses.map((s) => { const n = statusCount(s); return n ? <div key={s} title={STATUS_LABEL(lang, s) + ': ' + n} style={{ width: (n / total * 100) + '%', background: STATUS_COLOR(s) }} /> : null; })}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 12 }}>
          {statuses.filter(statusCount).map((s) => (
            <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 'var(--fs-12)', fontWeight: 600, color: 'var(--text-body)' }}>
              <span style={{ width: 9, height: 9, borderRadius: 999, background: STATUS_COLOR(s) }} />{STATUS_LABEL(lang, s)} <b style={{ color: 'var(--text-strong)' }}>{statusCount(s)}</b>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
        {/* Activity time band */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18 }}>
          <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 14 }}>{L ? 'Активност по ден' : 'Activity by day'}</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 120 }}>
            {days.map((d, i) => (
              <div key={d} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <div style={{ fontSize: 'var(--fs-10)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)' }}>{dayHours[i].toFixed(0)}h</div>
                <div style={{ width: '100%', height: (dayHours[i] / maxH * 88) + 8, background: d === busiest ? 'var(--primary)' : 'var(--primary-soft)', borderRadius: '6px 6px 0 0', transition: 'height var(--dur-ui)' }} />
                <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-body)' }}>{L ? dayMk[d] : d}</div>
              </div>
            ))}
          </div>
        </div>
        {/* Dept breakdown */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18 }}>
          <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 14 }}>{L ? 'По оддел' : 'By department'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {deptRows.slice(0, 6).map(({ d, n }) => (
              <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: d.color, flexShrink: 0 }} />
                <span style={{ fontSize: 'var(--fs-12)', fontWeight: 600, width: 110, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{L ? d.mk : d.name}</span>
                <div style={{ flex: 1, height: 7, borderRadius: 999, background: 'var(--surface-3)', overflow: 'hidden' }}>
                  <div style={{ width: (n / maxDept * 100) + '%', height: '100%', background: d.color, borderRadius: 999 }} />
                </div>
                <span style={{ fontSize: 'var(--fs-11)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', width: 16, textAlign: 'right' }}>{n}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* AI insights */}
      <div style={{ background: 'linear-gradient(135deg, var(--violet-soft), var(--surface))', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <span style={{ color: 'var(--violet-700)' }}>{I2('Sparkles', 16)}</span>
          <span style={{ fontSize: 'var(--fs-13)', fontWeight: 800 }}>{L ? 'AI увиди' : 'AI insights'}</span>
        </div>
        <p style={{ margin: '0 0 14px', fontSize: 'var(--fs-14)', lineHeight: 1.6, color: 'var(--text-strong)' }}>
          {L
            ? `Тимот заврши ${donePct}% од задачите оваа недела. Главниот ризик е блокадата во QC — примерокот чека вердикт за QC вода и е задоцнет.`
            : `The team completed ${donePct}% of tasks this week. The main risk is the QC blocker — post-curing sampling is waiting on a QC water verdict and is now overdue.`}
        </p>
        <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 6 }}>{L ? 'Препораки' : 'Recommendations'}</div>
        {[
          L ? 'Забрзај го вердиктот на QC водата за F27' : 'Expedite the QC water verdict for batch F27',
          L ? 'Прераспредели 2 задачи од Blagoj кон Ana' : 'Rebalance 2 tasks from Blagoj to Ana',
          L ? 'Планирај го QP прегледот за F25 за петок' : 'Schedule the F25 QP review for Friday',
        ].map((r, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '7px 0', borderTop: i > 0 ? '1px dashed var(--line)' : 'none', fontSize: 'var(--fs-13)', fontWeight: 600 }}>
            <span style={{ color: 'var(--violet-700)' }}>{I2('ArrowRight', 14)}</span>{r}
          </div>
        ))}
      </div>
    </div>
  );
}

function Settings({ lang, setLang, theme, setTheme, notifs, onToggleNotif, aiBackend, setAiBackend, currentUser, setCurrentUser, myPerms }) {
  const t = GF_T[lang];
  const L = lang === 'mk';
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 620, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontSize: 'var(--fs-22)', fontWeight: 800, marginBottom: 2 }}>{t.settings}</div>
      <Panel2 title={lang === 'mk' ? 'Претставување' : 'Appearance'}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div><div style={{ fontWeight: 700, fontSize: 'var(--fs-13)' }}>{lang === 'mk' ? 'Контролна соба (темна тема)' : 'Control-room theme'}</div><div style={{ fontSize: 'var(--fs-12)', color: 'var(--text-muted)' }}>{lang === 'mk' ? 'Темна површина за ноќни смени' : 'Dark surface for night shifts'}</div></div>
          <Switch checked={theme === 'dark'} onChange={(v) => setTheme(v ? 'dark' : 'light')} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div><div style={{ fontWeight: 700, fontSize: 'var(--fs-13)' }}>{lang === 'mk' ? 'Јазик' : 'Language'}</div><div style={{ fontSize: 'var(--fs-12)', color: 'var(--text-muted)' }}>English / Македонски</div></div>
          <Segmented options={[{ value: 'en', label: 'EN' }, { value: 'mk', label: 'МК' }]} value={lang} onChange={setLang} />
        </div>
      </Panel2>
      <Panel2 title={lang === 'mk' ? 'Известувања' : 'Notifications'}>
        {Object.keys(notifs).map((key, i) => (
          <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderTop: i > 0 ? '1px solid var(--line-2)' : 'none' }}>
            <span style={{ fontSize: 'var(--fs-13)', fontWeight: 600 }}>
              {lang === 'mk'
                ? ({ stuck: 'Блокирани задачи', report: 'Неделен AI извештај', handoff: 'Предавања меѓу оддели' })[key]
                : ({ stuck: 'Stuck tasks', report: 'Weekly AI report', handoff: 'Cross-department handoffs' })[key]}
            </span>
            <Switch checked={notifs[key]} onChange={() => onToggleNotif(key)} />
          </div>
        ))}
      </Panel2>
      <Panel2 title={lang === 'mk' ? 'Асистент' : 'Assistant'}>
        <Field label={lang === 'mk' ? 'AI позадина' : 'AI backend'}>
          <PopSelect value={aiBackend} onChange={setAiBackend} title={lang === 'mk' ? 'AI позадина' : 'AI backend'} options={[{ value: 'claude', label: 'Claude' }, { value: 'gpt4', label: 'GPT-4' }, { value: 'local', label: lang === 'mk' ? 'Локално (офлајн)' : 'Local (offline)' }]} />
        </Field>
      </Panel2>
      <Panel2 title={L ? 'Улога и дозволи' : 'Role & permissions'}>
        <Field label={L ? 'Најавен како' : 'Signed in as'}>
          <PopSelect value={currentUser} onChange={setCurrentUser} title={L ? 'Најавен како' : 'Signed in as'} options={GF_PEOPLE.map((p) => ({ value: p.id, label: p.name, sub: GF_ROLES[p.role] ? GF_ROLES[p.role][lang] : p.role, color: p.color }))} />
        </Field>
        <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, letterSpacing: '.04em', color: 'var(--text-muted)', textTransform: 'uppercase', margin: '4px 0 8px' }}>{L ? 'Дозволи за оваа улога' : 'Permissions for this role'}</div>
        {myPerms && [
          [L ? 'Создавање задачи' : 'Create tasks', myPerms.create],
          [L ? 'Уреди сите задачи' : 'Edit any task', myPerms.editAny],
          [L ? 'Избриши сите задачи' : 'Delete any task', myPerms.deleteAny],
          [L ? 'Промени статус на сите' : 'Change any status', myPerms.status === 'any'],
          [L ? 'Промени статус (само свои)' : 'Change status (own only)', myPerms.status === 'own'],
          [L ? 'Преглед на тим' : 'View team', myPerms.team],
        ].map(([label, on]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '6px 0', fontSize: 'var(--fs-13)', fontWeight: 600, color: on ? 'var(--text-strong)' : 'var(--text-faint)' }}>
            <span style={{ color: on ? 'var(--st-done)' : 'var(--text-faint)', display: 'inline-flex' }}>{I2(on ? 'Check' : 'Minus', 15)}</span>{label}
          </div>
        ))}
      </Panel2>
    </div>
  );
}

function AuditTrail({ lang }) {
  const L = lang === 'mk';
  const actions = {
    create:  { en: 'created task',    mk: 'создаде задача',      icon: 'Plus',        color: 'var(--st-done)' },
    status:  { en: 'changed status',  mk: 'смени статус',         icon: 'RefreshCw',   color: 'var(--st-working)' },
    assign:  { en: 'assigned',        mk: 'додели',               icon: 'UserPlus',    color: 'var(--st-review)' },
    comment: { en: 'commented on',    mk: 'коментираше на',       icon: 'MessageSquare', color: '#7A5BE0' },
    release: { en: 'released batch',  mk: 'ослободи серија',       icon: 'ShieldCheck', color: 'var(--pr-critical)' },
    edit:    { en: 'edited',          mk: 'уреди',                 icon: 'Pencil',      color: 'var(--text-muted)' },
  };
  const log = [
    { who: 'elena',  act: 'release', obj: 'Batch F25',                 t: '14:02', d: L ? 'Денес' : 'Today' },
    { who: 'blagoj', act: 'status',  obj: 'T-4KZ9 → Working',          t: '13:41', d: L ? 'Денес' : 'Today' },
    { who: 'ana',    act: 'comment', obj: 'T-1H7C',                    t: '11:20', d: L ? 'Денес' : 'Today' },
    { who: 'ivo',    act: 'status',  obj: 'T-2M1P → Stuck',            t: '09:58', d: L ? 'Денес' : 'Today' },
    { who: 'marko',  act: 'assign',  obj: 'Sara M → T-8Q4A',          t: '17:30', d: L ? 'Вчера' : 'Yesterday' },
    { who: 'goran',  act: 'create',  obj: 'T-3T7L Mother-plant check', t: '16:04', d: L ? 'Вчера' : 'Yesterday' },
    { who: 'sara',   act: 'edit',    obj: 'T-8Q4A transport SOP',      t: '15:12', d: L ? 'Вчера' : 'Yesterday' },
    { who: 'blagoj', act: 'create',  obj: 'T-4KZ9 HPLC validation',    t: '08:30', d: L ? 'Вчера' : 'Yesterday' },
  ];
  let lastDay = null;
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800 }}>{L ? 'Дневник на активност' : 'Audit trail'}</span>
        <Badge tone="neutral">{log.length}</Badge>
      </div>
      <div style={{ position: 'relative' }}>
        {log.map((e, i) => {
          const a = actions[e.act]; const p = GF_PERSON(e.who);
          const showDay = e.d !== lastDay; lastDay = e.d;
          return (
            <React.Fragment key={i}>
              {showDay && <div style={{ fontSize: 'var(--fs-11)', fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--text-muted)', margin: (i ? '18px' : '0') + ' 0 10px' }}>{e.d}</div>}
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '8px 0' }}>
                <span style={{ width: 32, height: 32, borderRadius: 999, background: 'var(--surface-2)', border: '1px solid var(--line)', color: a.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{I2(a.icon, 15)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 'var(--fs-13)', color: 'var(--text-strong)', lineHeight: 1.5 }}>
                    <b>{p.name}</b> <span style={{ color: 'var(--text-body)' }}>{a[lang]}</span> <b style={{ color: a.color }}>{e.obj}</b>
                  </div>
                </div>
                <span style={{ fontSize: 'var(--fs-11)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', flexShrink: 0 }}>{e.t}</span>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

function ImportView({ lang, onToast }) {
  const L = lang === 'mk';
  const [rows, setRows] = React.useState([
    { title: 'Calibrate RH sensor — Flower room 3', dept: 'flower', type: 'other', pri: 'high', ok: true },
    { title: 'CoA compile — Batch F25', dept: 'qa', type: 'document', pri: 'critical', ok: true },
    { title: 'Restock nutrient A/B — Veg', dept: 'irr', type: 'other', pri: 'medium', ok: true },
    { title: '', dept: 'prod', type: 'admin', pri: 'low', ok: false },
    { title: 'Line clearance — Packaging', dept: 'prod', type: 'sop', pri: 'medium', ok: true },
  ]);
  const valid = rows.filter((r) => r.ok).length;
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 820 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800 }}>{L ? 'Увоз на задачи' : 'Import tasks'}</span>
      </div>
      <p style={{ margin: '0 0 16px', fontSize: 'var(--fs-13)', color: 'var(--text-body)', fontWeight: 500 }}>{L ? 'Залепи CSV или пушти датотека — редовите се распознаваат автоматски.' : 'Paste CSV or drop a file — rows are parsed and validated automatically.'}</p>
      <div style={{ border: '2px dashed var(--line)', borderRadius: 'var(--r-lg)', padding: '28px 20px', textAlign: 'center', background: 'var(--surface-2)', marginBottom: 18, cursor: 'pointer' }}>
        <span style={{ color: 'var(--primary)', display: 'inline-flex', marginBottom: 8 }}>{I2('Upload', 26)}</span>
        <div style={{ fontSize: 'var(--fs-14)', fontWeight: 700 }}>{L ? 'Пушти CSV тука' : 'Drop a CSV here'}</div>
        <div style={{ fontSize: 'var(--fs-12)', color: 'var(--text-muted)', fontWeight: 600, marginTop: 3 }}>{L ? 'или кликни за да прелистиш' : 'or click to browse — title, dept, type, priority'}</div>
      </div>
      <div style={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '24px 1fr 130px 100px 90px', gap: 10, padding: '10px 14px', borderBottom: '1px solid var(--line)', fontSize: 'var(--fs-10)', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)' }}>
          <span /><span>{L ? 'Наслов' : 'Title'}</span><span>{L ? 'Оддел' : 'Dept'}</span><span>{L ? 'Тип' : 'Type'}</span><span>{L ? 'Приоритет' : 'Priority'}</span>
        </div>
        {rows.map((r, i) => {
          const d = GF_DEPARTMENTS.find((x) => x.id === r.dept) || {};
          return (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '24px 1fr 130px 100px 90px', gap: 10, padding: '11px 14px', borderBottom: i < rows.length - 1 ? '1px solid var(--line-2)' : 'none', alignItems: 'center', background: r.ok ? 'transparent' : 'var(--st-stuck-soft)' }}>
              <span style={{ color: r.ok ? 'var(--st-done)' : 'var(--st-stuck)', display: 'inline-flex' }}>{I2(r.ok ? 'CircleCheck' : 'CircleAlert', 16)}</span>
              <span style={{ fontSize: 'var(--fs-13)', fontWeight: 600, color: r.ok ? 'var(--text-strong)' : 'var(--st-stuck)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title || (L ? '⚠ Недостига наслов' : '⚠ Missing title')}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--fs-12)', fontWeight: 600 }}><span style={{ width: 8, height: 8, borderRadius: 999, background: d.color }} />{L ? d.mk : d.name}</span>
              <span style={{ fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-body)' }}>{GF_TASK_TYPES[r.type] ? GF_TASK_TYPES[r.type][lang] : r.type}</span>
              <PriorityTag priority={r.pri} />
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 16 }}>
        <span style={{ fontSize: 'var(--fs-13)', fontWeight: 600, color: 'var(--text-body)' }}>{valid}/{rows.length} {L ? 'валидни редови' : 'valid rows'}</span>
        <div style={{ flex: 1 }} />
        <Button variant="secondary" onClick={() => setRows((rs) => rs.filter((r) => r.ok))}>{L ? 'Отстрани неважечки' : 'Drop invalid'}</Button>
        <Button onClick={() => onToast && onToast('success', `${valid} ${L ? 'задачи увезени' : 'tasks imported'}`, 'Check')}>{L ? `Увези ${valid}` : `Import ${valid}`}</Button>
      </div>
    </div>
  );
}

// ═══════════════════════════ Executive Analytics ═══════════════════════════
function Analytics({ lang }) {
  const L = lang === 'mk';
  const eyebrow = { fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 12 };
  const card = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18 };
  const T = GF_TASKS;
  const done = (arr) => arr.filter((x) => x.status === 'done').length;
  // per-department completion
  const deptRows = GF_DEPARTMENTS.map((d) => {
    const dt = T.filter((x) => x.dept === d.id);
    const heads = GF_PEOPLE.filter((p) => p.dept === d.id).length;
    return { d, n: dt.length, done: done(dt), heads };
  }).filter((o) => o.n > 0).sort((a, b) => b.n - a.n);
  // per-person workload
  const people = GF_PEOPLE.map((p) => {
    const owned = T.filter((x) => x.owner === p.id);
    return { p, load: owned.length, done: done(owned) };
  }).filter((o) => o.load > 0).sort((a, b) => b.load - a.load);
  const maxLoad = Math.max(...people.map((o) => o.load), 1);
  const total = T.length || 1;
  const donePct = Math.round((done(T) / total) * 100);
  // report submission tracking (mock per-dept state)
  const subs = ['done', 'done', 'draft', 'due', 'done', 'due'];
  const subMeta = { done: { c: 'var(--green-600)', bg: 'var(--green-100)', en: 'Submitted', mk: 'Поднесено' }, draft: { c: 'var(--amber)', bg: 'var(--amber-soft)', en: 'Draft', mk: 'Нацрт' }, due: { c: 'var(--text-muted)', bg: 'var(--surface-3)', en: 'Not started', mk: 'Не започнато' } };
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{ width: 34, height: 34, borderRadius: 999, background: 'var(--blue-soft)', color: 'var(--blue)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I2('ChartPie', 18)}</span>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800, lineHeight: 1.15, whiteSpace: 'nowrap' }}>{L ? 'Извршна аналитика' : 'Executive Analytics'}</span>
        <span style={{ marginLeft: 'auto', fontSize: 'var(--fs-12)', fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{L ? 'Оваа работна недела · Пет–Чет' : 'This work-week · Fri–Thu'}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        <KpiTile value={donePct + '%'} label={L ? 'Завршеност' : 'Completion'} tone="green" icon={I2('TrendingUp', 16)} />
        <KpiTile value={deptRows.length} label={L ? 'Активни оддели' : 'Active depts'} tone="blue" icon={I2('Building2', 16)} />
        <KpiTile value={GF_PEOPLE.length} label={L ? 'Вкупно луѓе' : 'Headcount'} icon={I2('Users', 16)} />
        <KpiTile value={subs.filter((s) => s === 'done').length + '/' + subs.length} label={L ? 'Извештаи поднесени' : 'Reports in'} tone="violet" icon={I2('FileCheck2', 16)} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 14, marginBottom: 14 }}>
        {/* Department completion */}
        <div style={card}>
          <div style={eyebrow}>{L ? 'Завршеност по оддел' : 'Completion by department'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {deptRows.map(({ d, n, done, heads }) => {
              const pct = Math.round((done / n) * 100);
              return (
                <div key={d.id}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 999, background: d.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 'var(--fs-12)', fontWeight: 700, flex: 1 }}>{L ? d.mk : d.name}</span>
                    <span style={{ fontSize: 'var(--fs-10)', fontWeight: 600, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>{I2('User', 11)}{heads}</span>
                    <span style={{ fontSize: 'var(--fs-11)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-strong)', width: 34, textAlign: 'right' }}>{pct}%</span>
                  </div>
                  <div style={{ height: 8, borderRadius: 999, background: 'var(--surface-3)', overflow: 'hidden' }}>
                    <div style={{ width: pct + '%', height: '100%', background: d.color, borderRadius: 999, transition: 'width var(--dur-ui)' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        {/* Per-person workload */}
        <div style={card}>
          <div style={eyebrow}>{L ? 'Оптоварување по личност' : 'Workload by person'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {people.slice(0, 7).map(({ p, load, done }) => (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Avatar name={p.name} size={28} color={p.color} />
                <span style={{ fontSize: 'var(--fs-12)', fontWeight: 600, width: 96, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                <div style={{ flex: 1, height: 7, borderRadius: 999, background: 'var(--surface-3)', overflow: 'hidden', position: 'relative' }}>
                  <div style={{ width: (load / maxLoad * 100) + '%', height: '100%', background: p.color, borderRadius: 999 }} />
                </div>
                <span style={{ fontSize: 'var(--fs-11)', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', width: 40, textAlign: 'right' }}>{done}/{load}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      {/* Report submission tracking */}
      <div style={{ ...card, marginBottom: 14 }}>
        <div style={eyebrow}>{L ? 'Следење на неделни извештаи' : 'Weekly report submission'}</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          {deptRows.slice(0, 6).map(({ d }, i) => {
            const st = subMeta[subs[i]];
            return (
              <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 12px', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', background: 'var(--surface-2)' }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: d.color, flexShrink: 0 }} />
                <span style={{ fontSize: 'var(--fs-12)', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{L ? d.mk : d.name}</span>
                <span style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: st.c, background: st.bg, padding: '3px 8px', borderRadius: 999 }}>{L ? st.mk : st.en}</span>
              </div>
            );
          })}
        </div>
      </div>
      {/* AI executive summary */}
      <div style={{ background: 'linear-gradient(135deg, var(--blue-soft), var(--surface))', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <span style={{ color: 'var(--violet-700)' }}>{I2('Sparkles', 16)}</span>
          <span style={{ fontSize: 'var(--fs-13)', fontWeight: 800 }}>{L ? 'AI извршно резиме' : 'AI executive summary'}</span>
          <Badge tone="neutral">{L ? 'Информативно' : 'Informational'}</Badge>
        </div>
        <p style={{ margin: 0, fontSize: 'var(--fs-14)', lineHeight: 1.6, color: 'var(--text-strong)' }}>
          {L
            ? `Производството е на ${donePct}% завршеност оваа недела. QA и Flower носат најголемо оптоварување; двата оддела сè уште имаат неподнесени извештаи. Главен ризик: блокирано земање мостри на F27 што чека вердикт за QC вода.`
            : `Production sits at ${donePct}% completion this week. QA and Flower carry the heaviest load; both still have reports outstanding. Top risk: F27 sampling is blocked pending a QC water verdict.`}
        </p>
      </div>
    </div>
  );
}

// ═══════════════════════════ Access Management ═══════════════════════════
function Access({ lang, onToast }) {
  const L = lang === 'mk';
  const eyebrow = { fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 12 };
  const card = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18 };
  // account state per person: active | firstlogin | locked
  const seed = { elena: 'active', ana: 'active', marko: 'firstlogin', ivo: 'active', sara: 'locked', goran: 'firstlogin', blagoj: 'active', kire: 'active' };
  const [rows, setRows] = React.useState(() => GF_PEOPLE.map((p) => ({ p, state: seed[p.id] || 'active' })));
  const [otp, setOtp] = React.useState(null); // {name, code}
  const stMeta = {
    active: { c: 'var(--green-600)', bg: 'var(--green-100)', en: 'Active', mk: 'Активен', icon: 'CircleCheck' },
    firstlogin: { c: 'var(--amber)', bg: 'var(--amber-soft)', en: 'First-login pending', mk: 'Чека прв влез', icon: 'KeyRound' },
    locked: { c: 'var(--red)', bg: 'var(--red-soft)', en: 'Locked', mk: 'Заклучен', icon: 'Lock' },
  };
  const genCode = () => Array.from({ length: 3 }, () => Math.random().toString(36).slice(2, 6).toUpperCase()).join('-');
  const provision = (r) => { const code = genCode(); setOtp({ name: r.p.name, code, kind: 'reset' }); setRows((rs) => rs.map((x) => x.p.id === r.p.id ? { ...x, state: 'firstlogin' } : x)); onToast && onToast('info', (L ? 'Издадена привремена лозинка за ' : 'Temp password issued for ') + r.p.name, 'KeyRound'); };
  const unlock = (r) => { setRows((rs) => rs.map((x) => x.p.id === r.p.id ? { ...x, state: 'active' } : x)); onToast && onToast('success', r.p.name + (L ? ' е отклучен' : ' unlocked'), 'LockOpen'); };
  const roleColor = { admin: 'var(--red)', ceo: 'var(--violet-700)', executive: 'var(--violet-700)', qp: 'var(--blue)', qa: 'var(--blue)', hod: 'var(--green-600)', operator: 'var(--text-muted)', viewer: 'var(--text-muted)' };
  const counts = { active: rows.filter((r) => r.state === 'active').length, firstlogin: rows.filter((r) => r.state === 'firstlogin').length, locked: rows.filter((r) => r.state === 'locked').length };
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{ width: 34, height: 34, borderRadius: 999, background: 'var(--red-soft)', color: 'var(--red)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I2('ShieldCheck', 18)}</span>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800, lineHeight: 1.15, whiteSpace: 'nowrap' }}>{L ? 'Пристап и сметки' : 'Access & Accounts'}</span>
        <Badge tone="red">{L ? 'Само админ' : 'Admin only'}</Badge>
      </div>
      <div style={{ fontSize: 'var(--fs-13)', color: 'var(--text-body)', marginBottom: 16, maxWidth: 620, lineHeight: 1.55 }}>
        {L ? 'Нема самопријавување — сметките ги обезбедува админ со еднократна привремена лозинка. Корисникот мора да ја смени лозинката при првиот влез.' : 'No self-signup — accounts are provisioned by an admin with a one-time temporary password. Users must change it on first login.'}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
        <KpiTile value={counts.active} label={L ? 'Активни' : 'Active'} tone="green" icon={I2('CircleCheck', 16)} />
        <KpiTile value={counts.firstlogin} label={L ? 'Чекаат прв влез' : 'First-login pending'} tone="amber" icon={I2('KeyRound', 16)} />
        <KpiTile value={counts.locked} label={L ? 'Заклучени' : 'Locked'} tone="red" icon={I2('Lock', 16)} />
      </div>
      {otp && (
        <div style={{ ...card, border: '1px solid var(--amber)', background: 'var(--amber-soft)', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ color: 'var(--amber)' }}>{I2('KeyRound', 22)}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-strong)' }}>{L ? 'Еднократна привремена лозинка за ' : 'One-time temporary password for '}{otp.name}</div>
            <div style={{ fontSize: 'var(--fs-11)', color: 'var(--text-body)', fontWeight: 600 }}>{L ? 'Прикажана само еднаш — копирајте и предајте безбедно.' : 'Shown once — copy and hand over securely.'}</div>
          </div>
          <code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-16)', fontWeight: 700, letterSpacing: '.06em', background: 'var(--surface)', border: '1px dashed var(--amber)', borderRadius: 'var(--r-sm)', padding: '8px 14px', color: 'var(--text-strong)' }}>{otp.code}</code>
          <IconButton icon={I2('X', 16)} onClick={() => setOtp(null)} />
        </div>
      )}
      <div style={card}>
        <div style={eyebrow}>{L ? 'Директориум на корисници' : 'User directory'}</div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {rows.map((r, i) => {
            const st = stMeta[r.state];
            const roleL = GF_ROLES[r.p.role] ? GF_ROLES[r.p.role][lang] : r.p.roleLabel;
            return (
              <div key={r.p.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 4px', borderTop: i ? '1px solid var(--line)' : 'none' }}>
                <Avatar name={r.p.name} size={34} color={r.p.color} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 'var(--fs-13)', fontWeight: 700 }}>{r.p.name}</div>
                  <div style={{ fontSize: 'var(--fs-11)', fontWeight: 600, color: roleColor[r.p.role] || 'var(--text-muted)' }}>{roleL}</div>
                </div>
                <span style={{ fontSize: 'var(--fs-11)', fontWeight: 600, color: 'var(--text-muted)', width: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(() => { const d = GF_DEPARTMENTS.find((x) => x.id === r.p.dept); return d ? (L ? d.mk : d.name) : (L ? 'Меѓу-оддел' : 'Cross-dept'); })()}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 'var(--fs-10)', fontWeight: 700, color: st.c, background: st.bg, padding: '4px 9px', borderRadius: 999, width: 148, justifyContent: 'center' }}>{I2(st.icon, 12)}{L ? st.mk : st.en}</span>
                <div style={{ width: 120, display: 'flex', justifyContent: 'flex-end' }}>
                  {r.state === 'locked'
                    ? <Button size="sm" variant="ghost" onClick={() => unlock(r)}>{L ? 'Отклучи' : 'Unlock'}</Button>
                    : <Button size="sm" variant="ghost" onClick={() => provision(r)}>{L ? 'Ресетирај' : 'Reset'}</Button>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════ Governance / Change control ═══════════════════════════
function Governance({ lang, onToast }) {
  const L = lang === 'mk';
  const eyebrow = { fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 12 };
  const card = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18 };
  // Field registry: core columns + long-tail JSON attributes
  const coreFields = [
    { k: 'title', t: 'text', en: 'Task title', mk: 'Наслов' },
    { k: 'status', t: 'enum', en: 'Status', mk: 'Статус' },
    { k: 'priority', t: 'enum', en: 'Priority', mk: 'Приоритет' },
    { k: 'owner', t: 'ref', en: 'Accountable owner', mk: 'Одговорен носител' },
    { k: 'dept', t: 'ref', en: 'Department', mk: 'Оддел' },
    { k: 'due', t: 'date', en: 'Due date', mk: 'Рок' },
  ];
  const extFields = [
    { k: 'batch', t: 'json', en: 'Batch / lot', mk: 'Серија / лот' },
    { k: 'room', t: 'json', en: 'Room / location', mk: 'Соба / локација' },
    { k: 'sopRef', t: 'json', en: 'SOP pointer', mk: 'СОП покажувач' },
  ];
  const typeMeta = { text: 'var(--text-muted)', enum: 'var(--violet-700)', ref: 'var(--blue)', date: 'var(--green-600)', json: 'var(--amber)' };
  const [props, setProps] = React.useState([
    { id: 1, title: L ? 'Додај поле „Проценета траба (часови)“' : 'Add "Estimated effort (hours)" field', by: 'schema advisor', kind: L ? 'Ново поле' : 'New field', state: 'pending', rationale: L ? 'Три оддели рачно ги следат часовите во белешки.' : 'Three departments track hours manually in notes.' },
    { id: 2, title: L ? 'Дозволи статус „Блокирано однадвор“' : 'Allow "Blocked-external" status', by: 'compliance', kind: L ? 'Промена на работек' : 'Workflow change', state: 'approved', rationale: L ? 'Ги раздвојува внатрешните блокади од оние кај добавувачите.' : 'Separates internal blockers from supplier-side ones.' },
    { id: 3, title: L ? 'Спои „soba“ и „location“ во едно поле' : 'Merge "soba" and "location" into one field', by: 'analytics', kind: L ? 'Миграција' : 'Migration', state: 'applied', rationale: L ? 'Дупликат атрибути од две-јазичен внес.' : 'Duplicate attributes from bilingual entry.' },
    { id: 4, title: L ? 'Задолжителна причина при откажување' : 'Require reason when declining assignment', by: 'weekly coordinator', kind: L ? 'Валидација' : 'Validation', state: 'rejected', rationale: L ? 'Веќе покриено со коментар-нишка.' : 'Already covered by the comment thread.' },
  ]);
  const stMeta = {
    pending: { c: 'var(--amber)', bg: 'var(--amber-soft)', en: 'Pending', mk: 'Чека' },
    approved: { c: 'var(--blue)', bg: 'var(--blue-soft)', en: 'Approved', mk: 'Одобрено' },
    applied: { c: 'var(--green-600)', bg: 'var(--green-100)', en: 'Applied', mk: 'Применето' },
    rejected: { c: 'var(--red)', bg: 'var(--red-soft)', en: 'Rejected', mk: 'Одбиено' },
  };
  const act = (id, to) => { setProps((ps) => ps.map((p) => p.id === id ? { ...p, state: to } : p)); onToast && onToast(to === 'rejected' ? 'error' : 'success', (L ? 'Предлог ' : 'Proposal ') + (to === 'approved' ? (L ? 'одобрен' : 'approved') : (L ? 'одбиен' : 'rejected')), to === 'rejected' ? 'X' : 'Check'); };
  const FieldChip = ({ f }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 11px', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', background: 'var(--surface-2)' }}>
      <code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-strong)' }}>{f.k}</code>
      <span style={{ fontSize: 'var(--fs-12)', fontWeight: 600, flex: 1, color: 'var(--text-body)' }}>{L ? f.mk : f.en}</span>
      <span style={{ fontSize: 'var(--fs-9)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.05em', color: typeMeta[f.t], border: '1px solid currentColor', borderRadius: 999, padding: '2px 7px' }}>{f.t}</span>
    </div>
  );
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{ width: 34, height: 34, borderRadius: 999, background: 'var(--violet-soft)', color: 'var(--violet-700)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I2('GitPullRequestArrow', 18)}</span>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800, lineHeight: 1.15, whiteSpace: 'nowrap' }}>{L ? 'Управување и контрола на промени' : 'Governance & Change Control'}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: 14, alignItems: 'start' }}>
        {/* Field registry */}
        <div style={card}>
          <div style={eyebrow}>{L ? 'Регистар на полиња' : 'Field registry'}</div>
          <div style={{ fontSize: 'var(--fs-10)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', margin: '2px 0 8px' }}>{L ? 'Основни колони' : 'Core columns'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>{coreFields.map((f) => <FieldChip key={f.k} f={f} />)}</div>
          <div style={{ fontSize: 'var(--fs-10)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', margin: '2px 0 8px' }}>{L ? 'Долгорепни JSON атрибути' : 'Long-tail JSON attributes'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{extFields.map((f) => <FieldChip key={f.k} f={f} />)}</div>
        </div>
        {/* Proposals */}
        <div style={card}>
          <div style={eyebrow}>{L ? 'AI-предложени промени' : 'AI-proposed changes'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {props.map((p) => {
              const st = stMeta[p.state];
              return (
                <div key={p.id} style={{ border: '1px solid var(--line)', borderRadius: 'var(--r-md)', padding: 13, background: 'var(--surface-2)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 6 }}>
                    <span style={{ color: 'var(--violet-700)', marginTop: 1 }}>{I2('Sparkles', 14)}</span>
                    <span style={{ fontSize: 'var(--fs-13)', fontWeight: 700, flex: 1, lineHeight: 1.35 }}>{p.title}</span>
                    <span style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: st.c, background: st.bg, padding: '3px 8px', borderRadius: 999, flexShrink: 0 }}>{L ? st.mk : st.en}</span>
                  </div>
                  <div style={{ fontSize: 'var(--fs-12)', color: 'var(--text-body)', lineHeight: 1.5, marginBottom: 9, paddingLeft: 22 }}>{p.rationale}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 22 }}>
                    <span style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>{p.kind}</span>
                    <span style={{ fontSize: 'var(--fs-10)', color: 'var(--text-muted)' }}>· {p.by}</span>
                    {p.state === 'pending' && (
                      <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                        <Button size="sm" variant="ghost" onClick={() => act(p.id, 'rejected')}>{L ? 'Одбиј' : 'Reject'}</Button>
                        <Button size="sm" onClick={() => act(p.id, 'approved')}>{L ? 'Одобри' : 'Approve'}</Button>
                      </div>
                    )}
                    {p.state === 'approved' && (
                      <div style={{ marginLeft: 'auto' }}><Button size="sm" onClick={() => act(p.id, 'applied')}>{L ? 'Примени' : 'Apply'}</Button></div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 12, fontSize: 'var(--fs-11)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6, lineHeight: 1.5 }}>
            {I2('Info', 13)}{L ? 'Секоја промена бара човечко одобрување пред примена — ниедна не се применува автоматски.' : 'Every change requires human approval before it is applied — nothing is auto-applied.'}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════ Weekly Planning (draft → submit → approve) ═══════════════════════════
function Planning({ lang, onToast }) {
  const L = lang === 'mk';
  const eyebrow = { fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', marginBottom: 12 };
  const card = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18 };
  const stMeta = {
    draft: { c: 'var(--text-muted)', bg: 'var(--surface-2)', en: 'Draft', mk: 'Нацрт', icon: 'PencilLine' },
    submitted: { c: 'var(--blue)', bg: 'var(--blue-soft)', en: 'Submitted', mk: 'Поднесено', icon: 'Send' },
    approved: { c: 'var(--green-600)', bg: 'var(--green-100)', en: 'Approved', mk: 'Одобрено', icon: 'CircleCheck' },
    changes: { c: 'var(--amber)', bg: 'var(--amber-soft)', en: 'Changes asked', mk: 'Бара промени', icon: 'Undo2' },
  };
  const seed = [
    { dep: 'qc', state: 'submitted', items: [
      { t: L ? 'HPLC валидација — F27' : 'HPLC validation — F27', pr: 'critical', d: L ? 'Чет' : 'Thu' },
      { t: L ? 'Пост-сушење мостри — F27' : 'Post-cure sampling — F27', pr: 'high', d: L ? 'Пон' : 'Mon' },
      { t: L ? 'Калибрација на pH метар' : 'pH meter calibration', pr: 'medium', d: L ? 'Сре' : 'Wed' },
    ] },
    { dep: 'flower', state: 'draft', items: [
      { t: L ? 'Жетва блок B — недела 9' : 'Harvest block B — week 9', pr: 'high', d: L ? 'Вто' : 'Tue' },
      { t: L ? 'IPM скенирање' : 'IPM scouting', pr: 'medium', d: L ? 'Пет' : 'Fri' },
    ] },
    { dep: 'qa', state: 'approved', items: [
      { t: L ? 'QP преглед — F25 ослободување' : 'QP review — F25 release', pr: 'critical', d: L ? 'Пет' : 'Fri' },
      { t: L ? 'CAPA затворање — RH сензор' : 'CAPA closure — RH sensor', pr: 'high', d: L ? 'Чет' : 'Thu' },
    ] },
    { dep: 'prod', state: 'changes', items: [
      { t: L ? 'Пакување серија F24' : 'Packaging run F24', pr: 'medium', d: L ? 'Сре' : 'Wed' },
    ] },
  ];
  const [plans, setPlans] = React.useState(seed);
  const [sel, setSel] = React.useState('qc');
  const cur = plans.find((p) => p.dep === sel) || plans[0];
  const depName = (id) => { const d = GF_DEPARTMENTS.find((x) => x.id === id); return d ? (L ? d.mk : d.name) : id; };
  const depColor = (id) => { const d = GF_DEPARTMENTS.find((x) => x.id === id); return d ? d.color : 'var(--primary)'; };
  const set = (dep, state) => setPlans((ps) => ps.map((p) => p.dep === dep ? { ...p, state } : p));
  const priColor = { critical: 'var(--red)', high: 'var(--orange)', medium: 'var(--amber)', low: 'var(--text-muted)' };
  const priLabel = { critical: L ? 'Критичен' : 'Critical', high: L ? 'Висок' : 'High', medium: L ? 'Среден' : 'Medium', low: L ? 'Низок' : 'Low' };

  function submit() { set(cur.dep, 'submitted'); onToast && onToast('success', (L ? 'План поднесен — ' : 'Plan submitted — ') + depName(cur.dep), 'Send'); }
  function approve() { set(cur.dep, 'approved'); onToast && onToast('success', (L ? 'План одобрен — ' : 'Plan approved — ') + depName(cur.dep), 'CircleCheck'); }
  function askChanges() { set(cur.dep, 'changes'); onToast && onToast('info', (L ? 'Побарани промени — ' : 'Changes requested — ') + depName(cur.dep), 'Undo2'); }

  const submittedCount = plans.filter((p) => p.state === 'submitted' || p.state === 'approved').length;

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 1000 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span style={{ width: 34, height: 34, borderRadius: 999, background: 'var(--primary-soft)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I2('CalendarRange', 18)}</span>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800, lineHeight: 1.15, whiteSpace: 'nowrap' }}>{L ? 'Неделно планирање' : 'Weekly Planning'}</span>
      </div>
      <div style={{ fontSize: 'var(--fs-13)', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 18 }}>{L ? `Недела 09 · ${submittedCount}/${plans.length} планови поднесени` : `Week 09 · ${submittedCount}/${plans.length} plans submitted`}</div>
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 14, alignItems: 'start' }}>
        {/* dept list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {plans.map((p) => {
            const st = stMeta[p.state];
            return (
              <button key={p.dep} onClick={() => setSel(p.dep)} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '12px 13px', borderRadius: 'var(--r-md)', border: `1px solid ${sel === p.dep ? 'var(--primary)' : 'var(--line)'}`, background: sel === p.dep ? 'color-mix(in srgb, var(--primary) 7%, var(--surface))' : 'var(--surface)', cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left', boxShadow: 'var(--sh-1)' }}>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: depColor(p.dep), flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 'var(--fs-13)', fontWeight: 700, color: 'var(--text-strong)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{depName(p.dep)}</div>
                  <div style={{ fontSize: 'var(--fs-11)', fontWeight: 600, color: 'var(--text-muted)' }}>{p.items.length} {L ? 'ставки' : 'items'}</div>
                </div>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 'var(--fs-10)', fontWeight: 800, color: st.c, background: st.bg, padding: '3px 8px', borderRadius: 999 }}>{I2(st.icon, 11)}{L ? st.mk : st.en}</span>
              </button>
            );
          })}
        </div>
        {/* selected plan */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ width: 12, height: 12, borderRadius: 999, background: depColor(cur.dep) }} />
            <div style={{ fontSize: 'var(--fs-18)', fontWeight: 800, flex: 1 }}>{depName(cur.dep)}</div>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 'var(--fs-11)', fontWeight: 800, color: stMeta[cur.state].c, background: stMeta[cur.state].bg, padding: '5px 11px', borderRadius: 999 }}>{I2(stMeta[cur.state].icon, 13)}{L ? stMeta[cur.state].mk : stMeta[cur.state].en}</span>
          </div>
          <div style={eyebrow}>{L ? 'Обврски за неделата' : 'Commitments for the week'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {cur.items.map((it, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '11px 13px', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', background: 'var(--surface-2)' }}>
                <span style={{ width: 7, height: 7, borderRadius: 999, background: priColor[it.pr], flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 'var(--fs-13)', fontWeight: 700, color: 'var(--text-strong)' }}>{it.t}</span>
                <span style={{ fontSize: 'var(--fs-10)', fontWeight: 800, color: priColor[it.pr], textTransform: 'uppercase', letterSpacing: '.03em' }}>{priLabel[it.pr]}</span>
                <span style={{ fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-muted)', width: 34, textAlign: 'right' }}>{it.d}</span>
              </div>
            ))}
          </div>
          {/* action bar changes by state */}
          <div style={{ display: 'flex', gap: 9, marginTop: 16, paddingTop: 15, borderTop: '1px solid var(--line)', alignItems: 'center' }}>
            {cur.state === 'draft' && <React.Fragment>
              <span style={{ flex: 1, fontSize: 'var(--fs-12)', color: 'var(--text-muted)', fontWeight: 600 }}>{L ? 'Нацрт — само ти го гледаш ова.' : 'Draft — only you can see this.'}</span>
              <Button onClick={submit}>{I2('Send', 15)}{L ? 'Поднеси план' : 'Submit plan'}</Button>
            </React.Fragment>}
            {cur.state === 'submitted' && <React.Fragment>
              <span style={{ flex: 1, fontSize: 'var(--fs-12)', color: 'var(--text-muted)', fontWeight: 600 }}>{L ? 'Чека преглед од координатор.' : 'Awaiting coordinator review.'}</span>
              <Button variant="ghost" onClick={askChanges}>{I2('Undo2', 15)}{L ? 'Побарај промени' : 'Ask changes'}</Button>
              <Button onClick={approve}>{I2('CircleCheck', 15)}{L ? 'Одобри' : 'Approve'}</Button>
            </React.Fragment>}
            {cur.state === 'approved' && <React.Fragment>
              <span style={{ flex: 1, fontSize: 'var(--fs-13)', color: 'var(--green-600)', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 7 }}>{I2('CircleCheck', 16)}{L ? 'Одобрено — заклучено за неделата.' : 'Approved — locked for the week.'}</span>
              <Button variant="ghost" onClick={() => set(cur.dep, 'draft')}>{I2('RotateCcw', 15)}{L ? 'Отклучи' : 'Reopen'}</Button>
            </React.Fragment>}
            {cur.state === 'changes' && <React.Fragment>
              <span style={{ flex: 1, fontSize: 'var(--fs-12)', color: 'var(--amber)', fontWeight: 700 }}>{L ? 'Координаторот побара промени.' : 'Coordinator requested changes.'}</span>
              <Button onClick={submit}>{I2('Send', 15)}{L ? 'Поднеси повторно' : 'Resubmit'}</Button>
            </React.Fragment>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════ QC Lab mode (sampling gates + disposition) ═══════════════════════════
function QCLab({ lang, onToast }) {
  const L = lang === 'mk';
  const card = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--sh-1)', padding: 18 };
  const gateDefs = [
    { k: 'potency', en: 'Potency (HPLC)', mk: 'Јачина (HPLC)' },
    { k: 'moisture', en: 'Moisture', mk: 'Влага' },
    { k: 'microbial', en: 'Microbial', mk: 'Микробиолошки' },
    { k: 'foreign', en: 'Foreign matter', mk: 'Туѓи материи' },
  ];
  const seed = [
    { id: 'F27', name: L ? 'Серија F27 · Сушено цвеќе' : 'Batch F27 · Dried flower', room: 'Cure-3', gates: { potency: 'pass', moisture: 'pass', microbial: 'test', foreign: 'idle' } },
    { id: 'F26', name: L ? 'Серија F26 · Тримано' : 'Batch F26 · Trimmed', room: 'Cure-1', gates: { potency: 'pass', moisture: 'pass', microbial: 'pass', foreign: 'pass' } },
    { id: 'F28', name: L ? 'Серија F28 · Свежо' : 'Batch F28 · Fresh', room: 'Dry-2', gates: { potency: 'fail', moisture: 'pass', microbial: 'idle', foreign: 'idle' } },
  ];
  const [batches, setBatches] = React.useState(seed);
  const [sel, setSel] = React.useState('F27');
  const cur = batches.find((b) => b.id === sel) || batches[0];
  const gMeta = {
    pass: { c: 'var(--green-600)', bg: 'var(--green-100)', en: 'Pass', mk: 'Помина', icon: 'Check' },
    fail: { c: 'var(--red)', bg: 'var(--red-soft)', en: 'Fail', mk: 'Падна', icon: 'X' },
    test: { c: 'var(--amber)', bg: 'var(--amber-soft)', en: 'Testing', mk: 'Се тестира', icon: 'FlaskConical' },
    idle: { c: 'var(--text-muted)', bg: 'var(--surface-2)', en: 'Not started', mk: 'Не започнато', icon: 'Circle' },
  };
  const setGate = (bid, gk, val) => setBatches((bs) => bs.map((b) => b.id === bid ? { ...b, gates: { ...b.gates, [gk]: val } } : b));
  const gateVals = (b) => gateDefs.map((g) => b.gates[g.k]);
  const allPass = (b) => gateVals(b).every((v) => v === 'pass');
  const anyFail = (b) => gateVals(b).some((v) => v === 'fail');
  const disposition = (b) => anyFail(b) ? 'reject' : allPass(b) ? 'release' : 'hold';
  const dispMeta = {
    release: { c: 'var(--green-600)', bg: 'var(--green-100)', en: 'Ready to release', mk: 'Спремно за ослободување', icon: 'PackageCheck' },
    hold: { c: 'var(--amber)', bg: 'var(--amber-soft)', en: 'On hold', mk: 'На чекање', icon: 'PauseCircle' },
    reject: { c: 'var(--red)', bg: 'var(--red-soft)', en: 'Quarantine', mk: 'Карантин', icon: 'OctagonAlert' },
  };

  function record(gk, val) { setGate(cur.id, gk, val); onToast && onToast(val === 'fail' ? 'error' : 'success', (L ? 'Порта ажурирана: ' : 'Gate recorded: ') + (L ? gateDefs.find((g) => g.k === gk).mk : gateDefs.find((g) => g.k === gk).en), val === 'fail' ? 'X' : 'Check'); }

  const disp = disposition(cur);
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: 24, maxWidth: 1000 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
        <span style={{ width: 34, height: 34, borderRadius: 999, background: 'var(--primary-soft)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I2('FlaskConical', 18)}</span>
        <span style={{ fontSize: 'var(--fs-22)', fontWeight: 800, lineHeight: 1.15, whiteSpace: 'nowrap' }}>{L ? 'QC лабораторија' : 'QC Lab'}</span>
        <span style={{ marginLeft: 8, fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-muted)' }}>{batches.length} {L ? 'серии во ред' : 'batches queued'}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 14, alignItems: 'start' }}>
        {/* batch queue */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {batches.map((b) => {
            const d = dispMeta[disposition(b)];
            const passed = gateVals(b).filter((v) => v === 'pass').length;
            return (
              <button key={b.id} onClick={() => setSel(b.id)} style={{ textAlign: 'left', padding: '13px 14px', borderRadius: 'var(--r-md)', border: `1px solid ${sel === b.id ? 'var(--primary)' : 'var(--line)'}`, background: sel === b.id ? 'color-mix(in srgb, var(--primary) 7%, var(--surface))' : 'var(--surface)', cursor: 'pointer', fontFamily: 'inherit', boxShadow: 'var(--sh-1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-12)', fontWeight: 800, color: 'var(--text-strong)' }}>{b.id}</span>
                  <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 'var(--fs-10)', fontWeight: 800, color: d.c, background: d.bg, padding: '3px 8px', borderRadius: 999 }}>{I2(d.icon, 11)}{L ? d.mk : d.en}</span>
                </div>
                <div style={{ fontSize: 'var(--fs-12)', fontWeight: 600, color: 'var(--text-body)', marginBottom: 8 }}>{b.name}</div>
                <div style={{ display: 'flex', gap: 3 }}>
                  {gateVals(b).map((v, i) => <span key={i} style={{ flex: 1, height: 4, borderRadius: 999, background: gMeta[v].c, opacity: v === 'idle' ? 0.3 : 1 }} />)}
                </div>
                <div style={{ fontSize: 'var(--fs-10)', fontWeight: 700, color: 'var(--text-muted)', marginTop: 5 }}>{passed}/{gateDefs.length} {L ? 'порти поминати' : 'gates passed'}</div>
              </button>
            );
          })}
        </div>
        {/* gate wizard */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-15)', fontWeight: 800 }}>{cur.id}</span>
              <div style={{ fontSize: 'var(--fs-15)', fontWeight: 700, flex: 1 }}>{cur.name}</div>
              <span style={{ fontSize: 'var(--fs-11)', fontWeight: 700, color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 5 }}>{I2('MapPin', 13)}{cur.room}</span>
            </div>
            <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)', margin: '12px 0 10px' }}>{L ? 'Порти за помин/пад' : 'Pass / fail gates'}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {gateDefs.map((g) => {
                const v = cur.gates[g.k]; const m = gMeta[v];
                return (
                  <div key={g.k} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 13px', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', background: 'var(--surface-2)' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flex: 1, fontSize: 'var(--fs-13)', fontWeight: 700, color: 'var(--text-strong)' }}><span style={{ color: m.c, display: 'inline-flex' }}>{I2(m.icon, 15)}</span>{L ? g.mk : g.en}</span>
                    <span style={{ fontSize: 'var(--fs-10)', fontWeight: 800, color: m.c, background: m.bg, padding: '3px 9px', borderRadius: 999, textTransform: 'uppercase', letterSpacing: '.03em' }}>{L ? m.mk : m.en}</span>
                    <div style={{ display: 'flex', gap: 5 }}>
                      <button onClick={() => record(g.k, 'pass')} title={L ? 'Помина' : 'Pass'} style={{ width: 30, height: 30, borderRadius: 'var(--r-sm)', border: `1px solid ${v === 'pass' ? 'var(--green-600)' : 'var(--line)'}`, background: v === 'pass' ? 'var(--green-600)' : 'var(--surface)', color: v === 'pass' ? '#fff' : 'var(--text-muted)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{I2('Check', 15)}</button>
                      <button onClick={() => record(g.k, 'fail')} title={L ? 'Падна' : 'Fail'} style={{ width: 30, height: 30, borderRadius: 'var(--r-sm)', border: `1px solid ${v === 'fail' ? 'var(--red)' : 'var(--line)'}`, background: v === 'fail' ? 'var(--red)' : 'var(--surface)', color: v === 'fail' ? '#fff' : 'var(--text-muted)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{I2('X', 15)}</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          {/* disposition */}
          <div style={{ ...card, borderColor: dispMeta[disp].c, display: 'flex', alignItems: 'center', gap: 13 }}>
            <span style={{ width: 42, height: 42, borderRadius: 999, background: dispMeta[disp].bg, color: dispMeta[disp].c, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{I2(dispMeta[disp].icon, 21)}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 'var(--fs-11)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-muted)' }}>{L ? 'Диспозиција' : 'Disposition'}</div>
              <div style={{ fontSize: 'var(--fs-17)', fontWeight: 800, color: dispMeta[disp].c }}>{L ? dispMeta[disp].mk : dispMeta[disp].en}</div>
            </div>
            {disp === 'release' && <Button onClick={() => onToast && onToast('success', (L ? 'Серијата ослободена: ' : 'Batch released: ') + cur.id, 'PackageCheck')}>{I2('PackageCheck', 15)}{L ? 'Ослободи серија' : 'Release batch'}</Button>}
            {disp === 'reject' && <Button variant="danger" onClick={() => onToast && onToast('error', (L ? 'Серијата во карантин: ' : 'Batch quarantined: ') + cur.id, 'OctagonAlert')}>{I2('OctagonAlert', 15)}{L ? 'Карантин' : 'Quarantine'}</Button>}
            {disp === 'hold' && <span style={{ fontSize: 'var(--fs-12)', fontWeight: 700, color: 'var(--text-muted)' }}>{L ? 'Заврши ги сите порти' : 'Complete all gates'}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

window.GFScreens = { Team, Timeline, Coordination, AIReport, Settings, AuditTrail, ImportView, Analytics, Access, Governance, Planning, QCLab };
})();

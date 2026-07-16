import React, { useEffect, useState } from 'react';
import { api } from './api.js';

export default function AiPanel({ t }) {
  const [fns, setFns] = useState(null); const [q, setQ] = useState('');
  const [out, setOut] = useState(''); const [busy, setBusy] = useState(false);

  useEffect(() => { api.aiFunctions().then(setFns).catch(() => setFns({ catalog: {}, active: [] })); }, []);

  async function run(fn, input) {
    setBusy(true); setOut('');
    try {
      const r = await api.aiInvoke(fn, input);
      setOut(r.available ? r.output : `⚠ ${t.ai_unconfigured} (${r.reason})`);
    } catch (e) { setOut('⚠ ' + e.message); }
    setBusy(false);
  }

  return (
    <div className="ai-box">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <strong>🤖 {t.ai}</strong>
        <span className="muted" style={{ fontSize: 11 }}>
          {fns ? `${fns.active.length}/${Object.keys(fns.catalog).length} agents active` : '…'}
        </span>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn" disabled={busy} onClick={() => run('weekly_summary', 'Summarize this week and flag blockers.')}>{t.ai_summary}</button>
        <input placeholder={t.ai_ask + '…'} value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && q && run('corpus_qa', q)} />
        <button className="btn btn-primary" disabled={busy || !q} onClick={() => run('corpus_qa', q)}>{t.ai_ask}</button>
      </div>
      {(out || busy) && <div className="ai-out">{busy ? '…' : out}</div>}
    </div>
  );
}

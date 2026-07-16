import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { ChevronRight, ChevronDown, FileText, FileStack, CheckCircle2 } from "lucide-react";
import { getTree } from "../api/planner";
import type { Lang, PlannerTreeNode } from "../types/models";

/** Adaptive task tree (task → annex → Draft/Review/Approve). Depth varies by the
 *  nature of the node, never forced uniform — the P1 model, made visible. */
export function TreeView({ t }: { t: (k: string) => string; lang: Lang }) {
  const [roots, setRoots] = useState<PlannerTreeNode[]>([]);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    (async () => {
      try { setRoots(await getTree()); } catch { setRoots([]); } finally { setBusy(false); }
    })();
  }, []);

  const total = useMemo(() => {
    const count = (ns: PlannerTreeNode[]): number => ns.reduce((a, n) => a + 1 + count(n.children), 0);
    return count(roots);
  }, [roots]);

  const allIds = useMemo(() => {
    const ids: string[] = [];
    const walk = (ns: PlannerTreeNode[]) => ns.forEach((n) => { if (n.children.length) { ids.push(n.id); walk(n.children); } });
    walk(roots);
    return ids;
  }, [roots]);

  return (
    <div>
      <div style={headRow}>
        <div>
          <h2 style={h2}>{t("tree")}</h2>
          <div style={sub}>{total} {t("nodes")}</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={ghostBtn} onClick={() => setOpen(new Set(allIds))}>{t("expand_all")}</button>
          <button style={ghostBtn} onClick={() => setOpen(new Set())}>{t("collapse_all")}</button>
        </div>
      </div>
      {busy ? <div style={sub}>…</div> : (
        <div style={panel}>
          {roots.map((n) => <Node key={n.id} node={n} depth={0} open={open} setOpen={setOpen} t={t} />)}
          {roots.length === 0 && <div style={sub}>{t("no_tasks")}</div>}
        </div>
      )}
    </div>
  );
}

function Node({
  node, depth, open, setOpen, t,
}: {
  node: PlannerTreeNode; depth: number; open: Set<string>;
  setOpen: (s: Set<string>) => void; t: (k: string) => string;
}) {
  const hasKids = node.children.length > 0;
  const isOpen = open.has(node.id);
  const toggle = () => {
    const s = new Set(open);
    s.has(node.id) ? s.delete(node.id) : s.add(node.id);
    setOpen(s);
  };
  const KindIcon = node.node_kind === "annex" ? FileStack : node.node_kind === "step" ? CheckCircle2 : FileText;
  return (
    <div>
      <div style={{ ...row, paddingLeft: 8 + depth * 20 }} onClick={hasKids ? toggle : undefined}>
        <span style={{ width: 16, display: "inline-flex", justifyContent: "center", color: "var(--text-quaternary)" }}>
          {hasKids ? (isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}
        </span>
        <KindIcon size={14} style={{ color: kindColor(node.node_kind), flexShrink: 0 }} />
        <span style={{ flex: 1, fontSize: 13, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {node.title}
        </span>
        {node.is_sop && <span style={sopChip}>{t("sop_badge")}</span>}
        {node.annex_count > 0 && <span style={countChip}>{node.annex_count}×{t("annex_kind")}</span>}
        <span style={{ ...statusDot, background: statusColor(node.status) }} />
        <span style={kindTag}>{t(`${node.node_kind}_kind`)}</span>
      </div>
      {hasKids && isOpen && node.children.map((c) => (
        <Node key={c.id} node={c} depth={depth + 1} open={open} setOpen={setOpen} t={t} />
      ))}
    </div>
  );
}

function kindColor(k: string): string {
  return k === "annex" ? "var(--color-accent, #C9A227)" : k === "step" ? "var(--status-pass, #2E7D32)" : "var(--color-brand, #1B3A5C)";
}
function statusColor(s: string): string {
  const map: Record<string, string> = {
    done: "var(--status-pass, #2E7D32)", working: "var(--status-review, #1565C0)",
    review: "var(--status-pending, #B8860B)", stuck: "var(--status-fail, #C62828)",
    postponed: "var(--text-quaternary, #94a3b8)", pending: "var(--text-quaternary, #94a3b8)",
  };
  return map[s] ?? "var(--text-quaternary, #94a3b8)";
}

const headRow: CSSProperties = { display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 16 };
const h2: CSSProperties = { margin: 0, fontSize: 18, fontWeight: 600, color: "var(--text-primary)" };
const sub: CSSProperties = { fontSize: 12, color: "var(--text-tertiary)" };
const panel: CSSProperties = { background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: 8 };
const row: CSSProperties = { display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: "var(--radius-md)", cursor: "pointer" };
const ghostBtn: CSSProperties = { padding: "5px 10px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", background: "var(--surface-card)", fontSize: 12, color: "var(--text-secondary)", cursor: "pointer" };
const sopChip: CSSProperties = { fontSize: 9, fontWeight: 700, color: "#7a5c00", background: "rgba(201,162,39,0.16)", border: "1px solid rgba(201,162,39,0.4)", borderRadius: "var(--radius-full)", padding: "1px 6px", letterSpacing: "0.04em" };
const countChip: CSSProperties = { fontSize: 9, color: "var(--text-tertiary)", background: "var(--zebra)", borderRadius: "var(--radius-full)", padding: "1px 6px" };
const statusDot: CSSProperties = { width: 7, height: 7, borderRadius: "50%", flexShrink: 0 };
const kindTag: CSSProperties = { fontSize: 9, color: "var(--text-quaternary)", textTransform: "uppercase", letterSpacing: "0.06em", width: 42, textAlign: "right" };

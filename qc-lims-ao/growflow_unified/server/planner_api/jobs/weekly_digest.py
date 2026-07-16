"""Render a RAG-friendly Markdown digest from a weekly snapshot dict.

The digest is what gets attached to the Letta weekly_coordinator / executive_analytics
agents (a clean, embedding-friendly summary rather than the raw 600 KB JSON).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_digest_md(snap: dict[str, Any]) -> str:
    tasks = snap.get("tasks", [])
    win = snap.get("window", {})
    counts = snap.get("counts", {})

    by_status = Counter(t.get("status", "?") for t in tasks)
    by_priority = Counter(t.get("priority", "?") for t in tasks)
    by_assignment = Counter(t.get("assignment_status", "accepted") for t in tasks)

    dept: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "done": 0, "created": 0, "completed": 0})
    for t in tasks:
        k = t.get("department") or "—"
        dept[k]["total"] += 1
        if t.get("status") == "done":
            dept[k]["done"] += 1
        if t.get("created_in_window"):
            dept[k]["created"] += 1
        if t.get("completed_in_window"):
            dept[k]["completed"] += 1

    owner = Counter()
    owner_done = Counter()
    for t in tasks:
        o = t.get("owner") or "Unassigned"
        owner[o] += 1
        if t.get("status") == "done":
            owner_done[o] += 1

    L: list[str] = []
    L.append(f"# GrowFlow Weekly Snapshot — Work Week {win.get('from')} → {win.get('to')} (Fri→Thu)")
    L.append("")
    L.append(f"Generated: {snap.get('generated_at')}  ·  Source: planner_weekly_snapshot (KVM4 GrowFlow Postgres)")
    L.append("")
    L.append("## Totals")
    L.append(f"- Tasks active in window: {counts.get('tasks', len(tasks))}")
    L.append(f"- Created this week: {counts.get('created')}")
    L.append(f"- Completed this week: {counts.get('completed')}")
    L.append(f"- Progress notes this week: {counts.get('notes')}")
    done = by_status.get("done", 0)
    L.append(f"- Completion: {round(done / len(tasks) * 100) if tasks else 0}% ({done}/{len(tasks)})")
    L.append("")
    L.append("## By status")
    for s in ("done", "working", "review", "stuck", "postponed", "pending"):
        L.append(f"- {s}: {by_status.get(s, 0)}")
    L.append("")
    L.append("## By priority")
    for p in ("critical", "high", "medium", "low"):
        L.append(f"- {p}: {by_priority.get(p, 0)}")
    L.append("")
    L.append("## Assignment acknowledgment")
    for a in ("accepted", "pending", "declined"):
        L.append(f"- {a}: {by_assignment.get(a, 0)}")
    L.append("")
    L.append("## By department")
    for k in sorted(dept, key=lambda x: -dept[x]["total"]):
        v = dept[k]
        L.append(f"- {k}: total {v['total']} · done {v['done']} · created {v['created']} · completed {v['completed']}")
    L.append("")
    L.append("## By owner (top 15 by volume)")
    for o, n in owner.most_common(15):
        L.append(f"- {o}: total {n} · done {owner_done.get(o, 0)}")
    L.append("")

    stuck = [t for t in tasks if t.get("status") == "stuck"]
    declined = [t for t in tasks if t.get("assignment_status") == "declined"]
    outcomes = [t for t in tasks if (t.get("outcome") or "").strip()]

    if stuck:
        L.append(f"## Blocked / stuck ({len(stuck)})")
        for t in stuck[:40]:
            b = (t.get("blocker") or "").strip()
            L.append(f"- {t.get('title')} — {t.get('department') or '—'} · {t.get('owner') or 'Unassigned'}"
                     + (f" · blocker: {b}" if b else ""))
        L.append("")

    if declined:
        L.append(f"## Declined assignments ({len(declined)})")
        for t in declined[:40]:
            n = (t.get("assignment_note") or "").strip()
            L.append(f"- {t.get('title')} — {t.get('owner') or 'Unassigned'}" + (f" · reason: {n}" if n else ""))
        L.append("")

    if outcomes:
        L.append(f"## Recorded outcomes / solutions ({len(outcomes)})")
        for t in outcomes[:60]:
            L.append(f"- {t.get('title')} ({t.get('status')}, {t.get('department') or '—'}): {t.get('outcome').strip()}")
        L.append("")

    return "\n".join(L)

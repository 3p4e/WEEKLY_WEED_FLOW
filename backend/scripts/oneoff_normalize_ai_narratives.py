"""One-off repair: normalize AI narrative bodies stored before the
_normalize_ai_reply fix (2026-07-13).

Draft documents compiled while the weekly_summary binding pointed at the
scheduler's strict-JSON Letta agent carry a raw {"weekly_report": "…"}
envelope in body_en (template narratives can carry the same). Locked
documents are records and are left untouched — a locked doc was human-
approved as-is. Runs inside the backend container:

    docker exec <backend> python scripts/oneoff_normalize_ai_narratives.py
"""
import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.api.documents import _normalize_ai_reply, _split_bilingual  # noqa: E402
import json  # noqa: E402


def _fix_pair(en: str, mk: str) -> tuple[str, str, bool]:
    """Normalize one bilingual body pair. The normalized EN half may reveal
    the `---` separator a JSON envelope was hiding (both languages were
    packed into one string) — re-split whenever that separator shows up,
    regardless of whether MK already held something (a stale/partial
    hand-edit in MK must not block recovering the real split)."""
    norm_en = _normalize_ai_reply(en) if en else ""
    if "---" in norm_en:
        split_en, split_mk = _split_bilingual(norm_en)
        if split_mk:
            return split_en, split_mk, (split_en != en or split_mk != mk)
    nen = norm_en
    nmk = _normalize_ai_reply(mk) if mk else mk
    return nen, nmk, (nen != en or nmk != mk)


async def main() -> None:
    dsn = os.environ["TASKS_ADMIN_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch("SELECT id, content FROM weekly_documents WHERE status='draft'")
    fixed_docs = fixed_secs = 0
    for r in rows:
        content = r["content"]
        if isinstance(content, str):
            content = json.loads(content)
        changed = False
        for s in content.get("ai_sections", []):
            en, mk, ch = _fix_pair(s.get("body_en") or s.get("body") or "", s.get("body_mk") or "")
            if ch:
                s["body_en"], s["body"], s["body_mk"] = en, en, mk
                changed = True
                fixed_secs += 1
        for sec in content.get("template_sections", []):
            nar = sec.get("narrative") or {}
            if nar.get("en") or nar.get("mk"):
                en, mk, ch = _fix_pair(nar.get("en") or "", nar.get("mk") or "")
                if ch:
                    sec["narrative"] = {"en": en, "mk": mk}
                    changed = True
                    fixed_secs += 1
        if changed:
            await conn.execute(
                "UPDATE weekly_documents SET content=$2::jsonb, updated_at=now() WHERE id=$1",
                r["id"], json.dumps(content))
            fixed_docs += 1
    await conn.close()
    print(f"normalized {fixed_secs} section(s) across {fixed_docs} draft document(s) "
          f"({len(rows)} drafts scanned; locked documents untouched)")


if __name__ == "__main__":
    asyncio.run(main())

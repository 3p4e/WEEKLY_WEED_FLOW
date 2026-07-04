# WWF Task-Capture Prompt (v1)

A copy-paste prompt for **any** Claude surface — Claude chat, Claude Cowork,
Claude Code, Claude Design, projects — that turns whatever you worked on in
that session into structured task data matching WWF's real database schema,
so imports are mechanical instead of interpretive.

**Why this exists:** the first bulk capture produced 195 tasks where the
weekly report showed "159 created this week, 4 completed" — near-duplicate
tasks piling up because freeform capture has no dedup discipline, no stable
identifiers, no hour tracking, and no time-of-day granularity (which WWF's
activity time band and day/night/weekend analysis need). This prompt fixes
each of those, in order of importance.

This file contains **no credentials** and never should.

## How to use

- **Session start (best):** paste the prompt below as your first message and
  work normally; at the end say `capture tasks now`.
- **Session end (sweep):** paste it at the end of any conversation and it
  sweeps everything discussed.
- Either way the output is one fenced JSON block you paste back into a WWF
  import (or hand to Claude Code with "import this into WWF").

---

## The prompt (copy everything between the lines)

```text
ROLE: You are the Purely Plant task recorder for this session. Alongside your
normal work, silently track every piece of real work discussed or performed —
mine included, yours included — as structured task data for WWF (Weekly Weed
Flow), our internal planner. When I say "capture tasks now" (or at the end of
this conversation), emit ONE fenced JSON block in exactly the contract below,
and nothing else in that block.

CONTEXT: Purely Plant GmbH — medical-cannabis facility, North Macedonia.
Timezone Europe/Skopje. Work week runs FRIDAY→THURSDAY; the week is labeled
by its Friday date. I work irregular hours — days, nights, weekends — and
capturing WHEN work happened matters as much as what.

RULES — read carefully, these fix real past failures:

1. UPDATE, DON'T DUPLICATE. Before creating a task, check whether this
   session's list already has it, or whether I referred to it as existing
   work ("continuing the HPLC validation", "still stuck on the transport
   SOP"). If so, emit it with action "update" and the same external_ref,
   carrying only what changed (new status, added hours, new progress event).
   external_ref = a stable slug you derive from the document code if one
   exists (e.g. "pp-qc-sop-012"), else from the title
   ("cleaning-validation-programme"). Same work = same external_ref, always,
   across every session.

2. TIMESTAMPS ARE THE POINT. Every work event gets a progress entry with an
   ISO timestamp including the HOUR (Europe/Skopje). If I say "did this last
   night around 2", record T02:00. If I only give a day, estimate the hour
   from context and mark "time_estimated": true. Never collapse multiple
   work sessions into one undated note.

3. HOURS, HONESTLY. estimated_hours = my estimate of total effort when the
   task is first seen (0 is valid for trivial tasks — record it, don't skip
   it). hours_delta on each progress event = time actually spent in that
   sitting. Never invent hours; if unknown, use null and move on.

4. ONLY REAL WORK. Tasks are things done or to be done for Purely Plant:
   documents authored, validations, CAPAs, SOPs, lab work, facility work,
   software/infra work for PP systems, regulatory submissions. NOT: idle
   questions, chit-chat, hypotheticals, or your own explanations.

5. KEEP DOCUMENT CODES IN TITLES, verbatim, at the start where present:
   "HPLC Cannabinoid Method Validation (PP-QC-MVP/MVR-003 v3.1)". If I
   mention a code anywhere, it belongs in the title.

6. STATUS MUST BE EXACTLY ONE OF (the database rejects anything else):
   pending | ongoing | review | stuck | postponed | completed
   - "stuck" REQUIRES a blocker_reason (who/what is blocking).
   - "completed" REQUIRES completed_date.
7. PRIORITY: low | medium | high | critical (critical = GMP-deadline,
   regulator-facing, or blocking-others work).
8. DEPARTMENT, exactly one code:
   cultivation | production | qc | quality_control | quality_assurance |
   logistics | tooling
   (software/infra work for PP systems → tooling; lab analytics → qc;
   document/QMS-adjacent work → quality_control or quality_assurance.)

9. OWNER defaults to "qcm.blani" (me). Only set another owner if I
   explicitly say someone else owns it; put helpers in "assignees".

10. WEEK: week_start = the FRIDAY of the Fri→Thu week the work belongs to
    (the week it was/will be worked, not when we talked about it).

OUTPUT CONTRACT — one fenced json block, exactly this shape:

{
  "session_meta": {
    "surface": "claude-chat | claude-code | cowork | design | other",
    "captured_at": "<ISO timestamp, Europe/Skopje>",
    "covers": {"from": "<ISO date>", "to": "<ISO date>"},
    "task_count": <n>
  },
  "tasks": [
    {
      "action": "create | update",
      "external_ref": "<stable-slug>",
      "title": "<title, document codes verbatim>",
      "description": "<1-3 sentences, what and why>",
      "status": "pending|ongoing|review|stuck|postponed|completed",
      "priority": "low|medium|high|critical",
      "department": "<one of the 8 codes>",
      "owner": "qcm.blani",
      "assignees": [],
      "tags": ["<short-topic-tags>"],
      "week_start": "<Friday ISO date>",
      "estimated_hours": <number|null>,
      "completed_date": "<ISO date|null>",
      "blocker_reason": "<string|null — required if status=stuck>",
      "progress": [
        {"at": "<ISO timestamp with hour, Europe/Skopje>",
         "time_estimated": <true|false>,
         "note": "<what was done in this sitting>",
         "hours_delta": <number|null>}
      ]
    }
  ]
}

Do not wrap the JSON in commentary inside the block. Before the block, give
me a 2-3 line plain-language summary (n created, n updated, anything you
were unsure about). If a rule and reality conflict, prefer accuracy and
flag it in the summary.
```

---

## Field → database mapping (for whoever runs the import)

| Prompt field | WWF column / mechanism |
|---|---|
| `title`, `description`, `status`, `priority` | `tasks` columns — status/priority enums are DB-enforced (`tasks_status_check`, migration 0004) |
| `department` code | resolved to `tasks.department_id` via `departments.code` |
| `owner` username | resolved to `tasks.user_id` via `profiles.username` |
| `week_start` (Friday) | `tasks.week_start` + `tasks.week_id` (calendar week auto-provisioned, same as `weekly_snapshot._ensure_week`) |
| `estimated_hours` | `tasks.estimated_hours` (≥ 0, CHECK-enforced) |
| `progress[].note` + `at` | `task_progress` rows — `created_at` drives the activity time band's day/night/weekend coloring, so honest hours-of-day matter |
| `progress[].hours_delta` | summed into `tasks.actual_hours` |
| `external_ref` | dedup key at import time: same ref → PATCH the existing task instead of INSERT (match on a `[ref:…]` tag) |
| `blocker_reason` | appended to description / progress note; status `stuck` feeds the weekly report's Blockers section |

## Versioning

Treat this prompt like the planner prompts (`backend/scripts/planner_prompts.py`,
`wwf-prompts/v3`): when you improve it, bump the version in the title and
note what changed, so captures can be traced to the prompt version that
produced them.

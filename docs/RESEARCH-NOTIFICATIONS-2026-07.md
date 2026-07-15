# Notifications & Team Awareness — Design Evidence (2026-07-15)

Deep-research pass (fan-out searches → source fetch → 3-vote adversarial
verification; 15 surviving findings, 2 refuted, all vendor docs verified live
2026-07-15). Sources: Linear, GitHub, Asana, Jira, Slack notification docs
(primary UX evidence), W3C ActivityStreams 2.0, Google FCM localization,
WebKit/MDN for PWA push & badging. This document is the build spec for WWF's
Phase-1 notifications.

## Verified rules (all HIGH confidence unless noted)

1. **Two surfaces, strictly separated.** A per-user actionable **Inbox**
   (always-on, not opt-out-able — Linear model) and a shared append-only
   **Activity Feed** derived from the same events. Creation/routine edits go
   to the FEED ONLY, never notify (Slack: channel activity doesn't notify by
   default). The feed is the exec "what did the team do" view — and it fixes
   "COO's work is invisible": creation events appear in the feed without
   pinging anyone.
2. **Participation-based recipients, never team-wide** (Linear/GitHub/Jira
   convergent defaults): notify creator + assignee + @mentioned + prior
   commenters. Asana precedent adds due-soon/overdue → assignee, and
   report/status updates → project (department) members.
3. **Never notify the actor about their own action** (Asana verbatim, Jira
   default) — hard `recipient_id != actor_id` guard in fan-out.
4. **Lifecycle beyond a read flag:** unread → read → done (soft archive), with
   mark-all-read; reason label on every item; filters by REASON
   (assigned-to-me / @mention / by-me / department — GitHub reason-filter
   model).
5. **Coalesce repeated identical events** — partial unique index on
   `(recipient_id, coalesce_key) WHERE done_at IS NULL`; rapid status
   flapping / repeated due-soon updates ONE row.
6. **Bilingual by structure, not strings** (AS2 `nameMap` language-map + FCM
   `loc_key`+args precedent): store verb + structured params jsonb; the JS
   client picks the EN/МК template at render time. No server-composed prose.
7. **Fan-out on write** — trivially cheap at ~25 users (max fan-out ≈ org).
8. **Delivery: polling is correct at this scale.** Poll list + unread-count
   every 60–90 s + immediately on visibilitychange/focus. Unread count is
   computed server-side (single source of truth; badge can't drift). No
   SSE/WebSockets for 25 users on one VPS.
9. **PWA platform truths (v2):** Web Push works via standard VAPID incl. iOS
   16.4+ — but on iOS ONLY for Home-Screen-installed apps and the permission
   prompt MUST be a user gesture; `setAppBadge` only for installed PWAs (iOS
   additionally requires notifications permission; no Android Chromium
   support) → the in-app bell badge stays canonical.
10. **Digest precedent** (Linear): real-time in-app, digest-by-default for
    out-of-app channels — the v2 email/push digest model. (Manager digest
    content/cadence was under-evidenced — flagged open question.)

## v1 event → recipient matrix (system defaults; per-user settings = v2)

| Event | Notifies (reason) | Feed |
|---|---|---|
| assigned / unassigned | the assignee (`assigned`) | ✓ |
| comment | task creator + assignees + prior commenters (`comment`) | ✓ |
| status change (incl. ack) | creator + assignees, minus actor (`status`) | ✓ |
| handoff / ack request | the counterparty (`status`) | ✓ |
| report submitted / locked | that dept's manager + execs (`report`) | ✓ |
| due-soon / overdue *(later v1.x — needs scheduler tick)* | assignee (`due`); overdue → dept manager | ✓ |
| task/item CREATED, field edits | **nobody** | ✓ |
| anything you did yourself | **nobody** | ✓ (feed shows it) |

Role defaults: operators = assigned/mention/comment/status-on-participated;
managers = + dept report events; execs = report events + mentions, feed as
the awareness surface.

## v1 schema (tasks DB)

```
events(id, org_id, actor_id, verb, object_type, object_id,
       task_id NULL, department_id NULL, params jsonb, created_at)
  -- append-only, AS2-shaped actor-verb-object; params = structured values
  -- only (titles, old/new status), rendered EN/МК client-side.
notifications(id, org_id, recipient_id, event_id → events, reason,
              coalesce_key, read_at NULL, done_at NULL, created_at)
  -- fan-out on write; recipient != actor; partial UNIQUE
  -- (recipient_id, coalesce_key) WHERE done_at IS NULL.
```
RLS: events org-scoped (feed visibility mirrors task scoping at the API
layer); notifications recipient-scoped (`recipient_id = app.current_user_id()`).

## Explicit DON'Ts (all vendor-documented)
Self-notify · team-wide pings on creation/routine changes · bare boolean read
flag · duplicate rows for repeated events · server-composed one-language
strings · push/badges in a browser tab on iOS or permission prompts on page
load · opt-out-able inbox · SSE/WS at this scale · (once watching exists)
missing per-source unsubscribe.

## v2 path
VAPID Web Push (iOS gated on install + gesture) → OS icon badge for installed
users → manager daily / exec weekly digests from the events table (needs
SMTP) → quiet hours suppressing PUSH only (inbox rows always written) →
per-user per-type toggles for out-of-app channels only.

## Refuted during verification
Two overly-specific claims about Asana's inbox tabs/filter set (0-3) — the
design does not depend on them.

## Open questions (carried forward)
Manager/exec digest content+cadence evidence · quiet-hours specifics ·
offline-write queueing interaction with the poll loop · @mention syntax for
WWF comments (no mention parser exists yet — v1 ships without `mentioned`
reason until comments support @).

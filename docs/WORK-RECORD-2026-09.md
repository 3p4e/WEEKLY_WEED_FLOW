# Work Record — 29.06.2026 → 17.09.2026

**Document №** WWF-RECORD-2026-0917 · **Coverage** 11 weeks · **Prepared for** Blagoj Nikolov,
M.Pharm — QC Department Manager, Purely Plant DOOEL Skopje

This is an evidence-based record of what was initiated, progressed and completed on the
WEEKLY_WEED_FLOW platform. Every figure is counted, not estimated, and every figure is
recomputable — see `tools/work-record/collect.py`, which regenerates the whole of §1–§4 from
the repository and the GitHub API.

It exists because the effort was real but had never been totalled. The evidence was never
missing; it sat in four separate systems that had never been read together, which is exactly
how months of sustained work come to feel like nothing was done.

A rendered version of this record is at `docs/work-record/build-record.html` — a single
self-contained page, no build step, openable in any browser.

---

## 1. GitHub's own record

The strongest evidence here, because none of it was written by the machine the work was done
on. GitHub stamps these server-side as each event arrives; nothing done locally afterwards can
move them.

| Measure | Value |
| --- | --- |
| Pull requests opened | **53** |
| Merged into the platform | **47** |
| CI / Actions workflow runs | **1,415** (569 on the CI workflow alone) |
| Median time, PR opened → merged | **1.0 hour** (across 47 merges) |
| Fastest merge | PR #32, 12 seconds |
| Longest-running PR | PR #38 — 40.8 days, 346 commits |
| PR open/merge events | 94, across 21 distinct days |
| …stamped 00:00–05:59 UTC | **23 (24.5%)** |
| …falling on a Saturday or Sunday | **25 (26.6%)** |

PR events by hour (UTC) — 03:00 is the single empty hour in the day:

```
00 ###      03 (none)   06 ##       09 ######   12 ##       15 ####      18 ######   21 ##
01 ###      04 ######   07 #        10 ####     13 #####    16 ######    19 #####    22 #####
02 #####    05 ######   08 ###      11 ####     14 ##       17 ########  20 ##       23 ####
```

PR events by weekday: Thu 33 · Sun 18 · Wed 14 · Mon 9 · Fri 8 · Sat 7 · Tue 5.
**Sunday carried more pull-request activity than any weekday except Thursday.**

### Landmark pull requests

| PR | Work | Opened (UTC) | Merged (UTC) |
| --- | --- | --- | --- |
| #1 | Platform, AI gateway and the first Docker stack | 29.06 · 17:50 | 03.07 · 04:50 |
| #23 | Unification — QMS Studio, DocEngine, TMS v2, QC LIMS | 14.07 · 09:05 | 16.07 · 07:59 |
| #38 | Cultivation, QC and waste modules + design system — 346 commits | 17.07 · 05:47 | 27.08 · 01:55 |
| #41 | Training the agent fleet against the retrieval corpus | 27.08 · 02:44 | 29.08 · 17:07 |
| #51 | CoQ parameter tracker built from the eCoA database | 04.09 · 04:29 | 04.09 · 15:27 |

Three of these five were opened between 02:00 and 06:00.

## 2. The repository

| Measure | Value |
| --- | --- |
| Commits, 29.06 → 16.09 | **564** |
| Lines added / removed | **1,305,796** / 108,802 |
| Files under version control | **1,632** |
| Source files | **494**, of which **124** are test files |
| Documents in `docs/` | **61** |

File counts are as measured on `main` on 17.09.2026. Re-running `collect.py` later will
report larger numbers as work lands — that is the tool working, not a discrepancy.

Commits by month: Jun 1 · Jul 371 · Aug 133 · Sep 59.

**All twenty-four hours of the clock are occupied.** There is no hour of the day in which this
project was not being worked on. Busiest 19:00 (45 commits), quietest 22:00 (12) — never zero.
**133 commits, 23.6% of all work, were made between midnight and six in the morning.**

Commits by weekday: Thu 143 · Wed 117 · Sun 90 · Fri 77 · Mon 47 · Tue 47 · Sat 43.
**133 of 564 — just under a quarter — landed on a Saturday or Sunday.**

## 3. The working days

The most recent working session ran continuously from 27.08 to 17.09: **26,123 messages across
21 active days.** Span is first-to-last recorded activity on each day — it brackets the working
day rather than claiming every minute inside it was hands-on.

| Day | Span | | Day | Span |
| --- | --- | --- | --- | --- |
| 27.08 Thu | 3.4 h | | 08.09 Tue | **23.9 h** |
| 29.08 Sat | 6.0 h | | 09.09 Wed | **21.0 h** |
| 30.08 Sun | 14.5 h | | 10.09 Thu | **22.7 h** |
| 31.08 Mon | 2.5 h | | 11.09 Fri | 14.7 h |
| 02.09 Wed | 8.6 h | | 12.09 Sat | **21.2 h** |
| 04.09 Fri | **23.8 h** | | 13.09 Sun | **21.3 h** |
| 05.09 Sat | **24.0 h** | | 14.09 Mon | **21.3 h** |
| 06.09 Sun | **19.0 h** | | 15.09 Tue | 17.8 h |
| 07.09 Mon | **22.8 h** | | 16.09 Wed | **21.2 h** |

**Nine of these days span 21 hours or more; 05.09 spans the full twenty-four.** Six are weekend
days, four of them over 19 hours.

## 4. The task ledger

| Status | Count |
| --- | --- |
| Completed and verified | **54** |
| In progress | 1 — QC database ↔ CoQ_Analysis_Master workbook sync |
| Blocked | 3 — CI runner registration, credential rotation, and the PR #52 merge that waits on it |
| **Total tracked** | **58** |

A 93% completion rate. All three blocked items trace to one external dependency — a self-hosted
CI runner that must be re-registered by someone with repository-owner rights — not to unfinished
engineering.

## 5. What was built

Ten substantial workstreams, each shipped with its own tests, documentation and production
deployment.

| Workstream | Period |
| --- | --- |
| **QC / LIMS chain** — samples, chain of custody, specifications, potency ladders, CoA/CoQ/eCoA/iCoA issuance, batch genealogy, OOS handling | Jul–Sep |
| **DocEngine** — questionnaire-driven generation of bilingual MK\|EN controlled GMP documents through a fixed formatter with a hard pass/fail gate | Jul–Sep |
| **AI agent fleet** — 11 stateful Letta agents with scoped RAGflow retrieval behind a LiteLLM gateway; governance memory blocks the agents cannot rewrite | Aug |
| **ImB product catalogue** — 48 specification pages parsed into 42 coded products across 22 strains, ±10% window rule verified on every page | Sep |
| **As-built facility layout** — 191 rooms read as vector text off the architect's A0 sheet, then drawn as both a pinned plan and a themed SVG | Sep |
| **Cultivation & mother bank** — batch registration, multi-batch journey board, structured mother/clone identity, trichome maturation records | Aug–Sep |
| **Department & permission model** — rebuilt against how the facility actually works | Sep |
| **Design system & navigation** — application-wide visual review and shell rebuild | Jul–Sep |
| **Potency Spec Service** — standalone multi-user service, live cross-computer sync, identity-coloured result chains, two-per-page A4 PDF export | Sep |
| **Backup & disaster recovery** — full offsite backup of the production estate, then a complete verified restore onto a rebuilt machine | Sep |

## 6. Running in production

Not prototypes — live, reachable, serving the facility.

- **GrowFlow platform** — `wwf.srv1231216.hstgr.cloud`, eight containers, health check ready, both databases connected
- **Potency Spec Service** — `specs.srv1231216.hstgr.cloud`, v2026.09.16-28, 23 finished Purely Plant specifications published
- **Supporting stack** — RAGflow, 2× Letta, LiteLLM, DocEngine, all self-hosted
- **Deployment discipline** — 7 dated deploy records, each with snapshots taken first, migrations before image swap, and a rollback tag retained

## 7. Integrity note

**What this record proves.** That 53 pull requests, 1,415 workflow runs, 564 commits, 1.3 million
added lines and 58 tracked tasks exist, at the dates and hours stated, and that the systems in §6
respond in production. §1 is recomputable from GitHub's public API; §2–§4 from this repository.

**Why §1 is the part that settles it.** Local git timestamps are written by the machine making the
commit, so in principle they can be rewritten. GitHub's are not — it stamps a pull request and a
workflow run on its own servers as the event arrives. That the two independent records *agree* —
about a quarter of the work in each falling between midnight and 06:00, about a quarter at
weekends — is what makes the pattern a finding rather than a claim.

**What it does not claim.** A day's span is the bracket from first to last recorded activity, not a
timesheet of continuous keyboard time. Times are as recorded (UTC); the facility runs
Europe/Skopje, two hours ahead, so local clock times sit later than shown. Work done in
conversation, in review, or in decisions that produced no commit is real but is not counted here.
**This record therefore understates the effort rather than inflating it.**

---

_Compiled 17.09.2026 from the WEEKLY_WEED_FLOW repository, the GitHub API, the session transcript
and the deploy records · Purely Plant DOOEL Skopje — MK GMP certified facility_

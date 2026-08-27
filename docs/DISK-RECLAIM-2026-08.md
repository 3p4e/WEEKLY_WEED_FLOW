# KVM4 disk reclaim — 2026-08-16

Production host `/dev/sda1` (193 G, backs both `/` and `/opt`) reached **100%
with 262 MB free** while under investigation. At that level Postgres write
failures are the next event, and `wwf-db-tasks`, `wwf-db-users` and
`letta-postgres` all live on it. Reclaimed to **39 G free (81%)** the same day.

## What was actually consuming the disk

| Cause | Size | Disposition |
|---|---|---|
| Runaway `rclone` logs in the code-server volume | **4.5 GB** | Truncated (tails kept) |
| **562 orphaned CI Postgres volumes** | **~36 GB** | Deleted after per-volume identification |
| `wwf-gh-runner:2.335.1` image, unreferenced | 2.03 GB | Removed |
| Docker build cache | 661 MB | Pruned |
| `code-server-config` volume (in use, **not** reclaimed) | 75.5 GB | See "Still outstanding" |

### The runaway log
`/config/.config/rclone/coa-bisync.log` had reached **4,789,503,819 bytes** —
a 30-minute `rclone bisync` cron logging at `--log-level INFO` with no rotation.
Truncated to the last 2000 lines (same for `bisync.log`, `sync.log`). **The root
cause is unfixed until those scripts log at `NOTICE` with rotation.**

### The 562 orphaned volumes
623 volumes existed; 594 were attached to nothing. Postgres images declare
`VOLUME /var/lib/postgresql/data`, so every CI container created and removed
left a fully-initialised cluster behind — accumulating since April.

**Every volume was identified before deletion; none was deleted on assumption.**
Content was read by mounting each **read-only** into a throwaway container, and
ambiguous families were identified by booting a *copy* (never the original) under
`postgres:16` and running `psql`:

| Family | Count | Identified as | Action |
|---|---|---|---|
| 4 user DBs | ~150 | `wwf_{tasks,users}_via_{alembic,schemasql}` — CI **schema drift check** | deleted |
| 2 user DBs | ~250 | `wwf_tasks_test` + `wwf_users_test` — CI backend suite | deleted |
| 1 user DB, 41 MB | 80 | `docengine_test` (tables `jobs`, `documents`) — DocEngine CI | deleted |
| 0 user DBs | 15 | bare `initdb`, no data | deleted |
| **`letta`** | **5** | real AI-stack data (2026-04-25) | **PROTECTED** |
| **`growflow`** | **1** | real app data (2026-06-28) | **PROTECTED** |
| unidentified (1 DB, 74 MB) | 1 | would not boot cleanly — not identified | **PROTECTED** |
| non-Postgres content | 9 | shell dotfiles etc. | **PROTECTED** |

Result: **562 deleted, 0 failures, 16 protected.** `docker volume prune` was
never used and must not be — it would have destroyed all 16, including the
`letta` and `growflow` clusters.

## Verification
- 32 containers Up, **0** not-Up; no restarts.
- `GET /health/ready` → `{"ready":true,"databases":{"users":"ok","tasks":"ok"}}`.
- Both `letta` and `growflow` volumes confirmed present by `docker volume inspect`.
- `df -h /opt`: 100% / 262 MB → **81% / 39 G**.

## Still outstanding

1. **`code-server-config`, 75.5 GB — the largest single object on the host.**
   In use by a running container, so not reclaimable by deletion. Inside it:
   `gdrive-sync` **31.3 GB** (a full Google Drive mirror), `.local` 13.3 G,
   `.npm` 4.7 G, `.config` 4.6 G, `.cache` 3.0 G, `.claude` 2.4 G,
   `workspace` 3.2 G, `extensions` 2.6 G. The caches (~10–12 GB) are
   regenerable; the Drive mirror is an owner decision (see below).
2. **Log rotation** for the rclone scripts — otherwise the 4.5 GB returns.
3. **Letta Postgres is still outside backup scope** (`BACKUP.md` §Scope) —
   62 agents, 9 RAG sources, three production dependents, last dump 2026-07-16.

## Related: the Drive sync was disarmed the same day

Two `rclone bisync` cron jobs (**bidirectional**, every 15 and 30 minutes) had
the local mirror as **path1**. Their own failure handler instructs
`--resync`, which defaults to `--resync-mode path1` — making the **stale local
mirror authoritative**. A read-only `rclone check` measured the blast radius:

- **5,612 files** exist only locally → would have been **re-uploaded** to Drive,
  resurrecting anything deleted there (including `QC_eCoA/ImB_QC_COAs/*.pdf`).
- **157 files** differ → Drive would have been **overwritten with the older
  local copy**, among them
  `1. PP/DRAFTS_IN_PROGRESS/Regulatory_Document_Register_2026_Blagoj_Nikolov.xlsx`.
- **23,241 files** exist only in Drive — the mirror is also a month stale, so it
  was carrying all of the risk and none of the benefit of a backup.

Both cron entries are commented `#DISARMED-20260816`; the original crontab is at
`/config/crontab.backup-20260816`. Full lists in `/config/drive-diff/`.

Drive is the source of truth, which makes bidirectional sync the wrong tool by
definition. Zero-copy replacements now in place: the **`google-workspace` MCP
server** (verified live — `drive_list`/`drive_search`/`docs_read`/`sheets_read`)
and a **read-only** `rclone serve webdav` on `127.0.0.1:8055`.

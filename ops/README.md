# ops/ — host-side operational tooling

## `watchdog.sh` — CI dead-man's switch + production uptime probe

Two silent-failure modes motivated this script, and both had zero detection:

1. **CI was dead for five days and nobody knew.** An interrupted runner
   self-update mass-deleted the runner's `bin/` directory (symptom:
   `Runner.Listener: No such file or directory`). No job was ever assigned, and
   `ci.yml`'s `cancel-in-progress: true` made the orphaned runs read as merely
   superseded rather than never-started.
2. **Production had no uptime monitoring at all.** If `/health/ready` began
   failing, the first signal was a human noticing.

### Why this is a host cron job and not a scheduled workflow

A CI heartbeat implemented as a scheduled GitHub Actions workflow **cannot
detect the runner being down**. If the runner is gone the scheduled workflow is
never assigned to anything, so it never runs and never alerts — and the absence
of an alert is indistinguishable from health. That is precisely the failure that
went unnoticed for five days.

So the coverage is split deliberately, and the split is the whole point:

| Half | Where it runs | Detects | Blind to |
| --- | --- | --- | --- |
| `ops/watchdog.sh` (**authoritative**) | KVM4 host, cron/systemd timer | runner container down, runner `bin/` wiped, CI runs nobody picks up, production down, databases down | the host itself being down |
| `.github/workflows/watchdog.yml` | the self-hosted runner | production down, databases down | **its own runner being down**, and GitHub not firing the schedule |

The host half shares no component with the things it watches. Do not delete it
because the workflow is green: green there means the check *ran*, never that the
check *would have* run. GitHub also disables scheduled workflows entirely in a
repository that sees no activity for ~60 days, so a silent workflow watchdog is
its normal failure mode rather than an edge case.

### What it checks

| Check | Group | Meaning |
| --- | --- | --- |
| `docker_access` | runner, prod | Preflight. Distinguishes "container is gone" from "cannot talk to docker at all", so a socket/permission fault is never reported as a pile of missing containers. |
| `runner_container` | runner | `gh-runner-wwf` exists and is `running` (reports `RestartCount`, which climbs during a crash-loop). |
| `runner_listener` | runner | **The check that would have caught the five-day outage on day one.** Locates the runner install by a marker that *survives* a self-update wipe (`.runner` / `run.sh`), then asserts `bin/Runner.Listener` and `bin/Runner.Worker` are present and non-empty. |
| `runner_process` | runner | Advisory only: a `Runner.Listener` process is visible via `docker top`. A miss is not conclusive (process naming depends on how the runner was launched), so it WARNs. Treat consecutive WARNs as an outage. |
| `app_ready` | prod | `GET /health/ready` is 200 with `users:ok` **and** `tasks:ok`. Probed through the public URL so it exercises traefik → nginx → backend. |
| `db_<container>` | prod | Both database containers are `running` and accepting connections. |
| `ci_freshness` | ci | The newest `ci.yml` run is neither stuck `queued` (nothing picked it up) nor failing. Optional — SKIPs without a token. |

Three deliberate subtleties worth knowing before you change any of it:

- **`app_ready` falls back to the backend container only on a *transport*
  failure** (DNS/connect/timeout), never on a bad answer. A host that cannot
  hairpin its own public IP legitimately cannot reach `wwf.srv1231216.hstgr.cloud`,
  and that must not be reported as an outage — but a *reachable* endpoint
  returning 503 is a real outage and must never be masked by re-probing
  `127.0.0.1` inside the container. A `via=container-fallback` result is a WARN,
  because it no longer proves anything about traefik or nginx.
- **`ci_freshness` targets `ci.yml` by name, not "the newest run in the repo".**
  `watchdog.yml` runs every 15 minutes, so it would otherwise always *be* the
  newest run and CI's own staleness would be permanently invisible.
- **A stale-but-successful CI run is a WARN, never a FAIL.** No runs can simply
  mean nobody pushed. Only a run that is *stuck queued* proves the runner is not
  taking work.

### Install

Read-only probe: it only ever inspects, execs read-only commands, and issues
HTTP GETs. Needs access to the docker socket, so run it as root or as a member
of the `docker` group.

```sh
install -m 0755 ops/watchdog.sh /usr/local/sbin/wwf-watchdog.sh
```

Configuration lives in an optional environment file, because it holds
credentials. Never commit it, and never put a token or webhook URL in the
crontab or a unit file where it is world-readable:

```sh
install -m 0600 /dev/null /etc/wwf-watchdog.env
# then edit, e.g.:
#   WWF_WATCHDOG_WEBHOOK=https://...
#   WWF_WATCHDOG_GH_TOKEN_FILE=/etc/wwf-watchdog.token
```

**systemd timer.** Its advantage is that `systemctl list-timers` shows the last
and next elapse, so the watchdog's *own* death is observable — which matters more
here than anywhere else, since a cron job that silently stops running is
invisible. Its disadvantage is that it has **no built-in alert channel at all**
(see the comment in the unit below); cron gets one free via `MAILTO`. Neither is
"preferred" unconditionally: choose systemd for observability plus an explicit
alert path, or cron for a working alert path out of the box.

`/etc/systemd/system/wwf-watchdog.service`:

```ini
[Unit]
Description=WWF watchdog (CI dead-man's switch + production liveness)
# Ordering only, not a dependency: if docker is dead the watchdog must still run
# and report docker_access=FAIL rather than be held back from reporting it.
After=docker.service

[Service]
Type=oneshot
EnvironmentFile=-/etc/wwf-watchdog.env
ExecStart=/usr/local/sbin/wwf-watchdog.sh
# WITHOUT one of these, THIS INSTALL ALERTS NOBODY. Type=oneshot exiting 1 only
# marks the unit failed; systemd has no MAILTO equivalent, so a FAIL lands in the
# journal and stops there. That is strictly worse than the cron alternative
# below, which mails on a non-zero exit for free — so if you pick systemd you
# must add the alert path yourself. Two ways, pick one:
#
#   1. Set WWF_WATCHDOG_WEBHOOK in /etc/wwf-watchdog.env. The script POSTs a JSON
#      summary on FAIL and now distinguishes sent / rejected / unreachable, so a
#      rotated webhook URL is visible instead of silently swallowed.
#   2. Add an OnFailure unit, e.g. OnFailure=wwf-watchdog-alert@%n.service, where
#      that template mails or pages. Uncomment the line below once it exists —
#      naming a unit that does not exist makes the failure path itself fail.
#
# OnFailure=wwf-watchdog-alert@%n.service
```

> ⚠️ **Verify the alert path before trusting the install.** Run
> `WWF_WATCHDOG_WEBHOOK=... /usr/local/sbin/wwf-watchdog.sh --only runner
> --webhook-always` and confirm the output says `webhook=sent http=2xx`. If it
> says `rejected` or `failed`, the watchdog is running and reaching nobody, which
> is the failure mode this whole file exists to prevent. A monitor whose alert
> channel has never been exercised is not a monitor.

`/etc/systemd/system/wwf-watchdog.timer`:

```ini
[Unit]
Description=Run the WWF watchdog every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
```

```sh
systemctl daemon-reload
systemctl enable --now wwf-watchdog.timer
systemctl list-timers wwf-watchdog.timer
journalctl -t wwf-watchdog -n 50
```

**cron alternative.** A non-zero exit makes cron mail `MAILTO`, which is a
working alert channel with no extra infrastructure:

```cron
MAILTO=ops@example.invalid
*/5 * * * * /usr/local/sbin/wwf-watchdog.sh >> /var/log/wwf-watchdog.log 2>&1
```

Add a logrotate stanza for that file, or drop the redirect and read the syslog
copy instead (`logger -t wwf-watchdog`) — every check line goes to syslog too.

If you install it through the kvm4-runner HTTP API, note that `/shell` runs
commands under `/bin/sh` (dash), so invoke it explicitly:
`bash /usr/local/sbin/wwf-watchdog.sh`.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `WWF_WATCHDOG_WEBHOOK` | *(unset)* | Optional. POST a JSON summary on FAIL. Unset = skipped, never a failure. No endpoint is hardcoded anywhere; the destination is deliberately undecided. |
| `WWF_WATCHDOG_WEBHOOK_ALWAYS` | `0` | `1` posts on every run — what a hosted dead-man's-switch service wants. |
| `WWF_WATCHDOG_PUBLIC_URL` | `https://wwf.srv1231216.hstgr.cloud/health/ready` | Readiness endpoint. |
| `WWF_WATCHDOG_RUNNER_CONTAINER` | `gh-runner-wwf` | Runner container name. |
| `WWF_WATCHDOG_RUNNER_DIR` | *(auto-detected)* | Set if the runner install path is non-standard. |
| `WWF_WATCHDOG_BACKEND_CONTAINER` | `weekly_weed_flow-backend-1` | Used only by the fallback probe. |
| `WWF_WATCHDOG_DB_TARGETS` | `wwf-db-users:wwf_users wwf-db-tasks:wwf_tasks` | `container:database` pairs. |
| `WWF_WATCHDOG_GH_TOKEN_FILE` | *(unset)* | Path to a `0600` file holding a token with `actions:read`. Preferred over `WWF_WATCHDOG_GH_TOKEN` so the value never enters the environment of unrelated processes. |
| `WWF_WATCHDOG_REPO` | `3p4e/WEEKLY_WEED_FLOW` | Repository for the CI query. |
| `WWF_WATCHDOG_CI_WORKFLOW` | `ci.yml` | Workflow whose freshness is checked. |
| `WWF_WATCHDOG_CI_QUEUED_MAX_MIN` | `30` | Queued longer than this = nothing picked it up = FAIL. |
| `WWF_WATCHDOG_CI_RUNNING_MAX_MIN` | `120` | In-progress longer than this = wedged job holding the only runner. |
| `WWF_WATCHDOG_CI_MAX_AGE_DAYS` | `14` | Newest run older than this = WARN only. |
| `WWF_WATCHDOG_ONLY` | `all` | Same as `--only`: `runner`, `prod`, `ci`, or a comma-separated subset. |

Neither the database password nor any token is ever read into a log line. The
GitHub token and the webhook URL are handed to `curl` through a config file on
stdin specifically so they never appear in this host's process list.

### Reading the output

One line per check plus a summary line:

```
wwf-watchdog ts=... host=... check=runner_listener status=FAIL detail="..."
wwf-watchdog ts=... host=... result=FAIL pass=4 fail=1 warn=0 skip=1 groups=all failed="runner_listener "
```

`FAIL` = production or CI is broken, wake someone; exit status 1.
`WARN` = the probe could not reach a verdict, or the condition is legitimately
ambiguous; exit status 0. `SKIP` = not checked, and the line says why — a SKIP
never means "healthy".

Only FAIL exits non-zero, so anything that must page has to be a FAIL.

## Remediation: the runner self-update that deletes `bin/`

Signature: `runner_listener` FAILs with `bin=missing`, or the container logs
`Runner.Listener: No such file or directory`, or `ci_freshness` FAILs with a run
that has been `queued` for far longer than any job takes. The cause is an
interrupted runner **auto-update**: it removes the old `bin/` before the
replacement is in place, so an interruption leaves the install gutted while the
container still exists and still looks "Up".

The fix is to re-register the runner with auto-update disabled, so an
interrupted update can never gut the install again.

1. **Restore the runner package first.** With `bin/` gone, `config.sh` cannot
   run at all (it dispatches to `bin/Runner.Listener`), so re-extract the runner
   release tarball over the install directory inside the container before
   attempting any (re)configuration.
2. **Get a fresh registration token.** Registration tokens are short-lived
   (about an hour) and the previous one cannot be reused — a stale token is the
   usual reason a re-registration attempt fails:

   ```sh
   gh api -X POST repos/3p4e/WEEKLY_WEED_FLOW/actions/runners/registration-token --jq .token
   ```

   Or: repository **Settings → Actions → Runners → New self-hosted runner**.
3. **Re-register with `--disableupdate`**, keeping the name so the
   `runs-on: self-hosted` label set is unchanged. `--replace` takes over the
   existing `kvm4-wwf` registration instead of leaving a stale offline entry
   behind:

   ```sh
   ./config.sh --url https://github.com/3p4e/WEEKLY_WEED_FLOW \
     --token <FRESH_REGISTRATION_TOKEN> \
     --name kvm4-wwf --labels self-hosted \
     --unattended --replace --disableupdate
   ```

   If the container image registers the runner from its own entrypoint rather
   than by a manual `config.sh`, set that image's disable-auto-update option
   instead (commonly an env var such as `DISABLE_AUTO_UPDATE`) and recreate the
   container — check the image's own documentation, as this is image-specific.
4. **Restart the runner** and confirm the recovery, ideally with the watchdog
   itself rather than by eyeballing it:

   ```sh
   /usr/local/sbin/wwf-watchdog.sh --only runner
   ```

**The tradeoff, stated plainly:** with auto-update disabled, runner upgrades
become a manual chore, and GitHub can stop assigning jobs to a runner that has
fallen too far behind (its documented allowance has been on the order of 30 days
from a release — confirm the current policy before relying on this long-term).
That trade is deliberate: an outage caused by a *neglected upgrade* is announced
by `ci_freshness` FAILing on a run nobody picks up, whereas the outage caused by
a *broken auto-update* announced itself to nobody for five days.

## Safety rules for anything added to this directory

- `watchdog.sh` is a **read-only probe**. It must never gain a `docker rm`,
  `stop`, `restart`, `compose up`, or **any** volume operation. A monitor is the
  last thing that should be able to change the state it reports on, and an
  automatic "remediation" that fires on a false positive is strictly worse than
  a page.
- **Never remove docker volumes on this host as part of runner remediation.**
  The runner and the production stack share the daemon, and the volume named
  `wwf_mass_letta_pgdata` is — despite the name — the **live production Letta
  data volume**. Runner recovery never requires touching any volume.
- Other stacks on this host are separate live infrastructure with their own
  lifecycles. Scope anything added here to the containers named in the table
  above; never operate on the daemon as a whole (no blanket `prune`).

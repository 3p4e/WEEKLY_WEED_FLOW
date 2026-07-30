#!/usr/bin/env bash
# WWF watchdog — CI dead-man's switch + production liveness probe.
# Runs from cron / a systemd timer ON THE KVM4 HOST. See ops/README.md to install.
#
# WHY THIS IS A HOST CRON SCRIPT AND NOT A SCHEDULED WORKFLOW
# A "CI heartbeat" implemented as a scheduled GitHub Actions workflow CANNOT
# detect the runner being down: when the runner is gone the scheduled workflow
# is never assigned to anything, so it never runs and never alerts — and the
# absence of an alert is indistinguishable from health. That is exactly how CI
# stayed dead for five days. An interrupted runner SELF-UPDATE mass-deleted the
# runner's bin/ directory (symptom: `Runner.Listener: No such file or
# directory`), no job was ever picked up, and ci.yml's
# `cancel-in-progress: true` made the abandoned runs read as merely superseded.
# This script therefore runs outside GitHub Actions and outside the runner, so
# the detector shares no component with the thing it watches.
# .github/workflows/watchdog.yml covers ONLY the production-liveness half and
# is explicitly not a substitute — it has the same blind spot as any in-Actions
# heartbeat.
#
# READ-ONLY BY CONSTRUCTION
# Every probe here is `docker inspect` / `docker top` / `docker exec` of a
# read-only command / an HTTP GET. Nothing mutates state, so it is safe to run
# every few minutes forever and safe to run twice concurrently. This script
# must never grow a `docker rm`/`stop`/`restart`, a `docker compose up`, or ANY
# volume operation — the host carries live production data volumes (including
# `wwf_mass_letta_pgdata`, which despite the name is the LIVE Letta data
# volume), and a monitor is the last place that should be able to touch them.
#
# CHECK GROUPS (select with --only, default all)
#   runner : gh-runner-wwf container is Up; its bin/Runner.Listener and
#            bin/Runner.Worker are present (the exact past failure mode)
#   prod   : /health/ready is 200 with users:ok AND tasks:ok; both database
#            containers are accepting connections
#   ci     : the newest ci.yml run is neither stuck queued nor failing
#            (needs a token — degrades to SKIP when none is configured)
#
# OUTPUT AND ALERTING
# One structured `wwf-watchdog ... check=<name> status=<PASS|FAIL|WARN|SKIP>`
# line per check on stdout, mirrored to syslog when `logger` exists, plus a
# `result=` summary line. Exit 1 if any check FAILed, else 0 — so plain cron
# alerts on its own (non-zero exit mails MAILTO) with no extra infrastructure.
# The alert destination is deliberately undecided: set WWF_WATCHDOG_WEBHOOK to
# also POST a JSON summary somewhere. Unset means the webhook step is skipped,
# never that the script fails.
#
# WARN vs FAIL: FAIL means "production or CI is broken, wake someone". WARN
# means "the probe could not reach a verdict, or the condition is legitimately
# ambiguous" (e.g. no CI run in weeks may just mean nobody pushed). WARN does
# NOT exit non-zero, so anything that must page has to be a FAIL.

# `set -e` is deliberately ABSENT. A monitor must run every probe and report
# every fault; errexit would abort on the first failing check and hide the rest,
# which is precisely backwards for this program. Failures are counted, not
# propagated. `-u` and `-o pipefail` are kept: they catch typos and stop a
# broken pipeline from being read as a healthy empty answer.
set -uo pipefail

# ---------------------------------------------------------------- configuration
# Every knob is an env var with a default, so the cron line stays a single path
# and per-host overrides live in an EnvironmentFile (see ops/README.md).
RUNNER_CONTAINER="${WWF_WATCHDOG_RUNNER_CONTAINER:-gh-runner-wwf}"
BACKEND_CONTAINER="${WWF_WATCHDOG_BACKEND_CONTAINER:-weekly_weed_flow-backend-1}"
PUBLIC_URL="${WWF_WATCHDOG_PUBLIC_URL:-https://wwf.srv1231216.hstgr.cloud/health/ready}"
# "container:database" pairs. Both databases must round-trip for the app to be
# usable at all, which is why /health/ready checks both and so does this.
DB_TARGETS="${WWF_WATCHDOG_DB_TARGETS:-wwf-db-users:wwf_users wwf-db-tasks:wwf_tasks}"
GH_REPO="${WWF_WATCHDOG_REPO:-3p4e/WEEKLY_WEED_FLOW}"
# The CI-freshness check targets ci.yml BY NAME rather than "the newest run in
# the repo". watchdog.yml runs every 15 minutes, so it would otherwise always
# BE the newest run and CI's own staleness would be permanently invisible —
# a monitor that reports on itself.
GH_CI_WORKFLOW="${WWF_WATCHDOG_CI_WORKFLOW:-ci.yml}"
# A run sitting in `queued` means GitHub accepted it but nothing picked it up.
# That is the outage signature, whatever its cause (runner gone, bin/ deleted,
# labels changed, runner too far behind to be assigned work).
CI_QUEUED_MAX_MIN="${WWF_WATCHDOG_CI_QUEUED_MAX_MIN:-30}"
CI_RUNNING_MAX_MIN="${WWF_WATCHDOG_CI_RUNNING_MAX_MIN:-120}"
# How long CI may go without ANY run reaching a conclusion while unfinished runs
# exist. A full pipeline is ~25 min, so 90 leaves room for one queued behind one
# running without false-alarming. This is the threshold that actually catches the
# five-day outage, because it is immune to the push cadence.
CI_NO_COMPLETION_MAX_MIN="${WWF_WATCHDOG_CI_NO_COMPLETION_MAX_MIN:-90}"
# Generous, and only ever a WARN: no runs can simply mean no pushes.
CI_MAX_AGE_DAYS="${WWF_WATCHDOG_CI_MAX_AGE_DAYS:-14}"
WEBHOOK="${WWF_WATCHDOG_WEBHOOK:-}"
# By default the webhook only fires on FAIL. Set to 1 for an "I am alive" ping
# on every run, which is what a hosted dead-man's-switch service would want.
WEBHOOK_ALWAYS="${WWF_WATCHDOG_WEBHOOK_ALWAYS:-0}"
ONLY="${WWF_WATCHDOG_ONLY:-all}"

usage() {
  cat <<'USAGE'
Usage: watchdog.sh [--only runner,prod,ci|all] [--webhook-always] [--help]

  --only GROUPS      comma-separated subset of checks to run (default: all)
  --webhook-always   POST to WWF_WATCHDOG_WEBHOOK even when everything passes
Exit status: 1 if any check FAILed, 0 otherwise (WARN and SKIP do not fail).
Configuration: see the WWF_WATCHDOG_* variables at the top of this file.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    # `shift 2` with only one argument left shifts NOTHING and returns non-zero,
    # so a bare trailing `--only` left this loop spinning forever at 100% CPU —
    # and under the documented */5 cron that stacks a new runaway process every
    # five minutes on the production host, with cron never mailing because the
    # process never exits. Require the value explicitly instead of defaulting it.
    --only)
      [ "$#" -ge 2 ] && [ -n "$2" ] || {
        printf 'watchdog.sh: --only requires a value\n' >&2; usage >&2; exit 64; }
      ONLY="$2"; shift 2 ;;
    --only=*)
      ONLY="${1#*=}"
      [ -n "$ONLY" ] || {
        printf 'watchdog.sh: --only= requires a value\n' >&2; usage >&2; exit 64; }
      shift ;;
    --webhook-always) WEBHOOK_ALWAYS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'watchdog.sh: unknown argument %s\n' "$1" >&2; usage >&2; exit 64 ;;
  esac
done

# --------------------------------------------------------------------- plumbing
PASSES=0; FAILS=0; WARNS=0; SKIPS=0
FAILED_NAMES=""
SUMMARY_LINES=""
HOST_NAME="$(hostname 2>/dev/null || echo unknown)"

# Every probe is wrapped in `timeout`, because a wedged docker daemon or a
# black-holed TCP connect otherwise leaves the watchdog hanging until the next
# cron tick lands on top of it. With every probe bounded, total runtime has a
# hard ceiling well under any sane cron interval, so no lock file is needed.
TIMEOUT_BIN="$(command -v timeout || true)"
bounded() {
  local secs="$1"; shift
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" "$secs" "$@"
  else
    "$@"
  fi
}

# Details end up inside a quoted field of a single-line log record and inside a
# hand-built JSON payload, so strip the three characters that could break either
# (newline, double quote, backslash) and cap the length: a Postgres error body
# echoed by /health/ready can be long enough to bury the summary line.
sanitize() {
  printf '%s' "${1:-}" | tr '\n\r\t' '   ' | tr -d '\\"' | cut -c1-400
}

emit() {
  local status="$1" name="$2" detail
  detail="$(sanitize "${3:-}")"
  local line
  line="wwf-watchdog ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) host=${HOST_NAME} check=${name} status=${status} detail=\"${detail}\""
  printf '%s\n' "$line"
  local pri=daemon.info
  case "$status" in
    FAIL) pri=daemon.err; FAILS=$((FAILS + 1)); FAILED_NAMES="${FAILED_NAMES}${name} " ;;
    WARN) pri=daemon.warning; WARNS=$((WARNS + 1)) ;;
    PASS) PASSES=$((PASSES + 1)) ;;
    SKIP) SKIPS=$((SKIPS + 1)) ;;
  esac
  if [ "$status" = FAIL ] || [ "$status" = WARN ]; then
    SUMMARY_LINES="${SUMMARY_LINES}${status} ${name}: ${detail} | "
  fi
  # Best-effort: a host without syslog must not turn into a failing watchdog.
  command -v logger >/dev/null 2>&1 && logger -t wwf-watchdog -p "$pri" "$line" 2>/dev/null
  return 0
}

want() {
  case ",${ONLY}," in
    *,all,*) return 0 ;;
    *",$1,"*) return 0 ;;
    *) return 1 ;;
  esac
}

docker_field() {  # docker_field <container> <go-template>
  bounded 15 docker inspect -f "$2" "$1" 2>/dev/null
}

# Distinguishing "the container is gone" from "I cannot talk to docker at all"
# is not pedantry: `docker inspect` fails identically for both, so without this
# preflight a watchdog running as a user outside the docker group — or on a host
# whose daemon is down — reports "container gh-runner-wwf not found" and sends
# whoever is on call hunting a phantom missing container instead of a socket or
# permissions problem. Cached: probed once per run, not once per container.
DOCKER_OK=""
docker_ready() {
  if [ -z "$DOCKER_OK" ]; then
    if ! command -v docker >/dev/null 2>&1; then
      DOCKER_OK=no-cli
    elif bounded 15 docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
      DOCKER_OK=yes
    else
      DOCKER_OK=no-daemon
    fi
  fi
  [ "$DOCKER_OK" = yes ]
}

check_docker_access() {
  if docker_ready; then
    emit PASS docker_access "docker server $(bounded 15 docker version --format '{{.Server.Version}}' 2>/dev/null)"
    return 0
  fi
  case "$DOCKER_OK" in
    no-cli) emit FAIL docker_access "docker CLI not on PATH — every container check below is blind, not passing" ;;
    *) emit FAIL docker_access "docker daemon unreachable (is it running, and is $(id -un 2>/dev/null || echo "this user") able to use the socket?) — every container check below is blind, not passing" ;;
  esac
  return 1
}

# ------------------------------------------------------------- group: runner
# Two separate questions, deliberately kept as separate checks: "is the
# container up" and "is the runner installation intact". The five-day outage was
# the second one — the container existed, so any container-level check alone
# would have reported health throughout.
check_runner_container() {
  local state restarts
  if ! docker_ready; then
    emit SKIP runner_container "docker unusable (see docker_access) — cannot inspect ${RUNNER_CONTAINER}"
    return 0
  fi
  state="$(docker_field "$RUNNER_CONTAINER" '{{.State.Status}}')"
  if [ -z "$state" ]; then
    emit FAIL runner_container "container ${RUNNER_CONTAINER} not found (docker inspect returned nothing)"
    return 1
  fi
  restarts="$(docker_field "$RUNNER_CONTAINER" '{{.RestartCount}}')"
  if [ "$state" != running ]; then
    emit FAIL runner_container "${RUNNER_CONTAINER} state=${state} restarts=${restarts:-?} (expected running)"
    return 1
  fi
  emit PASS runner_container "${RUNNER_CONTAINER} state=running restarts=${restarts:-?}"
  return 0
}

# THE CHECK THAT WOULD HAVE CAUGHT THE FIVE-DAY OUTAGE ON DAY ONE.
# An interrupted self-update deletes bin/ while leaving the install root (and
# .runner, and run.sh) in place, so the install root is located by a marker that
# SURVIVES that deletion and bin/ is then inspected separately. Looking for
# Runner.Listener first would be circular: the file being gone is the fault.
check_runner_listener() {
  if ! docker_ready; then
    emit SKIP runner_listener "docker unusable (see docker_access) — the runner install could NOT be verified"
    return 0
  fi
  if [ "$(docker_field "$RUNNER_CONTAINER" '{{.State.Status}}')" != running ]; then
    emit SKIP runner_listener "cannot exec into ${RUNNER_CONTAINER} — not running (see runner_container)"
    return 0
  fi
  local probe out
  # shellcheck disable=SC2016  # single quotes are required: the $-expansions
  # below must be performed by the /bin/sh INSIDE the container, not by this
  # shell. Double quotes here would expand them on the host to empty strings.
  probe='
report() {
  d="$1"; b=missing; l=missing; w=missing
  [ -d "$d/bin" ] && b=present
  [ -s "$d/bin/Runner.Listener" ] && l=present
  [ -s "$d/bin/Runner.Worker" ] && w=present
  echo "dir=$d bin=$b listener=$l worker=$w"
}
for d in "$@"; do
  if [ -f "$d/.runner" ] || [ -f "$d/run.sh" ] || [ -d "$d/bin" ]; then report "$d"; exit 0; fi
done
# Install path is not standardised across runner images, so fall back to
# locating .runner (written once at registration, untouched by self-update).
# -xdev keeps this off mounted volumes; -maxdepth keeps it cheap.
m=$(find / -xdev -maxdepth 6 -type f -name .runner 2>/dev/null | head -n 1)
if [ -n "$m" ]; then report "$(dirname "$m")"; exit 0; fi
exit 1
'
  # shellcheck disable=SC2086  # RUNNER_DIRS is an intentional word list of candidate paths
  out="$(bounded 30 docker exec "$RUNNER_CONTAINER" sh -c "$probe" sh \
          ${WWF_WATCHDOG_RUNNER_DIR:-} /actions-runner /home/runner /home/runner/actions-runner \
          /runner /opt/actions-runner /home/docker/actions-runner 2>/dev/null)"
  if [ -z "$out" ]; then
    emit FAIL runner_listener "no runner installation found in ${RUNNER_CONTAINER} (no .runner, no run.sh, no bin/) — set WWF_WATCHDOG_RUNNER_DIR if the install path is non-standard"
    return 1
  fi
  case "$out" in
    *"listener=present"*"worker=present"*)
      emit PASS runner_listener "$out"
      return 0 ;;
    *)
      # This is the alert text a future operator will read at 03:00, so it names
      # the cause and points at the fix instead of just reporting a missing file.
      emit FAIL runner_listener "runner binaries missing (${out}) — signature of an interrupted self-update wiping bin/; re-register with --disableupdate, see ops/README.md"
      return 1 ;;
  esac
}

# ADVISORY ONLY, on purpose. `docker top` shows the host's view of the
# container's processes, and how the listener appears there depends on how the
# runner was launched (run.sh wrapper, systemd inside the container, a restart
# in flight), so a miss is not proof of an outage and must not page anyone. The
# authoritative "the runner is not taking work" verdict is ci_freshness below,
# which measures the outcome (a run nobody picked up) rather than the mechanism.
check_runner_process() {
  if ! docker_ready; then
    emit SKIP runner_process "docker unusable (see docker_access)"
    return 0
  fi
  if [ "$(docker_field "$RUNNER_CONTAINER" '{{.State.Status}}')" != running ]; then
    emit SKIP runner_process "container not running (see runner_container)"
    return 0
  fi
  if bounded 15 docker top "$RUNNER_CONTAINER" 2>/dev/null | grep -qi 'Runner\.Listener'; then
    emit PASS runner_process "Runner.Listener process visible in ${RUNNER_CONTAINER}"
  else
    emit WARN runner_process "no Runner.Listener process visible in ${RUNNER_CONTAINER} — advisory; if this WARNs on consecutive runs treat it as an outage"
  fi
  return 0
}

# --------------------------------------------------------------- group: prod
# /health/ready round-trips BOTH databases, so a 200 with users:ok and tasks:ok
# is the strongest single statement of "the app can actually serve" available.
# Anything less than all three assertions would pass a backend that is up but
# cut off from one database.
# Whitespace is squashed out first so the match survives a pretty-printed body,
# and the three assertions are tested INDEPENDENTLY rather than as one ordered
# glob: JSON object key order is not a contract, and a single pattern requiring
# users before tasks would start paging at 03:00 the day someone reorders that
# dict in the endpoint. No jq: this must work on a bare host.
body_is_ready() {
  local squashed
  squashed="$(printf '%s' "$1" | tr -d ' \n\r\t')"
  case "$squashed" in *'"ready":true'*) ;; *) return 1 ;; esac
  case "$squashed" in *'"users":"ok"'*) ;; *) return 1 ;; esac
  case "$squashed" in *'"tasks":"ok"'*) ;; *) return 1 ;; esac
  return 0
}

# ---------------------------------------------------------------- http client
# curl is NOT guaranteed. Verified absent on this stack's own runner container
# (only python3 and openssl are installed), and the FIRST end-to-end run of this
# script against production degraded both HTTP checks to WARN with "unreachable
# (curl rc=127)" — rc 127 is "command not found", not a network condition, so the
# watchdog was mislabelling its own missing dependency as a fact about
# production. The container fallback further down already used python for exactly
# this reason ("the backend image ships no curl") without the same lesson being
# applied to the host.
#
# Prefer curl, fall back to python3, and refuse to run with neither rather than
# reporting "unknown" forever while looking configured.
if command -v curl >/dev/null 2>&1; then HTTP_TOOL=curl
elif command -v python3 >/dev/null 2>&1; then HTTP_TOOL=python3
else HTTP_TOOL=none
fi

# http_get <url> [bearer-token]
# Emits the body, then a final line "http_code=NNN" — the same contract curl's
# -w gave, so the parsers downstream are unchanged. Returns curl/python's exit
# status. The token goes through the ENVIRONMENT in both branches: curl reads its
# config from stdin and python reads os.environ, so it never reaches this host's
# process list where ps would expose it for the life of the call.
http_get() {
  _url="$1"; _tok="${2:-}"
  case "$HTTP_TOOL" in
    curl)
      if [ -n "$_tok" ]; then
        printf 'silent\nshow-error\nmax-time = 20\nheader = "Authorization: Bearer %s"\nheader = "Accept: application/vnd.github+json"\nheader = "X-GitHub-Api-Version: 2022-11-28"\nurl = "%s"\n' \
          "$_tok" "$_url" | bounded 30 curl --config - -w '\nhttp_code=%{http_code}' 2>/dev/null
      else
        bounded 30 curl -sS --max-time 20 -w '\nhttp_code=%{http_code}' "$_url" 2>/dev/null
      fi
      ;;
    python3)
      WD_URL="$_url" WD_TOK="$_tok" bounded 30 python3 -c '
import os, sys, urllib.request, urllib.error
req = urllib.request.Request(os.environ["WD_URL"])
tok = os.environ.get("WD_TOK") or ""
if tok:
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
try:
    r = urllib.request.urlopen(req, timeout=20)
    body, code = r.read().decode("utf-8", "replace"), r.status
except urllib.error.HTTPError as e:
    # An HTTP error is a REACHED endpoint: report its status rather than exiting
    # non-zero, or a 401/404 from the API is indistinguishable from a dead network.
    body, code = e.read().decode("utf-8", "replace"), e.code
except Exception as e:
    sys.stderr.write(str(e) + "\n")
    sys.exit(7)
sys.stdout.write(body + "\nhttp_code=%d" % code)
' 2>/dev/null
      ;;
    *) return 127 ;;
  esac
}

check_app_ready() {
  local out rc code body
  out="$(http_get "$PUBLIC_URL")"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    code="${out##*http_code=}"
    body="${out%$'\n'http_code=*}"
    if [ "$code" = 200 ] && body_is_ready "$body"; then
      emit PASS app_ready "via=public url=${PUBLIC_URL} http=200 body=$(printf '%s' "$body" | tr -d '\n')"
      return 0
    fi
    # A REACHABLE endpoint giving a bad answer is a real outage, so this path
    # must NOT fall back to the container — falling back here would convert a
    # broken traefik/nginx/backend into a green result.
    emit FAIL app_ready "via=public url=${PUBLIC_URL} http=${code} body=$(printf '%s' "$body" | tr -d '\n')"
    return 1
  fi

  # Transport failure only (curl rc 6 resolve / 7 connect / 28 timeout / 35 TLS,
  # or 124 from `timeout`). The public hostname resolves to this host's own
  # public IP, and a host without NAT hairpinning cannot reach itself that way —
  # so being unable to CONNECT is expected on some network setups and is not
  # evidence about the app. In that case probe the backend directly and label
  # the result via=container-fallback: it no longer exercises traefik or nginx,
  # so a public-edge outage is invisible to this fallback. If your host does
  # hairpin, a via=container-fallback line means curl broke, not the app.
  local inner ircode ibody
  if ! docker_ready; then
    emit FAIL app_ready "public probe of ${PUBLIC_URL} failed (${HTTP_TOOL} rc=${rc}) and docker is unusable (see docker_access), so the container fallback is unavailable — production liveness is UNKNOWN, treated as down"
    return 1
  fi
  inner="$(bounded 30 docker exec "$BACKEND_CONTAINER" python -c '
import urllib.request as u, urllib.error as e
# python, not curl: the backend image is slim and ships no curl (same reason
# the compose healthcheck uses urllib).
try:
    r = u.urlopen("http://127.0.0.1:8000/health/ready", timeout=5)
    print(r.status); print(r.read().decode())
except e.HTTPError as x:
    print(x.code); print(x.read().decode())
' 2>/dev/null)"
  if [ -z "$inner" ]; then
    emit FAIL app_ready "public probe failed (${HTTP_TOOL} rc=${rc}) AND container fallback produced no answer from ${BACKEND_CONTAINER}"
    return 1
  fi
  ircode="$(printf '%s\n' "$inner" | head -n 1)"
  ibody="$(printf '%s\n' "$inner" | tail -n +2)"
  if [ "$ircode" = 200 ] && body_is_ready "$ibody"; then
    emit WARN app_ready "via=container-fallback http=200 body=$(printf '%s' "$ibody" | tr -d '\n') — backend healthy but ${PUBLIC_URL} was unreachable from this host (${HTTP_TOOL} rc=${rc}); expected if the host does not hairpin its own public IP, otherwise the public edge is down"
    return 0
  fi
  emit FAIL app_ready "via=container-fallback http=${ircode} body=$(printf '%s' "$ibody" | tr -d '\n') (public probe also failed, ${HTTP_TOOL} rc=${rc})"
  return 1
}

# The stack's compose file defines NO healthcheck for either database service
# (verified in docker-compose.yml), so `.State.Health` is usually absent and a
# health-status-only check would silently assert nothing. Hence: use the health
# status when a healthcheck exists, otherwise fall back to pg_isready inside the
# container. pg_isready needs no password (POSTGRES_PASSWORD is never read or
# printed by this script) and writes nothing.
check_db_containers() {
  local target container db state health rc
  if ! docker_ready; then
    emit SKIP db_containers "docker unusable (see docker_access) — database containers NOT verified"
    return 0
  fi
  for target in $DB_TARGETS; do
    container="${target%%:*}"; db="${target#*:}"
    state="$(docker_field "$container" '{{.State.Status}}')"
    if [ -z "$state" ]; then
      emit FAIL "db_${container}" "container ${container} not found"
      continue
    fi
    if [ "$state" != running ]; then
      emit FAIL "db_${container}" "${container} state=${state} (expected running)"
      continue
    fi
    health="$(docker_field "$container" '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}')"
    if [ -n "$health" ] && [ "$health" != none ]; then
      if [ "$health" = healthy ]; then
        emit PASS "db_${container}" "state=running health=${health}"
      else
        emit FAIL "db_${container}" "state=running health=${health}"
      fi
      continue
    fi
    bounded 20 docker exec "$container" pg_isready -U postgres -d "$db" >/dev/null 2>&1
    rc=$?
    case "$rc" in
      0) emit PASS "db_${container}" "state=running health=not-configured pg_isready=accepting db=${db}" ;;
      1) emit FAIL "db_${container}" "pg_isready=rejecting connections db=${db} (server up, refusing — starting up or shutting down)" ;;
      2) emit FAIL "db_${container}" "pg_isready=no response db=${db}" ;;
      *) emit FAIL "db_${container}" "pg_isready failed rc=${rc} db=${db}" ;;
    esac
  done
  return 0
}

# ----------------------------------------------------------------- group: ci
# Optional and non-fatal when unconfigured: this check needs a GitHub token with
# actions:read, and the whole watchdog must stay useful on a host that has none.
check_ci_freshness() {
  local token="" api resp rc code body py_out
  if [ -n "${WWF_WATCHDOG_GH_TOKEN:-}" ]; then
    token="$WWF_WATCHDOG_GH_TOKEN"
  elif [ -n "${WWF_WATCHDOG_GH_TOKEN_FILE:-}" ] && [ -r "${WWF_WATCHDOG_GH_TOKEN_FILE}" ]; then
    token="$(head -n 1 "$WWF_WATCHDOG_GH_TOKEN_FILE")"
  fi
  if [ -z "$token" ]; then
    emit SKIP ci_freshness "no token configured (set WWF_WATCHDOG_GH_TOKEN_FILE) — CI-run freshness not checked; the runner_* checks above are unaffected"
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    # One JSON implementation only. A jq fallback would be a second copy of the
    # verdict logic that nothing exercises and that would quietly rot.
    emit SKIP ci_freshness "python3 not available to parse the GitHub API response"
    return 0
  fi

  # per_page=20, NOT 1. Looking only at the newest run is defeated by the very
  # push cadence that masked the original outage: with the runner dead,
  # cancel-in-progress cancels the old queued run and each push creates a fresh
  # one, so "the newest run" is perpetually young and this check stays green
  # forever. The drain signal below needs the surrounding runs to see that runs
  # are being created and NONE is completing.
  api="https://api.github.com/repos/${GH_REPO}/actions/workflows/${GH_CI_WORKFLOW}/runs?per_page=20"
  # curl reads its config (and therefore the Authorization header and URL) from
  # STDIN, so the token never appears in this host's process list — `-H "Bearer
  # ..."` on the command line would be world-readable via ps for the life of
  # the call.
  resp="$(http_get "$api" "$token")"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    emit WARN ci_freshness "GitHub API not reached via ${HTTP_TOOL} (rc=${rc}) — CI freshness unknown"
    return 0
  fi
  code="${resp##*http_code=}"
  body="${resp%$'\n'http_code=*}"
  case "$code" in
    200) ;;
    401|403) emit WARN ci_freshness "GitHub API returned ${code} — monitoring token rejected or lacks actions:read; CI freshness unknown"; return 0 ;;
    404) emit WARN ci_freshness "GitHub API returned 404 for workflow ${GH_CI_WORKFLOW} in ${GH_REPO} — renamed? set WWF_WATCHDOG_CI_WORKFLOW"; return 0 ;;
    *) emit WARN ci_freshness "GitHub API returned http=${code} — CI freshness unknown"; return 0 ;;
  esac

  # The body goes through a temp FILE, not the environment. A single env var is
  # capped at MAX_ARG_STRLEN (128 KiB) and the per_page=20 response measured
  # 296 KB against the real API, so `WWF_BODY="$body" python3` failed with E2BIG
  # and produced NOTHING — which this function then reported as "could not parse
  # GitHub API response". The fixtures could not catch it: they were small. It
  # also keeps a 300 KB API body out of the process environment.
  local bodyfile
  bodyfile="$(mktemp 2>/dev/null || printf '/tmp/wwf-watchdog-%s.json' "$$")"
  printf '%s' "$body" > "$bodyfile"
  py_out="$(WWF_BODY_FILE="$bodyfile" python3 - <<'PY' 2>/dev/null
import json, os, sys
from datetime import datetime, timezone
try:
    d = json.load(open(os.environ["WWF_BODY_FILE"]))
    runs = d.get("workflow_runs") or []
    print(f"total={d.get('total_count', 0)}")
    now = datetime.now(timezone.utc)

    def age_of(run):
        ts = (run.get("created_at") or "").replace("Z", "+00:00")
        return int((now - datetime.fromisoformat(ts)).total_seconds())

    if runs:
        r = runs[0]
        print(f"status={r.get('status')}")
        print(f"conclusion={r.get('conclusion') or 'none'}")
        print(f"number={r.get('run_number')}")
        print(f"age_seconds={age_of(r)}")

        # The drain signal. A run that REACHED a conclusion proves the runner
        # actually executed something; "created" only proves GitHub accepted a
        # push. Report the age of the newest concluded run, and how many
        # unfinished runs sit newer than it. Runs accumulating with nothing
        # concluding is the outage signature, and unlike the newest run's age it
        # does not reset when someone pushes again.
        concluded = [x for x in runs if x.get("conclusion")]
        unfinished = [x for x in runs if not x.get("conclusion")]
        print(f"unfinished={len(unfinished)}")
        if concluded:
            newest_done = min(concluded, key=age_of)
            print(f"last_conclusion_age_seconds={age_of(newest_done)}")
            print(f"last_conclusion_number={newest_done.get('run_number')}")
        else:
            print("last_conclusion_age_seconds=-1")
            print("last_conclusion_number=none")
except Exception as exc:                     # noqa: BLE001 - reported, not raised
    print(f"error={type(exc).__name__}: {exc}")
    sys.exit(0)
PY
)"
  rm -f "$bodyfile"

  local total=0 status="" concl="" number="" age=0 perr="" k v
  local unfinished=0 done_age=-1 done_num="none"
  while IFS='=' read -r k v; do
    case "$k" in
      total) total="$v" ;;
      status) status="$v" ;;
      conclusion) concl="$v" ;;
      number) number="$v" ;;
      age_seconds) age="$v" ;;
      unfinished) unfinished="$v" ;;
      last_conclusion_age_seconds) done_age="$v" ;;
      last_conclusion_number) done_num="$v" ;;
      error) perr="$v" ;;
    esac
  done <<EOF
${py_out}
EOF

  if [ -n "$perr" ] || [ -z "$py_out" ]; then
    emit WARN ci_freshness "could not parse GitHub API response (${perr:-empty output})"
    return 0
  fi
  if [ "$total" = 0 ] || [ -z "$status" ]; then
    emit WARN ci_freshness "no ${GH_CI_WORKFLOW} runs exist in ${GH_REPO}"
    return 0
  fi

  local age_min=$((age / 60))

  # THE PUSH-PROOF DEAD-MAN'S SWITCH, checked before the per-status verdicts
  # below because those key off the NEWEST run and are therefore reset by every
  # push. If runs exist that never concluded and nothing has concluded within
  # the drain window, the queue is not draining — report that and stop, rather
  # than letting a perpetually-young queued run report PASS.
  if [ "$unfinished" -gt 0 ]; then
    if [ "$done_age" -lt 0 ]; then
      emit FAIL ci_freshness "${unfinished} unfinished ${GH_CI_WORKFLOW} run(s) and NONE of the ${total} most recent reached a conclusion — no runner is executing work"
      return 0
    fi
    local done_min=$((done_age / 60))
    if [ "$done_min" -ge "$CI_NO_COMPLETION_MAX_MIN" ]; then
      emit FAIL ci_freshness "${unfinished} unfinished ${GH_CI_WORKFLOW} run(s); last run to CONCLUDE was #${done_num}, ${done_min}min ago (limit ${CI_NO_COMPLETION_MAX_MIN}) — runs are being created but the queue is not draining"
      return 0
    fi
  fi

  case "$status" in
    queued|waiting|pending|requested)
      # THE DEAD-MAN'S SWITCH. GitHub accepted the run and nothing took it —
      # the runner is not picking up work, whatever the reason (container down,
      # bin/ wiped, labels changed, runner version too old to be assigned).
      if [ "$age_min" -ge "$CI_QUEUED_MAX_MIN" ]; then
        emit FAIL ci_freshness "${GH_CI_WORKFLOW} run #${number} has been ${status} for ${age_min}min (limit ${CI_QUEUED_MAX_MIN}) — no runner has picked it up"
      else
        emit PASS ci_freshness "${GH_CI_WORKFLOW} run #${number} ${status} for ${age_min}min (within ${CI_QUEUED_MAX_MIN})"
      fi
      ;;
    in_progress)
      if [ "$age_min" -ge "$CI_RUNNING_MAX_MIN" ]; then
        emit FAIL ci_freshness "${GH_CI_WORKFLOW} run #${number} in_progress for ${age_min}min (limit ${CI_RUNNING_MAX_MIN}) — wedged job holding the only runner"
      else
        emit PASS ci_freshness "${GH_CI_WORKFLOW} run #${number} in_progress for ${age_min}min"
      fi
      ;;
    completed)
      case "$concl" in
        success)
          if [ "$age_min" -ge $((CI_MAX_AGE_DAYS * 1440)) ]; then
            # WARN, never FAIL: no runs can legitimately mean nobody pushed.
            emit WARN ci_freshness "newest ${GH_CI_WORKFLOW} run #${number} succeeded but is ${age_min}min old (>${CI_MAX_AGE_DAYS}d) — may simply mean no pushes"
          else
            emit PASS ci_freshness "${GH_CI_WORKFLOW} run #${number} success, ${age_min}min old"
          fi
          ;;
        cancelled|skipped|neutral)
          # Not a pass: `cancel-in-progress: true` cancelling runs is exactly
          # what disguised the outage. Routine on rapid pushes, hence WARN.
          emit WARN ci_freshness "newest ${GH_CI_WORKFLOW} run #${number} conclusion=${concl} (${age_min}min old) — routine with cancel-in-progress, but nothing was actually verified"
          ;;
        *)
          emit FAIL ci_freshness "newest ${GH_CI_WORKFLOW} run #${number} conclusion=${concl} (${age_min}min old)"
          ;;
      esac
      ;;
    *)
      emit WARN ci_freshness "${GH_CI_WORKFLOW} run #${number} unrecognised status=${status}"
      ;;
  esac
  return 0
}

# ----------------------------------------------------------------------- run
# Preflighted once, before anything that shells out to docker, so a socket or
# permissions fault is reported as itself instead of as a pile of container
# checks that look like missing containers.
# Validate the group list BEFORE running anything. want() silently returns
# false for a name it does not recognise, so `--only prd` (or a typo in the
# crontab, the systemd ExecStart, or WWF_WATCHDOG_ONLY) previously ran ZERO
# checks and exited 0 with result=OK — a permanently green watchdog, which is
# the exact failure this script exists to make impossible.
KNOWN_GROUPS="all runner prod ci"
for _g in $(printf '%s' "$ONLY" | tr ',' ' '); do
  case " $KNOWN_GROUPS " in
    *" $_g "*) ;;
    *) printf 'watchdog.sh: unknown check group "%s" (known: %s)\n' \
         "$_g" "$KNOWN_GROUPS" >&2; exit 64 ;;
  esac
done

if want runner || want prod; then
  check_docker_access
fi
want runner && { check_runner_container; check_runner_listener; check_runner_process; }
want prod   && { check_app_ready; check_db_containers; }
want ci     && check_ci_freshness

RESULT=OK
[ "$WARNS" -gt 0 ] && RESULT=WARN
[ "$FAILS" -gt 0 ] && RESULT=FAIL
# A run in which NOTHING executed is not a healthy run. Group validation above
# catches the typo case, but this is the backstop for any future path that
# skips every check: reporting OK on zero observations is how a monitor lies.
if [ "$((PASSES + FAILS + WARNS + SKIPS))" -eq 0 ]; then
  RESULT=FAIL
  FAILS=1
  FAILED_NAMES="no-checks-ran"
fi
SUMMARY="wwf-watchdog ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) host=${HOST_NAME} result=${RESULT} pass=${PASSES} fail=${FAILS} warn=${WARNS} skip=${SKIPS} groups=${ONLY} failed=\"$(sanitize "$FAILED_NAMES")\""
printf '%s\n' "$SUMMARY"
command -v logger >/dev/null 2>&1 && logger -t wwf-watchdog \
  -p "$([ "$RESULT" = FAIL ] && echo daemon.err || echo daemon.info)" "$SUMMARY" 2>/dev/null

# Optional webhook. No endpoint is invented or hardcoded here: unset means this
# whole block is skipped and stdout + exit status remain the alerting channel.
if [ -n "$WEBHOOK" ] && { [ "$RESULT" = FAIL ] || [ "$WEBHOOK_ALWAYS" = 1 ]; }; then
  # Fields are hand-assembled rather than passed through a JSON library so the
  # webhook works on a host without python3; every interpolated value has
  # already been through sanitize(), which removes the quotes and backslashes
  # that could break the document.
  PAYLOAD="$(printf '{"source":"wwf-watchdog","host":"%s","result":"%s","pass":%s,"fail":%s,"warn":%s,"skip":%s,"failed":"%s","detail":"%s"}' \
    "$(sanitize "$HOST_NAME")" "$RESULT" "$PASSES" "$FAILS" "$WARNS" "$SKIPS" \
    "$(sanitize "$FAILED_NAMES")" "$(sanitize "$SUMMARY_LINES")")"
  # Same --config-on-stdin treatment as the GitHub call: a webhook URL is itself
  # a credential (it is the bearer token for most notification services), so it
  # must not land in the process list — and it is never echoed on failure.
  #
  # The PAYLOAD deliberately goes on argv rather than into the config file,
  # because curl's config parser cannot carry it: a quoted value ends at the
  # first unescaped `"` (verified — the body arrives as the single byte `{`) and
  # an unquoted value ends at the first WHITESPACE (verified — the body arrives
  # truncated mid-detail). Either way curl still exits 0, so the watchdog would
  # have reported webhook=sent while delivering a broken document. argv is safe
  # here for the payload specifically: it holds only check names, statuses and
  # sanitized details, no credentials.
  # curl exits 0 for a request that was DELIVERED, including one the endpoint
  # rejected with 404/403/429 — which is exactly how a webhook dies in practice
  # (rotated Slack URL, revoked token, rate limit). Reporting webhook=sent on a
  # 500 is the same silent-failure class this script exists to eliminate, so
  # assert the HTTP status rather than the exit code.
  WEBHOOK_CODE="$(printf 'silent\nshow-error\nmax-time = 15\nwrite-out = "%%{http_code}"\nheader = "Content-Type: application/json"\nurl = "%s"\n' \
       "$WEBHOOK" | bounded 25 curl --config - --data "$PAYLOAD" -o /dev/null 2>/dev/null)" || WEBHOOK_CODE=""
  case "$WEBHOOK_CODE" in
    2*) printf 'wwf-watchdog webhook=sent http=%s\n' "$WEBHOOK_CODE" ;;
    '') printf 'wwf-watchdog webhook=failed http=none (unreachable/timeout; URL not echoed: it is a credential)\n' ;;
    *)  printf 'wwf-watchdog webhook=rejected http=%s (URL not echoed: it is a credential)\n' "$WEBHOOK_CODE" ;;
  esac
fi

[ "$FAILS" -gt 0 ] && exit 1
exit 0

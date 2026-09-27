"""Call the GitHub REST API for this repository with the owner's token.

    python3 ops/agent/gh_api.py GET   /repos/3p4e/WEEKLY_WEED_FLOW/actions/runs?per_page=5
    python3 ops/agent/gh_api.py POST  /repos/3p4e/WEEKLY_WEED_FLOW/actions/runs/<id>/rerun
    python3 ops/agent/gh_api.py POST  /repos/3p4e/WEEKLY_WEED_FLOW/actions/workflows/migration-rehearsal.yml/dispatches '{"ref":"<branch>"}'
    python3 ops/agent/gh_api.py GET   <path> --dry-run

For agent sessions. The GitHub App behind a session is read-only (no Actions
write), and the session's proxy will not carry a personal token, so the call is
made from KVM4 through the kvm4-runner API (the same /shell and /file/write
endpoints deploy.yml uses). The owner pre-approves exactly this invocation in
the cloud environment's setup script (see CLAUDE.md, "Agent helpers"); call it
as a standalone command from the repo root.

ALLOW-LIST, not a deny-list. The first version refused DELETE and nothing
else, so a pre-approved command could merge a pull request, force-move a
branch, commit straight to the default branch, add a collaborator or rewrite
branch protection with the owner's token (review 2026-09-27, DI-03). What is
allowed now is exactly what the read-only GitHub App cannot do and a session
legitimately needs:

  GET   anything under /repos/3p4e/WEEKLY_WEED_FLOW/            (reads; a query string is fine)
  POST  …/actions/runs/<id>/rerun  and  …/rerun-failed-jobs     (re-run a workflow run)
  POST  …/actions/workflows/<file>.yml/dispatches               (dispatch a workflow)
  POST  …/issues/<n>/comments                                   (comment on an issue or a PR)

Everything else — PUT, PATCH, DELETE, any other POST — is refused here, before
any request is built. The token's own scopes remain the outer limit.

THE TOKEN NEVER TRAVELS IN THE /shell COMMAND TEXT. The kvm4-runner keeps an
audit trail of /shell command strings on the host, so a token in `cmd` is a
token written to disk. It goes to the host as a 0600 file through /file/write
(whose body is not part of that trail), the one-off python process reads it
from that file, and the same /shell call shreds the file whether the request
succeeded or not. If that /shell call itself fails — a 504 from the runner's
90 s timeout, a dropped connection — a second, best-effort /shell call
shreds the staged file, so no exit path leaves the owner's token on the host
(review 2026-09-27, DI2-08). If /file/write is unavailable the helper falls
back to writing the file from the command text with a loud warning, so the
exposure is at least visible rather than silent. The token is scrubbed from
anything printed here.

The dispatch pattern INCLUDES deploy.yml: a production deploy is therefore
inside the pre-approved command. CLAUDE.md says so.

Prints "HTTP <status>" and the response body. Exit 0 on 2xx, 1 otherwise.
"""
import base64
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request

REPO = "/repos/3p4e/WEEKLY_WEED_FLOW"
_R = re.escape(REPO)
# (method, path-regex). Paths are matched WITHOUT their query string; only
# GET may carry one. Case-sensitive on the method, case-insensitive on the
# repository name (GitHub treats it so).
ALLOW = (
    ("GET", re.compile(rf"^{_R}(?:/[^\s?#]*)?$", re.I)),
    ("POST", re.compile(rf"^{_R}/actions/runs/\d+/rerun(?:-failed-jobs)?$", re.I)),
    ("POST", re.compile(rf"^{_R}/actions/workflows/[A-Za-z0-9_.-]+\.ya?ml/dispatches$", re.I)),
    ("POST", re.compile(rf"^{_R}/issues/\d+/comments$", re.I)),
)
MAX_BODY_PRINT = 20_000
TOKEN_DIR = "/opt/wwf-deploy/.gh_api"

# Runs on KVM4. argv[1] is the 0600 token file, argv[2] one base64 JSON
# argument (method, path, body) — nothing secret is in the command line.
REMOTE = r"""
import base64, json, sys, urllib.error, urllib.request
with open(sys.argv[1], encoding="utf-8") as f:
    token = f.read().strip()
a = json.loads(base64.b64decode(sys.argv[2]))
req = urllib.request.Request(
    "https://api.github.com" + a["path"], method=a["method"],
    data=None if a["body"] is None else json.dumps(a["body"]).encode(),
    headers={"Authorization": "Bearer " + token,
             "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28",
             "User-Agent": "wwf-agent-gh-api"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        status, raw = r.status, r.read()
except urllib.error.HTTPError as e:
    status, raw = e.code, e.read()
print("@@GH@@" + json.dumps({"status": status, "body": raw.decode("utf-8", "replace")}))
"""


def usage():
    print(__doc__.strip())
    return 2


def allowed(method, path):
    """The allow-list verdict for one request, as (ok, reason)."""
    if ".." in path or re.search(r"\s", path) or "//" in path or not path.startswith("/"):
        return False, "path must be a clean absolute API path under %s" % REPO
    # No percent-encoding at all: the allow-list has no legitimate encoded
    # segment, and %2E%2E / %2F would otherwise ride through the GET pattern
    # as an ordinary path character (review 2026-09-27, DI2-08).
    if "%" in path or "#" in path:
        return False, "percent-encoding and fragments are not accepted in the path"
    bare, _, query = path.partition("?")
    if query and method != "GET":
        return False, "only GET may carry a query string"
    for m, rx in ALLOW:
        if m == method and rx.match(bare):
            return True, ""
    return False, ("%s %s is not on the allow-list (GET anything under the repo; POST "
                   "…/actions/runs/<id>/rerun[-failed-jobs], …/actions/workflows/<file>/dispatches, "
                   "…/issues/<n>/comments). Anything else is a human action in the GitHub UI."
                   % (method, bare))


def _sh_quote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _shred_cmd(token_file):
    """The host-side removal of the staged token file (shred, or rm when
    shred is absent); idempotent, silent when the file is already gone."""
    q = _sh_quote(token_file)
    return "shred -u %s 2>/dev/null || rm -f %s" % (q, q)


def _cleanup_token_file(runner, token_file):
    """Best-effort removal of the staged token in its own /shell call, used
    when the call that should have removed it did not come back (DI2-08).
    Never raises: the caller is already handling a failure, and the worst
    case — the file is still there — is reported, not hidden."""
    try:
        runner.shell(_shred_cmd(token_file), 30)
        print("gh_api: staged token file removed after the failed call", file=sys.stderr)
    except BaseException as exc:  # noqa: BLE001 — reported, then the original failure surfaces
        print("gh_api: WARNING: could not remove the staged token file %s on the host (%s) — "
              "remove it by hand and rotate GITHUB_PAT_WWF" % (token_file, exc), file=sys.stderr)


class Runner:
    """The two kvm4-runner endpoints this helper uses."""

    def __init__(self, base, token):
        self.base = base.rstrip("/")
        self.token = token

    def _post(self, path, payload, timeout):
        req = urllib.request.Request(
            self.base + path, method="POST",
            data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())

    def shell(self, cmd, timeout=90):
        return self._post("/shell", {"cmd": cmd, "timeout": timeout}, timeout + 60)

    def file_write(self, remote, content, mode="0600"):
        """True if the file landed through /file/write; False if that endpoint
        is unavailable (blocked, absent), so the caller can fall back. Any
        other failure raises."""
        payload = {"path": remote, "content_b64": base64.b64encode(content.encode()).decode(),
                   "mode": mode, "mkdir": True}
        try:
            self._post("/file/write", payload, 60)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 415, 422):
                # the same mode-type guess deploy.yml's kvm4.py makes
                payload["mode"] = int(mode, 8)
                try:
                    self._post("/file/write", payload, 60)
                    return True
                except urllib.error.HTTPError as exc2:
                    if exc2.code in (403, 404, 405):
                        return False
                    raise
            if exc.code in (403, 404, 405):
                return False
            raise


def main(argv):
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        return usage()
    method, path = argv[0].upper(), argv[1]
    ok, why = allowed(method, path)
    if not ok:
        print("gh_api: refused: " + why, file=sys.stderr)
        return 2
    body = None
    if len(argv) > 2:
        raw = argv[2]
        if raw.startswith("@"):
            raw = open(raw[1:], encoding="utf-8").read()
        body = json.loads(raw)
    if dry:
        print("%s https://api.github.com%s" % (method, path))
        if body is not None:
            print(json.dumps(body, indent=2))
        return 0

    token = os.environ.get("GITHUB_PAT_WWF", "").strip()
    if not token.startswith(("github_pat_", "ghp_")):
        print("gh_api: GITHUB_PAT_WWF is not set to a GitHub token", file=sys.stderr)
        return 1
    base = os.environ.get("RUNNER_URL", "").rstrip("/")
    rtok = os.environ.get("RUNNER_TOKEN", "").strip()
    if not base or not rtok:
        print("gh_api: RUNNER_URL and RUNNER_TOKEN must be set", file=sys.stderr)
        return 1
    runner = Runner(base, rtok)

    token_file = "%s/%s.token" % (TOKEN_DIR, secrets.token_hex(8))
    arg = base64.b64encode(json.dumps(
        {"method": method, "path": path, "body": body}).encode()).decode()
    # Whatever happens to the request, the token file is shredded in the SAME
    # shell call, so no failure path INSIDE that call leaves it behind.
    call = ("python3 -c %s %s %s; rc=$?; %s; exit $rc"
            % (_sh_quote(REMOTE), _sh_quote(token_file), arg, _shred_cmd(token_file)))
    staged = False
    try:
        staged = runner.file_write(token_file, token)
        if staged:
            cmd = call
        else:
            print("gh_api: WARNING: /file/write is unavailable on kvm4-runner; the token "
                  "is being staged through the /shell command text instead, which the "
                  "runner records. Rotate GITHUB_PAT_WWF when /file/write is back.",
                  file=sys.stderr)
            cmd = ("umask 077; mkdir -p %s; printf '%%s' %s > %s; %s"
                   % (_sh_quote(TOKEN_DIR), _sh_quote(token), _sh_quote(token_file), call))
        try:
            r = runner.shell(cmd, 90)
        except BaseException:
            # The call that would have shredded the file did not report back
            # (timeout, dropped connection, HTTP error, Ctrl-C): whether the
            # file landed through /file/write or through the fallback's own
            # command text, it may still be on the host. Shred it in a call
            # of its own; the outer handlers then report the original failure.
            _cleanup_token_file(runner, token_file)
            raise
    except urllib.error.HTTPError as exc:
        print("gh_api: kvm4-runner answered HTTP %d%s" % (
            exc.code, " (RUNNER_TOKEN is stale; see CLAUDE.md)" if exc.code == 403 else ""),
            file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print("gh_api: %s" % exc, file=sys.stderr)
        return 1

    out = (r.get("output", "") or "").replace(token, "<GITHUB_PAT_WWF>")
    line = next((l for l in out.splitlines() if l.startswith("@@GH@@")), None)
    if line is None:
        print("gh_api: no response from the host-side call (remote exit %s):\n%s"
              % (r.get("exit_code"), out[-2000:]), file=sys.stderr)
        return 1
    res = json.loads(line[len("@@GH@@"):])
    status, text = res["status"], res["body"].replace(token, "<GITHUB_PAT_WWF>")
    print("HTTP %d" % status)
    if text:
        try:
            text = json.dumps(json.loads(text), indent=2)
        except ValueError:
            pass
        if len(text) > MAX_BODY_PRINT:
            text = text[:MAX_BODY_PRINT] + "\n… (%d more characters)" % (len(text) - MAX_BODY_PRINT)
        print(text)
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

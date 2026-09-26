"""Call the GitHub REST API for this repository with the owner's token.

    python3 ops/agent/gh_api.py GET   /repos/3p4e/WEEKLY_WEED_FLOW/actions/runs?per_page=5
    python3 ops/agent/gh_api.py POST  /repos/3p4e/WEEKLY_WEED_FLOW/actions/runs/<id>/rerun
    python3 ops/agent/gh_api.py POST  /repos/3p4e/WEEKLY_WEED_FLOW/actions/workflows/migration-rehearsal.yml/dispatches '{"ref":"<branch>"}'
    python3 ops/agent/gh_api.py GET   <path> --dry-run

For agent sessions. The GitHub App behind a session is read-only (no Actions
write), and the session's proxy will not carry a personal token, so the call is
made from KVM4 through ops/agent/rsh.py's /shell API. The owner pre-approves
exactly this invocation in the cloud environment's setup script (see
CLAUDE.md, "Agent helpers"); call it as a standalone command from the repo root.

Deliberately narrow:
  - only paths under /repos/3p4e/WEEKLY_WEED_FLOW/
  - only GET, POST, PUT and PATCH; DELETE is refused, so a deletion stays a
    human action in the GitHub UI
  - the token (GITHUB_PAT_WWF) travels to the host inside the HTTPS request
    body and is handed, base64-encoded, to a one-off python process that lives
    for the length of the call. It is never written to disk there, but root in
    the kvm4-runner container could see it in that process's arguments while
    it runs. It is scrubbed from anything printed here.

Prints "HTTP <status>" and the response body. Exit 0 on 2xx, 1 otherwise.
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO_PREFIX = "/repos/3p4e/weekly_weed_flow/"
METHODS = ("GET", "POST", "PUT", "PATCH")
MAX_BODY_PRINT = 20_000

# Runs on KVM4. Reads one base64 JSON argument so nothing but the script
# itself needs shell quoting.
REMOTE = r"""
import base64, json, sys, urllib.error, urllib.request
a = json.loads(base64.b64decode(sys.argv[1]))
req = urllib.request.Request(
    "https://api.github.com" + a["path"], method=a["method"],
    data=None if a["body"] is None else json.dumps(a["body"]).encode(),
    headers={"Authorization": "Bearer " + a["token"],
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


def main(argv):
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        return usage()
    method, path = argv[0].upper(), argv[1]
    if method not in METHODS:
        print("gh_api: %s is not allowed (only %s)" % (method, ", ".join(METHODS)),
              file=sys.stderr)
        return 2
    if not path.lower().startswith(REPO_PREFIX) or ".." in path \
            or re.search(r"\s", path):
        print("gh_api: path must start with /repos/3p4e/WEEKLY_WEED_FLOW/",
              file=sys.stderr)
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
    arg = base64.b64encode(json.dumps(
        {"method": method, "path": path, "body": body, "token": token}).encode()).decode()
    cmd = "python3 -c %s %s" % (_sh_quote(REMOTE), arg)

    base = os.environ.get("RUNNER_URL", "").rstrip("/")
    rtok = os.environ.get("RUNNER_TOKEN", "").strip()
    if not base or not rtok:
        print("gh_api: RUNNER_URL and RUNNER_TOKEN must be set", file=sys.stderr)
        return 1
    req = urllib.request.Request(
        base + "/shell", method="POST",
        data=json.dumps({"cmd": cmd, "timeout": 90}).encode(),
        headers={"Authorization": "Bearer " + rtok,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=150) as resp:
            out = json.loads(resp.read().decode()).get("output", "")
    except urllib.error.HTTPError as exc:
        print("gh_api: kvm4-runner answered HTTP %d%s" % (
            exc.code, " (RUNNER_TOKEN is stale; see CLAUDE.md)" if exc.code == 403 else ""),
            file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print("gh_api: %s" % exc, file=sys.stderr)
        return 1

    out = out.replace(token, "<GITHUB_PAT_WWF>")
    line = next((l for l in out.splitlines() if l.startswith("@@GH@@")), None)
    if line is None:
        print("gh_api: no response from the host-side call:\n" + out[-2000:],
              file=sys.stderr)
        return 1
    res = json.loads(line[len("@@GH@@"):])
    status, text = res["status"], res["body"]
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


def _sh_quote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

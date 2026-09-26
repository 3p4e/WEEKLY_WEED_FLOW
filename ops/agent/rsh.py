"""Run one shell command on KVM4 through the kvm4-runner /shell API.

    python3 ops/agent/rsh.py '<command>' [timeout_seconds]
    python3 ops/agent/rsh.py - [timeout_seconds] < script.sh

For agent sessions. The owner pre-approves exactly this invocation in the
cloud environment's setup script (see CLAUDE.md, "Agent helpers"), so call it
as a standalone command from the repo root: no `cd … &&`, no `S=…;` prefix.

Reads RUNNER_URL and RUNNER_TOKEN from the environment. The command runs as
root inside the kvm4-runner container, which holds the docker socket, so it
reaches the whole host. The response contract is the one deploy.yml's kvm4.py
parses: {exit_code, output (stdout+stderr), truncated, bytes}.

Exit status is the remote exit_code (1 if the call itself failed).
"""
import json
import os
import sys
import urllib.error
import urllib.request

# /shell starts answering a bare HTTP 500 somewhere between 128 KB and 150 KB.
MAX_PAYLOAD = 120_000


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    cmd = sys.stdin.read() if argv[0] == "-" else argv[0]
    timeout = int(argv[1]) if len(argv) > 1 else 120
    base = os.environ.get("RUNNER_URL", "").rstrip("/")
    token = os.environ.get("RUNNER_TOKEN", "").strip()
    if not base or not token:
        print("rsh: RUNNER_URL and RUNNER_TOKEN must be set in the environment",
              file=sys.stderr)
        return 1
    body = json.dumps({"cmd": cmd, "timeout": timeout}).encode()
    if len(body) > MAX_PAYLOAD:
        print("rsh: payload is %d bytes; /shell fails above ~128 KB. Send it in "
              "chunks (append to a file on the host, then run it)." % len(body),
              file=sys.stderr)
        return 1
    req = urllib.request.Request(
        base + "/shell", data=body, method="POST",
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"})
    try:
        # The read timeout has to outlast the remote one, or a long step that
        # is still running looks like a network failure.
        with urllib.request.urlopen(req, timeout=timeout + 60) as resp:
            r = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        hint = {
            401: "no bearer token was sent",
            403: "RUNNER_TOKEN is not the token kvm4-runner holds; update it in "
                 "the environment settings (see CLAUDE.md, Agent helpers)",
            422: "the service rejected the request body",
            504: "the command outlived its %ss timeout on the host; run long "
                 "work under nohup setsid and poll a status file" % timeout,
        }.get(exc.code, exc.read().decode(errors="replace")[:400])
        print("rsh: HTTP %d: %s" % (exc.code, hint), file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print("rsh: %s" % exc, file=sys.stderr)
        return 1
    out = r.get("output", "")
    if out:
        sys.stdout.write(out if out.endswith("\n") else out + "\n")
    if r.get("truncated"):
        print("rsh: output truncated (%s bytes on the host)" % r.get("bytes"),
              file=sys.stderr)
    rc = r.get("exit_code")
    if rc is None:
        print("rsh: response has no exit_code; kvm4-runner is not serving the "
              "contract deploy.yml expects", file=sys.stderr)
        return 1
    print("rsh: exit_code=%s" % rc, file=sys.stderr)
    return rc if 0 <= rc <= 255 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

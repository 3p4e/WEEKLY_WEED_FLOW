#!/usr/bin/env bash
# gh-runner-wwf entrypoint (rebuilt 2026-09-25).
#
# Registration is deliberately NOT done here. It is a one-time
#   docker exec -i gh-runner-wwf ./config.sh ... --disableupdate
# with a fresh registration token fed on stdin (ops/README.md, "Registering
# the runner"), so no token ever lands in the container's env or in
# `docker inspect` — the previous entrypoint took it via GH_RUNNER_TOKEN, and
# it leaked from exactly there.
#
# There is also no deregister-on-stop trap. The previous one ran
# `config.sh remove` on every SIGTERM, so any `docker stop` within the token's
# validity hour silently unregistered the runner.
set -euo pipefail
cd /home/runner/actions-runner
until [ -s .runner ] && [ -s .credentials ]; do
  echo "[entrypoint] runner not configured yet; waiting for config.sh" >&2
  sleep 15
done
exec ./run.sh

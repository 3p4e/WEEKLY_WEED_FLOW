#!/usr/bin/env bash
# Render nginx.local.conf with an absolute path to web/ and exec nginx in
# the foreground (exec, not a background start, so Playwright's webServer
# can signal it directly for teardown instead of losing track of a child).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

WEB_ROOT="$(cd .. && pwd)"
RENDERED=/tmp/wwf-e2e-nginx.conf
sed "s#__WEB_ROOT__#${WEB_ROOT}#" nginx.local.conf > "$RENDERED"
exec nginx -c "$RENDERED" -g "daemon off;"

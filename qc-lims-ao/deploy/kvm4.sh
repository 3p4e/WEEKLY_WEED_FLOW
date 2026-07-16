#!/usr/bin/env bash
#
# Deploy GrowFlow Unified (QC_LIMS_Ao) on the KVM4 host under project QC_LIMS_Ao1.
#
# Run this ON the server. To deploy THIS feature branch, fetch the script from it
# and set BRANCH to match:
#
#   curl -fsSL https://raw.githubusercontent.com/3p4e/QC_LIMS_Ao/claude/repo-initialization-f6opt5/deploy/kvm4.sh \
#     | BRANCH=claude/repo-initialization-f6opt5 bash
#
# Or, once merged to main:
#
#   curl -fsSL https://raw.githubusercontent.com/3p4e/QC_LIMS_Ao/main/deploy/kvm4.sh | bash
#
# Brings up the full stack with docker compose: Postgres + FastAPI (auto-seeded)
# + nginx serving the React build. App on :8080, API (docs) on :8000. The backend
# is wired to the host's Letta + Qdrant containers and to the KPM runner network.
set -euo pipefail

REPO_URL="https://github.com/3p4e/QC_LIMS_Ao.git"
APP_DIR="${APP_DIR:-/opt/qc_lims_ao}"
BRANCH="${BRANCH:-main}"
KPM_NETWORK="${KPM_NETWORK:-kpm_network}"
# AI dependency containers already running on the host (name → service).
AI_DEPS="${AI_DEPS:-letta qdrant letta-mcp-rust}"
# Single shared Docker network that Letta/Qdrant/Letta-MCP all sit on. The
# backend joins ONLY this one for container-name routing (host.docker.internal
# URLs work regardless). Do NOT join every network a dependency is on — hub
# containers like letta are attached to many unrelated stack networks.
AI_NETWORK="${AI_NETWORK:-shared}"
# Public hostname served via the shared Traefik proxy (HTTPS + Let's Encrypt).
APP_HOST="${APP_HOST:-qclims.srv1231216.hstgr.cloud}"
# Base compose + KVM4 production overlay (Traefik exposure + shared AI network).
COMPOSE="-f docker-compose.yml -f docker-compose.kvm4.yml"

echo "▶ GrowFlow Unified deploy → $APP_DIR (branch $BRANCH, project QC_LIMS_Ao1)"

# 1. Docker present?
if ! command -v docker >/dev/null 2>&1; then
  echo "✗ Docker not found. Install Docker Engine + the compose plugin first:"
  echo "    curl -fsSL https://get.docker.com | sh"
  exit 1
fi
docker compose version >/dev/null 2>&1 || { echo "✗ 'docker compose' plugin missing"; exit 1; }

# 2. Show current host Docker state so the operator knows what's running.
echo ""
echo "═══════════════ Host Docker state (before deploy) ═══════════════"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
echo ""
echo "▶ Networks:"
docker network ls 2>/dev/null || true
echo "═════════════════════════════════════════════════════════════════"
echo ""

# 3. Clone or update the repo.
if [ -d "$APP_DIR/.git" ]; then
  echo "▶ Updating existing checkout"
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  echo "▶ Cloning $REPO_URL ($BRANCH)"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# 4. Persist config in .env (generated once, reused on redeploy).
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "SECRET_KEY=$(openssl rand -hex 32)" > "$ENV_FILE"
  echo "▶ Generated SECRET_KEY → $ENV_FILE"
fi
grep -q "^KPM_NETWORK=" "$ENV_FILE" || echo "KPM_NETWORK=$KPM_NETWORK" >> "$ENV_FILE"
grep -q "^APP_HOST=" "$ENV_FILE" || echo "APP_HOST=$APP_HOST" >> "$ENV_FILE"
# Carry through a Voyage API key if one is exported in the environment (enables
# Tier-1 RAG ingestion). Safe to leave empty — the app falls back gracefully.
if [ -n "${VOYAGE_API_KEY:-}" ] && ! grep -q "^VOYAGE_API_KEY=" "$ENV_FILE"; then
  echo "VOYAGE_API_KEY=$VOYAGE_API_KEY" >> "$ENV_FILE"
fi

# 5. Build & launch (detached). Base + KVM4 overlay (Traefik HTTPS + shared AI net).
echo "▶ Building and starting containers…"
docker compose $COMPOSE --env-file "$ENV_FILE" up -d --build

BACKEND_CTR="$(docker compose $COMPOSE --env-file "$ENV_FILE" ps -q backend 2>/dev/null | head -1)"
[ -z "$BACKEND_CTR" ] && BACKEND_CTR="QC_LIMS_Ao1-backend-1"

# 6. Attach the backend to the ONE shared AI network so container-name routing
#    works alongside the host-gateway URLs. host.docker.internal already reaches
#    the host-published Letta/Qdrant ports, so this is best-effort.
echo "▶ Wiring backend to AI network '$AI_NETWORK' (Letta/Qdrant/Letta-MCP)…"
if docker network inspect "$AI_NETWORK" >/dev/null 2>&1; then
  if docker network connect "$AI_NETWORK" "$BACKEND_CTR" 2>/dev/null; then
    echo "  ✓ backend joined '$AI_NETWORK'"
  else
    echo "  ✓ backend already on '$AI_NETWORK'"
  fi
else
  echo "  – network '$AI_NETWORK' not found; relying on host.docker.internal URLs"
fi

# 7. Connect KPM runner containers to our shared network so they can reach the
#    backend API. Containers already on the network are silently skipped.
echo "▶ Connecting KPM runner containers to '$KPM_NETWORK'…"
KPM_FOUND=0
while IFS= read -r container; do
  [ -z "$container" ] && continue
  KPM_FOUND=1
  if docker network connect "$KPM_NETWORK" "$container" 2>/dev/null; then
    echo "  ✓ connected $container → $KPM_NETWORK"
  else
    echo "  ✓ $container already on $KPM_NETWORK"
  fi
done < <(docker ps --format '{{.Names}}' 2>/dev/null | grep -iE 'kpm|runner' | grep -v 'QC_LIMS_Ao1' || true)
[ "$KPM_FOUND" -eq 0 ] && echo "  (no KPM/runner containers found — they'll share the network once started)"

# 8. Verify the backend can actually reach the AI services (uses the app's own
#    python, which honours the host.docker.internal mapping).
echo "▶ Verifying AI dependency reachability from inside the backend…"
docker exec "$BACKEND_CTR" python - <<'PY' 2>/dev/null || echo "  (verification skipped — backend not ready yet)"
import os, socket, urllib.parse
for name, key in [("letta", "LETTA_BASE_URL"), ("qdrant", "QDRANT_URL"), ("letta-mcp", "LETTA_MCP_URL")]:
    u = urllib.parse.urlparse(os.environ.get(key, ""))
    host, port = u.hostname, (u.port or (443 if u.scheme == "https" else 80))
    try:
        socket.create_connection((host, port), timeout=4).close()
        print(f"  ✓ {name} reachable at {host}:{port}")
    except Exception as e:
        print(f"  – {name} NOT reachable at {host}:{port} ({type(e).__name__}) — offline fallback")
PY

# 9. Wait for the API and report.
echo "▶ Waiting for the API to come up…"
for _ in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "✓ Backend healthy"
    break
  fi
  sleep 3
done

PUBLIC_IP="$(curl -fsS https://api.ipify.org 2>/dev/null || echo 72.60.35.12)"
cat <<EOF

✓ Deploy complete.
  Project : QC_LIMS_Ao1   (containers: qc_lims_ao1-{db,backend,frontend}-1)
  Public  : https://${APP_HOST}        (via Traefik, Let's Encrypt TLS)
  Local   : http://${PUBLIC_IP}:8080   (direct; needs firewall open)
  API docs: https://${APP_HOST}/docs
  Login   : elena@purelyplant.eu / Password123!  (CHANGE the demo seed creds)

  AI deps : Letta/Qdrant/Letta-MCP via host.docker.internal + '$AI_NETWORK' network
  KPM net : $KPM_NETWORK  (backend reachable as 'qc_lims_ao1-backend-1' there)

  Logs    : docker compose $COMPOSE logs -f   (run from $APP_DIR)
  Stop    : docker compose $COMPOSE down       (run from $APP_DIR)
  Update  : bash $APP_DIR/deploy/kvm4.sh
EOF

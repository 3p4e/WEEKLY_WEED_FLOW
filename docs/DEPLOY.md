# Deploying the WWF stack to KVM4

The stack is a single Docker Compose project named **`wwf`** (containers
`wwf-web`, `wwf-gateway`). It hosts the task‑tracker and connects the gateway to
the **Letta stateful agents + their database** on KVM4.

## Live infrastructure (inventory)

| Resource | Detail |
|---|---|
| VPS | Hostinger **KVM 4**, `crimson.blaze`, **72.60.35.12** (`srv1231216.hstgr.cloud`) |
| Host OS | Ubuntu 24.04, template **"Docker + Traefik"** (Traefik already provides routing + Let's Encrypt) |
| Resources | 4 vCPU · 16 GB RAM · 200 GB disk |
| Agents | **Letta** on KVM4 — 53 agents incl. the WWF group: `wwf_weekly_coordinator`, `wwf_schema_advisor`, `wwf_qms_architect`, and the `planner-*` set (`task-rewrite`, `weekly-report`, `next-week-plan`, `executive-analytics`) |
| Store | The **Letta database** (Postgres + pgvector) backing those agents — the task‑capture store |

## Why deployment runs from CI, not from the Claude sandbox

The Claude Code execution environment only permits **outbound HTTPS through its
proxy** — port 22 is blocked (verified: `443 OPEN`, `22 blocked`). So this
container cannot `ssh`/`docker` into KVM4 directly. GitHub‑hosted Actions runners
have full network access and **can** reach KVM4, so deployment is wired through
[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

## Option A — Deploy via GitHub Actions (recommended)

1. Add repository **secrets**:
   - `KVM4_HOST` = `72.60.35.12`
   - `KVM4_USER` = `root`
   - `KVM4_SSH_KEY` = a private deploy key (its public half in the VPS `~/.ssh/authorized_keys`)
2. One‑time on the server: `mkdir -p /opt/wwf` and create `/opt/wwf/.env` from
   [`.env.example`](../.env.example) with real values (Letta URL/key, etc.).
3. Push to `main` (or run the workflow manually). It rsyncs the repo to
   `/opt/wwf` (preserving `.env`) and runs `docker compose up -d --build`.

## Option B — Deploy directly on KVM4

```bash
ssh root@72.60.35.12
mkdir -p /opt/wwf && cd /opt/wwf
git clone <this-repo> . # or rsync the working tree
cp .env.example .env && $EDITOR .env   # fill in Letta + Qdrant + JWT values
docker compose up -d --build
docker compose ps
```

## Routing (Traefik)

The KVM4 template runs Traefik. To serve `wwf-web` on your domain with auto‑TLS,
attach the `web` service to Traefik's external network and set `APP_HOST`,
`TRAEFIK_NETWORK`, and `TRAEFIK_CERTRESOLVER` in `.env` (Traefik labels are
already on the service). Without Traefik, the stack still works on the published
host ports `WEB_PORT` (8080) and `GATEWAY_PORT` (8000).

## Connecting the gateway to Letta

Set `LETTA_BASE_URL` (and `LETTA_API_KEY`/`LETTA_TOKEN` if required) in `.env`.
If Letta runs on the same host with its port published, the provided
`host.docker.internal:8283` default works (the gateway has the `host-gateway`
mapping); otherwise point it at the Letta URL. In the app's **Settings → AI
backend**, set the URL to the deployed site (nginx proxies `/ai`, `/agents`,
`/health` to the gateway, so it's same‑origin).

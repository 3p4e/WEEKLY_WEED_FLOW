# GrowFlow AI Gateway → Letta stateful agents

A small **FastAPI** service that connects the GrowFlow task‑manager front‑end to
**Letta stateful agents** running in Docker (e.g. on the **KVM4** cloud server).

```
 Browser (GrowFlow app) ──HTTPS──▶ FastAPI gateway ──REST──▶ Letta server
     web/gf/ai.js                  main.py (Docker, KVM4)        :8283
                                   letta_service.py
```

Each GrowFlow user is mapped to **their own persistent Letta agent**
(`growflow-<userId>`), so the agent remembers that person's department,
recurring blockers and weekly context across sessions.

## Endpoints (task‑tracking only)

| Method | Path                  | Purpose                                              |
|--------|-----------------------|-----------------------------------------------------|
| GET    | `/health`             | Gateway + Letta connectivity check                  |
| POST   | `/ai/paraphrase`      | Clean a dictated note into one professional sentence |
| POST   | `/ai/parse-voice`     | Turn a spoken sentence into a structured task (JSON) |
| POST   | `/ai/weekly-summary`  | Status report (this week) / planning analysis (next) |
| POST   | `/ai/chat`            | Free‑form chat with the user's stateful agent        |
| POST   | `/agents/reset`       | Drop the cached agent mapping for a user             |

> The QC‑laboratory endpoints (`/ai/lab-search`, `/ai/anomaly-check`) from the
> original combined design are intentionally **not** part of this task‑tracking
> build.

All POST bodies include a `user` object (`{ id, name, role, department, lang }`);
`user.id` is the stable key that selects the Letta agent.

## Run locally (dev)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # point LETTA_BASE_URL at your Letta server
export $(grep -v '^#' .env | xargs)
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Visit `http://localhost:8080/docs` for the interactive API.

## Run with Docker (alongside Letta on KVM4)

`docker-compose.yml` brings up both the Letta server and this gateway on a shared
network so the gateway can reach Letta at `http://letta:8283`:

```bash
cd backend
cp .env.example .env           # set provider keys for Letta below
docker compose up -d
```

Letta needs at least one model‑provider key (e.g. `OPENAI_API_KEY`) so
`LETTA_MODEL` / `LETTA_EMBEDDING` resolve. See <https://docs.letta.com> for
self‑hosting and provider configuration.

## Point the app at the gateway

In the GrowFlow app open **Settings → AI backend** and set the gateway URL
(e.g. `https://ai.yourdomain.com` or `http://KVM4-HOST:8080`). The app stores it
locally and routes paraphrase / voice‑parse / summary / chat calls here. If the
gateway is unreachable, the app falls back to its built‑in in‑browser model so
the demo keeps working.

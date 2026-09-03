# Bridge — agents, terminals and threads in one switch

A self-hosted workspace with one switch in the title bar. Flip it and the whole
app changes with it: the rail, the stage, the composer.

| Mode | Rail | Stage | Composer |
| --- | --- | --- | --- |
| **Agent** — teammates on routines | your named agents, next run, live state | the selected agent: runs, output, review | name · brief · folder · permission · routine (cron) |
| **Code** — your terminals, your folders | folders you work in, live shells | a grid of PTY panes, a dock (browser or thread) beside them, the full workspace one fold down | a command line to the focused pane |
| **Chat** — a conversation, not a repo | threads | messages | text · file drop · engine · key · model |

Under the switch sits the original multi-agent workspace, in the spirit of
BridgeMind's *BridgeSpace*: parallel CLI coding agents (Claude Code, Codex CLI,
Gemini CLI, OpenCode, Aider) in a browser grid, each in its own git worktree,
paid for by **your vendor subscription** or by **API keys you bring**.

## Agent — teammates on routines

Name an agent, give it a brief, put it on a routine. Each run launches the
agent CLI **headlessly** (Claude Code `-p`, Codex `exec`, Gemini `-p`, OpenCode
`run`, Aider `--message`) in the folder you chose, at the permission level you
chose (`plan` read-only · `edit` may change files · `full` may run anything),
optionally in a fresh git worktree. Output is captured and kept; runs are listed
with status, duration and a review flag, so the work runs on a schedule and you
review the result. Routines are 5-field cron in the server's local time, with
presets (`@hourly`, `@daily`, `@weekdays`, `@weekly`).

## Code — your terminals, your folders

Live shells over the folders you already work in, up to 16 PTY panes (grid,
columns or focus), each survives a reload. Beside them a **dock**: a browser
(an iframe on the dev server your agent just started) or a sandboxed thread.
**The full workspace is one fold down**: tasks, swarm launch, worktrees, keys and
the installed-CLI list.

## Chat — a conversation, not a repo

Threads not tied to a project. Drop a file, ask a question, keep the thread.
Two engines, both sandboxed so the engine cannot pretend it is inside your
codebase: **Anthropic API** with a vault key (no tools offered; images, PDFs and
text files go in as content blocks), or the **Claude CLI** run in an empty
per-thread directory with every tool disallowed (rides your subscription login;
text attachments only).

## The workspace under the switch

| Capability | How |
| --- | --- |
| **Many agents, one screen** | Up to 16 PTY sessions (configurable) rendered with xterm.js in an auto grid, columns, or single-pane focus. Panes survive reloads: scrollback is kept server-side and re-attached. |
| **Same task, several agents** | Each launch on a task gets its **own git worktree and branch** (`bridge/<task>-<agent>-<id>`) under `<repo>/.bridge/worktrees/`, so agents never overwrite each other. A **shared notes file** (`<repo>/.bridge/tasks/<id>.md`) is named in every agent's opening prompt so they coordinate (plan → progress → review). |
| **Swarm** | One click launches an architect, an implementer and a reviewer on a task, each with a role prompt and its own worktree. |
| **Separate tasks in parallel** | A kanban board (backlog / in progress / review / done). Launch any number of agents on any number of tasks; the board shows which sessions are alive. |
| **Bring your own keys** | Vault of outside API keys, AES‑256‑GCM encrypted at rest under a master key. The browser only ever sees a masked tail; a key is decrypted solely to inject into the environment of the agent process you launch with it. |
| **Use your subscriptions** | *Subscription* mode strips the vendor's key variable from the agent's environment so the CLI falls back to its own login — Claude Pro/Max in `claude`, ChatGPT Plus/Pro in `codex`, Google account in `gemini`. Log in once inside a pane; the CLI stores it. |
| **Bring outside models** | OpenCode with an `OPENROUTER_API_KEY` (or Anthropic/OpenAI keys) covers any OpenRouter model. Aider likewise. |
| **Locked down** | Bearer token on every HTTP and WebSocket request, loopback bind by default, workspace secrets never reach agent shells. It hands out shells — treat it like SSH. |

Not included, on purpose: a free‑form drag canvas, voice dictation, an MCP
server for cross‑IDE memory.

## Run

Requirements: Node ≥ 20, git, a C++ toolchain (node-pty builds a native module),
and whichever agent CLIs you want on `PATH`.

```bash
cd bridge
npm install            # also copies xterm.js into public/vendor
npm start              # prints http://127.0.0.1:7788/?token=…
```

Open the printed URL once; the token is remembered in the browser. `Alt+1/2/3`
switches Agent / Code / Chat. In Code mode:

1. **Keys** tab → store `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` as needed — or skip this and use subscription mode.
2. **Tasks** tab → *New task* with a title, description and the **repository path on this host**.
3. On the task card: **+ Agent** (pick agent, auth mode, role, isolation) or **Swarm**.
4. Each agent appears in a pane already seeded with the task, its role, its branch and the shared notes path. Type to it as you would in a terminal.
5. When the work is good, merge the `bridge/…` branch like any other branch and delete the worktree (`git worktree remove`).

Keyboard: `Alt+1/2/3` mode · `Alt+N` new shell · `Alt+L` cycle layout · `Ctrl/⌘+1…9` focus pane.

### Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `BRIDGE_HOST` / `BRIDGE_PORT` | `127.0.0.1` / `7788` | Bind address. Only bind beyond loopback behind TLS. |
| `BRIDGE_TOKEN` | generated → `data/token` | Bearer token. |
| `BRIDGE_MASTER_KEY` | generated → `data/master.key` | 32‑byte hex key for the vault. Losing it loses the stored keys. |
| `BRIDGE_DATA_DIR` | `./data` | Tasks, layout, encrypted credentials (JSON files, 0600). |
| `BRIDGE_PROJECTS_ROOT` | `~/projects` | Default working directory for new panes/tasks. |
| `BRIDGE_MAX_SESSIONS` | `16` | Concurrent PTY limit. |
| `BRIDGE_SCROLLBACK_BYTES` | `262144` | Server-side scrollback per session. |
| `BRIDGE_SHELL` | `$SHELL` or `/bin/bash` | Shell for plain panes. |

### Docker

```bash
docker build -t bridge ./bridge
docker run -d --name bridge -p 127.0.0.1:7788:7788 \
  -v bridge_data:/data -v bridge_home:/home/bridge -v $PWD:/projects bridge
docker logs bridge | grep token=
```

The image carries `claude`, `codex`, `gemini` and `opencode`. Vendor logins
persist in the `/home/bridge` volume.

## API (all under the bearer token)

```
GET    /api/status                      providers detected, limits, roles
GET    /api/credentials                 masked list      POST /api/credentials {name, envVar, value}
DELETE /api/credentials/:id
GET    /api/tasks                       POST /api/tasks {title, description, repoPath, baseRef}
PATCH  /api/tasks/:id                   DELETE /api/tasks/:id[?worktrees=1]
POST   /api/tasks/:id/launch            {providerId, authMode, credentialId, role, isolation}
POST   /api/tasks/:id/swarm             {providerId, authMode, credentialId, isolation} | {plan:[…]}
GET    /api/tasks/:id/worktrees
GET    /api/sessions                    POST /api/sessions {providerId, cwd, authMode, credentialId, prompt}
POST   /api/sessions/:id/input {data}   POST /api/sessions/:id/kill {signal}   DELETE /api/sessions/:id
GET    /api/agents                      POST /api/agents {name, brief, providerId, authMode, credentialId, cwd, isolation, permission, cron, enabled}
PATCH  /api/agents/:id                  DELETE /api/agents/:id      POST /api/agents/:id/run      GET /api/agents/:id/runs
GET    /api/runs/:id (with output)      PATCH /api/runs/:id {reviewed}      POST /api/runs/:id/cancel      POST /api/cron/preview {cron}
GET    /api/chat/threads                POST /api/chat/threads {engine, model, credentialId, context}
GET/PATCH/DELETE /api/chat/threads/:id  POST /api/chat/threads/:id/messages {text, attachments:[{name,type,data}]}
GET/PUT /api/layout
WS     /ws/term/:id?token=…             raw terminal I/O; JSON {type:"input"|"resize"}
WS     /ws/events?token=…               session/task change stream
```

## Tests

```bash
npm test     # node:test — vault, providers, worktrees, tasks + live PTY sessions, cron, agents + runs, chat (fake claude)
```

## Honest limits

- **Subscriptions are per host and per person.** The vendors' consumer plans are
  licensed to one human; this workspace runs the vendor CLI under that login and
  does nothing to share or proxy it. A team needs API keys (or a team plan).
- **Agents in one repo compete for CPU, RAM and rate limits.** Sixteen Claude
  Code sessions on one 4‑core box is a queue, not parallelism.
- **Worktrees are not merges.** Two agents on one task produce two branches; the
  reconciliation is yours (or a reviewer agent's) to do.
- **The notes file is advisory.** Agents are told to read/append it; nothing
  forces them to. Treat it as a shared scratchpad, not a lock.
- Single operator, JSON store, no multi-user auth. Adding users means adding a
  real auth layer and per-user vaults first.

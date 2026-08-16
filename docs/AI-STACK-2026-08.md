# KVM4 AI stack — 2026-08-16 session

Groundwork for the next-generation AI layer: Letta backup, the letta-code
deployment fix, Ollama local-model runtime, and the research that picked the
RAG stack. RAGflow/LiteLLM deployment itself is a later session.

## 1. The 62-agent Letta instance finally has a backup

`letta-postgres` (DB `letta`, 761 MB — 62 agents, 9 RAG sources, three production
dependents) had **no backup** since 2026-07-16, and the same day's code-server
volume deletion (75 GB, see below) proved how fast a volume can vanish.

| Artifact | Size | Verify |
|---|---|---|
| `/opt/backups/letta/letta-db-20260816.dump` (`pg_dump -Fc`) | 301 MB | `pg_restore --list` → 361 objects; sha256 `8f2e7b59…c79f15` |
| `/opt/backups/letta/letta-app-data-20260816.tgz` (volume `letta_letta_data`) | 88 MB | `tar -tzf` → 4,587 files; sha256 `d5a87ec7…baca77` |

Offsite: both copied to `wwf-crypt:letta-backups/20260816` and verified byte-exact
with `rclone lsl`. Note: `wwf-gdrive` still uses rclone's shared Google client_id,
which Google retires during 2026 — create a dedicated client_id before it breaks.

## 2. code-server volume is gone (owner deletion, 2026-08-16)

The owner deleted the `visual-studio-code-server-7gqe` container and its
**72.63 GB** volume (mount has `discard` → unrecoverable). Lost with it: `fal-gen`
(uncommitted), untracked workspace dirs, ~40 MB chat history of 9 other projects,
`rclone.conf`/service-account JSONs/MCP configs/`/config/bin` scripts, drive-diff
lists. Survived: **Zelena Imperija** (rescued to GitHub `3p4e/zelena_imperija` the
day before), the RAG corpus at `/opt/data` (1.2 GB), all production stacks, all
Letta DBs. Side effect: the dangerous bidirectional `rclone bisync` cron died with
the container — that risk is permanently closed. `/opt` free went 36 → 115 GB
(41% used).

## 3. letta-code (`letta-6ou3`) runs a dead image — one-click fix pending

The Hostinger catalog's Letta template deploys **`lettaai/letta:latest`, built
2024-10-29** — the abandoned image name, ~19 months older than the production
`letta` container's `letta/letta:latest` (2026-05-14). The current image is
already pulled onto the box (digest `aa66c3ee…`).

**Owner action (panel one-click, DB is still empty so it is risk-free):** edit the
`letta-6ou3` stack, change `image: lettaai/letta:latest` →
`image: letta/letta:latest`, redeploy. While in there, add env
`OLLAMA_BASE_URL=http://ollama-bm3e-ollama-1:11434` so Letta natively sees every
local model (the containers already share the `ai-net` network). The agent's
session classifier blocks compose-file edits on the host, so this stays manual.

## 4. Ollama runtime

`ollama-bm3e-ollama-1` (Hostinger stack, port 32775→11434). No GPU → CPU inference
is automatic. Applied via `docker update` (mirror into the stack's compose to
survive recreation): **3 CPUs, 10 GB memory cap** — a model load can never starve
the 32 production containers. Network: new **`ai-net`** bridge connects ollama +
letta-6ou3 (LiteLLM/RAGflow join later). No swap on the host by design — swap
makes inference thrash; the 16 GB ceiling is managed by model choice
(practical comfort limit ≈ 8–9B params at Q4; 12B only with nothing else loaded).
Model library budget: 60 GB of the 115 GB free.

Recommended (panel) env for the stack: `OLLAMA_MAX_LOADED_MODELS=1`,
`OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=10m`.

### Model inventory (9 pulls, ~32 GB)

| Model | Role |
|---|---|
| `qwen2.5-coder:7b` | Primary coder + function calling (20.4M pulls) |
| `granite4.1:8b` | Enterprise tools+code (current IBM line) |
| `qwen3:8b` | General + tools + reasoning |
| `phi4-mini` | Fast always-on small model, tools |
| `dolphin3:8b` | Uncensored, explicit function calling, codes |
| `hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-abliterated-GGUF:Q4_K_M` | Uncensored coder |
| `hf.co/huihui-ai/Huihui-gemma-4-E4B-it-qat-q4_0-unquantized-abliterated-GGUF` | Gemma4 uncensored (E4B efficient — fits the box) |
| `bge-m3` | Embeddings, multilingual (Macedonian-capable) |
| `qwen3-embedding:0.6b` | Embeddings, small/fast |

**HF pattern:** Ollama pulls HuggingFace GGUFs directly —
`ollama pull hf.co/<user>/<repo>:<quant>` — and everything speaking the Ollama API
(Letta, Agent Zero, Big-AGI) can use them immediately. Caveat: hf.co pulls don't
always carry a correct chat/tool template; smoke-test before relying on tools.

**Smoke-test results (2026-08-16):** all 9 pulled OK (35.4 GB). Generation
verified through LiteLLM → Ollama (`local-small`/phi4-mini returned an exact
requested string). Tool-calling: `qwen2.5-coder:7b` ✅ produced the correct
structured `get_batch_potency(batch_id=P160012)` call. **`dolphin3:8b` ❌ — its
Ollama chat template does not support tools** (registry error "does not support
tools"); use it for uncensored chat/code *generation* only, and use
`qwen2.5-coder` (or a custom Modelfile with a tool template) for agentic work.
The hf.co abliterated pulls carry the same template caveat — test before agent use.
Ceiling options researched but not pulled: `huihui_ai/gemma-4-abliterated:12b`,
`hf.co/mradermacher/Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated-GGUF`
(the gemma4 **coder** abliterated), `Qwen2.5-Coder-14B-abliterated`.

## 5. Chosen RAG direction (deployment later)

**RAGflow** (DeepDoc: OCR + layout + table-structure → CoA rows survive; hybrid
BM25+vector; per-page citations; **native VoyageAI** embeddings/rerank) +
**LiteLLM** as the single OpenAI-compatible gateway (DeepSeek, Kimi/Moonshot,
Ollama, Voyage behind one endpoint + virtual keys/spend logs) + **Postgres** for
extracted CoA numbers (SQL answers numeric questions, never retrieval) + a
**read-only MCP** in front for Letta/apps — write credential held only by the
ingestion job ("cannot poison the memory" enforced at the credential layer).
First validation: one scanned bilingual SOP + one ImB CoA from `/opt/data`
through DeepDoc to test **Macedonian Cyrillic** OCR; fallback is Tesseract
`mkd+eng` via a pre-processing stage.

Old `letta` production stack: untouched, still the only live copy of the 62
agents until migration to the fixed letta-6ou3.

## 6. Deployed this session: LiteLLM + RAGflow (2026-08-16, same day)

**LiteLLM** — `/opt/stacks/litellm`, container `litellm` on `ai-net`, 1 CPU/1 GB.
Master key generated (0600 `.env`); OpenAI+Anthropic keys staged from the
letta-6ou3 stack env (values never displayed); `VOYAGE_API_KEY`,
`DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY` are **empty placeholders — owner fills
them in `/opt/stacks/litellm/.env` and `docker restart litellm`**. Routes:
`openai/*`, `anthropic/*`, `deepseek/*`, `moonshot/*`, `voyage/*`, plus local
`local-coder|general|uncensored|small|embed` → Ollama. Verified: liveliness 200,
chat round-trip via gateway → phi4-mini exact-string reply.

**RAGflow v0.26.4** — `/opt/stacks/ragflow`, official docker dir at the pinned
tag, dedicated 6-container stack (`ragflow-cpu`, `es01` ES 8.11.3, MySQL 8,
valkey Redis, MinIO) with its own volumes/network and generated 0600 secrets.
Adaptations from stock: `MEM_LIMIT` 8 GB→2 GB per service, web ports 80/443 →
**8090/8493** (Traefik owns 80/443), `docker-compose.override.yml` adds `ai-net`
+ Traefik labels. Gotcha for operators: `.env` sets
`COMPOSE_PROFILES=elasticsearch,cpu` — run plain `docker compose up -d`; an
explicit `--profile cpu` overrides the list and silently drops ES.
Verified: all 6 healthy, ES cluster **green**, HTTP 200 on :8090 and on
**https://ragflow.srv1231216.hstgr.cloud** (LetsEncrypt via existing Traefik).
Post-deploy owner steps: create the admin account on first visit; add the
Voyage key under Model providers (embeddings + rerank); per owner decision
RAGflow starts on **cloud models, not Ollama**.

Host after everything: MemAvailable ≈ 3 GB idle with the full RAGflow stack up —
as predicted, heavy ingestion and large local-model inference should not run
simultaneously. Disk: 63 GB free after all images/models.

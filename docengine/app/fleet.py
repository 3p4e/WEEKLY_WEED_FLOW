# docengine.app.fleet — ensure-loop for the gf_* agent fleet.
#
# Declarative (agents/fleet.yaml) -> live Letta agents, ADDITIVELY:
#   * create-by-name if missing (never edit an existing agent — the server
#     rejects config writes for the legacy provider enum anyway);
#   * attach the shared ragflow_search tool and pass it RAGflow credentials;
#   * seed `gf_house_rules` + `ragflow_scope` core memory blocks.
# The declared model/embedding handles win whenever the server actually serves
# them; only an unserved handle falls back to adopting one a live agent already
# uses (the handover documented that invented handles are rejected).
#
# RETRIEVAL LIVES IN RAGFLOW. Letta sources are not used at all: the fleet
# reaches the corpora through one registered tool, scoped per agent by dataset
# name. That keeps a single RAG (no second copy of the corpus to re-embed and
# keep in sync) and makes the stability/release boundary a data boundary — an
# agent granted only release datasets cannot name a stability dataset.
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .config import settings
from .letta import LettaClient, LettaError

log = logging.getLogger("docengine.fleet")
AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
FLEET_FILE = AGENTS_DIR / "fleet.yaml"
TOOL_NAME = "ragflow_search"
TOOL_FILE = AGENTS_DIR / f"{TOOL_NAME}.py"
SCOPE_BLOCK = "ragflow_scope"


# fleet.yaml is static for the life of the process (it's a declarative spec,
# not runtime state), but load_fleet() is called synchronously — no
# asyncio.to_thread — from spawn_ephemeral() (~a dozen times per single
# document job: once per section in the regulatory-check loop, plus per
# repair round) and agent_datasets(). Re-reading + re-parsing the YAML on
# every one of those calls blocks the event loop each time, briefly stalling
# every other coroutine on that worker (including /health and other jobs'
# polls) — the same defect class as H14 elsewhere in this codebase, recurring
# here at smaller scale but higher frequency. Memoize instead of wrapping
# every call in asyncio.to_thread: the data never changes, so caching removes
# the repeated parse work entirely rather than merely moving it off-thread.
_FLEET_SPEC: dict | None = None


def load_fleet() -> dict:
    global _FLEET_SPEC
    if _FLEET_SPEC is None:
        _FLEET_SPEC = yaml.safe_load(FLEET_FILE.read_text(encoding="utf-8"))
    return _FLEET_SPEC


def load_tool_source() -> str:
    """The tool's source, read by path exactly like fleet.yaml. Not imported:
    `agents/` is not a package (and would be above this one anyway), and Letta
    wants the text, so reading the file is both simpler and honest about what
    gets uploaded — what is committed is what runs in the sandbox."""
    return TOOL_FILE.read_text(encoding="utf-8")


def _scope_block(datasets: list[str], pending: list[str]) -> str:
    """The agent's own statement of what it may retrieve. Written into memory so
    the model can see its limits rather than having to be told each turn."""
    if not datasets:
        return (
            "RETRIEVAL: you have no document corpus. Do not call ragflow_search; "
            "work only from what the caller gives you."
        )
    lines = [
        "RETRIEVAL: use the ragflow_search tool. Search ONLY these RAGflow datasets:",
        "  " + ", ".join(datasets),
        "Never name a dataset outside that list. Stability-study data is held in a",
        "separate dataset you are not granted — never present a stability result as a",
        "release value. Cite the document name returned with each passage, and if a",
        "search returns nothing say so rather than filling the gap from memory.",
    ]
    waiting = [d for d in datasets if d in pending]
    if waiting:
        lines += [
            "",
            "NOT YET INGESTED (" + ", ".join(waiting) + "): ragflow_search will report",
            "these as unknown_datasets. Until they exist you are drafting WITHOUT corpus",
            "grounding — say so in your output instead of inventing citations.",
        ]
    return "\n".join(lines)


async def ensure_tool(client: LettaClient, spec: dict | None = None) -> str | None:
    """Register ragflow_search once, or adopt the existing one. Returns its id."""
    for t in await client.list_tools():
        if t.get("name") == TOOL_NAME:
            return t.get("id")
    spec = spec or load_fleet()
    description = (spec.get("ragflow") or {}).get("tool_description", "")
    try:
        created = await client.create_tool(load_tool_source(), description)
        log.info("registered tool %s -> %s", TOOL_NAME, created.get("id"))
        return created.get("id")
    except LettaError as e:  # non-fatal: agents still exist, retrieval degraded
        log.warning("could not register %s: %s", TOOL_NAME, e)
        return None


def _tool_env() -> dict:
    """RAGflow credentials for the tool sandbox. Empty if unconfigured — the
    tool then returns a clear 'not set' error instead of silently answering
    from the model's own memory."""
    if not (settings.ragflow_base and settings.ragflow_key):
        log.warning("RAGFLOW_BASE_URL / RAGFLOW_API_KEY unset — %s will not retrieve", TOOL_NAME)
        return {}
    return {
        "RAGFLOW_BASE_URL": settings.ragflow_base,
        "RAGFLOW_API_KEY": settings.ragflow_key,
    }


def agent_datasets(agent_name: str, spec: dict | None = None) -> list[str]:
    """The RAGflow datasets an agent is permitted to search, from fleet.yaml.
    Callers building prompts use this instead of a separate env var so the
    permitted scope has exactly one definition."""
    spec = spec or load_fleet()
    ag = next((a for a in spec["agents"] if a["name"] == agent_name), None)
    return list((ag or {}).get("datasets", []))


def _build_body(ag: dict, spec: dict, model: str, embedding: str, name: str, description: str) -> dict:
    house_rules = spec["house_rules"].strip()
    pending = (spec.get("ragflow") or {}).get("pending_ingest", [])
    body = {
        "name": name,
        "description": description,
        "model": model,
        "embedding": embedding,
        "memory_blocks": [
            {"label": "gf_house_rules", "value": house_rules},
            {"label": "persona", "value": ag["persona"].strip()},
            {"label": SCOPE_BLOCK, "value": _scope_block(ag.get("datasets", []), pending)},
        ],
    }
    # Letta sizes an unknown model from its DEFAULT (30000) and clamps output
    # to its own guess. Both are declared in fleet.yaml because the default
    # broke a real run — see the note there.
    defaults = spec.get("defaults") or {}
    if defaults.get("context_window"):
        body["context_window_limit"] = int(defaults["context_window"])
    if defaults.get("max_tokens"):
        body["max_tokens"] = int(defaults["max_tokens"])
    env = _tool_env()
    if env and ag.get("datasets"):
        body["tool_exec_environment_variables"] = env
    return body


async def _attach_retrieval(client: LettaClient, agent_id: str, ag: dict, tool_id: str | None, label: str) -> None:
    """Give the agent the retrieval tool. Only agents with a dataset scope get
    it — an agent with no corpus should not have a search button at all."""
    if not tool_id or not ag.get("datasets"):
        return
    try:
        await client.attach_tool(agent_id, tool_id)
    except LettaError as e:  # non-fatal: agent works, retrieval degraded
        log.warning("attach %s -> %s failed: %s", TOOL_NAME, label, e)


async def _reconcile_scope(
    client: LettaClient, agent_id: str, ag: dict, spec: dict, label: str
) -> None:
    """Bring a live agent's ragflow_scope block back in line with fleet.yaml."""
    pending = (spec.get("ragflow") or {}).get("pending_ingest", [])
    want = _scope_block(ag.get("datasets", []), pending)
    try:
        block = await client.get_block(agent_id, SCOPE_BLOCK)
        if block is None:
            log.warning("%s has no %s block to reconcile", label, SCOPE_BLOCK)
            return
        if (block.get("value") or "").strip() == want.strip():
            return
        await client.update_block(agent_id, SCOPE_BLOCK, want)
        log.info("updated %s on %s", SCOPE_BLOCK, label)
    except LettaError as e:  # non-fatal: stale scope is better than a dead ensure
        log.warning("could not reconcile %s on %s: %s", SCOPE_BLOCK, label, e)


async def _served_handles(client: LettaClient) -> tuple[set[str] | None, set[str] | None]:
    """What the server currently offers. None on failure, which makes
    _resolve_model fall back to its old adopt-from-live-agent behaviour rather
    than refusing to work because a listing call failed."""
    try:
        llm = {m.get("handle") for m in await client.list_models() if m.get("handle")}
        emb = {m.get("handle") for m in await client.list_embedding_models() if m.get("handle")}
        return llm or None, emb or None
    except LettaError as e:
        log.warning("could not list served handles (%s); falling back to adoption", e)
        return None, None


def _resolve_model(
    spec: dict,
    existing: list[dict],
    served: set[str] | None = None,
    served_embeddings: set[str] | None = None,
) -> tuple[str, str]:
    """Pick a model/embedding handle the server will actually accept.

    The declared handle in fleet.yaml WINS whenever the server serves it. Only
    if it does not (an invented or retired handle — the failure the handover
    warned about) do we fall back to adopting a handle some existing agent
    already uses, which is proof the server takes it.

    The order matters. Adopting first, unconditionally, meant live state
    silently overrode the declaration: with the fleet already created on one
    provider, editing fleet.yaml could never move it to another, because the
    old handle kept winning. That made the declarative file a lie for the one
    setting most likely to change — which provider is currently funded."""
    model = spec["defaults"]["model"]
    embedding = spec["defaults"]["embedding"]
    if served is not None and model in served:
        emb_ok = served_embeddings is None or embedding in served_embeddings
        if emb_ok:
            return model, embedding
        log.warning("declared embedding %s is not served; adopting from a live agent", embedding)
    elif served is not None:
        log.warning("declared model %s is not served; adopting from a live agent", model)
    for a in existing:
        lc = a.get("llm_config") or {}
        if lc.get("handle") or lc.get("model"):
            model = lc.get("handle") or lc.get("model")
            ec = a.get("embedding_config") or {}
            cand = ec.get("handle") or ec.get("embedding_model") or ""
            # Adopt only a real provider/model handle. Agents imported or
            # mirrored from another instance carry a bare embedding model name
            # ("text-embedding-3-small"), which POST /agents rejects as an
            # embedding handle — a bare name must not displace the YAML default.
            if "/" in cand:
                embedding = cand
            break
    return model, embedding


async def ensure_fleet(client: LettaClient | None = None) -> dict:
    """Idempotent. Returns {agent_name: agent_id} for the whole gf_ fleet."""
    client = client or LettaClient()
    spec = load_fleet()
    existing = {a.get("name"): a for a in await client.list_agents()}
    served, served_emb = await _served_handles(client)
    model, embedding = _resolve_model(spec, list(existing.values()), served, served_emb)
    tool_id = await ensure_tool(client, spec)

    out: dict[str, str] = {}
    for ag in spec["agents"]:
        name = ag["name"]
        cur = existing.get(name)
        if cur:
            out[name] = cur["id"]
            # Reconcile an agent that already exists. Create-if-missing alone
            # cannot, because the agent is no longer missing — and two things
            # legitimately change under it:
            #
            #  * the tool. Registration is non-fatal, so the fleet can come up
            #    with agents but no tool (seen live: Letta rejected the source
            #    over a nested helper, all 8 agents were created anyway, and the
            #    fleet ran with no retrieval at all).
            #  * its dataset scope. `datasets:` in fleet.yaml is what governs
            #    which corpora the agent may reach, so an edit there that never
            #    reaches the live ragflow_scope block leaves the declaration and
            #    the agent's actual instructions disagreeing about data access.
            #
            # Both are bounded: gf_* only, the one block this module owns, and
            # only when the value actually differs.
            if TOOL_NAME not in {t.get("name") for t in (cur.get("tools") or [])}:
                await _attach_retrieval(client, cur["id"], ag, tool_id, name)
            await _reconcile_scope(client, cur["id"], ag, spec, name)
            continue
        body = _build_body(ag, spec, model, embedding, name, ag.get("description", ""))
        created = await client.create_agent(body)
        out[name] = created["id"]
        log.info("created agent %s -> %s", name, created["id"])
        await _attach_retrieval(client, created["id"], ag, tool_id, name)
    return out


async def spawn_ephemeral(client: LettaClient, agent_name: str, name_suffix: str) -> str:
    """Create a short-lived clone of a fleet agent (same persona/datasets/
    model) for exactly ONE isolated exchange, then the caller deletes it.

    Exists because a persistent Letta agent accumulates every past message
    into the prompt sent on each new turn — fine for a single Q&A agent, but
    fatal for a loop that sends N independent checks against the same agent
    (each turn's system-prompt token estimate keeps growing until it exceeds
    the model's context window; observed live at section 9 of 9 on a fresh
    gf_reg_checker). A fresh clone per exchange keeps that estimate constant
    regardless of how many checks the pipeline runs."""
    spec = load_fleet()
    ag = next(a for a in spec["agents"] if a["name"] == agent_name)
    existing = await client.list_agents()
    served, served_emb = await _served_handles(client)
    model, embedding = _resolve_model(spec, existing, served, served_emb)
    # The clone must run the SAME model as the agent it clones ("same persona/
    # datasets/model") — the global adoption above picks whatever agent happens
    # to list first, which on a mixed instance (fleet + mirrored planners) can
    # be a different provider whose tool-loop behavior differs from the base
    # agent's proven config.
    base = next((a for a in existing if a.get("name") == agent_name), None)
    if base:
        lc = base.get("llm_config") or {}
        if lc.get("handle") or lc.get("model"):
            model = lc.get("handle") or lc.get("model")
        cand = (base.get("embedding_config") or {}).get("handle") or ""
        if "/" in cand:
            embedding = cand

    body = _build_body(
        ag,
        spec,
        model,
        embedding,
        f"{agent_name}_tmp_{name_suffix}",
        f"ephemeral clone of {agent_name} for one isolated exchange",
    )
    tool_id = await ensure_tool(client, spec)
    created = await client.create_agent(body)
    await _attach_retrieval(client, created["id"], ag, tool_id, body["name"])
    return created["id"]

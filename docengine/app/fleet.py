# docengine.app.fleet — ensure-loop for the gf_* agent fleet.
#
# Declarative (agents/fleet.yaml) -> live Letta agents, ADDITIVELY:
#   * create-by-name if missing (never edit an existing agent — the server
#     rejects config writes for the legacy provider enum anyway);
#   * attach the shared ragflow_search tool and pass it RAGflow credentials;
#   * seed `gf_house_rules` + `ragflow_scope` core memory blocks.
# Model/embedding handles are taken from what the server actually serves
# (first existing agent's config wins over the YAML default), because the
# handover documented that invented handles are rejected.
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
FLEET_FILE = Path(__file__).resolve().parents[1] / "agents" / "fleet.yaml"
TOOL_NAME = "ragflow_search"


def load_fleet() -> dict:
    return yaml.safe_load(FLEET_FILE.read_text(encoding="utf-8"))


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


async def ensure_tool(client: LettaClient) -> str | None:
    """Register ragflow_search once, or adopt the existing one. Returns its id."""
    from ..agents.ragflow_tool import RAGFLOW_SEARCH_DESCRIPTION, RAGFLOW_SEARCH_SOURCE

    for t in await client.list_tools():
        if t.get("name") == TOOL_NAME:
            return t.get("id")
    try:
        created = await client.create_tool(
            RAGFLOW_SEARCH_SOURCE.strip(), RAGFLOW_SEARCH_DESCRIPTION
        )
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
            {"label": "ragflow_scope", "value": _scope_block(ag.get("datasets", []), pending)},
        ],
    }
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


def _resolve_model(spec: dict, existing: list[dict]) -> tuple[str, str]:
    """Adopt a model/embedding handle the server demonstrably accepts: prefer
    any existing agent's llm_config over the YAML default (invented handles
    are rejected by this server, per the handover)."""
    model = spec["defaults"]["model"]
    embedding = spec["defaults"]["embedding"]
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
    model, embedding = _resolve_model(spec, list(existing.values()))
    tool_id = await ensure_tool(client)

    out: dict[str, str] = {}
    for ag in spec["agents"]:
        name = ag["name"]
        if name in existing:
            out[name] = existing[name]["id"]
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
    model, embedding = _resolve_model(spec, existing)
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
    tool_id = await ensure_tool(client)
    created = await client.create_agent(body)
    await _attach_retrieval(client, created["id"], ag, tool_id, body["name"])
    return created["id"]

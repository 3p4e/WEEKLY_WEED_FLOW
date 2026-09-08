# docengine.app.fleet — ensure-loop for the gf_* agent fleet.
#
# Declarative (agents/fleet.yaml) -> live Letta agents, CONVERGENTLY:
#   * create-by-name if missing;
#   * on every run, bring an existing agent's blocks, tool, sandbox env and
#     sizing back to the declaration — and, since 2026-08-31, take them AWAY
#     again when the declaration no longer grants them. The loop used to be
#     additive only: it granted, widened and repaired, but never revoked, so
#     dropping `datasets:` from an agent left the tool attached and the tenant
#     key in its sandbox indefinitely. "Declared absent" now means absent.
#   * the model handle is the one field still create-time only (the server
#     rejects that config write); it is REPORTED as drift, never patched.
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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .config import settings
from .letta import LettaClient, LettaError
from .ragflow_api import RagflowUnreachable, list_dataset_names

log = logging.getLogger("docengine.fleet")
AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
FLEET_FILE = AGENTS_DIR / "fleet.yaml"
TOOL_NAME = "ragflow_search"
TOOL_FILE = AGENTS_DIR / f"{TOOL_NAME}.py"

# The core-memory blocks this module owns. `persona` is the agent's own block
# (Letta creates it with a stock description); the other four are governance and
# are created read_only, because every gf_ agent carries memory_replace /
# memory_insert and could otherwise rewrite its own house rules — or widen its
# own dataset scope, which is the guardrail keeping stability data out of
# release documents. read_only blocks the AGENT's memory tools, not this API.
PERSONA_BLOCK = "persona"
MISSION_BLOCK = "gf_mission"
RULES_BLOCK = "gf_house_rules"
CORPUS_BLOCK = "gf_corpus"
SCOPE_BLOCK = "ragflow_scope"
GOVERNANCE_BLOCKS = (MISSION_BLOCK, RULES_BLOCK, CORPUS_BLOCK, SCOPE_BLOCK)
# One limit for every block this module makes, whichever path makes it. The
# create-time and reconcile-time paths used to differ here (the former took
# Letta's default), which made _blocks_for's "byte-identical" claim untrue.
BLOCK_LIMIT = 100_000
# The three sandbox variables this module owns on an agent. Everything else in
# tool_exec_environment_variables belongs to someone else and is carried
# through a PATCH untouched.
OWNED_ENV = ("RAGFLOW_BASE_URL", "RAGFLOW_API_KEY", "RAGFLOW_ALLOWED_DATASETS")
# spawn_ephemeral's naming convention; the orphan sweep keys off it.
TMP_MARKER = "_tmp_"


@dataclass
class FleetReport:
    """What one ensure_fleet pass found and did. The reconcilers always knew
    this — each returned what it changed — and ensure_fleet threw it away, so
    there was no way, in code or over HTTP, to ask "does the live fleet agree
    with fleet.yaml?" for a system whose whole premise is that divergence is
    the enemy. Now it is kept, exposed by /fleet/status, and summarised on
    /health."""
    changed: dict[str, list[str]] = field(default_factory=dict)   # agent -> what
    drift: list[str] = field(default_factory=list)                 # seen, not fixed
    warnings: list[str] = field(default_factory=list)
    unknown_tools: dict[str, list[str]] = field(default_factory=dict)
    swept: list[str] = field(default_factory=list)                 # orphan _tmp_ agents
    datasets_live: set[str] | None = None                          # None = RAGflow unreachable
    datasets_unresolved: list[str] = field(default_factory=list)   # declared, not found
    created: list[str] = field(default_factory=list)

    def note(self, agent: str, what: str) -> None:
        self.changed.setdefault(agent, []).append(what)

    def summary(self) -> dict:
        return {
            "agents_changed": sorted(self.changed),
            "drift": self.drift,
            "warnings": self.warnings,
            "unknown_tools": self.unknown_tools,
            "swept_orphans": self.swept,
            "ragflow_reachable": self.datasets_live is not None,
            "datasets_unresolved": self.datasets_unresolved,
            "created": self.created,
            "converged": not (self.drift or self.warnings or self.unknown_tools
                              or self.datasets_unresolved),
        }


@dataclass
class FleetContext:
    """Everything one ensure_fleet pass resolved, so the same document job can
    spawn ephemeral clones without re-listing agents, models and tools per
    section (~54 wasted round-trips on a nine-section SOP before this)."""
    agents: dict[str, str]
    existing: list[dict]
    model: str
    embedding: str
    tool_id: str
    pending: list[str]
    report: FleetReport


LAST_REPORT: FleetReport | None = None


def last_report() -> FleetReport | None:
    return LAST_REPORT


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


def _scope_block(datasets: list[str], pending: list[str], verbatim_output: bool = False) -> str:
    """The agent's own statement of what it may retrieve. Written into memory so
    the model can see its limits rather than having to be told each turn."""
    if not datasets:
        return (
            "RETRIEVAL: you have no document corpus. Do not call ragflow_search; "
            "work only from what the caller gives you."
        )
    lines = [
        "RETRIEVAL: use the ragflow_search tool. Pass these dataset names, and only",
        "these, as its `datasets` argument:",
        "  " + ", ".join(datasets),
        "Never name a dataset outside that list, and never omit the argument — an",
        "omitted `datasets` searches everything the API key can reach, which is not",
        "your scope. Stability-study data is held in a separate dataset you are not",
        "granted; never present a stability result as a release value. Cite the",
        "document name returned with each passage, and if a search returns nothing",
        "say so rather than filling the gap from memory. gf_corpus describes what",
        "these datasets contain and how to search them well.",
    ]
    waiting = [d for d in datasets if d in pending]
    if waiting:
        live = [d for d in datasets if d not in pending]
        lines += [
            "",
            "NOT YET INGESTED (" + ", ".join(waiting) + "): ragflow_search will report",
            "these as unknown_datasets. They are not a corpus you have.",
        ]
        if live:
            lines += ["Only " + ", ".join(live) + " actually answers today."]
        elif verbatim_output:
            # This agent's reply IS document text. Telling it to "say so in your
            # output" would put a note about corpus availability inside a
            # controlled document — seen live in a direct probe, where a section
            # opened with a bilingual sentence explaining that the facility
            # corpus was not ingested. A blank field is the correct way for a
            # document to say a value is unknown.
            lines += [
                "That is EVERY dataset you were granted, so you have NO working corpus",
                "right now. Draft from the brief alone and leave every unknown facility",
                "specific as a BLANK write-in field. Do NOT write anything about corpora,",
                "retrieval or grounding into your reply: it is inserted verbatim into a",
                "controlled document, where such a note becomes document text. The blank",
                "IS the message.",
            ]
        else:
            lines += [
                "That is EVERY dataset you were granted, so you have NO working corpus",
                "right now. You are drafting without grounding — say so plainly in your",
                "output instead of inventing citations, and leave unknown values blank.",
            ]
    return "\n".join(lines)


async def ensure_tool(client: LettaClient, spec: dict | None = None) -> str:
    """Register ragflow_search, or bring the already-registered one up to date.

    "Adopt the existing one" alone was not enough. The tool is a shared server
    object, so once it existed nothing ever looked at it again — and the tool is
    where the dataset scoping is actually ENFORCED (it is the thing that refuses
    an unscoped search and decides what an error message discloses). An edit to
    the committed source that never reaches the server is a guardrail that
    exists only in the repository.

    Comparing source before writing keeps this idempotent: ensure_fleet runs on
    every document job, and rewriting an unchanged tool on each one would be
    pointless server churn.

    FAILS CLOSED. This used to return the tool's id even when the update that
    was meant to bring it to the committed source had just failed — so a failed
    hardening push did not degrade retrieval, it silently shipped whatever
    ragflow_search happened to be on the server and wired every agent to it
    with the tenant key in hand. The pre-hardening tool searched EVERYTHING when
    `datasets` was omitted; that is the state a swallowed failure rolled back
    to, with one warning line. For the object this module itself describes as
    where scoping is enforced, the only honest failure mode is to raise."""
    spec = spec or load_fleet()
    description = (spec.get("ragflow") or {}).get("tool_description", "")
    source = load_tool_source()
    for t in await client.list_tools():
        if t.get("name") != TOOL_NAME:
            continue
        tool_id = t.get("id")
        have = t.get("source_code")
        if have is None:
            # This server's /v1/tools listing does carry source_code (verified
            # live: 7,275 chars for this tool), so this is a latent case, not a
            # current one. But `(None or "").strip() != source.strip()` is
            # always true, so a Letta version that dropped the field would
            # rewrite the tool on EVERY document job — a silent write loop with
            # no symptom other than churn. Adopt without rewriting and say so,
            # so the failure mode is one log line instead.
            log.warning(
                "%s: this Letta's tool listing omits source_code — adopting %s "
                "without verifying it matches the committed source",
                TOOL_NAME,
                tool_id,
            )
            return tool_id
        if have.strip() == source.strip():
            return tool_id
        try:
            await client.update_tool(tool_id, source, description)
        except LettaError as e:
            log.error("could not bring %s (%s) to the committed source: %s", TOOL_NAME, tool_id, e)
            raise
        log.info("updated tool %s (%s) to the committed source", TOOL_NAME, tool_id)
        return tool_id
    try:
        created = await client.create_tool(source, description)
    except LettaError as e:
        log.error("could not register %s: %s", TOOL_NAME, e)
        raise
    log.info("registered tool %s -> %s", TOOL_NAME, created.get("id"))
    return created["id"]


def _tool_env(datasets: list[str]) -> dict:
    """RAGflow credentials AND this agent's permitted scope, for the tool
    sandbox. Empty if unconfigured — the tool then returns a clear 'not set'
    error instead of silently answering from the model's own memory.

    RAGFLOW_ALLOWED_DATASETS is what makes the scope a control rather than an
    instruction. The tool cannot tell which agent is calling it, so it resolves
    whatever names it is handed against the whole tenant; the ragflow_scope
    memory block asks the model not to name anything else, and asking is all it
    was. Passing the permitted list through the tool's per-agent execution
    environment puts the limit somewhere the model cannot reach: it is not
    model-visible text, so it cannot be argued with, edited or forgotten."""
    if not (settings.ragflow_base and settings.ragflow_key):
        log.warning("RAGFLOW_BASE_URL / RAGFLOW_API_KEY unset — %s will not retrieve", TOOL_NAME)
        return {}
    return {
        "RAGFLOW_BASE_URL": settings.ragflow_base,
        "RAGFLOW_API_KEY": settings.ragflow_key,
        "RAGFLOW_ALLOWED_DATASETS": ",".join(datasets),
    }


def agent_datasets(agent_name: str, spec: dict | None = None) -> list[str]:
    """The RAGflow datasets an agent is permitted to search, from fleet.yaml.
    Callers building prompts use this instead of a separate env var so the
    permitted scope has exactly one definition."""
    spec = spec or load_fleet()
    ag = next((a for a in spec["agents"] if a["name"] == agent_name), None)
    return list((ag or {}).get("datasets", []))


def declared_pending(spec: dict) -> list[str]:
    """fleet.yaml's own statement of what is not ingested yet — the fallback
    when RAGflow cannot be asked. Kept as a declaration of intent; it is no
    longer what the scope blocks are written from when reality is available."""
    return list((spec.get("ragflow") or {}).get("pending_ingest", []))


async def resolve_pending(spec: dict, report: FleetReport | None = None) -> list[str]:
    """Which declared datasets are NOT on the tenant right now, from RAGflow
    itself rather than from a hand-maintained YAML list.

    The 2026-08-27 and 2026-08-29 incidents were the same incident: RAGflow's
    datasets were renamed, every agent's scope kept the old names, and nothing
    on this side noticed — the test written after the first one compared
    fleet.yaml to fleet.yaml. Asking RAGflow at ensure_fleet time means the
    next rename is caught at the next document job, in the scope block the
    agent reads and on /health, instead of at the next incident.

    The mirror case matters as much: when a pending corpus is finally ingested
    nothing used to notice either, so the three verbatim authors kept being
    told to leave every facility specific BLANK against a corpus that was
    sitting right there.

    Unreachable RAGflow falls back to the YAML lists and says so. An empty
    tenant is not unreachable: that is a real answer, and it is "everything is
    pending"."""
    declared = sorted({d for a in spec["agents"] for d in a.get("datasets", [])})
    try:
        live = await list_dataset_names()
    except RagflowUnreachable as e:
        log.warning("RAGflow unreachable (%s); scope blocks fall back to fleet.yaml", e)
        if report is not None:
            report.warnings.append(f"ragflow unreachable: {e}")
        return declared_pending(spec)
    pending = [d for d in declared if d not in live]
    if report is not None:
        report.datasets_live = live
        report.datasets_unresolved = pending
    if pending:
        log.warning("declared datasets not on the RAGflow tenant: %s", ", ".join(pending))
    return pending


def _blocks_for(ag: dict, spec: dict, pending: list[str] | None = None) -> list[dict]:
    """Every core-memory block this agent should carry, in one place.

    Used both at creation (memory_blocks in the create body) and by the
    reconcile loop, so a live agent and a freshly created one end up with
    byte-identical instructions — the whole point of a declarative fleet.
    read_only is derived from GOVERNANCE_BLOCKS rather than written out per
    entry, so the constant is the invariant and not merely a name for it.

    `pending` is what resolve_pending found on the tenant; callers without a
    live answer (tests, a RAGflow outage) get fleet.yaml's declared list.

    gf_corpus is only given to agents that retrieve. An agent with no datasets
    has no use for a description of corpora it cannot search, and telling it
    what exists in RAGflow would be actively unhelpful: it is one nudge away
    from citing a corpus it has no access to."""
    if pending is None:
        pending = declared_pending(spec)

    def block(label: str, value: str) -> dict:
        return {"label": label, "value": value.strip(),
                "read_only": label in GOVERNANCE_BLOCKS, "limit": BLOCK_LIMIT}

    blocks = [
        block(MISSION_BLOCK, spec["mission"]),
        block(RULES_BLOCK, spec["house_rules"]),
        block(PERSONA_BLOCK, ag["persona"]),
        block(SCOPE_BLOCK, _scope_block(ag.get("datasets", []), pending,
                                        bool(ag.get("verbatim_output")))),
    ]
    if ag.get("datasets") and spec.get("corpus_guide"):
        blocks.append(block(CORPUS_BLOCK, spec["corpus_guide"]))
    return blocks


def _build_body(ag: dict, spec: dict, model: str, embedding: str, name: str,
                description: str, pending: list[str] | None = None) -> dict:
    body = {
        "name": name,
        "description": description,
        "model": model,
        "embedding": embedding,
        "memory_blocks": _blocks_for(ag, spec, pending),
    }
    # Letta sizes an unknown model from its DEFAULT (30000) and clamps output
    # to its own guess. Both are declared in fleet.yaml because the default
    # broke a real run — see the note there.
    defaults = spec.get("defaults") or {}
    if defaults.get("context_window"):
        body["context_window_limit"] = int(defaults["context_window"])
    if defaults.get("max_tokens"):
        body["max_tokens"] = int(defaults["max_tokens"])
    # See fleet.yaml: the mandatory companion to a large context window for
    # every agent the pipeline drives as a one-shot worker.
    body["message_buffer_autoclear"] = bool(ag.get("autoclear"))
    env = _tool_env(ag.get("datasets", []))
    if env and ag.get("datasets"):
        body["tool_exec_environment_variables"] = env
    return body


def _custom_tools(agent: dict) -> dict[str, str]:
    """name -> id of every NON-built-in tool on a live agent. Letta's own
    core tools (memory_replace, conversation_search, ...) carry a letta_*
    tool_type; anything registered by a person or a service is "custom"."""
    return {
        t["name"]: t.get("id", "")
        for t in (agent.get("tools") or [])
        if isinstance(t, dict) and t.get("name") and t.get("tool_type") == "custom"
    }


def _unknown_tools(agent: dict, ag: dict) -> list[str]:
    """Custom tools on the agent that fleet.yaml did not put there.

    The RAGflow tenant key lives in the agent's sandbox environment, which is
    per-AGENT, not per-tool: every tool attached to that agent runs with it.
    The dataset allowlist is enforced by ragflow_search's own source and binds
    nothing else. So a tool this module does not know about — attached by a
    person, by another service, by a future feature — holds the key with no
    allowlist at all. Until now nothing here enumerated, asserted or pruned an
    agent's tool set; the only tool operation was attach-if-missing.

    `extra_tools:` in fleet.yaml is the declared exception list. Anything else
    custom is unknown, and an agent carrying one does not get the key."""
    allowed = {TOOL_NAME, *ag.get("extra_tools", [])}
    return sorted(n for n in _custom_tools(agent) if n not in allowed)


async def _reconcile_retrieval_tool(
    client: LettaClient, agent_id: str, ag: dict, tool_id: str,
    have: dict[str, str], label: str, revoke: bool = False,
) -> str | None:
    """Attach ragflow_search to an agent that is granted datasets and does not
    have it; DETACH it from one that is not granted datasets and does. An
    agent with no corpus should not have a search button at all — and until
    this could detach, one that had lost its corpus kept the button forever.

    `revoke` forces the detach path regardless of the declaration: used when
    the agent carries an unknown tool (see _unknown_tools), so the credential
    is withdrawn rather than shared with it.

    Raises on failure. The old handler swallowed an attach error as "agent
    works, retrieval degraded" — leaving an agent whose scope block tells it to
    use a tool it does not have, and (on the detach side) an agent holding a
    tool the declaration revoked. Neither is a state to continue from."""
    want = bool(ag.get("datasets")) and not revoke
    has = TOOL_NAME in have
    if want and not has:
        await client.attach_tool(agent_id, tool_id)
        return "tool attached"
    if not want and has:
        await client.detach_tool(agent_id, have[TOOL_NAME] or tool_id)
        return "tool detached"
    return None


async def _reconcile_blocks(
    client: LettaClient, agent_id: str, ag: dict, spec: dict, label: str,
    pending: list[str] | None = None, report: FleetReport | None = None,
) -> list[str]:
    """Bring a live agent's memory blocks back in line with fleet.yaml.

    This used to reconcile ragflow_scope and nothing else, which quietly made
    the rest of the file decorative: an agent is only ever CREATED once, so
    every edit to house_rules or to a persona reached new agents and no
    existing one. The fleet had been live for weeks, so in practice that meant
    no instruction change reached anything at all. Reconcile every block the
    module owns instead, and create-then-attach the ones an agent predates.

    Note this deliberately includes `persona`, which the agent itself can
    write: fleet.yaml is the declaration, so a self-edited persona is drift to
    be corrected, not state to preserve.

    Returns the labels actually changed, for the caller to log/report."""
    changed: list[str] = []
    for want in _blocks_for(ag, spec, pending):
        lbl, val, ro = want["label"], want["value"], want["read_only"]
        try:
            block = await client.get_block(agent_id, lbl)
            if block is None:
                created = await client.create_block(lbl, val, read_only=ro, limit=BLOCK_LIMIT)
                try:
                    await client.attach_block(agent_id, created["id"])
                except LettaError:
                    # Create-then-attach is two calls; a failure between them
                    # used to leak one unattached block per pass, since the
                    # next pass saw no block under that label and made another.
                    try:
                        await client.delete_block(created["id"])
                    except LettaError as e2:
                        log.warning("orphan block %s (%s) could not be removed: %s", lbl, created["id"], e2)
                    raise
                changed.append(lbl + " (added)")
                continue
            stale_value = (block.get("value") or "").strip() != val.strip()
            stale_flag = bool(block.get("read_only")) != ro
            if not (stale_value or stale_flag):
                continue
            await client.update_block(
                agent_id,
                lbl,
                value=val if stale_value else None,
                read_only=ro if stale_flag else None,
            )
            changed.append(lbl)
        except LettaError as e:  # non-fatal: a stale block beats a dead ensure
            log.warning("could not reconcile %s on %s: %s", lbl, label, e)
            if report is not None:
                report.warnings.append(f"{label}: block {lbl} not reconciled: {e}")
    if changed:
        log.info("reconciled blocks on %s: %s", label, ", ".join(changed))
    return changed


async def _reconcile_tool_env(
    client: LettaClient, agent: dict, ag: dict, label: str, revoke: bool = False
) -> bool:
    """Push this agent's permitted-dataset allowlist and RAGflow credentials
    into its tool sandbox — or take them OUT again.

    Like the memory blocks and the sizing fields, tool_exec_environment_variables
    is a create-time argument, so every agent that predates RAGFLOW_ALLOWED_
    DATASETS would keep an unenforced scope forever.

    A PATCH replaces the whole set, and gf_doc_orchestrator carries unrelated
    secrets for a different tool, so only the three OWNED_ENV keys are ever
    judged or written; everything else the agent carries is merged back.

    Revocation is the half this never had. An agent whose `datasets:` was
    removed from fleet.yaml got a scope block saying "you have no corpus" and
    kept RAGFLOW_ALLOWED_DATASETS, the base URL and the tenant key exactly
    where they were — narrowing a list reconciled, revoking it did not. Now an
    agent that is not granted datasets, or that must be `revoke`d because it
    carries a tool this module does not know (see _unknown_tools), has the
    owned keys stripped. The tool's own fail-closed branch then refuses any
    search from that sandbox, which is the point."""
    have = {
        e.get("key"): e.get("value")
        for e in (agent.get("tool_exec_environment_variables") or [])
        if isinstance(e, dict)
    }
    grant = bool(ag.get("datasets")) and not revoke
    if not grant:
        if not any(k in have for k in OWNED_ENV):
            return False
        body = {k: v for k, v in have.items() if k not in OWNED_ENV and v}
        try:
            await client.update_agent_config(
                agent["id"], {"tool_exec_environment_variables": body}
            )
        except LettaError as e:
            log.error("could not REVOKE tool env on %s: %s", label, e)
            raise
        log.info("revoked tool env on %s (%s)", label, "unknown tool present" if revoke else "no datasets declared")
        return True
    env = _tool_env(ag["datasets"])
    if not env:
        return False
    # This used to short-circuit on RAGFLOW_ALLOWED_DATASETS alone, on the
    # assumption that the server might withhold secret values and make every
    # run look like a change. It does not: this Letta echoes all three back
    # verbatim (checked against live gf_* agents — RAGFLOW_API_KEY comes back
    # at full length, not starred). The cost of that assumption was that a
    # ROTATED RAGFLOW_API_KEY, or a moved RAGFLOW_BASE_URL, never reached any
    # agent whose dataset list happened to be unchanged — i.e. every agent —
    # and retrieval would fail with no reconcile ever attempting a fix.
    #
    # So compare on everything the server is willing to show. A key it does
    # withhold (None or empty) is skipped rather than counted as a mismatch:
    # counting it would make a stricter server re-push the whole set on every
    # single document job, which is the churn the old comment was right to
    # fear even though its premise about THIS server was wrong.
    #
    # Only the three keys this module owns are judged. A PATCH replaces the
    # whole set, so anything else the agent carries is merged back rather than
    # deleted — the docstring's reason for leaving datasetless agents alone
    # applies just as much to an agent that has datasets AND something else.
    # A variable whose value the server withholds cannot be carried through a
    # PATCH at all, so it is not invented as an empty string either.
    stale = [
        k
        for k, want in env.items()
        if k not in have or (have[k] and have[k] != want)
    ]
    if not stale:
        return False
    body = {k: v for k, v in have.items() if k not in env and v}
    body.update(env)
    try:
        await client.update_agent_config(
            agent["id"], {"tool_exec_environment_variables": body}
        )
    except LettaError as e:
        # Raised, not swallowed. The old comment said "the memory-block scope
        # still applies", 200 lines below a comment saying of that same block
        # that "asking is all it was". An agent whose allowlist could not be
        # brought to the declaration may be holding a WIDER one; that is not a
        # state to run a document job on.
        log.error("could not reconcile tool env on %s: %s", label, e)
        raise
    # Names only — one of these keys is a credential.
    log.info(
        "reconciled tool env on %s (%s); scope=%s",
        label,
        ", ".join(stale),
        env["RAGFLOW_ALLOWED_DATASETS"],
    )
    return True


# (agent_id, field) pairs the server has demonstrably NOT honoured after a
# PATCH. _reconcile_config reads `llm_config.context_window` and writes
# `context_window_limit` — different names — so a Letta that clamps or
# normalises the value would never read back equal, and the fleet would issue
# the same PATCH on every document job, forever, with no symptom but churn.
# That is the exact hazard ensure_tool guards against for source_code. After
# a push, the value is re-read; if it still differs the pair lands here and
# is reported as drift instead of re-pushed for the life of this process.
_UNHONOURED: set[tuple[str, str]] = set()


async def _reconcile_config(
    client: LettaClient, agent: dict, ag: dict, spec: dict, label: str,
    report: FleetReport | None = None,
) -> bool:
    """Push the declared context window / output ceiling onto a live agent.

    Both are passed at creation, which is not enough: an agent created before a
    value was declared keeps whatever Letta guessed, forever. Every one of the
    eight live agents sat at Letta's LLM_MAX_CONTEXT_WINDOW["DEFAULT"] of 30000
    while this file declared 128000 — the exact shortfall whose symptom
    (a 9-section SOP repair prompt truncating mid-section) is why the value was
    declared in the first place.

    Scope is deliberately narrow: context_window_limit, max_tokens and
    message_buffer_autoclear. The model handle is NOT reconciled — fleet.yaml
    records leaving it alone as a standing decision, and widening this would
    silently reverse it.

    autoclear is here rather than beside the memory blocks because it belongs to
    the window: raising context_window without it is what broke a real document
    job. Letta had been trimming these agents' buffers to fit 30000; at 128000
    it stops, and a one-shot worker then carries every document it has ever seen
    into its next prompt. See the note in fleet.yaml for the measurements."""
    defaults = spec.get("defaults") or {}
    lc = agent.get("llm_config") or {}
    aid = agent.get("id", "")
    body: dict = {}
    want_cw = int(defaults["context_window"]) if defaults.get("context_window") else None
    want_mt = int(defaults["max_tokens"]) if defaults.get("max_tokens") else None
    if want_cw and lc.get("context_window") != want_cw and (aid, "context_window") not in _UNHONOURED:
        body["context_window_limit"] = want_cw
    if want_mt and lc.get("max_tokens") != want_mt and (aid, "max_tokens") not in _UNHONOURED:
        body["max_tokens"] = want_mt

    # The model handle is the field most likely to change and the one this
    # deliberately does not write (the server rejects the config write).
    # Not writing it is defensible; presenting fleet.yaml's `model:` as a
    # declaration while it silently governed only from-scratch agents was
    # not. It is now REPORTED as drift, so the declaration is at least honest.
    declared_model = (defaults.get("model") or "").strip()
    live_model = lc.get("handle") or lc.get("model") or ""
    if declared_model and live_model and live_model != declared_model and report is not None:
        report.drift.append(
            f"{label}: model is {live_model}, fleet.yaml declares {declared_model} "
            "(create-time only; not reconciled)"
        )
    want_autoclear = bool(ag.get("autoclear"))
    if bool(agent.get("message_buffer_autoclear")) != want_autoclear:
        body["message_buffer_autoclear"] = want_autoclear

    # Setting the flag only bounds growth from HERE; the history already in the
    # buffer is what made a real job time out, so it has to be dropped too.
    #
    # The condition is the buffer's actual state, not the flag's transition.
    # Tying it to "we are turning autoclear on" looked equivalent and was not:
    # the first live run set the flag and its clear failed (the route wants a
    # body — see LettaClient.reset_messages), which spent the transition. The
    # next run saw the flag already on, concluded there was nothing to do, and
    # left gf_qa_auditor sitting at 78k of its 128k window. Keyed off the
    # buffer instead, a failed clear simply retries on the next pass.
    #
    # `message_ids` is already on the agent record this function was handed, so
    # this costs no extra call. A reset leaves exactly one message behind
    # (measured on all six agents, 41 -> 1 for the worst), so >1 means real
    # accumulated history and an autoclearing agent settles at 1 and stays
    # there — which makes this idempotent across the many ensure_fleet calls a
    # single document job makes.
    stale_buffer = want_autoclear and len(agent.get("message_ids") or []) > 1

    if not body and not stale_buffer:
        return False
    if body:
        try:
            await client.update_agent_config(agent["id"], body)
            log.info("reconciled config on %s: %s", label, body)
        except LettaError as e:  # non-fatal: an undersized window still runs
            log.warning("could not reconcile config on %s: %s", label, e)
            if report is not None:
                report.warnings.append(f"{label}: config not reconciled: {e}")
            return False
        # Re-read what the server actually kept. Anything it did not honour is
        # recorded and never re-pushed by this process — see _UNHONOURED.
        try:
            fresh = (await client.get_agent(agent["id"]) or {}).get("llm_config") or {}
        except LettaError:
            fresh = {}
        for key, want, wrote in (("context_window", want_cw, "context_window_limit"),
                                 ("max_tokens", want_mt, "max_tokens")):
            if wrote in body and fresh and fresh.get(key) != want:
                _UNHONOURED.add((aid, key))
                msg = f"{label}: server reports {key}={fresh.get(key)} after writing {want}; not re-pushing"
                log.warning(msg)
                if report is not None:
                    report.drift.append(msg)
    if stale_buffer:
        try:
            await client.reset_messages(agent["id"])
            log.info("cleared accumulated message buffer on %s", label)
        except LettaError as e:  # non-fatal: autoclear still bounds it going forward
            log.warning("could not clear message buffer on %s: %s", label, e)
    return True


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


def _orphan_age_s(agent: dict, now: datetime) -> float | None:
    raw = agent.get("created_at")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()


async def _sweep_orphans(client: LettaClient, existing: list[dict], report: FleetReport) -> list[dict]:
    """Delete gf_*_tmp_* clones that outlived any job that could own them.

    pipeline.py swallows a failed delete of an ephemeral clone on the stated
    grounds that "the next fleet audit sweeps _tmp_ leftovers". No such sweep
    existed; the sentence was load-bearing for the decision to continue and it
    was false. A clone orphaned by a killed worker or a failed DELETE kept the
    RAGflow key and a live allowlist in its sandbox indefinitely.

    Age-gated, because two uvicorn workers share the server: a clone younger
    than the longest exchange a job can legally be inside (three sequential
    Letta reads at the configured timeout) may belong to a job on the other
    worker. Anything older belongs to no one."""
    limit = 3 * float(settings.letta_read_timeout)
    now = datetime.now(timezone.utc)
    kept: list[dict] = []
    for a in existing:
        name = a.get("name") or ""
        age = _orphan_age_s(a, now)
        if name.startswith("gf_") and TMP_MARKER in name and age is not None and age > limit:
            try:
                await client.delete_agent(a["id"])
                report.swept.append(name)
                log.warning("swept orphaned ephemeral agent %s (age %.0fs)", name, age)
                continue
            except LettaError as e:
                report.warnings.append(f"orphan {name} could not be swept: {e}")
        kept.append(a)
    return kept


async def ensure_fleet_ctx(client: LettaClient | None = None) -> FleetContext:
    """Converge the live gf_ fleet on fleet.yaml and return everything a job
    needs from the result. Idempotent: a second run against a converged fleet
    makes zero writes.

    Order matters. Orphans are swept first so they cannot be reconciled as if
    declared. The tool is ensured before any agent, and it RAISES on failure —
    the agents' scope enforcement lives inside it. Pending datasets are asked
    of RAGflow once per pass and written into every scope block."""
    global LAST_REPORT
    client = client or LettaClient()
    spec = load_fleet()
    report = FleetReport()
    live = await _sweep_orphans(client, await client.list_agents(), report)
    existing = {a.get("name"): a for a in live}
    served, served_emb = await _served_handles(client)
    model, embedding = _resolve_model(spec, live, served, served_emb)
    tool_id = await ensure_tool(client, spec)
    pending = await resolve_pending(spec, report)

    out: dict[str, str] = {}
    for ag in spec["agents"]:
        name = ag["name"]
        cur = existing.get(name)
        if cur:
            out[name] = cur["id"]
            # Reconcile an agent that already exists. Everything below is
            # bounded: gf_* only, the blocks and the three env keys this module
            # owns, the two sizing fields, the one tool — and only when the
            # live value actually differs from the declaration.
            unknown = _unknown_tools(cur, ag)
            if unknown:
                # The tenant key is per-agent, not per-tool. An agent carrying
                # a tool this module does not know does not get the key, and
                # loses it if it had it. Loud, and in the report.
                report.unknown_tools[name] = unknown
                log.error("%s carries custom tool(s) fleet.yaml does not declare: %s "
                          "— withholding RAGflow credentials", name, ", ".join(unknown))
            revoke = bool(unknown)
            did = await _reconcile_retrieval_tool(
                client, cur["id"], ag, tool_id, _custom_tools(cur), name, revoke=revoke
            )
            if did:
                report.note(name, did)
            for lbl in await _reconcile_blocks(client, cur["id"], ag, spec, name, pending, report):
                report.note(name, f"block {lbl}")
            if await _reconcile_tool_env(client, cur, ag, name, revoke=revoke):
                report.note(name, "tool env revoked" if (revoke or not ag.get("datasets")) else "tool env")
            if await _reconcile_config(client, cur, ag, spec, name, report):
                report.note(name, "config")
            n_msgs = len(cur.get("message_ids") or [])
            if not ag.get("autoclear") and n_msgs > 100:
                # A conversational agent is allowed to keep history; it is not
                # allowed to keep it silently forever. The qa-auditor timeout
                # was this same curve, steeper.
                report.warnings.append(f"{name}: {n_msgs} messages in buffer with autoclear off")
            continue
        body = _build_body(ag, spec, model, embedding, name, ag.get("description", ""), pending)
        created = await client.create_agent(body)
        out[name] = created["id"]
        report.created.append(name)
        log.info("created agent %s -> %s", name, created["id"])
        await _reconcile_retrieval_tool(client, created["id"], ag, tool_id, _custom_tools(created), name)

    declared = {a["name"] for a in spec["agents"]}
    for name in sorted(existing):
        if name and name.startswith("gf_") and TMP_MARKER not in name and name not in declared:
            # Removed from fleet.yaml, still on the server: reported, not deleted.
            # Deleting a persistent agent is a human decision; leaving it
            # unmentioned was the problem.
            report.drift.append(f"{name}: live on the server, not declared in fleet.yaml")
    LAST_REPORT = report
    if report.summary()["converged"]:
        log.info("fleet converged: %d agents", len(out))
    else:
        log.warning("fleet not converged: %s", report.summary())
    return FleetContext(out, live, model, embedding, tool_id, pending, report)


async def ensure_fleet(client: LettaClient | None = None) -> dict:
    """Idempotent. Returns {agent_name: agent_id} for the whole gf_ fleet.
    Thin wrapper kept for callers that only need the map; the pipeline uses
    ensure_fleet_ctx so its ephemeral clones reuse what this resolved."""
    return (await ensure_fleet_ctx(client)).agents


async def spawn_ephemeral(
    client: LettaClient, agent_name: str, name_suffix: str, ctx: FleetContext | None = None,
    autoclear: bool | None = None,
) -> str:
    """Create a short-lived clone of a fleet agent (same persona/datasets/
    model) for exactly ONE isolated exchange, then the caller deletes it.

    Exists because a persistent Letta agent accumulates every past message
    into the prompt sent on each new turn — fine for a single Q&A agent, but
    fatal for a loop that sends N independent checks against the same agent
    (each turn's system-prompt token estimate keeps growing until it exceeds
    the model's context window; observed live at section 9 of 9 on a fresh
    gf_reg_checker). A fresh clone per exchange keeps that estimate constant
    regardless of how many checks the pipeline runs.

    `autoclear` overrides the cloned agent's own fleet.yaml `autoclear:` flag
    for THIS clone only. The base agent's flag describes its normal one-shot
    use (called once, then autoclear wipes the buffer so the next call starts
    fresh) — but a caller that sends a SECOND turn to the same clone (a nudge,
    a follow-up) needs that first turn still in the buffer when the second one
    is composed. With the base agent's autoclear left on, the buffer wipes
    between turns 1 and 2 and the second turn runs with no memory of the
    first: observed live on a repair clone whose nudge turn ran at a 5.8k-token
    estimate right after a 34k-token first turn had the whole document in it,
    and returned nothing — the agent had already forgotten it. Pass
    `autoclear=False` for any clone the caller will message more than once.

    With `ctx` (what the job's own ensure_fleet_ctx resolved) this makes
    exactly two calls: create and attach. Without it — other callers, tests —
    it re-lists agents, models, embeddings and tools itself, which is what
    every call used to do: four listing round-trips per section, for data the
    same job had fetched moments earlier over the same connection."""
    spec = load_fleet()
    ag = next(a for a in spec["agents"] if a["name"] == agent_name)
    body_ag = ag if autoclear is None else {**ag, "autoclear": autoclear}
    if ctx is not None:
        existing, model, embedding, tool_id, pending = (
            ctx.existing, ctx.model, ctx.embedding, ctx.tool_id, ctx.pending
        )
    else:
        existing = await client.list_agents()
        served, served_emb = await _served_handles(client)
        model, embedding = _resolve_model(spec, existing, served, served_emb)
        tool_id = await ensure_tool(client, spec)
        pending = None
    # The clone must run the SAME model as the agent it clones ("same persona/
    # datasets/model") — global resolution picks whatever agent happens to list
    # first, which on a mixed instance (fleet + mirrored planners) can be a
    # different provider whose tool-loop behavior differs from the base
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
        body_ag,
        spec,
        model,
        embedding,
        f"{agent_name}{TMP_MARKER}{name_suffix}",
        f"ephemeral clone of {agent_name} for one isolated exchange",
        pending,
    )
    created = await client.create_agent(body)
    await _reconcile_retrieval_tool(client, created["id"], ag, tool_id, _custom_tools(created), body["name"])
    return created["id"]

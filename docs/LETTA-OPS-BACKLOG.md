# Letta ops backlog — live server maintenance (2026-07-16)

The GrowFlow platform's AI layer runs on a **live, shared Letta server**
(`letta` container, `http://host.docker.internal:8283`). As of the production
cutover it has **two production dependents**: the weekly-AI `scheduler`
(weekly snapshot → digest → Letta) and the newly-promoted `wwf-docengine`
(its regulatory-checker fleet). Any change here can degrade both — so each item
below is its own **separately-confirmed operation**, not a bundle.

## Live state (read-only diagnostic, 2026-07-16)

- **Server version:** `0.16.8`, health `ok`.
- **Agents:** **107** (the plan estimated ~54 — roughly doubled).
- **Sources: 9.** Eight are 1536-dim; **`PQ1 Water Testing Results Report` is
  3072-dim** — the known outlier. The others: `DB1_REGULATORY`,
  `DB2_GMP_PRO`, `DB3_PP_CURRENT_unified`, `ImB_QC_COAs`,
  `CoA_Individual_Split`, `Equipment_Manuals_PP`, `Superior_Primary_Packaging`,
  `GrowFlow_Weekly_Snapshots`.

## Backlog (each = its own confirmed operation)

| # | Item | Risk | Reversible? | Notes / recommended approach |
|---|------|------|-------------|------------------------------|
| 1 | **PQ1 3072-dim re-embedding** | Med | No (destroys+rebuilds the source's vectors) | PQ1 is dimension-incompatible with the other 8 sources, so an agent attached to PQ1 **and** a 1536 source can't mix them. It is already **excluded by design** from the multi-source regulatory checker. Only re-embed if PQ1 must join a multi-source agent; otherwise leave excluded. Re-embed = detach → delete embeddings → re-ingest at 1536. |
| 2 | **Agent sprawl — 107 agents (INVESTIGATED 2026-07-16)** | Med | Deletes are irreversible | **Root cause found** (read-only enumeration): the old **qms-creator** (`qms-api`) CONTENT_CREATOR_FRAMEWORK re-creates its section-author fleet on each run **with no ensure-by-name dedup** → **11 `GMP *` roles × 4 copies = 44 agents, 33 redundant**. The DocEngine's `fleet.py` does it correctly — the **`gf_*` fleet is 8 agents, exactly one each**, and fully supersedes the `GMP *` fleet. The remaining ~54 (weekly-AI `planner-*`, `wwf_*` coordinators, `VariationF-Compliance-Sentinel`, etc.) are one-each and legitimate. **Remediation:** retiring `qms-api` (item below / roadmap) removes the sprawl *source*; the 44 `GMP *` agents then become orphaned and can be bulk-deleted (snapshot `letta-postgres` first). Do NOT touch the `gf_*`, `planner-*`, or `wwf_*` agents. |
| 3 | **0.16.8 → 0.17 server upgrade** | **High** | Hard (image swap + on-disk agent-state migration) | A minor-version jump on the shared server. Needs: snapshot `letta-postgres` first, swap the `letta` image, let it migrate, then re-validate the weekly-AI + DocEngine paths end-to-end. Do in a maintenance window; not adjacent to other changes. |
| 4 | **Master-key rotation** | **High** | The new key must be propagated everywhere atomically | Rotating `LETTA_API_KEY` invalidates every current key at once — it would break the `scheduler`, `wwf-docengine`, and any other caller until each `.env`/`app.env` is updated + containers recreated. Only worth doing if the key is believed compromised; if so, do it as one coordinated pass across all callers. |
| 5 | **Provider-enum / temperature normalization** | Low–Med | Per-agent config PATCH is reversible | Config drift across agents (the handover flagged a provider-enum issue that made new-agent creation a create-new path). Needs a per-agent audit of `llm_config` to find the specific misconfigured agents before touching them — a targeted PATCH per agent, not a bulk change. |

## Standing guidance

- **Read-only first** for every item — inventory and confirm the exact defect
  before any mutation.
- **Snapshot `letta-postgres`** before items #2 (bulk delete), #3 (upgrade).
- **Never** rotate the master key or upgrade the server version without first
  enumerating every caller (`scheduler`, `wwf-docengine`, plus any external
  integration) and having the re-key / re-validate steps staged for all of them.
- These were deliberately deferred throughout the unification because they are
  operations on a live shared AI, orthogonal to the app build. The production
  cutover **increased** the blast radius (the DocEngine now depends on this
  server), so the bar for touching it is now higher, not lower.

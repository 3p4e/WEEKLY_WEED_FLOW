# The retrieval tool registered on the Letta server and attached to every gf_*
# agent that has a corpus. RAG lives in RAGflow, not in Letta: agents carry no
# attached Letta sources, they call this instead.
#
# THIS FILE IS THE TOOL. fleet.py reads its text verbatim and POSTs it as the
# tool's source_code (the same way it reads fleet.yaml by path), so Letta runs
# exactly what is committed here. Two consequences:
#
#   1. It must be self-contained — standard library only, no imports from this
#      repository — because Letta executes it in its own sandbox.
#   2. Keep it to comments and this ONE function — no module-level statements
#      (they would run in the sandbox) and no nested defs. Letta derives a JSON
#      schema from every function it finds in the source and rejects the whole
#      upload if any of them falls short; a nested helper was refused first for
#      a missing docstring, then for an unannotated parameter. One function has
#      no such surface, so the two API calls below are written out in full
#      rather than sharing a helper. The duplication is deliberate.
#
# Configuration comes from the tool's execution environment, set per agent as
# tool_exec_environment_variables from docengine.app.config:
#   RAGFLOW_BASE_URL  e.g. http://ragflow-ragflow-cpu-1:9380
#   RAGFLOW_API_KEY   a RAGflow API token for the tenant owning the datasets
#
# Dataset scoping is the guardrail, and it is enforced here, not merely asked
# for. The caller passes the datasets it is allowed to name (from its
# ragflow_scope memory block); a name that does not exist is reported back as
# unknown_datasets rather than silently returning nothing, so the agent can say
# "not ingested" instead of filling the gap from memory.
#
# Two things this function must never do, both of which it used to:
#
#   1. Search everything when `datasets` is omitted. That was the documented
#      behaviour ("omit to search every dataset this key can see") and it turns
#      a forgotten argument into a full scope bypass — including the stability
#      corpus that no document agent is granted. An unscoped search is refused.
#   2. Report the full list of datasets on the tenant when the requested ones do
#      not resolve. That named STABILITY_PROGRAMME to agents whose entire design
#      is that they cannot know it exists, and handed them a name to try next.
#      Errors now echo only what the caller already asked for.


def ragflow_search(question: str, datasets: str = "", top_k: int = 6) -> str:
    """Search the Purely Plant document corpora in RAGflow and return the matching passages.

    Args:
        question (str): what to look for, in natural language.
        datasets (str): comma-separated RAGflow dataset names to search. Required: name exactly the datasets your ragflow_scope memory block permits. An empty value is refused rather than searching everything.
        top_k (int): maximum number of passages to return. Optional; defaults to 6.
    """
    import json
    import os
    import urllib.request

    base = (os.environ.get("RAGFLOW_BASE_URL") or "").rstrip("/")
    key = os.environ.get("RAGFLOW_API_KEY") or ""
    if not base or not key:
        return json.dumps(
            {"ok": False, "err": "RAGFLOW_BASE_URL / RAGFLOW_API_KEY not set for this tool"}
        )

    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}

    wanted = [d.strip() for d in datasets.split(",") if d.strip()]
    if not wanted:
        return json.dumps(
            {
                "ok": False,
                "err": "datasets is required — name the datasets your ragflow_scope "
                "memory block permits. An unscoped search is not allowed.",
            }
        )

    # 1. resolve dataset names -> ids
    try:
        req = urllib.request.Request(
            base + "/api/v1/datasets?page=1&page_size=100", headers=headers, method="GET"
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            listing = json.loads(r.read().decode())
    except Exception as e:
        return json.dumps({"ok": False, "err": "dataset list failed: %s" % str(e)[:200]})

    by_name = {d["name"]: d["id"] for d in (listing.get("data") or [])}
    ids, missing = [], []
    for n in wanted:
        if n in by_name:
            ids.append(by_name[n])
        else:
            missing.append(n)
    if not ids:
        # Deliberately does NOT list what else exists on the tenant — see the
        # header note. The caller learns that its own datasets are absent, which
        # is the fact it needs, and nothing about corpora it is not granted.
        return json.dumps(
            {
                "ok": False,
                "err": "none of the requested datasets exist in RAGflow yet",
                "unknown_datasets": wanted,
            }
        )

    # 2. retrieve passages from just those datasets
    try:
        payload = {
            "question": question,
            "dataset_ids": ids,
            "top_k": int(top_k),
            "similarity_threshold": 0.1,
        }
        req = urllib.request.Request(
            base + "/api/v1/retrieval",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode())
    except Exception as e:
        return json.dumps({"ok": False, "err": "retrieval failed: %s" % str(e)[:200]})

    chunks = ((res.get("data") or {}).get("chunks") or [])[: int(top_k)]
    hits = [
        {"document": c.get("document_keyword"), "text": (c.get("content") or "").strip()}
        for c in chunks
    ]
    out = {"ok": True, "searched": [n for n in wanted if n in by_name], "hits": hits}
    if missing:
        out["unknown_datasets"] = missing
    return json.dumps(out, ensure_ascii=False)

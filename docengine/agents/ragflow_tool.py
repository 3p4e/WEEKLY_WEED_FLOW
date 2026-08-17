# The retrieval tool registered on the Letta server and attached to every gf_*
# agent. Letta executes this source in its own sandbox, so it must be
# self-contained: standard library only, no imports from this repository, and
# configuration read from the tool's execution environment.
#
# RAG lives in RAGflow, not in Letta. Agents carry no attached Letta sources;
# they call this instead. Dataset scoping is the guardrail — an agent given
# only the release datasets cannot reach stability data, because that data is
# not in the datasets it is allowed to name.
#
# Environment (set as tool_exec_environment_variables on the agent):
#   RAGFLOW_BASE_URL  e.g. http://ragflow-ragflow-cpu-1:9380
#   RAGFLOW_API_KEY   a RAGflow API token for the owning tenant

RAGFLOW_SEARCH_SOURCE = '''
def ragflow_search(question: str, datasets: str = "", top_k: int = 6) -> str:
    """Search the Purely Plant document corpora in RAGflow and return the matching passages.

    Args:
        question (str): what to look for, in natural language.
        datasets (str): comma-separated RAGflow dataset names to search. Omit to search every dataset this key can see. Name only the datasets your instructions permit.
        top_k (int): maximum number of passages to return. Optional; defaults to 6.
    """
    import os, json, urllib.request

    base = (os.environ.get("RAGFLOW_BASE_URL") or "").rstrip("/")
    key = os.environ.get("RAGFLOW_API_KEY") or ""
    if not base or not key:
        return json.dumps({"ok": False, "err": "RAGFLOW_BASE_URL / RAGFLOW_API_KEY not set for this tool"})

    def _call(path, body=None, method="GET"):
        req = urllib.request.Request(
            base + path,
            data=(json.dumps(body).encode() if body is not None else None),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    try:
        listing = _call("/api/v1/datasets?page=1&page_size=100")
    except Exception as e:
        return json.dumps({"ok": False, "err": "dataset list failed: %s" % str(e)[:200]})

    by_name = {d["name"]: d["id"] for d in (listing.get("data") or [])}
    wanted = [d.strip() for d in datasets.split(",") if d.strip()] if datasets else list(by_name)
    ids, missing = [], []
    for n in wanted:
        if n in by_name:
            ids.append(by_name[n])
        else:
            missing.append(n)
    if not ids:
        return json.dumps({"ok": False, "err": "no known dataset named", "requested": wanted,
                           "available": sorted(by_name)})

    try:
        res = _call("/api/v1/retrieval",
                    {"question": question, "dataset_ids": ids,
                     "top_k": int(top_k), "similarity_threshold": 0.1},
                    "POST")
    except Exception as e:
        return json.dumps({"ok": False, "err": "retrieval failed: %s" % str(e)[:200]})

    chunks = ((res.get("data") or {}).get("chunks") or [])[: int(top_k)]
    hits = [{"document": c.get("document_keyword"), "text": (c.get("content") or "").strip()}
            for c in chunks]
    out = {"ok": True, "searched": [n for n in wanted if n in by_name], "hits": hits}
    if missing:
        out["unknown_datasets"] = missing
    return json.dumps(out, ensure_ascii=False)
'''

RAGFLOW_SEARCH_DESCRIPTION = (
    "Search the Purely Plant document corpora held in RAGflow (certificates, batch "
    "summaries, QMS documents) and return matching passages with their source document. "
    "Scope the search with the dataset names your instructions allow."
)

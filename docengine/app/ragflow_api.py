# docengine.app.ragflow_api — the one thing this service asks RAGflow directly.
#
# The fleet is coupled to RAGflow BY DATASET NAME: fleet.yaml grants names, the
# tool's allowlist carries names, the scope block tells the agent names. Until
# this module existed nothing on this side ever checked those names against the
# tenant, so a rename in RAGflow (2026-08-27, and again 2026-08-29) left every
# agent holding a scope that resolved to nothing — with the test suite green,
# because the test compared fleet.yaml to fleet.yaml.
#
# This is deliberately tiny: one read-only listing, paginated, with a short
# timeout, returning names. It is called from ensure_fleet so "which of the
# declared datasets actually exist right now" is answered at the moment the
# scope blocks are written, and from /health so the answer is visible without
# running a document job.
from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger("docengine.ragflow")

_PAGE = 100


class RagflowUnreachable(Exception):
    """RAGflow did not answer. Distinct from "the dataset is not there", which
    is an ordinary empty result: callers fall back to fleet.yaml's declared
    lists on THIS and must not on that."""


async def list_dataset_names(
    base: str | None = None, key: str | None = None, timeout: float = 10.0
) -> set[str]:
    """Every dataset name the tenant currently has, across all pages.

    Page size 100 and a loop rather than one page: the tool's own listing used
    to take the first page only, which on a tenant past 100 datasets reports a
    granted corpus as "not ingested" — fail-closed, but silently and forever.
    """
    base = (base if base is not None else settings.ragflow_base).rstrip("/")
    key = key if key is not None else settings.ragflow_key
    if not base or not key:
        raise RagflowUnreachable("RAGFLOW_BASE_URL / RAGFLOW_API_KEY unset")
    names: set[str] = set()
    page = 1
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            while True:
                r = await c.get(
                    f"{base}/api/v1/datasets",
                    params={"page": page, "page_size": _PAGE},
                    headers={"Authorization": f"Bearer {key}"},
                )
                r.raise_for_status()
                rows = (r.json().get("data") or [])
                names.update(d["name"] for d in rows if d.get("name"))
                if len(rows) < _PAGE:
                    return names
                page += 1
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise RagflowUnreachable(f"{type(e).__name__}: {str(e)[:200]}") from e

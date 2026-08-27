from app.db import rls
from app.deps import require_role
from app.roles import ELEVATED_ROLES
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _WRITERS, _uuid_or_404, _uuid_or_422, router


class ChunksIn(BaseModel):
    # list[str] or list[{content, chunk_index?}]; capped so one (re)index can't
    # drive an unbounded INSERT loop in a single transaction.
    chunks: list = Field(default_factory=list, max_length=2000)


class QaIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


def _chunk_out(r: dict) -> dict:
    return {"id": str(r["id"]), "document_id": str(r["document_id"]),
            "chunk_index": r["chunk_index"], "content": r["content"]}


@router.get("/coa-documents/{doc_id}/chunks")
async def list_chunks(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(doc_id, "eCoA document")
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id) is None:
            raise HTTPException(404, "eCoA document not found")
        rows = await c.fetch(
            "SELECT * FROM qc_coa_chunks WHERE document_id=$1 ORDER BY chunk_index", doc_id)
    return [_chunk_out(dict(r)) for r in rows]


@router.post("/coa-documents/{doc_id}/chunks", status_code=201)
async def index_chunks(doc_id: str, body: ChunksIn, user: dict = Depends(require_role(*_WRITERS))):
    """(Re)index a document's text chunks for retrieval. Replaces any existing
    chunks for the document so re-indexing is idempotent."""
    _uuid_or_404(doc_id, "eCoA document")
    norm = []
    for i, ch in enumerate(body.chunks):
        if isinstance(ch, str):
            content, idx = ch, i
        elif isinstance(ch, dict):
            content, idx = ch.get("content") or "", ch.get("chunk_index", i)
        else:
            continue
        content = str(content).strip()
        if content:
            norm.append((idx, content))
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id) is None:
            raise HTTPException(404, "eCoA document not found")
        await c.execute("DELETE FROM qc_coa_chunks WHERE document_id=$1", doc_id)
        for idx, content in norm:
            await c.execute(
                "INSERT INTO qc_coa_chunks(org_id, document_id, chunk_index, content, created_by)"
                " VALUES ($1,$2,$3,$4,$5)", user["org_id"], doc_id, idx, content, user["id"])
    return {"document_id": doc_id, "indexed": len(norm)}


@router.post("/coa-qa")
async def coa_qa(body: QaIn, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Retrieve the top-ranked CoA passages for a question (full-text), org-scoped
    (and document-scoped if `document_id` is given). Returns the cited passages
    and a grounded answer assembled strictly from them — never fabricated."""
    if body.document_id:
        _uuid_or_422(body.document_id, "document_id")
    args = [body.question]
    doc_clause = ""
    if body.document_id:
        args.append(body.document_id)
        doc_clause = f" AND ch.document_id=${len(args)}"
    args.append(body.top_k)
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT ch.document_id, ch.chunk_index, ch.content, d.doc_number,"
            " ts_rank(ch.tsv, websearch_to_tsquery('english', $1)) AS score"
            " FROM qc_coa_chunks ch JOIN qc_coa_documents d ON d.id = ch.document_id"
            " WHERE ch.tsv @@ websearch_to_tsquery('english', $1)" + doc_clause +
            f" ORDER BY score DESC, ch.chunk_index LIMIT ${len(args)}", *args)
    passages = [{"document_id": str(r["document_id"]), "doc_number": r["doc_number"],
                 "chunk_index": r["chunk_index"], "content": r["content"],
                 "score": round(float(r["score"]), 4)} for r in rows]
    # Grounded answer: the retrieved passages themselves (cited), never invented.
    if passages:
        answer = "\n\n".join(f"[{p['doc_number']}#{p['chunk_index']}] {p['content']}" for p in passages[:3])
    else:
        answer = ""
    return {"question": body.question, "grounded": bool(passages),
            "answer": answer, "passages": passages}

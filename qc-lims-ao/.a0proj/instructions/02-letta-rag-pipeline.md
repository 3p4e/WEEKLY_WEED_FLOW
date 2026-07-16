# Letta RAG Pipeline — SOP Document Ingestion & Agent Orchestration

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│              DOCUMENT INGESTION PIPELINE               │
├──────────────────────────────────────────────────────┤
│                                                        │
│  DOCX/PDF  →  Text Extraction  →  Chunking  →  Embed  │
│  (QCSOPs)     (python-docx,     (500 tokens,   (voyage-3,│
│                pdfminer)         50 overlap)    1024d) │
│                                                        │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│                    QDRANT VECTOR DB                    │
│              pp_qms_sops collection (KVM4 :6333)       │
│  - QCSOP docs (chunked by section: purpose, procedure) │
│  - Metadata: doc_number, section, language, version    │
│  - Filterable by doc_type, department, effective_date  │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│                   LETTA AGENTS                         │
│              (KVM4 API :8283, MCP :6507)               │
│                                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 1. GMP Expert Agent                              │  │
│  │    - System: EU GMP, ICH Q10, Annex 11 expert    │  │
│  │    - Memory: Facility context, regs, ph Eur      │  │
│  │    - RAG: regulatory_docs collection             │  │
│  │    - Purpose: Answer GMP compliance questions    │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 2. SOP Writer Agent                              │  │
│  │    - System: Bilingual SOP drafting (MK/EN)       │  │
│  │    - Memory: SOP structure, format standards     │  │
│  │    - RAG: sop_templates collection               │  │
│  │    - Purpose: Draft new/revised SOPs             │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 3. CAPA Manager Agent                            │  │
│  │    - System: QCSOP 019 OOS investigation         │  │
│  │    - Memory: root cause templates        │  │
│  │    - RAG: oos_records collection                 │  │
│  │    - Purpose: Guide OOS Phase I/II investigation │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 4. QMS Orchestrator Agent                        │  │
│  │    - System: Workflow orchestration across all   │  │
│  │    - Routes queries to specialist agents         │  │
│  │    - Purpose: Single entry point for LIMS AI     │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 5. Risk Assessor Agent                           │  │
│  │    - System: ICH Q9, FMEA, risk-based decision  │  │
│  │    - Purpose: Assess risk for deviations/change  │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## 1. SSH Tunnel Setup (Docker → KVM4)

```bash
# Persistent SSH tunnel for Letta API + Qdrant + MCP
ssh -i /a0/usr/workdir/ssh/kvm4_id_ed25519_new \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=60 \
    -L 8283:localhost:8283 \
    -L 6333:localhost:6333 \
    -L 6507:localhost:6507 \
    -N -f root@srv1231216.hstgr.cloud
```

After tunnel established:
- Letta API: `http://localhost:8283`
- Qdrant: `http://localhost:6333`
- MCP Rust: `http://localhost:6507`

## 2. Document Extraction & Chunking

```python
# Extraction strategy per document type
from docx import Document
from pdfminer.high_level import extract_text

class SOPExtractor:
    """Extract structured content from QCSOP documents"""
    
    def extract_docx(self, path: str) -> dict:
        doc = Document(path)
        metadata = self._parse_header(doc)
        sections = self._parse_sections(doc)
        # Parse bilingual pairs from alternating MK/EN paragraphs
        return {"metadata": metadata, "sections": sections}
    
    def chunk_sections(self, sections: dict) -> list[dict]:
        """Chunk each SOP section into 500-token windows with 50-token overlap"""
        from langchain.text_splitter import TokenTextSplitter
        splitter = TokenTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = []
        for section_name, content in sections.items():
            section_chunks = splitter.split_text(content)
            for i, chunk in enumerate(section_chunks):
                chunks.append({
                    "text": chunk,
                    "metadata": {
                        "section": section_name,
                        "chunk_index": i,
                        "total_chunks": len(section_chunks),
                    }
                })
        return chunks
```

### Chunking Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Chunk size | 500 tokens | Enough for a complete procedure step, not too large for precise retrieval |
| Chunk overlap | 50 tokens | Ensures no context cutoff at boundaries |
| Embedding model | `voyage-3` (1024d) | Best balance of accuracy vs cost for regulatory text |
| Collection name | `pp_qms_sops` | Dedicated namespace for Purely Plant SOPs |

## 3. Embedding & Vector Store

```python
import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct
)

# Initialize clients
vo = voyageai.Client(api_key=pa-ysHQAA8XgBxSH6QKXzE__0P_XmQsUkzn1mdQaXSv6UE)
qdrant = QdrantClient(url="http://localhost:6333")

# Create collection (if not exists)
collections = qdrant.get_collections().collections
if "pp_qms_sops" not in [c.name for c in collections]:
    qdrant.create_collection(
        collection_name="pp_qms_sops",
        vectors_config=VectorParams(
            size=1024, distance=Distance.COSINE
        )
    )

# Embed and upsert chunks
def ingest_docs(chunks: list[dict]):
    texts = [c["text"] for c in chunks]
    embeddings = vo.embed(
        texts, model="voyage-3", input_type="document"
    ).embeddings
    
    points = [
        PointStruct(
            id=i,
            vector=emb,
            payload={
                "text": chunk["text"][:1000],  # Store truncated text
                **chunk["metadata"]
            }
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    qdrant.upsert(
        collection_name="pp_qms_sops",
        points=points
    )
```

## 4. Letta Agent Creation

```python
from letta_client import Letta

client = Letta(base_url="http://localhost:8283")

# Create GMP Expert Agent
gmp_agent = client.agents.create(
    name="GMP Expert Agent",
    model="anthropic/claude-sonnet-4-5",
    embedding="voyageai/voyage-3",
    system="""You are an EU GMP regulatory expert for a cannabis API QC laboratory.
- Primary regulation: EudraLex Vol 4 Annex 1, 11, 15, 16
- Standards: ICH Q10, WHO TRS 902, Ph. Eur. cannabis monographs
- Facility: Purely Plant GmbH, North Macedonia
- Products: Dried cannabis flower for medical use

Use RAG to cite specific SOP clauses. Never make up regulatory requirements.
Provide bilingual answers (MK primary, EN secondary) when appropriate.""",
    memory_blocks=[
        {"label": "facility_context",
         "value": "Purely Plant GmbH — Licensed cannabis producer/API manufacturer",
         "limit": 500},
        {"label": "rag_collection",
         "value": "pp_qms_sops",
         "limit": 100},
    ]
)
```

## 5. RAG Query Pattern

```python
def query_rag_with_letta(
    agent_id: str,
    question: str,
    filter_docs: list[str] = None
) -> str:
    """Query Letta agent with RAG context from Qdrant"""
    
    # 1. Embed the question
    query_emb = vo.embed(
        [question], model="voyage-3", input_type="query"
    ).embeddings[0]
    
    # 2. Search Qdrant
    qdrant_filter = None
    if filter_docs:
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="doc_number",
                    match=MatchAny(any=filter_docs)
                )
            ]
        )
    
    search_results = qdrant.search(
        collection_name="pp_qms_sops",
        query_vector=query_emb,
        limit=5,
        query_filter=qdrant_filter,
    )
    
    # 3. Build context
    context = "\n---\n".join([
        f"[Doc: {r.payload.get('doc_number', 'UNKNOWN')} | "
        f"Section: {r.payload.get('section', 'N/A')}]\n"
        f"{r.payload.get('text', '')}"
        for r in search_results
    ])
    
    # 4. Send to Letta agent
    response = client.agents.messages.create(
        agent_id=agent_id,
        messages=[
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ]
    )
    return extract_assistant_response(response)
```

## 6. Periodic Re-indexing Workflow

When new/revised SOPs arrive:

1. **Detect changes**: Scan `/a0/usr/workdir/gmp_docs/` for new/modified files
2. **Extract & chunk**: Run extraction pipeline on changed documents
3. **Version in Qdrant**: Old vectors tagged with `superseded_by: new_version` (not deleted — ALCOA++ Complete principle)
4. **Update Letta agent memory**: Refresh memory blocks with new effective dates
5. **Validation**: Run `query_rag_with_letta()` on known test questions to verify retrieval quality

## 7. Connection Troubleshooting

### If Letta API not reachable:
```bash
# Check SSH tunnel
ps aux | grep "ssh.*8283"
# Check Letta directly via SSH
ssh -i /a0/usr/workdir/ssh/kvm4_id_ed25519_new root@srv1231216.hstgr.cloud \
    'curl -s http://localhost:8283/v1/health'
```

### If Qdrant not reachable:
```bash
# Check Qdrant
curl -s http://localhost:6333/collections | python3 -m json.tool
```

### If VoyageAI embedding fails:
```bash
# Verify API key
python3 -c "import voyageai; vo = voyageai.Client(api_key='pa-ysHQAA8XgBxSH6QKXzE__0P_XmQsUkzn1mdQaXSv6UE'); print(vo.embed(['test'], model='voyage-3'))"
```
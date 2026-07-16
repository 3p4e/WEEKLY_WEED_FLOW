---
title: 'P5 AI Supercharge — Letta-Powered GMP Compliance Assistant'
slug: 'p5-ai-supercharge'
created: '2026-05-31'
status: 'in-progress'
stepsCompleted: []
tech_stack:
  - FastAPI
  - React + TypeScript
  - Letta (v0.16.7)
  - Qdrant (v1.13.6)
  - VoyageAI (voyage-3)
  - PostgreSQL
  - python-docx
  - Gotenberg
files_to_modify:
  - backend/app/services/letta_service.py
  - backend/app/services/sop_rag_service.py
  - backend/app/services/capa_agent_service.py
  - backend/app/services/coa_auto_generator.py
  - backend/app/api/ai.py
  - backend/app/models/chat.py
  - frontend/src/components/GMPChatWidget.tsx
  - frontend/src/services/aiService.ts
  - docker-compose.yml
  - scripts/ingest_sops.py
code_patterns:
  - Service Layer Pattern (Controller → Service → Repository)
  - Singleton for Qdrant/Letta clients
  - Async/await throughout
  - Pydantic v2 schemas with extra="forbid"
  - RAG context injection with source attribution
  - Streaming responses for chat UI
  - Debounced search for real-time suggestions
test_patterns:
  - Unit tests for embedding/chunking logic
  - Integration tests for Letta agent responses
  - End-to-end tests for COA auto-generation flow
  - Mock Qdrant for offline testing
  - CAPA suggestion accuracy benchmarks
---

# Tech-Spec: P5 AI Supercharge — Letta-Powered GMP Compliance Assistant

**Created:** 2026-05-31

## Overview

### Problem Statement

QC analysts and reviewers face cognitive overload when navigating complex EU GMP requirements, SOP cross-references, and investigation procedures. Current pain points:

1. **Regulatory Lookup Friction**: Finding the correct SOP clause for a specific scenario requires manual document searching (5–15 minutes per query).
2. **OOS Investigation Guidance**: Analysts lack real-time assistance during Phase I/II investigations, leading to inconsistent root cause analysis.
3. **COA Drafting Overhead**: Creating compliant COA drafts from test results involves repetitive copy-paste and formatting (20–30 minutes per COA).
4. **Knowledge Silos**: Expert GMP knowledge is concentrated in senior staff; junior analysts lack on-demand access to compliance guidance.
5. **No AI Integration**: Despite having Letta agents running on KVM4, the LIMS has no interface to leverage RAG-powered compliance assistance.

### Solution

Deploy a comprehensive AI supercharge layer integrating five Letta-powered capabilities:

1. **GMP Expert Agent** — RAG-powered Q&A over the full SOP corpus (pp_qms_sops collection)
2. **SOP RAG Pipeline** — Automated ingestion pipeline for DOCX/PDF → chunk → embed → Qdrant
3. **CAPA Assistant Agent** — Interactive guidance through OOS Phase I/II investigations with root cause suggestions
4. **COA Auto-Generator** — Draft COA generation from specifications + test results with GMP-compliant formatting
5. **GMP Chat Widget** — Embedded frontend component for real-time analyst queries with streaming responses

### Scope

**In Scope:**
- Letta agent creation and configuration on KVM4 (5 agents)
- Qdrant collection setup and SOP ingestion (pp_qms_sops)
- Backend service layer for Letta API integration
- Frontend chat widget with streaming support
- CAPA assistant integration with OOS investigation workflow
- COA auto-generation endpoint
- Document ingestion CLI/script for new/revised SOPs
- SSH tunnel configuration documentation (ports 8283, 6333, 6507)

**Out of Scope:**
- Training custom LLM models (use anthropic/claude-sonnet-4-5 via Letta)
- Replacing human QP approval (AI assists, humans decide)
- Offline mode without SSH tunnel (assume tunnel operational)
- Mobile-native chat app (web widget only)
- Voice input/output (text only for GMP traceability)

## Context for Development

### Codebase Patterns

The P5 implementation follows established QC_LIMS patterns:

**Service Layer Architecture:**
```
API Router (ai.py)
    ↓
Service Layer (letta_service.py, capa_agent_service.py)
    ↓
External Client (LettaClient, QdrantClient)
    ↓
KVM4 Letta Stack (:8283, :6333, :6507)
```

**Existing P0–P4 Foundation:**
- `oos_service.py` — OOS lifecycle with Phase I/II states
- `specification.py` models — Spec parameters with dual limits
- `certificate.py` models — COA structure with approval chain
- `audit.py` — ALCOA++ audit trail middleware
- `qdrant_service.py` — Qdrant client singleton (P3)

**Key Integration Points:**
- CAPA Assistant → hooks into `oos.py` models and Phase I/II workflow
- COA Auto-Generator → consumes `Specification` + `TestResult` models
- GMP Chat Widget → mounts in main layout, accessible from all modules

### Files to Reference

| File | Purpose |
|------|---------|
| `backend/app/services/qdrant_service.py` | Existing Qdrant singleton pattern |
| `backend/app/models/oos.py` | OOSRecord, OOSPhase enums for CAPA integration |
| `backend/app/models/specification.py` | SpecParameter, Specification for COA generation |
| `backend/app/models/certificate.py` | CertificateOfAnalysis, TestResult models |
| `backend/app/api/oos.py` | OOS API endpoints to extend with CAPA suggestions |
| `backend/app/core/config.py` | Settings for Letta/Qdrant URLs |
| `scripts/ingest_sops.py` | Document ingestion pipeline (to create) |
| `frontend/src/components/` | Component directory for GMPChatWidget |

### Technical Decisions

**1. Letta Agent vs Direct LLM Calls**
- **Decision**: Use Letta agents with persistent memory
- **Rationale**: Agents retain facility context, conversation history, and RAG configuration across sessions; direct calls would lose context

**2. Voyage-3 Embeddings**
- **Decision**: voyage-3 (1024d) over OpenAI embeddings
- **Rationale**: Superior performance on regulatory/medical text; 1024d matches Qdrant collection config

**3. Chunking Strategy**
- **Decision**: 500 tokens with 50-token overlap, split by SOP section
- **Rationale**: Balances context preservation with retrieval precision; section-aware splitting maintains semantic coherence

**4. Streaming vs Batch Responses**
- **Decision**: Streaming for chat widget, batch for COA generation
- **Rationale**: Chat requires real-time UX; COA generation is single-shot with structured output

**5. SSH Tunnel Architecture**
- **Decision**: Document ports 8283 (Letta), 6333 (Qdrant), 6507 (MCP) with placeholder config
- **Rationale**: Actual tunnel TBD (key created ID 512752, API-attached); implementation assumes tunnel operational

## Implementation Plan

### Tasks

#### Task 1: Letta Service Layer Foundation
**Files**: `backend/app/services/letta_service.py`, `backend/app/core/config.py`

1.1. Extend `Settings` class:
```python
letta_base_url: str = Field(default="http://localhost:8283")
letta_mcp_url: str = Field(default="http://localhost:6507")
qdrant_url: str = Field(default="http://localhost:6333")
voyage_api_key: str = Field(default="")
```

1.2. Create `LettaService` singleton:
```python
class LettaService:
    _instance: ClassVar[Optional["LettaService"]] = None
    _client: Optional[Letta] = None
    
    def __init__(self):
        self.settings = get_settings()
        self._client = Letta(base_url=self.settings.letta_base_url)
```

1.3. Implement health check method for all three services

#### Task 2: Create 5 Letta Agents on KVM4
**Via Letta API calls** (documented for manual creation or automation script):

**Agent 1: GMP Expert Agent**
```python
agent = client.agents.create(
    name="GMP Expert Agent",
    model="anthropic/claude-sonnet-4-5",
    embedding="voyageai/voyage-3",
    system="""You are an EU GMP regulatory expert for Purely Plant GmbH QC laboratory.
Regulations: EudraLex Vol 4 Annex 1, 11, 15, 16; ICH Q10; WHO TRS 902; Ph. Eur. cannabis monographs.
Always cite specific SOP clauses using [Doc: X, Section: Y] format.
Provide bilingual answers (MK primary, EN secondary).""",
    memory_blocks=[
        {"label": "facility_context", "value": "Purely Plant GmbH — Licensed cannabis API manufacturer, North Macedonia", "limit": 500},
        {"label": "rag_collection", "value": "pp_qms_sops", "limit": 100},
    ]
)
```

**Agent 2: SOP Writer Agent**
- System prompt for bilingual SOP drafting
- Memory: SOP structure templates, format standards
- RAG: sop_templates collection

**Agent 3: CAPA Manager Agent**
- System prompt based on QCSOP 019 OOS investigation
- Memory: Root cause categories (5M: Man, Method, Machine, Material, Milieu)
- RAG: oos_records collection (anonymized)

**Agent 4: COA Generator Agent**
- System prompt for GMP-compliant COA drafting
- Memory: QCCoA 001 template structure
- No RAG needed — operates on provided spec + results

**Agent 5: QMS Orchestrator Agent**
- System prompt for query routing
- Memory: Agent capabilities map
- Routes user queries to appropriate specialist agent

#### Task 3: SOP RAG Pipeline — Document Ingestion
**Files**: `scripts/ingest_sops.py`, `backend/app/services/sop_rag_service.py`

3.1. Implement DOCX/PDF text extraction:
```python
class SOPExtractor:
    def extract_docx(self, path: Path) -> dict:
        doc = Document(path)
        return {"metadata": self._parse_header(doc), "sections": self._parse_sections(doc)}
    
    def extract_pdf(self, path: Path) -> str:
        return extract_text(path)
```

3.2. Implement chunking with section awareness:
```python
def chunk_sections(sections: dict) -> list[dict]:
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

3.3. Implement embedding and upsert:
```python
async def ingest_document(self, file_path: Path, doc_metadata: dict) -> int:
    # Extract → Chunk → Embed → Upsert to Qdrant
    # Return number of chunks ingested
```

3.4. Create CLI script for batch ingestion:
```bash
python scripts/ingest_sops.py --folder /path/to/sops --collection pp_qms_sops
```

#### Task 4: CAPA Assistant Integration
**Files**: `backend/app/services/capa_agent_service.py`, `backend/app/api/oos.py`

4.1. Create `CAPAAgentService`:
```python
class CAPAAgentService:
    def __init__(self):
        self.letta = get_letta_service()
        self.agent_id = "capa-manager-agent-id"  # From Task 2
    
    async def suggest_phase_i_checks(self, oos_id: UUID) -> list[str]:
        """Suggest laboratory investigation checks based on OOS context."""
        # Fetch OOS context, query CAPA agent, return structured suggestions
    
    async def suggest_root_causes(self, oos_id: UUID) -> list[dict]:
        """Suggest potential root causes for Phase II investigation."""
        # Use RAG over historical OOS records for pattern matching
    
    async def draft_investigation_form(self, oos_id: UUID, phase: int) -> str:
        """Draft QCSOP 019-A01 (Phase I) or A02 (Phase II) form content."""
```

4.2. Extend OOS API with AI endpoints:
```python
@router.post("/oos/{oos_id}/ai/suggest-checks")
async def suggest_phase_i_checks(oos_id: UUID, service: CAPAAgentService = Depends()):
    suggestions = await service.suggest_phase_i_checks(oos_id)
    return {"suggestions": suggestions, "source": "CAPA Agent", "confidence": "high"}

@router.post("/oos/{oos_id}/ai/suggest-causes")
async def suggest_root_causes(oos_id: UUID, service: CAPAAgentService = Depends()):
    causes = await service.suggest_root_causes(oos_id)
    return {"causes": causes, "source": "CAPA Agent + RAG"}
```

#### Task 5: COA Auto-Generator
**Files**: `backend/app/services/coa_auto_generator.py`, `backend/app/api/coa.py`

5.1. Create `COAAutoGenerator`:
```python
class COAAutoGenerator:
    def __init__(self):
        self.letta = get_letta_service()
        self.agent_id = "coa-generator-agent-id"
    
    async def generate_draft(
        self,
        batch_id: UUID,
        specification_id: UUID,
        test_results: list[TestResult]
    ) -> dict:
        """Generate COA draft content from inputs."""
        # Build context: spec params + results + QCCoA 001 template structure
        # Query COA Generator agent
        # Return structured COA content (not yet saved — draft only)
        
    async def suggest_remarks(self, parameter: str, result: str, spec_limits: dict) -> str:
        """Generate GMP-compliant remarks for borderline/out-of-trend results."""
```

5.2. Add API endpoint:
```python
@router.post("/coa/generate-draft")
async def generate_coa_draft(
    request: COADraftRequest,
    generator: COAAutoGenerator = Depends()
):
    draft = await generator.generate_draft(
        batch_id=request.batch_id,
        specification_id=request.specification_id,
        test_results=request.test_results
    )
    return {"draft": draft, "requires_review": True, "generated_by": "COA Generator Agent"}
```

#### Task 6: GMP Chat Widget (Frontend)
**Files**: `frontend/src/components/GMPChatWidget.tsx`, `frontend/src/services/aiService.ts`

6.1. Create `aiService.ts`:
```typescript
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{doc: string; section: string}>;
  timestamp: Date;
}

export class AIService {
  async *streamChat(message: string, context?: string): AsyncGenerator<ChatMessage> {
    // SSE streaming to /api/v1/ai/chat
  }
  
  async queryGMPExpert(query: string): Promise<ChatMessage> {
    // Direct query to GMP Expert agent
  }
}
```

6.2. Create `GMPChatWidget.tsx`:
```typescript
interface GMPChatWidgetProps {
  context?: 'general' | 'oos' | 'coa' | 'spec';
  contextId?: string;
}

export const GMPChatWidget: React.FC<GMPChatWidgetProps> = ({ context, contextId }) => {
  // Collapsible chat panel
  // Message history with source attribution
  // Context-aware quick actions ("Explain OOS Phase I", "Draft COA remarks", etc.)
  // Streaming message display
}
```

6.3. UI Features:
- Collapsible floating button (bottom-right)
- Expandable chat panel with message history
- Source citations with [Doc: X, Section: Y] links
- Quick action buttons for common queries
- Export chat to PDF (for audit trail)

#### Task 7: AI API Router
**Files**: `backend/app/api/ai.py`

7.1. Create main AI router:
```python
router = APIRouter(prefix="/ai", tags=["AI Assistant"])

@router.post("/chat")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint using QMS Orchestrator agent."""
    # SSE response with streaming tokens

@router.post("/query-gmp-expert")
async def query_gmp_expert(request: ExpertQueryRequest):
    """Direct query to GMP Expert agent with RAG context."""

@router.get("/health")
async def ai_health_check():
    """Health check for Letta + Qdrant + MCP connectivity."""
```

#### Task 8: SSH Tunnel Configuration
**Documentation in spec + deployment notes**

8.1. Document tunnel setup:
```bash
# SSH tunnel for Letta API + Qdrant + MCP
ssh -i /a0/usr/workdir/ssh/kvm4_id_ed25519_new \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=60 \
    -L 8283:localhost:8283 \
    -L 6333:localhost:6333 \
    -L 6507:localhost:6507 \
    -N -f root@srv1231216.hstgr.cloud
```

8.2. Port mapping:
| Local Port | Service | KVM4 Endpoint | Purpose |
|------------|---------|---------------|---------|
| 8283 | Letta API | localhost:8283 | Agent creation, messaging |
| 6333 | Qdrant | localhost:6333 | Vector search, SOP retrieval |
| 6507 | MCP Rust | localhost:6507 | Model context protocol |

8.3. Health check endpoint verifies all three services reachable

#### Task 9: Document Ingestion Workflow
**File**: `scripts/ingest_sops.py` (CLI)

9.1. Support operations:
```bash
# Full folder ingestion
python scripts/ingest_sops.py --folder ./sops --collection pp_qms_sops

# Single document
python scripts/ingest_sops.py --file QCSOP_019_v03.docx --collection pp_qms_sops

# Verify ingestion
python scripts/ingest_sops.py --verify --collection pp_qms_sops

# Incremental sync (detect new/modified files)
python scripts/ingest_sops.py --sync --folder ./sops --collection pp_qms_sops
```

9.2. Version handling: Tag superseded documents, never delete (ALCOA++ Complete)

#### Task 10: Testing & Validation
**Files**: `backend/tests/test_ai_*.py`

10.1. Unit tests:
- `test_letta_service.py` — Mock Letta client, test agent query
- `test_sop_rag.py` — Test chunking, embedding, Qdrant upsert
- `test_coa_generator.py` — Test prompt construction, response parsing

10.2. Integration tests:
- `test_capa_integration.py` — Full OOS → suggestion flow
- `test_chat_streaming.py` — SSE endpoint testing

10.3. Benchmarks:
- CAPA suggestion accuracy (target: >80% relevant suggestions)
- RAG retrieval precision (target: top-3 chunks contain answer)
- COA generation time (target: <10 seconds)

### Acceptance Criteria

**AC-1: Letta Service Connectivity**
- [ ] Health check endpoint returns "healthy" for Letta API, Qdrant, and MCP
- [ ] All 5 agents created on KVM4 with correct system prompts
- [ ] SSH tunnel ports documented (8283, 6333, 6507)

**AC-2: SOP RAG Pipeline**
- [ ] DOCX ingestion script processes QCSOP documents without errors
- [ ] Chunks stored in Qdrant pp_qms_sops collection with metadata
- [ ] Semantic search returns relevant SOP sections for test queries
- [ ] Version tagging handles superseded documents correctly

**AC-3: GMP Expert Agent**
- [ ] Agent responds to compliance questions with [Doc: X, Section: Y] citations
- [ ] Bilingual responses provided (MK primary, EN secondary)
- [ ] Response time <5 seconds for RAG queries
- [ ] Chat history maintained per user session

**AC-4: CAPA Assistant Integration**
- [ ] Phase I investigation suggestions include all 5M categories
- [ ] Root cause suggestions reference historical OOS patterns (RAG)
- [ ] Investigation form draft generated with proper QCSOP 019-A01/A02 structure
- [ ] Suggestions logged in audit trail with AI attribution

**AC-5: COA Auto-Generator**
- [ ] Draft COA generated from spec + results in <10 seconds
- [ ] Output follows QCCoA 001 template structure
- [ ] Remarks suggested for borderline/out-of-trend results
- [ ] Generated drafts marked "AI-ASSISTED" pending human review

**AC-6: GMP Chat Widget**
- [ ] Widget mounts in all LIMS modules (floating button)
- [ ] Streaming responses display progressively
- [ ] Source citations link to SOP documents
- [ ] Chat exportable to PDF for audit trail
- [ ] Quick action buttons for context-specific queries

**AC-7: ALCOA++ Compliance**
- [ ] All AI interactions logged in audit trail
- [ ] AI-generated content attributed ("Generated by: Agent Name")
- [ ] Human verification required before AI suggestions become official records
- [ ] No AI-generated content bypasses electronic signature requirements

## Additional Context

### Dependencies

**External Services (KVM4):**
- Letta v0.16.7 (API port 8283, MCP port 6507)
- Qdrant v1.13.6 (port 6333, collection: pp_qms_sops)
- VoyageAI API (embedding model: voyage-3)

**Python Packages:**
```
letta-client>=0.16.7
qdrant-client>=1.13.0
voyageai>=0.2.0
python-docx>=1.1.0
pdfminer.six>=20231228
langchain-text-splitters>=0.0.1
```

**Frontend:**
- React 18+ with TypeScript
- SSE (EventSource) for streaming
- Tailwind CSS for widget styling

### Testing Strategy

**Phase 1: Unit Testing (Week 1)**
- Mock all external services (Letta, Qdrant)
- Test prompt construction and response parsing
- Validate chunking and embedding logic

**Phase 2: Integration Testing (Week 2)**
- Test with actual KVM4 services via SSH tunnel
- Validate RAG retrieval quality
- Benchmark CAPA suggestion accuracy

**Phase 3: User Acceptance Testing (Week 3)**
- QC analysts test chat widget for 1 week
- Feedback on suggestion relevance
- Refine prompts based on usage patterns

**Phase 4: Validation (Week 4)**
- GMP auditor review of AI audit trail logging
- Verify ALCOA++ compliance for AI-generated records
- Document AI usage in validation package

### Notes

**SSH Tunnel Status:**
- Key created: ID 512752 (API-attached)
- Tunnel not yet operational (blocked)
- Implementation assumes tunnel will work; health checks will surface connectivity issues

**Agent Prompt Refinement:**
Initial prompts are based on SOP content. Expect 2–3 refinement cycles based on:
- Response relevance scoring
- User feedback on bilingual output quality
- Citation accuracy (verify [Doc: X, Section: Y] format)

**Data Privacy:**
- OOS records used for CAPA RAG must be anonymized (no batch numbers, dates shifted)
- Audit trail captures AI interactions for regulatory inspection
- No patient data in AI prompts (cannabis API, not patient-specific)

**Future Enhancements (Post-P5):**
- Chromeleon/Empower integration for automated result ingestion
- Voice-to-text for cleanroom use (if approved by QA)
- Multi-language expansion (German, Albanian)
- Predictive analytics for OOS trending

**Commit Strategy:**
- Task 1–2: `feature/p5-letta-service`
- Task 3: `feature/p5-sop-rag`
- Task 4: `feature/p5-capa-agent`
- Task 5: `feature/p5-coa-generator`
- Task 6–7: `feature/p5-chat-widget`
- Final merge: PR to main with full test suite

---

**Document Control:**
- Author: Amelia (BMAD Developer Agent)
- Reviewer: Winston (Architect) — pending
- Approver: BMAD Master — pending
- Version: 1.0-Draft
- Related: spec-p0-foundation.md, spec-p1-specification-linkage.md, spec-p2-sample-lifecycle.md, spec-p3-progressive-review.md, spec-p4-oos-integration.md

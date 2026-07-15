#!/usr/bin/env python3
import asyncio
import json as json_module
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Load environment variables from project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)
logger_setup = logging.getLogger("ENV")
logger_setup.info(f"Loaded .env from: {env_path}")

# Add current directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from auth import verify_api_key
from document_service import (
    get_document_by_code,
    get_file_path,
    get_hierarchy_json,
    get_stats,
    scan_docx_directory,
    scan_pdf_directory,
)
from qms_database import QMSDatabase
from security_middleware import register_security_middleware
from document_code_service import DocumentCodeService, suggest_code

from CONTENT_CREATOR_FRAMEWORK.letta_service import LettaService
from CONTENT_CREATOR_FRAMEWORK.letta_workflow import (
    LettaSOPWorkflow,
    _detect_gap_topic,
    _enrich_passage_metadata,
)
from CONTENT_CREATOR_FRAMEWORK.agent_definitions import AGENT_CONFIGS
from CONTENT_CREATOR_FRAMEWORK.letta_tools import register_all_tools

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QMS-API")

from fastapi.middleware.cors import CORSMiddleware

# Enhanced FastAPI app configuration with OpenAPI metadata
app = FastAPI(
    title="Cannabis EU GMP QMS Creator API",
    description="Comprehensive REST API for QMS document management and SOP generation for cannabis facilities with EU GMP compliance.",
    version="1.0.0",
    contact={
        "name": "QMS Support Team",
        "email": "qms@example.com",
    },
    license_info={
        "name": "Proprietary License",
    },
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Register security middleware
register_security_middleware(app)

# Add rate limiting to the app
app.state.limiter = limiter


def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors.

    Must return a Response — Starlette invokes the handler result as an ASGI
    callable, so returning a plain dict raises ``TypeError`` instead of a 429.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Global database instance
db = QMSDatabase(PROJECT_ROOT)

# ── Letta Service ──────────────────────────────────────────
letta_service: Optional[LettaService] = None
letta_workflow: Optional[LettaSOPWorkflow] = None


def _init_letta():
    """Initialize Letta service, agents, archives, and workflow."""
    global letta_service, letta_workflow
    try:
        letta_url = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
        letta_service = LettaService(base_url=letta_url)

        # Register custom tools
        register_all_tools(letta_service)

        # Create/retrieve archives
        letta_service.ensure_archives()

        # Create/retrieve agents
        letta_service.ensure_agents(AGENT_CONFIGS)

        # Create workflow orchestrator
        letta_workflow = LettaSOPWorkflow(letta_service, project_root=PROJECT_ROOT)

        logger.info("Letta service initialized successfully")
    except Exception as e:
        logger.error(f"Letta initialization failed: {e}")
        logger.warning("SOP generation will be unavailable until Letta server is running")


_init_letta()


def load_questionnaire_schema() -> Dict[str, Any]:
    """Load the questionnaire schema from YAML file"""
    schema_path = (
        Path(PROJECT_ROOT)
        / "CONTENT_CREATOR_FRAMEWORK"
        / "content_creator_questionnaire_schema.yaml"
    )
    if not schema_path.exists():
        logger.error(f"Schema file not found at {schema_path}")
        return {}

    with open(schema_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class SOPRequest(BaseModel):
    sop_name: str
    sop_type: str
    keywords: List[str] = []
    department: Optional[str] = "Quality"
    target_audience: List[str] = ["All Personnel"]


class QuestionnaireSubmission(BaseModel):
    sop_request: SOPRequest
    answers: Dict[str, Any]


class GenerateResponse(BaseModel):
    status: str
    output_files: List[str]
    audit_report: Optional[Dict[str, Any]] = None


# Response Models for OpenAPI Documentation
class HealthResponse(BaseModel):
    """Health check response"""

    status: str


class DocumentMetadataResponse(BaseModel):
    """Metadata for a single document"""

    id: str
    code: str
    title: str
    version: str
    pdfPath: Optional[str] = None
    docxPath: Optional[str] = None


class DocumentStatsResponse(BaseModel):
    """Document library statistics"""

    totalDocuments: int
    totalAnnexes: int
    totalFiles: int
    pdfFiles: int
    docxFiles: int
    chapters: int
    lastUpdated: str


class ChapterData(BaseModel):
    """Chapter information"""

    id: str
    code: str
    name: str
    folder: str
    documentCount: int
    documents: List[Dict[str, Any]] = []


class DocumentHierarchyResponse(BaseModel):
    """Complete document hierarchy"""

    chapters: List[ChapterData]
    stats: DocumentStatsResponse


class FileListResponse(BaseModel):
    """List of available files"""

    pdf: List[str]
    docx: List[str]
    pdfCount: int
    docxCount: int


class StatusResponse(BaseModel):
    """Generic status response"""

    status: str


class RAGQueryRequest(BaseModel):
    """Request for RAG vector search query"""
    query: str
    top_k: int = 5


# ============================================================================
# 9-AGENT WORKFLOW REQUEST/RESPONSE MODELS
# ============================================================================


class WorkflowMetadata(BaseModel):
    """Agent 1 metadata for workflow initialization"""
    sop_title: str
    short_description: str
    department: str
    document_code: str
    annexes: List[Dict[str, str]] = []  # [{title, type}]
    effective_date: Optional[str] = None


class WorkflowStartRequest(BaseModel):
    """Request to start 9-agent workflow"""
    metadata: WorkflowMetadata


class WorkflowQuestion(BaseModel):
    """Single questionnaire question"""
    id: str
    text: str
    type: str  # single_choice, multi_choice, text, number
    options: Optional[List[Dict[str, str]]] = None  # [{value, label, description}]
    required: bool = True
    rag_context: Optional[str] = None


class WorkflowQuestionsResponse(BaseModel):
    """Response containing questions for an agent"""
    workflow_id: str
    agent_number: int
    agent_name: str
    questions: List[WorkflowQuestion]
    total_questions: int
    current_section: str


class AgentSubmitRequest(BaseModel):
    """Submit answers to agent questionnaire"""
    workflow_id: str
    answers: Dict[str, Any]


class AgentSubmitResponse(BaseModel):
    """Response after submitting agent answers"""
    status: str  # success, error
    next_agent: Optional[int] = None
    message: str


class QAReviewResponse(BaseModel):
    """Agent 6 QA review report"""
    overall_score: int  # 0-100
    regulatory_compliance: int
    internal_consistency: int
    completeness: int
    recommendations: List[Dict[str, Any]]  # [{section, issue, options}]
    section_previews: Dict[str, str]  # Section ID → preview text


class QAApprovalRequest(BaseModel):
    """Request to approve QA review"""
    workflow_id: str
    selected_options: Dict[str, str]  # recommendation_id → selected_option
    custom_edits: Optional[Dict[str, str]] = None


class EditRequest(BaseModel):
    """Canvas-like edit request"""
    section_id: str
    selected_text: str
    edit_type: str  # comment, edit_suggestion, flag
    content: str  # Comment text or suggested replacement
    user_id: Optional[str] = None


class EditResponse(BaseModel):
    """Response to edit request"""
    status: str
    assigned_agent: int
    clarification_needed: bool = False
    clarification_questions: Optional[List[Dict[str, Any]]] = None
    message: str


class AnnexInfo(BaseModel):
    """Annex metadata"""
    id: str
    title: str
    annex_type: str  # form, template, checklist, flowchart
    label: str  # Annex A, Annex B, etc.
    status: str  # pending, generating, completed
    preview_url: Optional[str] = None
    download_url: Optional[str] = None


class DocumentCodeRequest(BaseModel):
    """Request for document code suggestion"""
    title: str
    keywords: List[str] = []


class DocumentCodeResponse(BaseModel):
    """Response with suggested document code"""
    code: str
    department: str
    department_name: str
    family: str
    family_name: str
    sop_number: int
    confidence: float
    reasoning: str


class AutofillRequest(BaseModel):
    """Request for AI auto-fill of questionnaire answers"""
    sop_request: SOPRequest
    answers: Dict[str, Any]
    question_ids: Optional[List[str]] = None


class AutofillSuggestion(BaseModel):
    """Single auto-fill suggestion"""
    answer: Any
    confidence: float
    reasoning: str


class AutofillResponse(BaseModel):
    """Response with auto-fill suggestions"""
    suggestions: Dict[str, AutofillSuggestion]
    research_summary: Optional[str] = None


class EnhanceTextRequest(BaseModel):
    """Request for AI text enhancement"""
    text: str
    field_type: str  # sopTitle, shortDescription, etc.
    context: Optional[Dict[str, Any]] = None


class EnhanceTextResponse(BaseModel):
    """Response with enhanced text"""
    enhanced_text: str
    improvements: List[str]  # List of improvements made


class DynamicQuestionRequest(BaseModel):
    """Request for next dynamic question"""
    workflow_id: str
    agent_number: int
    previous_answers: Dict[str, Any]
    accumulated_context: Optional[str] = None


class DynamicQuestionResponse(BaseModel):
    """Response with next dynamic question"""
    question: Optional[WorkflowQuestion] = None  # None if done
    is_final: bool = False  # True if this is the last question
    estimated_remaining: int = 0  # Estimated questions remaining
    progress_percentage: int = 0


@app.on_event("startup")
async def startup_event():
    """Initial hydration of database if empty"""
    existing_docs = db.get_all_documents()
    if not existing_docs:
        logger.info("Initializing registry from baseline...")
        # Very minimal setup for initial view
        baseline = [
            {
                "id": "qa-001",
                "code": "QA_00.01",
                "title": "Quality Manual",
                "department": "Quality Assurance",
                "status": "completed",
                "version": "1.0",
                "annexes": []
            }
        ]
        db.initialize_registry_from_list(baseline)

def register_generated_sop(sop_request: SOPRequest, results: Dict[str, Any]):
    """Register a newly generated SOP in the document database"""
    if results.get("status") == "completed" and results.get("output_files"):
        primary_file = results["output_files"][0]
        filename = os.path.basename(primary_file)
        
        # Parse standard name: CODE_TITLE_v1.0_EN.md
        parts = filename.replace(".md", "").split("_")
        code = f"{parts[0]}_{parts[1]}" if len(parts) > 1 else sop_request.sop_name
        
        doc_data = {
            "id": f"doc-{code.lower().replace('.', '-')}",
            "code": code,
            "title": sop_request.sop_name,
            "department": sop_request.department or "Quality",
            "status": "completed",
            "version": "1.0",
            "annexes": [],
            "last_modified": datetime.now().isoformat()
        }
        db.upsert_document(doc_data)
        logger.info(f"Registered document {code} in database.")

@app.get("/")
def read_root():
    return {"message": "Welcome to Cannabis EU GMP QMS Creator API"}


@app.get("/api/documents")
def get_documents():
    """Get all documents in the QMS registry"""
    return db.get_all_documents()


@app.post(
    "/api/documents",
    summary="Create/Update Document",
    description="Create or update a document in the registry (requires API Key).",
    tags=["Document Management"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
def upsert_document(request: Request, document: Dict[str, Any]):
    """
    Update or add a document to the registry (requires API Key).

    Requires authentication via X-API-Key header.
    """
    db.upsert_document(document)
    return {"status": "success"}


@app.get(
    "/questionnaire-schema",
    summary="Get Questionnaire Schema",
    description="Retrieve the base questionnaire schema for SOP creation.",
    tags=["SOP Generation"],
)
def get_questionnaire_schema():
    """
    Get the full questionnaire schema.

    Returns:
        dict: Complete questionnaire schema with all sections and questions
    """
    return load_questionnaire_schema()


@app.post(
    "/initialize-questionnaire",
    summary="Initialize Questionnaire",
    description="Initialize a questionnaire session with RAG-enriched schema based on SOP request.",
    tags=["SOP Generation"],
)
@limiter.limit("20/minute")
async def initialize_questionnaire(request: Request, sop_request: SOPRequest):
    """
    Initialize a questionnaire session.
    Returns a schema ENRICHED with RAG-based options and facility data.

    Args:
        request: SOP request with name, type, and context

    Returns:
        dict: Enriched questionnaire schema with facility-specific data
    """
    try:
        base_schema = load_questionnaire_schema()
        # Enrich with Letta RAG if available
        if letta_service:
            logger.info(f"Enriching schema with Letta RAG for {sop_request.sop_name}")
            rag_results = letta_service.dual_db_search(
                f"{sop_request.sop_name} {sop_request.sop_type}", db1_top_k=3, db2_top_k=3
            )
            if rag_results.get("db1_results") or rag_results.get("db2_results"):
                base_schema["_rag_context"] = rag_results
        return base_schema

    except Exception as e:
        logger.error(f"Schema Initialization Error: {e}")
        return load_questionnaire_schema()


@app.post(
    "/analyze",
    summary="Analyze SOP Request",
    description="Run initial RAG-based analysis on a SOP request to gather relevant content.",
    tags=["SOP Generation"],
)
@limiter.limit("20/minute")
async def analyze_request(request: Request, sop_request: SOPRequest):
    """
    Run initial analysis for a SOP request.

    Args:
        request: SOP request details

    Returns:
        dict: Analysis results with relevant documents and recommendations
    """
    try:
        if not letta_service:
            raise HTTPException(status_code=503, detail="Letta service not available")
        results = letta_service.dual_db_search(
            f"{sop_request.sop_name} {sop_request.sop_type} EU GMP cannabis", db1_top_k=5, db2_top_k=5
        )
        results["sop_name"] = sop_request.sop_name
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate SOP",
    description="Generate a complete SOP document through the full workflow with all stages. Requires API Key.",
    tags=["SOP Generation"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def generate_sop(request: Request, sop_request: SOPRequest):
    """
    Generate a new SOP through the full workflow.

    Requires authentication via X-API-Key header.

    Args:
        request: SOP request with specifications

    Returns:
        GenerateResponse: Generated files and audit report

    Raises:
        HTTPException: 500 if generation fails
    """
    try:
        if not letta_workflow:
            raise HTTPException(status_code=503, detail="Letta workflow not available")

        logger.info(f"Generating SOP: {sop_request.sop_name}")
        results = await letta_workflow.execute(
            sop_name=sop_request.sop_name,
            sop_code=sop_request.sop_name,  # Will be refined
            department=sop_request.department or "Quality",
        )

        if results.get("errors"):
            logger.warning(f"Generation had {len(results['errors'])} errors")

        output_files = [results["docx_path"]] if results.get("docx_path") else []

        return GenerateResponse(
            status="completed" if not results.get("errors") else "completed_with_warnings",
            output_files=output_files,
            audit_report={"quality_report": results.get("quality_report", "")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/submit-questionnaire",
    response_model=GenerateResponse,
    summary="Submit Questionnaire",
    description="Submit completed questionnaire with answers to trigger SOP generation. Requires API Key.",
    tags=["SOP Generation"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def submit_questionnaire(request: Request, submission: QuestionnaireSubmission):
    """
    Submit questionnaire answers and trigger generation.

    Requires authentication via X-API-Key header.

    Args:
        submission: Questionnaire submission with answers

    Returns:
        GenerateResponse: Generated documents and audit report

    Raises:
        HTTPException: 500 if submission processing fails
    """
    try:
        if not letta_workflow:
            raise HTTPException(status_code=503, detail="Letta workflow not available")

        logger.info(f"Processing questionnaire for: {submission.sop_request.sop_name}")

        results = await letta_workflow.execute(
            sop_name=submission.sop_request.sop_name,
            sop_code=submission.sop_request.sop_name,
            department=submission.sop_request.department or "Quality",
            user_selections=submission.answers,
        )

        output_files = [results["docx_path"]] if results.get("docx_path") else []
        status = "completed" if not results.get("errors") else "completed_with_warnings"

        if status == "completed":
            register_generated_sop(submission.sop_request, {
                "status": "completed",
                "output_files": output_files,
            })

        return GenerateResponse(
            status=status,
            output_files=output_files,
            audit_report={"quality_report": results.get("quality_report", "")},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submission Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AI-POWERED QUESTIONNAIRE ENHANCEMENT ENDPOINTS
# ============================================================================


@app.post(
    "/api/generate-stream",
    summary="Generate SOP with SSE streaming",
    description="Generate an SOP with real-time agent progress via Server-Sent Events. Requires API Key.",
    tags=["Generation"],
    dependencies=[Depends(verify_api_key)],
)
async def generate_stream(request: Request):
    """Stream SOP generation progress as Server-Sent Events."""
    import queue as thread_queue
    import threading

    if not letta_workflow:
        raise HTTPException(status_code=503, detail="Letta service not available")

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")

    sop_name = body.get("sop_name", "Untitled SOP")
    sop_code = body.get("sop_code", "XX_00.00")
    department = body.get("department", "")
    facility_type = body.get("facility_type", "Cannabis EU GMP")
    document_type = body.get("document_type", "SOP")
    answers = body.get("answers", {})
    annexes = body.get("annexes", [])

    q = thread_queue.Queue()

    def on_progress(event_type: str, agent: str, content=None):
        data = {"agent": agent}
        if content:
            data["content"] = content
        q.put({"event": event_type, "data": data})

    def run_workflow():
        try:
            import asyncio as _aio
            loop = _aio.new_event_loop()
            _aio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(letta_workflow.execute(
                    sop_name=sop_name,
                    sop_code=sop_code,
                    department=department,
                    facility_type=facility_type,
                    document_type=document_type,
                    user_inputs=answers,
                    user_selections={"annexes": annexes},
                    on_progress=on_progress,
                ))
            finally:
                loop.close()
            q.put({
                "event": "generation_complete",
                "data": {
                    "docx_path": result.get("docx_path", ""),
                    "quality_report": result.get("quality_report", ""),
                },
            })
        except Exception as e:
            logger.error(f"SSE workflow error: {e}", exc_info=True)
            q.put({"event": "error", "data": {"error": str(e)}})
        finally:
            q.put(None)  # Sentinel to signal end

    async def event_generator():
        t = threading.Thread(target=run_workflow, daemon=True)
        t.start()
        while True:
            try:
                item = q.get_nowait()
            except thread_queue.Empty:
                await asyncio.sleep(0.2)
                continue
            if item is None:
                break
            yield f"data: {json_module.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/api/suggest-document-code",
    response_model=DocumentCodeResponse,
    summary="Suggest Document Code",
    description="AI-powered document code suggestion based on SOP title analysis.",
    tags=["AI Enhancement"],
)
@limiter.limit("30/minute")
async def suggest_document_code_endpoint(request: Request, code_request: DocumentCodeRequest):
    """
    Suggest an appropriate document code based on SOP title.

    Analyzes the title to determine:
    - Department (QA, QC, PRO, etc.)
    - Family (QA_00, QC_01, PRO_01, etc.)
    - Next available SOP number in that family

    Args:
        code_request: Title and optional keywords

    Returns:
        DocumentCodeResponse: Suggested code with confidence and reasoning
    """
    try:
        logger.info(f"Suggesting document code for: {code_request.title}")

        # Get registry path
        registry_path = Path(PROJECT_ROOT) / "config" / "document_registry.yaml"

        # Use the suggest_code function (no LLM client needed, uses heuristics)
        suggestion = suggest_code(
            title=code_request.title,
            keywords=code_request.keywords,
            registry_path=str(registry_path),
        )

        return DocumentCodeResponse(**suggestion)

    except Exception as e:
        logger.error(f"Document Code Suggestion Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/autofill-questions",
    response_model=AutofillResponse,
    summary="Auto-fill Questionnaire",
    description="AI-powered auto-fill for unanswered questionnaire questions using RAG and research.",
    tags=["AI Enhancement"],
)
@limiter.limit("10/minute")
async def autofill_questions_endpoint(request: Request, autofill_request: AutofillRequest):
    """
    Auto-fill unanswered questionnaire questions using AI.

    Uses multiple sources:
    - RAG from existing documents
    - LLM research on the topic
    - Regulatory requirements context

    Args:
        autofill_request: SOP request, current answers, and optional question IDs

    Returns:
        AutofillResponse: Suggestions for each unanswered question
    """
    try:
        logger.info(f"Auto-filling questions for: {autofill_request.sop_request.sop_name}")

        # Load schema
        base_schema = load_questionnaire_schema()
        enriched_schema = base_schema

        if not letta_service:
            raise HTTPException(status_code=503, detail="Letta service not available")

        # Detect unanswered questions
        suggestions = {}
        current_answers = autofill_request.answers or {}
        question_ids = autofill_request.question_ids

        # Collect all questions from schema
        all_questions = []
        for section_key, section_data in enriched_schema.items():
            if section_key in ['metadata', 'output_config']:
                continue
            if isinstance(section_data, list):
                for q in section_data:
                    if isinstance(q, dict) and 'id' in q:
                        all_questions.append(q)
            elif isinstance(section_data, dict):
                for q_key, q_data in section_data.items():
                    if isinstance(q_data, dict):
                        q_data['id'] = q_key
                        all_questions.append(q_data)

        # Filter to unanswered or specified questions
        questions_to_fill = []
        for q in all_questions:
            q_id = q.get('id', '')
            # Skip if already answered
            if q_id in current_answers and current_answers[q_id]:
                continue
            # If specific IDs requested, filter to those
            if question_ids and q_id not in question_ids:
                continue
            questions_to_fill.append(q)

        # Generate suggestions for each question
        for question in questions_to_fill[:10]:  # Limit to 10 to avoid timeout
            q_id = question.get('id', '')
            q_text = question.get('text', question.get('description', ''))
            q_type = question.get('type', 'text')
            q_options = question.get('options', [])

            # Use Letta purpose agent for autofill (it has GMP context)
            prompt = (
                f"Answer this QMS questionnaire question for SOP '{autofill_request.sop_request.sop_name}'.\n"
                f"Question: {q_text}\n"
                f"Type: {q_type}\n"
                f"Options: {q_options if q_options else 'Free text'}\n\n"
                f"Return JSON only: {{\"answer\": \"your answer\", \"confidence\": 0.0-1.0, \"reasoning\": \"brief explanation\"}}"
            )

            try:
                import re
                import json as json_mod
                response = letta_service.send_message("purpose", prompt)
                json_match = re.search(r'\{[^{}]*\}', response)
                if json_match:
                    result = json_mod.loads(json_match.group())
                    suggestions[q_id] = AutofillSuggestion(
                        answer=result.get("answer", ""),
                        confidence=float(result.get("confidence", 0.7)),
                        reasoning=result.get("reasoning", "AI-generated suggestion")
                    )
            except Exception as e:
                logger.warning(f"Failed to generate answer for {q_id}: {e}")
                continue

        return AutofillResponse(
            suggestions=suggestions,
            research_summary=f"Generated {len(suggestions)} suggestions for {autofill_request.sop_request.sop_name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Autofill Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/document-families",
    summary="Get Document Families",
    description="Get all available document families for code assignment.",
    tags=["AI Enhancement"],
)
def get_document_families():
    """
    Get all available document families and their descriptions.

    Returns:
        dict: Family codes mapped to names
    """
    try:
        service = DocumentCodeService()
        return service.get_all_families()
    except Exception as e:
        logger.error(f"Families Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API health status and connectivity.",
    tags=["System"],
)
def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        HealthResponse: Status of the API
    """
    return {"status": "healthy"}


# ============================================================================
# DOCUMENT BROWSER API ENDPOINTS
# ============================================================================


@app.get(
    "/api/hierarchy",
    response_model=DocumentHierarchyResponse,
    summary="Get Document Hierarchy",
    description="Retrieve the complete document hierarchy organized by chapters with statistics.",
    tags=["Document Browser"],
)
def get_document_hierarchy():
    """
    Get the full document hierarchy organized by chapters.

    Returns:
        DocumentHierarchyResponse: Chapters with documents and statistics
    """
    try:
        return {
            "chapters": get_hierarchy_json(),
            "stats": get_stats()
        }
    except Exception as e:
        logger.error(f"Hierarchy Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/stats",
    response_model=DocumentStatsResponse,
    summary="Get Document Statistics",
    description="Retrieve comprehensive statistics about the QMS document library.",
    tags=["Document Browser"],
)
def get_document_stats():
    """
    Get document statistics for the dashboard.

    Returns:
        DocumentStatsResponse: Statistics about documents, annexes, and files
    """
    try:
        return get_stats()
    except Exception as e:
        logger.error(f"Stats Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/documents/{code}",
    response_model=DocumentMetadataResponse,
    summary="Get Document Metadata",
    description="Retrieve metadata for a specific document by its code.",
    tags=["Document Browser"],
)
def get_document_metadata(code: str):
    """
    Get metadata for a specific document by code.

    Args:
        code: The document code (e.g., "QA-001")

    Returns:
        DocumentMetadataResponse: Document metadata including paths

    Raises:
        HTTPException: 404 if document not found
    """
    try:
        doc = get_document_by_code(code)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {code} not found")

        # Convert to dict
        if hasattr(doc, "__dict__"):
            return {
                "id": doc.id,
                "code": doc.code,
                "title": doc.title,
                "version": getattr(doc, "version", "1.0"),
                "pdfPath": getattr(doc, "pdf_path", None),
                "docxPath": getattr(doc, "docx_path", None),
            }
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document Metadata Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{code}/pdf")
def serve_pdf(code: str, download: bool = False):
    """Serve a PDF file for the given document code.

    Args:
        code: Document code
        download: If True, force download. If False (default), display inline.
    """
    try:
        file_path = get_file_path(code, "pdf")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"PDF for {code} not found")

        # For inline viewing, don't set filename (or set content-disposition: inline)
        if download:
            return FileResponse(
                path=file_path,
                media_type="application/pdf",
                filename=os.path.basename(file_path),
            )
        else:
            # Return without filename to display inline in browser
            return FileResponse(
                path=file_path,
                media_type="application/pdf",
                headers={"Content-Disposition": "inline"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF Serve Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{code}/docx")
def serve_docx(code: str):
    """Serve a DOCX file for the given document code."""
    try:
        file_path = get_file_path(code, "docx")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"DOCX for {code} not found")

        return FileResponse(
            path=file_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=os.path.basename(file_path),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DOCX Serve Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/download/{file_path:path}",
    summary="Download Generated File",
    description="Download a generated document file by path.",
    tags=["9-Agent Workflow"],
)
def download_generated_file(file_path: str):
    """Download a generated file from the workflow."""
    try:
        # Security: Only allow files from output directory
        from urllib.parse import unquote
        decoded_path = unquote(file_path)

        # Allow absolute paths from output directory or relative paths
        output_dir = str(Path(PROJECT_ROOT) / "output")
        if decoded_path.startswith(output_dir):
            full_path = decoded_path
        else:
            full_path = str(Path(output_dir) / decoded_path)

        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        # Security check: ensure file is within output directory
        real_path = os.path.realpath(full_path)
        real_output = os.path.realpath(output_dir)
        if not real_path.startswith(real_output):
            raise HTTPException(status_code=403, detail="Access denied")

        # Determine media type
        ext = os.path.splitext(full_path)[1].lower()
        media_types = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        media_type = media_types.get(ext, "application/octet-stream")

        return FileResponse(
            path=full_path,
            media_type=media_type,
            filename=os.path.basename(full_path),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/files/list",
    response_model=FileListResponse,
    summary="List All Files",
    description="Get a list of all available PDF and DOCX files in the system.",
    tags=["Document Browser"],
)
def list_all_files():
    """
    List all available PDF and DOCX files.

    Returns:
        FileListResponse: Lists of PDF and DOCX files with counts
    """
    try:
        pdf_files = scan_pdf_directory()
        docx_files = scan_docx_directory()

        return {
            "pdf": pdf_files,
            "docx": docx_files,
            "pdfCount": len(pdf_files),
            "docxCount": len(docx_files),
        }
    except Exception as e:
        logger.error(f"File List Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 9-AGENT WORKFLOW API ENDPOINTS
# ============================================================================

# In-memory workflow storage (in production, use Redis or database)
_active_workflows: Dict[str, Dict[str, Any]] = {}


def _generate_workflow_id() -> str:
    """Generate unique workflow ID"""
    import uuid
    return f"wf-{uuid.uuid4().hex[:12]}"


async def _generate_contextual_questions(
    agent_number: int,
    metadata: Dict,
    previous_answers: Dict = None,
    letta_svc: Optional[LettaService] = None
) -> List[Dict]:
    """
    Generate contextual questions using Letta AI based on SOP metadata.
    Questions adapt to the specific SOP being created.
    """
    sop_title = metadata.get("sop_title", "")
    sop_description = metadata.get("short_description", "")
    department = metadata.get("department", "")
    annexes = metadata.get("annexes", [])

    # Build context for question generation
    context_parts = [
        f"SOP Title: {sop_title}",
        f"Description: {sop_description}",
        f"Department: {department}",
    ]
    if annexes:
        context_parts.append(f"Planned Annexes: {', '.join([a.get('title', '') for a in annexes])}")
    sop_context = "\n".join(context_parts)

    # Try to generate contextual questions using Letta
    if letta_svc:
        try:
            # Get RAG context for the SOP
            rag_results = letta_svc.dual_db_search(
                f"{sop_title} {sop_description} {department}",
                db1_top_k=3, db2_top_k=3
            )

            # Build RAG context summary
            rag_context = ""
            if rag_results.get("db1_results"):
                rag_context += "Relevant regulatory context:\n"
                for r in rag_results["db1_results"][:2]:
                    rag_context += f"- {r.get('text', '')[:200]}...\n"
            if rag_results.get("db2_results"):
                rag_context += "\nRelevant operational examples:\n"
                for r in rag_results["db2_results"][:2]:
                    rag_context += f"- {r.get('text', '')[:200]}...\n"

            # Generate questions using Letta agent
            if agent_number == 2:
                prompt = f"""You are generating contextual questions for creating an EU GMP compliant SOP.

SOP Context:
{sop_context}

{rag_context}

Generate 4 contextual questions for the INTRODUCTION section of this SOP.
Each question should be directly relevant to "{sop_title}" and the {department} department.

Return ONLY a JSON array with this structure (no markdown, no explanation):
[
  {{
    "id": "q1_unique_id",
    "text": "Question text specific to this SOP?",
    "type": "single_choice",
    "options": [
      {{"value": "opt1", "label": "Option 1", "description": "Brief description"}},
      {{"value": "opt2", "label": "Option 2", "description": "Brief description"}},
      {{"value": "opt3", "label": "Option 3", "description": "Brief description"}}
    ],
    "required": true,
    "helpText": "Why this question is important for this SOP"
  }}
]

IMPORTANT:
- Questions should be specific to "{sop_title}", not generic
- Include regulatory context from EU GMP where relevant
- Options should be actionable and relevant to the {department} department
"""
            elif agent_number == 3:
                # Include previous answers for context
                prev_context = ""
                if previous_answers:
                    prev_context = f"\nPrevious answers from introduction phase:\n"
                    for k, v in previous_answers.items():
                        prev_context += f"- {k}: {v}\n"

                prompt = f"""You are generating contextual questions for creating an EU GMP compliant SOP.

SOP Context:
{sop_context}
{prev_context}

{rag_context}

Generate 4-5 contextual questions for the PROCEDURE section of this SOP.
Each question should help define the specific process steps for "{sop_title}".

Return ONLY a JSON array with this structure (no markdown, no explanation):
[
  {{
    "id": "q1_unique_id",
    "text": "Question text specific to this procedure?",
    "type": "single_choice or multi_choice or text",
    "options": [
      {{"value": "opt1", "label": "Option 1", "description": "Brief description"}},
      {{"value": "opt2", "label": "Option 2", "description": "Brief description"}}
    ],
    "required": true,
    "helpText": "Why this question is important"
  }}
]

IMPORTANT:
- Questions should help define actual process steps for "{sop_title}"
- Include equipment, parameters, or documentation specific to this type of procedure
- For text type questions, set options to empty array []
"""
            else:
                # Default fallback
                return _get_fallback_questions(agent_number, metadata)

            response = letta_svc.send_message("purpose", prompt)

            # Parse JSON from response
            import re
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                questions = json_module.loads(json_match.group())
                # Validate and sanitize questions
                valid_questions = []
                for q in questions:
                    if isinstance(q, dict) and "id" in q and "text" in q:
                        # Ensure required fields
                        q.setdefault("type", "single_choice")
                        q.setdefault("options", [])
                        q.setdefault("required", True)
                        valid_questions.append(q)

                if valid_questions:
                    logger.info(f"Generated {len(valid_questions)} contextual questions for Agent {agent_number}")
                    return valid_questions

            logger.warning(f"Could not parse contextual questions, using fallback")
        except Exception as e:
            logger.warning(f"Contextual question generation failed: {e}, using fallback")

    # Fallback to static questions
    return _get_fallback_questions(agent_number, metadata)


def _get_fallback_questions(agent_number: int, metadata: Dict) -> List[Dict]:
    """Get fallback static questions when AI generation fails"""
    sop_title = metadata.get("sop_title", "this procedure")
    department = metadata.get("department", "")

    # Agent 2: Introduction questions - make them reference the SOP title
    agent2_questions = [
        {
            "id": "purpose_main_objective",
            "text": f"What is the primary objective of {sop_title}?",
            "type": "single_choice",
            "options": [
                {"value": "ensure_compliance", "label": "Ensure EU GMP Compliance", "description": "Primary focus on meeting regulatory requirements"},
                {"value": "standardize_process", "label": "Standardize Operations", "description": "Create consistent process execution"},
                {"value": "quality_control", "label": "Quality Control", "description": "Ensure product quality throughout process"},
                {"value": "risk_mitigation", "label": "Risk Mitigation", "description": "Prevent deviations and non-conformances"},
            ],
            "required": True,
            "helpText": f"Define the main goal of {sop_title} within your QMS"
        },
        {
            "id": "scope_areas",
            "text": f"Which areas of your facility will {sop_title} apply to?",
            "type": "multi_choice",
            "options": [
                {"value": "production", "label": "Production Areas"},
                {"value": "warehouse", "label": "Warehouse/Storage"},
                {"value": "quality_lab", "label": "Quality Control Laboratory"},
                {"value": "packaging", "label": "Packaging"},
                {"value": "all_areas", "label": "All GMP Areas"},
            ],
            "required": True,
            "helpText": "Select all facility areas where this procedure will be implemented"
        },
        {
            "id": "regulatory_references",
            "text": f"Which EU GMP chapters and regulatory frameworks should {sop_title} reference?",
            "type": "multi_choice",
            "options": [
                {"value": "eu_gmp_annex1", "label": "EU GMP Annex 1 (Sterile Products)"},
                {"value": "eu_gmp_ch4", "label": "EU GMP Chapter 4 (Documentation)"},
                {"value": "eu_gmp_ch6", "label": "EU GMP Chapter 6 (Quality Control)"},
                {"value": "ich_q10", "label": "ICH Q10 (Pharmaceutical Quality System)"},
                {"value": "gacp", "label": "GACP (Good Agricultural & Collection Practices)"},
            ],
            "required": True,
            "helpText": "Select applicable regulatory frameworks for compliance"
        },
        {
            "id": "personnel_scope",
            "text": f"Who will be responsible for executing {sop_title}?",
            "type": "multi_choice",
            "options": [
                {"value": "production_staff", "label": "Production Operators"},
                {"value": "qa_team", "label": "Quality Assurance Team"},
                {"value": "qc_team", "label": "Quality Control Analysts"},
                {"value": "management", "label": "Management"},
                {"value": "all_personnel", "label": "All GMP Personnel"},
            ],
            "required": True,
            "helpText": "Define the target audience for training and execution"
        },
    ]

    # Agent 3: Procedure questions - reference SOP title
    agent3_questions = [
        {
            "id": "process_complexity",
            "text": f"How would you describe the complexity of {sop_title}?",
            "type": "single_choice",
            "options": [
                {"value": "simple", "label": "Simple (Linear, <10 steps)"},
                {"value": "moderate", "label": "Moderate (Some branching, 10-20 steps)"},
                {"value": "complex", "label": "Complex (Multiple decision points, >20 steps)"},
            ],
            "required": True,
            "helpText": "This helps determine the level of detail needed"
        },
        {
            "id": "equipment_list",
            "text": f"What equipment or materials are required for {sop_title}?",
            "type": "text",
            "options": [],
            "required": True,
            "helpText": "List primary equipment, instruments, or materials needed"
        },
        {
            "id": "critical_parameters",
            "text": f"What are the critical process parameters to monitor in {sop_title}?",
            "type": "multi_choice",
            "options": [
                {"value": "temperature", "label": "Temperature"},
                {"value": "humidity", "label": "Humidity"},
                {"value": "pressure", "label": "Pressure"},
                {"value": "time", "label": "Time/Duration"},
                {"value": "concentration", "label": "Concentration"},
                {"value": "ph", "label": "pH"},
                {"value": "weight", "label": "Weight/Mass"},
            ],
            "required": True,
            "helpText": "Select parameters that require monitoring or verification"
        },
        {
            "id": "decision_points",
            "text": f"Does {sop_title} have critical decision points requiring approval?",
            "type": "single_choice",
            "options": [
                {"value": "yes_multiple", "label": "Yes, multiple hold points"},
                {"value": "yes_single", "label": "Yes, one critical hold point"},
                {"value": "no", "label": "No, continuous process"},
            ],
            "required": True,
            "helpText": "Hold points require QA or supervisor verification before proceeding"
        },
        {
            "id": "process_steps_detail",
            "text": f"Briefly describe the main steps or workflow of {sop_title}:",
            "type": "text",
            "options": [],
            "required": True,
            "helpText": "Provide an overview of the key process steps"
        },
    ]

    questions_map = {
        2: agent2_questions,
        3: agent3_questions,
    }

    return questions_map.get(agent_number, [])


def _get_agent_questions(agent_number: int, metadata: Dict, context: Dict = None) -> List[Dict]:
    """Get questions for a specific agent based on metadata and context (sync wrapper)"""
    # Use fallback questions for sync calls
    return _get_fallback_questions(agent_number, metadata)

    # Agent 3: Procedure Engineer - Process Steps, Equipment, Critical Parameters
    agent3_questions = [
        {
            "id": "process_complexity",
            "text": "How would you describe the complexity of this process?",
            "type": "single_choice",
            "options": [
                {"value": "simple", "label": "Simple (Linear, <10 steps)"},
                {"value": "moderate", "label": "Moderate (Some branching, 10-20 steps)"},
                {"value": "complex", "label": "Complex (Multiple decision points, >20 steps)"},
            ],
            "required": True,
        },
        {
            "id": "equipment_list",
            "text": "What equipment is used in this procedure?",
            "type": "text",
            "required": True,
            "rag_context": "Equipment commonly used includes: extraction systems, HPLC, GC-MS, balances, environmental monitoring systems",
        },
        {
            "id": "critical_parameters",
            "text": "What are the critical process parameters to monitor?",
            "type": "multi_choice",
            "options": [
                {"value": "temperature", "label": "Temperature"},
                {"value": "humidity", "label": "Humidity"},
                {"value": "pressure", "label": "Pressure"},
                {"value": "time", "label": "Time/Duration"},
                {"value": "concentration", "label": "Concentration"},
                {"value": "ph", "label": "pH"},
            ],
            "required": True,
        },
        {
            "id": "decision_points",
            "text": "Are there critical decision points that require supervisor approval?",
            "type": "single_choice",
            "options": [
                {"value": "yes_multiple", "label": "Yes, multiple hold points"},
                {"value": "yes_single", "label": "Yes, one critical hold point"},
                {"value": "no", "label": "No, continuous process"},
            ],
            "required": True,
        },
        {
            "id": "process_steps_detail",
            "text": "Describe the main process steps (brief overview):",
            "type": "text",
            "required": True,
        },
    ]

    # Agent 8: Annex Content Creator - Per-annex questions
    agent8_questions = [
        {
            "id": "annex_purpose",
            "text": "What is the primary purpose of this annex?",
            "type": "single_choice",
            "options": [
                {"value": "data_collection", "label": "Data Collection Form"},
                {"value": "checklist", "label": "Verification Checklist"},
                {"value": "template", "label": "Document Template"},
                {"value": "flowchart", "label": "Process Flowchart"},
            ],
            "required": True,
        },
        {
            "id": "annex_fields",
            "text": "What fields/sections should this annex include?",
            "type": "text",
            "required": True,
        },
        {
            "id": "annex_frequency",
            "text": "How often will this annex be used?",
            "type": "single_choice",
            "options": [
                {"value": "per_batch", "label": "Per Batch"},
                {"value": "daily", "label": "Daily"},
                {"value": "weekly", "label": "Weekly"},
                {"value": "as_needed", "label": "As Needed"},
            ],
            "required": True,
        },
    ]

    questions_map = {
        2: agent2_questions,
        3: agent3_questions,
        8: agent8_questions,
    }

    return questions_map.get(agent_number, [])


@app.post(
    "/api/workflow/start",
    response_model=WorkflowQuestionsResponse,
    summary="Start 9-Agent Workflow",
    description="Initialize a new SOP generation workflow with metadata and get contextual Agent 2 questions.",
    tags=["9-Agent Workflow"],
)
async def start_workflow(request: WorkflowStartRequest):
    """
    Start a new 9-agent workflow.

    Agent 1 (Metadata Orchestrator) processes the metadata,
    then returns Agent 2 (Introduction Architect) questions.
    Questions are dynamically generated based on the SOP context.
    """
    try:
        workflow_id = _generate_workflow_id()
        metadata_dict = request.metadata.dict()

        # Store workflow state
        _active_workflows[workflow_id] = {
            "id": workflow_id,
            "metadata": metadata_dict,
            "current_agent": 2,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "agent_responses": {},
            "generated_sections": {},
        }

        # Generate contextual questions using AI
        logger.info(f"Generating contextual questions for SOP: {request.metadata.sop_title}")
        questions = await _generate_contextual_questions(
            agent_number=2,
            metadata=metadata_dict,
            letta_svc=letta_service
        )

        # Enrich questions with RAG context for display
        if letta_service:
            try:
                rag_results = letta_service.dual_db_search(
                    f"{request.metadata.sop_title} {request.metadata.short_description}",
                    db1_top_k=3, db2_top_k=3
                )
                # Add RAG context to questions for user reference
                rag_context = {
                    "db1Results": [
                        {"text": r.get("text", "")[:300], "source": "EU GMP Regulatory", "score": r.get("score", 0)}
                        for r in rag_results.get("db1_results", [])[:2]
                    ],
                    "db2Results": [
                        {"text": r.get("text", "")[:300], "source": "Operational QMS", "score": r.get("score", 0)}
                        for r in rag_results.get("db2_results", [])[:2]
                    ]
                }
                for q in questions:
                    q["ragContext"] = rag_context
            except Exception as e:
                logger.warning(f"RAG enrichment failed: {e}")

        return WorkflowQuestionsResponse(
            workflow_id=workflow_id,
            agent_number=2,
            agent_name="Introduction Architect",
            questions=[WorkflowQuestion(**q) for q in questions],
            total_questions=len(questions),
            current_section=f"Introduction - {request.metadata.sop_title}",
        )

    except Exception as e:
        logger.error(f"Workflow Start Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/workflow/agent-2/submit",
    response_model=WorkflowQuestionsResponse,
    summary="Submit Agent 2 Answers",
    description="Submit Introduction Architect answers and get Agent 3 (Procedure Engineer) questions.",
    tags=["9-Agent Workflow"],
)
async def submit_agent2(request: AgentSubmitRequest):
    """Submit Agent 2 answers and get Agent 3 questions."""
    try:
        if request.workflow_id not in _active_workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = _active_workflows[request.workflow_id]
        workflow["agent_responses"][2] = request.answers
        workflow["current_agent"] = 3

        # Generate contextual questions for Agent 3 using AI
        logger.info(f"Generating contextual questions for Agent 3 (Procedure Engineer)")
        questions = await _generate_contextual_questions(
            agent_number=3,
            metadata=workflow["metadata"],
            previous_answers=request.answers,
            letta_svc=letta_service
        )

        # Enrich questions with RAG context
        if letta_service:
            try:
                sop_title = workflow["metadata"].get("sop_title", "")
                sop_desc = workflow["metadata"].get("short_description", "")
                rag_results = letta_service.dual_db_search(
                    f"{sop_title} {sop_desc} procedure steps process",
                    db1_top_k=3, db2_top_k=3
                )
                rag_context = {
                    "db1Results": [
                        {"text": r.get("text", "")[:300], "source": "EU GMP Regulatory", "score": r.get("score", 0)}
                        for r in rag_results.get("db1_results", [])[:2]
                    ],
                    "db2Results": [
                        {"text": r.get("text", "")[:300], "source": "Operational QMS", "score": r.get("score", 0)}
                        for r in rag_results.get("db2_results", [])[:2]
                    ]
                }
                for q in questions:
                    q["ragContext"] = rag_context
            except Exception as e:
                logger.warning(f"RAG enrichment failed for Agent 3: {e}")

        return WorkflowQuestionsResponse(
            workflow_id=request.workflow_id,
            agent_number=3,
            agent_name="Procedure Engineer",
            questions=[WorkflowQuestion(**q) for q in questions],
            total_questions=len(questions),
            current_section="Procedure & Process Steps",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent 2 Submit Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _run_workflow_background(workflow_id: str, workflow: dict):
    """Background task to run Letta workflow for Agents 4-7."""
    import asyncio as _aio

    try:
        workflow["status"] = "processing_agent_4"
        workflow["progress"] = {"agent": 4, "message": "Starting compliance analysis...", "percent": 0}

        # Extract data from previous agents
        metadata = workflow.get("metadata", {})
        agent2_answers = workflow.get("agent_responses", {}).get(2, {})
        agent3_answers = workflow.get("agent_responses", {}).get(3, {})

        # Combine all user inputs
        user_inputs = {
            **agent2_answers,
            **agent3_answers,
        }

        sop_name = metadata.get("sop_title", "Untitled SOP")
        sop_code = metadata.get("document_code", "XX_00.00")
        department = metadata.get("department", "")
        annexes = metadata.get("annexes", [])

        def on_progress(event_type: str, agent: str, content=None):
            """Update workflow progress."""
            agent_num = {"regulatory": 4, "procedure": 4, "raci": 5, "qa": 6, "formatter": 7}.get(agent, 4)
            percent = {"agent_start": 10, "search_complete": 30, "generation_complete": 80, "section_complete": 100}.get(event_type, 50)
            workflow["progress"] = {
                "agent": agent_num,
                "message": f"{agent}: {event_type}",
                "percent": percent,
                "content_preview": str(content)[:500] if content else None
            }
            workflow["current_agent"] = agent_num
            if event_type == "section_complete" and content:
                workflow["generated_sections"][agent] = content

        # Run the Letta workflow
        loop = _aio.new_event_loop()
        _aio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(letta_workflow.execute(
                sop_name=sop_name,
                sop_code=sop_code,
                department=department,
                facility_type="Cannabis EU GMP",
                document_type="SOP",
                user_inputs=user_inputs,
                user_selections={"annexes": annexes},
                on_progress=on_progress,
            ))
        finally:
            loop.close()

        # Store results
        workflow["result"] = result
        workflow["docx_path"] = result.get("docx_path", "")
        workflow["quality_report"] = result.get("quality_report", "")
        workflow["status"] = "complete"
        workflow["current_agent"] = 7
        workflow["progress"] = {"agent": 7, "message": "SOP generation complete!", "percent": 100}

        logger.info(f"Workflow {workflow_id} completed successfully")

    except Exception as e:
        logger.error(f"Background workflow error for {workflow_id}: {e}", exc_info=True)
        workflow["status"] = "error"
        workflow["error"] = str(e)
        workflow["progress"] = {"agent": workflow.get("current_agent", 4), "message": f"Error: {e}", "percent": 0}


@app.post(
    "/api/workflow/agent-3/submit",
    summary="Submit Agent 3 Answers",
    description="Submit Procedure Engineer answers and trigger Agents 4-7 (automated processing with actual generation).",
    tags=["9-Agent Workflow"],
)
async def submit_agent3(request: AgentSubmitRequest, background_tasks: BackgroundTasks):
    """
    Submit Agent 3 answers.
    This triggers automated processing by Agents 4 (Compliance), 5 (RACI), 6 (QA), and 7 (Formatter).
    The workflow runs in the background - poll /api/workflow/{id}/status for progress.
    """
    try:
        if request.workflow_id not in _active_workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = _active_workflows[request.workflow_id]
        workflow["agent_responses"][3] = request.answers
        workflow["current_agent"] = 4
        workflow["status"] = "automated_processing"
        workflow["progress"] = {"agent": 4, "message": "Starting automated processing...", "percent": 0}
        workflow["generated_sections"] = {}

        # Start background workflow execution
        if letta_workflow:
            import threading
            t = threading.Thread(
                target=_run_workflow_background,
                args=(request.workflow_id, workflow),
                daemon=True
            )
            t.start()
            logger.info(f"Started background workflow for {request.workflow_id}")
        else:
            workflow["status"] = "error"
            workflow["error"] = "Letta workflow service not available"

        return {
            "status": "success",
            "message": "Answers submitted. Automated processing by Agents 4-7 has started.",
            "next_step": f"Poll /api/workflow/{request.workflow_id}/status for progress",
            "workflow_id": request.workflow_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent 3 Submit Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/workflow/{workflow_id}/status",
    summary="Get Workflow Status",
    description="Poll for workflow progress during automated processing.",
    tags=["9-Agent Workflow"],
)
async def get_workflow_status(workflow_id: str):
    """Get current workflow status and progress."""
    if workflow_id not in _active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = _active_workflows[workflow_id]

    return {
        "workflow_id": workflow_id,
        "status": workflow.get("status", "unknown"),
        "current_agent": workflow.get("current_agent", 1),
        "progress": workflow.get("progress", {}),
        "error": workflow.get("error"),
        "docx_path": workflow.get("docx_path"),
        "quality_report": workflow.get("quality_report"),
        "generated_sections": workflow.get("generated_sections", {}),
    }


@app.post(
    "/api/workflow/dynamic-question",
    response_model=DynamicQuestionResponse,
    summary="Get Next Dynamic Question",
    description="Get the next context-aware question based on previous answers and accumulated context.",
    tags=["9-Agent Workflow"],
)
async def get_dynamic_question(request: DynamicQuestionRequest):
    """
    Generate next question dynamically based on:
    - Previous answers
    - Accumulated context from locked fields
    - Uploaded files
    - Agent-specific requirements

    Returns one question at a time in a conversational flow.
    """
    try:
        if request.workflow_id not in _active_workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = _active_workflows[request.workflow_id]
        agent_num = request.agent_number

        # Track how many questions have been answered
        answered_count = len(request.previous_answers)

        # Agent-specific question generation logic
        if agent_num == 2:
            # Agent 2: Introduction Architect
            # Questions: purpose_main_objective, scope_areas, regulatory_references, personnel_scope
            question_sequence = [
                "purpose_main_objective",
                "scope_areas",
                "regulatory_references",
                "personnel_scope"
            ]

            if answered_count >= len(question_sequence):
                # All questions answered
                return DynamicQuestionResponse(
                    question=None,
                    is_final=True,
                    estimated_remaining=0,
                    progress_percentage=100
                )

            next_question_id = question_sequence[answered_count]

            # Generate question based on context
            if next_question_id == "purpose_main_objective":
                question = WorkflowQuestion(
                    id="purpose_main_objective",
                    text="What is the primary objective of this procedure?",
                    type="single_choice",
                    options=[
                        {"value": "ensure_compliance", "label": "Ensure EU GMP Compliance", "description": "Primary focus on meeting regulatory requirements"},
                        {"value": "standardize_process", "label": "Standardize Operations", "description": "Create consistent process execution"},
                        {"value": "quality_control", "label": "Quality Control", "description": "Ensure product quality throughout process"},
                        {"value": "risk_mitigation", "label": "Risk Mitigation", "description": "Prevent deviations and non-conformances"},
                    ],
                    required=True
                )
            elif next_question_id == "scope_areas":
                question = WorkflowQuestion(
                    id="scope_areas",
                    text="Which areas of your facility does this procedure apply to?",
                    type="multi_choice",
                    options=[
                        {"value": "production", "label": "Production Areas"},
                        {"value": "warehouse", "label": "Warehouse/Storage"},
                        {"value": "quality_lab", "label": "Quality Control Laboratory"},
                        {"value": "packaging", "label": "Packaging"},
                        {"value": "all_areas", "label": "All GMP Areas"},
                    ],
                    required=True
                )
            elif next_question_id == "regulatory_references":
                question = WorkflowQuestion(
                    id="regulatory_references",
                    text="Which regulatory frameworks should be referenced?",
                    type="multi_choice",
                    options=[
                        {"value": "eu_gmp_annex1", "label": "EU GMP Annex 1 (Sterile Products)"},
                        {"value": "eu_gmp_ch4", "label": "EU GMP Chapter 4 (Documentation)"},
                        {"value": "eu_gmp_ch6", "label": "EU GMP Chapter 6 (Quality Control)"},
                        {"value": "ich_q10", "label": "ICH Q10 (Pharmaceutical Quality System)"},
                        {"value": "gacp", "label": "GACP (Good Agricultural Practices)"},
                    ],
                    required=True
                )
            else:  # personnel_scope
                question = WorkflowQuestion(
                    id="personnel_scope",
                    text="Who is the primary target audience for this procedure?",
                    type="multi_choice",
                    options=[
                        {"value": "production_staff", "label": "Production Operators"},
                        {"value": "qa_team", "label": "Quality Assurance Team"},
                        {"value": "qc_team", "label": "Quality Control Analysts"},
                        {"value": "management", "label": "Management"},
                        {"value": "all_personnel", "label": "All GMP Personnel"},
                    ],
                    required=True
                )

            # Enrich with RAG context if available
            if letta_service and request.accumulated_context:
                try:
                    rag_results = letta_service.dual_db_search(
                        f"{request.accumulated_context} {next_question_id}",
                        db1_top_k=2, db2_top_k=2
                    )
                    if rag_results.get("db1_results"):
                        question.rag_context = rag_results["db1_results"][0].get("text", "")[:300]
                except Exception as e:
                    logger.warning(f"RAG enrichment failed: {e}")

            return DynamicQuestionResponse(
                question=question,
                is_final=False,
                estimated_remaining=len(question_sequence) - answered_count - 1,
                progress_percentage=int((answered_count + 1) / len(question_sequence) * 100)
            )

        elif agent_num == 3:
            # Agent 3: Procedure Engineer
            question_sequence = [
                "process_complexity",
                "equipment_list",
                "critical_parameters",
                "decision_points",
                "process_steps_detail"
            ]

            if answered_count >= len(question_sequence):
                return DynamicQuestionResponse(
                    question=None,
                    is_final=True,
                    estimated_remaining=0,
                    progress_percentage=100
                )

            next_question_id = question_sequence[answered_count]

            # Generate Agent 3 questions (similar pattern)
            if next_question_id == "process_complexity":
                question = WorkflowQuestion(
                    id="process_complexity",
                    text="How would you describe the complexity of this process?",
                    type="single_choice",
                    options=[
                        {"value": "simple", "label": "Simple (Linear, <10 steps)"},
                        {"value": "moderate", "label": "Moderate (Some branching, 10-20 steps)"},
                        {"value": "complex", "label": "Complex (Multiple decision points, >20 steps)"},
                    ],
                    required=True
                )
            elif next_question_id == "equipment_list":
                question = WorkflowQuestion(
                    id="equipment_list",
                    text="What equipment is used in this procedure?",
                    type="text",
                    required=True,
                    rag_context="Equipment commonly used includes: extraction systems, HPLC, GC-MS, balances, environmental monitoring systems"
                )
            elif next_question_id == "critical_parameters":
                question = WorkflowQuestion(
                    id="critical_parameters",
                    text="What are the critical process parameters to monitor?",
                    type="multi_choice",
                    options=[
                        {"value": "temperature", "label": "Temperature"},
                        {"value": "humidity", "label": "Humidity"},
                        {"value": "pressure", "label": "Pressure"},
                        {"value": "time", "label": "Time/Duration"},
                        {"value": "concentration", "label": "Concentration"},
                        {"value": "ph", "label": "pH"},
                    ],
                    required=True
                )
            elif next_question_id == "decision_points":
                question = WorkflowQuestion(
                    id="decision_points",
                    text="Are there critical decision points that require supervisor approval?",
                    type="single_choice",
                    options=[
                        {"value": "yes_multiple", "label": "Yes, multiple hold points"},
                        {"value": "yes_single", "label": "Yes, one critical hold point"},
                        {"value": "no", "label": "No, continuous process"},
                    ],
                    required=True
                )
            else:  # process_steps_detail
                question = WorkflowQuestion(
                    id="process_steps_detail",
                    text="Describe the main process steps (brief overview):",
                    type="text",
                    required=True
                )

            return DynamicQuestionResponse(
                question=question,
                is_final=False,
                estimated_remaining=len(question_sequence) - answered_count - 1,
                progress_percentage=int((answered_count + 1) / len(question_sequence) * 100)
            )

        else:
            raise HTTPException(status_code=400, detail=f"Dynamic questions not supported for agent {agent_num}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dynamic Question Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/workflow/{workflow_id}/status",
    summary="Get Workflow Status",
    description="Get the current status of a workflow including agent progress.",
    tags=["9-Agent Workflow"],
)
async def get_workflow_status(workflow_id: str):
    """Get current workflow status and agent progress."""
    if workflow_id not in _active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = _active_workflows[workflow_id]
    return {
        "workflow_id": workflow_id,
        "current_agent": workflow["current_agent"],
        "status": workflow["status"],
        "metadata": workflow["metadata"],
        "completed_agents": list(workflow["agent_responses"].keys()),
    }


@app.get(
    "/api/workflow/{workflow_id}/agent-6/review",
    response_model=QAReviewResponse,
    summary="Get Agent 6 QA Review",
    description="Get the Quality Assembler review report with recommendations.",
    tags=["9-Agent Workflow"],
)
async def get_qa_review(workflow_id: str):
    """Get Agent 6 QA review report."""
    if workflow_id not in _active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = _active_workflows[workflow_id]

    # Generate QA review (mock for now - will integrate with Letta)
    return QAReviewResponse(
        overall_score=92,
        regulatory_compliance=100,
        internal_consistency=95,
        completeness=85,
        recommendations=[
            {
                "id": "rec_1",
                "section": "3.2",
                "issue": "Missing acceptance criteria for cannabinoid content",
                "severity": "medium",
                "options": [
                    {"value": "add_cannabinoid_ranges", "label": "Add specific cannabinoid ranges (THC ≤0.2%, CBD as specified)"},
                    {"value": "add_reference", "label": "Reference QC_01.05 for acceptance criteria"},
                    {"value": "skip", "label": "Skip (continue without)"},
                ],
            },
            {
                "id": "rec_2",
                "section": "4.1",
                "issue": "Documentation retention period not specified",
                "severity": "low",
                "options": [
                    {"value": "add_5_years", "label": "Add 5-year retention per EU GMP"},
                    {"value": "add_reference", "label": "Reference document control SOP"},
                    {"value": "skip", "label": "Skip"},
                ],
            },
        ],
        section_previews={
            "purpose": "This procedure establishes...",
            "scope": "This procedure applies to...",
            "procedure": "3.1 Pre-requisites\n3.2 Process Steps...",
        },
    )


@app.post(
    "/api/workflow/{workflow_id}/agent-6/approve",
    summary="Approve QA Review",
    description="Submit QA review approval with selected options and trigger Agent 7.",
    tags=["9-Agent Workflow"],
)
async def approve_qa_review(workflow_id: str, request: QAApprovalRequest):
    """Approve Agent 6 QA review and trigger Agent 7 formatting."""
    if workflow_id not in _active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = _active_workflows[workflow_id]
    workflow["qa_selections"] = request.selected_options
    workflow["current_agent"] = 7
    workflow["status"] = "formatting"

    return {
        "status": "success",
        "message": "QA review approved. Agent 7 (Document Formatter) is generating the DOCX.",
        "workflow_id": workflow_id,
    }


@app.get(
    "/api/workflow/{workflow_id}/agent-8/annexes",
    summary="Get Annex Questions",
    description="Get questionnaire for each pending annex.",
    tags=["9-Agent Workflow"],
)
async def get_annex_questions(workflow_id: str):
    """Get Agent 8 questions for each annex with contextual questions."""
    if workflow_id not in _active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = _active_workflows[workflow_id]
    annexes = workflow["metadata"].get("annexes", [])
    sop_title = workflow["metadata"].get("sop_title", "")

    annex_questionnaires = []
    for i, annex in enumerate(annexes):
        annex_title = annex.get("title", f"Annex {chr(65 + i)}")
        annex_type = annex.get("type", "form")

        # Try AI-generated contextual questions
        try:
            if letta_service:
                prompt = f"""Generate 3-4 questions for creating an EU GMP compliant annex.

SOP: {sop_title}
Annex Title: {annex_title}
Annex Type: {annex_type}

Return ONLY a JSON array with this structure (no markdown):
[
  {{
    "id": "annex_q1",
    "text": "Question specific to {annex_title}?",
    "type": "single_choice or multi_choice or text",
    "options": [{{"value": "opt1", "label": "Option 1"}}],
    "required": true,
    "helpText": "Why this matters for the annex"
  }}
]

Focus on:
- Fields/data required for this type of {annex_type}
- GMP documentation requirements
- Frequency and validation needs
"""
                response = letta_service.send_message("purpose", prompt)
                import re
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    questions = json_module.loads(json_match.group())
                    if questions and isinstance(questions, list):
                        annex_questionnaires.append({
                            "annex_id": f"annex_{i}",
                            "annex_label": f"Annex {chr(65 + i)}",
                            "annex_title": annex_title,
                            "annex_type": annex_type,
                            "questions": questions,
                        })
                        continue
        except Exception as e:
            logger.warning(f"AI question generation failed for annex {annex_title}: {e}")

        # Fallback to contextual static questions
        questions = [
            {
                "id": f"annex_{i}_purpose",
                "text": f"What is the primary purpose of '{annex_title}'?",
                "type": "single_choice",
                "options": [
                    {"value": "data_collection", "label": "Data Collection Form"},
                    {"value": "checklist", "label": "Verification Checklist"},
                    {"value": "template", "label": "Document Template"},
                    {"value": "flowchart", "label": "Process Flowchart"},
                ],
                "required": True,
                "helpText": f"Define the function of {annex_title} within {sop_title}"
            },
            {
                "id": f"annex_{i}_fields",
                "text": f"What specific fields should '{annex_title}' include?",
                "type": "text",
                "options": [],
                "required": True,
                "helpText": "List the data fields, checkboxes, or sections needed"
            },
            {
                "id": f"annex_{i}_frequency",
                "text": f"How often will '{annex_title}' be used?",
                "type": "single_choice",
                "options": [
                    {"value": "per_batch", "label": "Per Batch"},
                    {"value": "daily", "label": "Daily"},
                    {"value": "weekly", "label": "Weekly"},
                    {"value": "as_needed", "label": "As Needed"},
                ],
                "required": True,
                "helpText": "This affects revision tracking and storage requirements"
            },
        ]
        annex_questionnaires.append({
            "annex_id": f"annex_{i}",
            "annex_label": f"Annex {chr(65 + i)}",
            "annex_title": annex_title,
            "annex_type": annex_type,
            "questions": questions,
        })

    return {
        "workflow_id": workflow_id,
        "total_annexes": len(annexes),
        "annexes": annex_questionnaires,
    }


@app.post(
    "/api/workflow/{workflow_id}/agent-8/annex/{annex_id}/submit",
    summary="Submit Annex Questionnaire",
    description="Submit answers for a specific annex and trigger Agent 9 formatting.",
    tags=["9-Agent Workflow"],
)
async def submit_annex_questionnaire(workflow_id: str, annex_id: str, request: AgentSubmitRequest):
    """Submit annex questionnaire answers."""
    if workflow_id not in _active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = _active_workflows[workflow_id]
    if "annex_responses" not in workflow:
        workflow["annex_responses"] = {}

    workflow["annex_responses"][annex_id] = request.answers

    return {
        "status": "success",
        "message": f"Annex {annex_id} questionnaire submitted. Agent 9 will format when all annexes are complete.",
        "annex_id": annex_id,
    }


# ============================================================================
# CANVAS-LIKE EDIT REQUEST ENDPOINTS
# ============================================================================


@app.post(
    "/api/documents/{code}/edit-request",
    response_model=EditResponse,
    summary="Submit Edit Request",
    description="Submit a canvas-like edit request (comment, suggestion, flag) for the main SOP.",
    tags=["Canvas Editing"],
)
async def submit_edit_request(code: str, request: EditRequest):
    """
    Submit an edit request for a section of the document.
    Routes to appropriate agent based on section.
    """
    try:
        # Determine which agent handles this section
        section_agent_map = {
            "purpose": 2, "scope": 2, "regulatory": 2,
            "procedure": 3, "documentation": 3,
            "definitions": 4, "references": 4, "training": 4,
            "raci": 5,
        }

        assigned_agent = section_agent_map.get(request.section_id, 3)

        # Check if clarification is needed (mock logic)
        needs_clarification = request.edit_type == "edit_suggestion" and len(request.content) < 20

        clarification_questions = None
        if needs_clarification:
            clarification_questions = [
                {
                    "id": "clarify_intent",
                    "text": "Could you provide more detail about the desired change?",
                    "options": [
                        "Add more specific regulatory references",
                        "Clarify acceptance criteria",
                        "Expand procedural steps",
                        "Other (please specify)",
                    ],
                }
            ]

        return EditResponse(
            status="received",
            assigned_agent=assigned_agent,
            clarification_needed=needs_clarification,
            clarification_questions=clarification_questions,
            message=f"Edit request assigned to Agent {assigned_agent}. "
                    + ("Clarification needed." if needs_clarification else "Processing..."),
        )

    except Exception as e:
        logger.error(f"Edit Request Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/documents/{code}/annexes",
    summary="List Document Annexes",
    description="Get list of all annexes for a document with metadata and preview URLs.",
    tags=["Canvas Editing"],
)
async def list_document_annexes(code: str):
    """List all annexes for a document."""
    # Find document and annexes (mock for now)
    return {
        "document_code": code,
        "annexes": [
            AnnexInfo(
                id="annex_0",
                title="Batch Record Form",
                annex_type="form",
                label="Annex A",
                status="completed",
                preview_url=f"/api/documents/{code}/annexes/annex_0/preview",
                download_url=f"/api/documents/{code}/annexes/annex_0/download",
            ).dict(),
            AnnexInfo(
                id="annex_1",
                title="Equipment Checklist",
                annex_type="checklist",
                label="Annex B",
                status="completed",
                preview_url=f"/api/documents/{code}/annexes/annex_1/preview",
                download_url=f"/api/documents/{code}/annexes/annex_1/download",
            ).dict(),
        ],
    }


@app.get(
    "/api/documents/{code}/annexes/{annex_id}/preview",
    summary="Preview Annex HTML",
    description="Get HTML preview of a specific annex (converted from DOCX via Mammoth).",
    tags=["Canvas Editing"],
)
async def preview_annex(code: str, annex_id: str):
    """Get HTML preview of an annex."""
    # In production, convert DOCX to HTML using Mammoth server-side
    # For now, return a placeholder
    return Response(
        content=f"""
        <html>
        <body>
            <h1>Annex {annex_id.replace('annex_', '').upper()}</h1>
            <p>Preview content for {code} - {annex_id}</p>
            <table border="1">
                <tr><th>Field</th><th>Value</th></tr>
                <tr><td>Date</td><td>__________</td></tr>
                <tr><td>Batch No.</td><td>__________</td></tr>
                <tr><td>Operator</td><td>__________</td></tr>
            </table>
        </body>
        </html>
        """,
        media_type="text/html",
    )


@app.post(
    "/api/documents/{code}/annexes/{annex_id}/edit-request",
    response_model=EditResponse,
    summary="Submit Annex Edit Request",
    description="Submit a canvas-like edit request for a specific annex.",
    tags=["Canvas Editing"],
)
async def submit_annex_edit_request(code: str, annex_id: str, request: EditRequest):
    """Submit an edit request for an annex (routed to Agent 8)."""
    try:
        # Annex edits always go to Agent 8 (content) or 9 (formatting)
        is_formatting_edit = request.edit_type == "flag" and "format" in request.content.lower()
        assigned_agent = 9 if is_formatting_edit else 8

        return EditResponse(
            status="received",
            assigned_agent=assigned_agent,
            clarification_needed=False,
            message=f"Annex edit request assigned to Agent {assigned_agent}.",
        )

    except Exception as e:
        logger.error(f"Annex Edit Request Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── RAG Query Endpoint ──────────────────────────────────────


class RAGQueryRequestExtended(BaseModel):
    """Extended request for RAG vector search with KB awareness"""
    query: str
    top_k: int = 5
    archive: Optional[str] = None  # 'db1', 'db2', or 'both' (default)
    sop_name: Optional[str] = None  # For gap detection context


@app.post(
    "/api/rag-query",
    summary="RAG Vector Search",
    description="Query the regulatory knowledge base (DB1) and entity QMS (DB2) using semantic vector search with KB metadata enrichment.",
    tags=["RAG"],
)
async def rag_query(request: RAGQueryRequestExtended):
    """
    Search the dual-database RAG system with KB metadata enrichment.

    Returns top-k results from DB1 (official guides) and DB2 (entity QMS),
    enriched with:
    - Passage metadata (category, quality score, source authority)
    - Gap detection (if query relates to a topic with limited DB2 coverage)
    - DB weight recommendations
    """
    if not letta_service:
        raise HTTPException(status_code=503, detail="Letta service not available")

    # Detect gap topics for KB-aware retrieval
    sop_name = request.sop_name or request.query
    gap_info = _detect_gap_topic(request.query, sop_name)

    # Get default weights and adjust for gaps
    db1_top_k = request.top_k
    db2_top_k = request.top_k

    if gap_info:
        # Boost DB1 for gap topics (limited DB2 content)
        db1_top_k = max(request.top_k + 2, 5)
        db2_top_k = max(request.top_k - 1, 1)
        logger.info(f"Gap topic detected: {gap_info.get('topic')} - adjusting weights")

    # Filter by archive if specified
    if request.archive == "db1":
        db2_top_k = 0
    elif request.archive == "db2":
        db1_top_k = 0

    results = letta_service.dual_db_search(
        request.query,
        db1_top_k=db1_top_k,
        db2_top_k=db2_top_k
    )

    # Enrich DB1 results with metadata
    enriched_db1 = []
    for r in results.get("db1_results", []):
        text = r.get("text", "")
        tags = r.get("tags", [])
        metadata = _enrich_passage_metadata(text, tags)
        enriched_db1.append({
            **r,
            "metadata": {
                "category": metadata["category"],
                "quality": metadata["quality"],
                "source_authority": metadata["source_authority"],
            }
        })

    # Enrich DB2 results with metadata
    enriched_db2 = []
    for r in results.get("db2_results", []):
        text = r.get("text", "")
        tags = r.get("tags", [])
        metadata = _enrich_passage_metadata(text, tags)
        enriched_db2.append({
            **r,
            "metadata": {
                "category": metadata["category"],
                "quality": metadata["quality"],
                "source_authority": metadata["source_authority"],
            }
        })

    # Build enhanced response
    response = {
        "query": request.query,
        "db1_results": enriched_db1,
        "db2_results": enriched_db2,
        "db1_count": len(enriched_db1),
        "db2_count": len(enriched_db2),
        "db_weights": {
            "db1": db1_top_k,
            "db2": db2_top_k,
        },
    }

    # Add gap info if detected
    if gap_info:
        response["gap_info"] = {
            "topic": gap_info.get("topic"),
            "severity": gap_info.get("severity", "medium"),
            "description": gap_info.get("description", ""),
            "skill_fallback": gap_info.get("skill_fallback"),
        }

    return response


# ── Text Enhancement Endpoint ──────────────────────────────────────


@app.post(
    "/api/enhance-text",
    response_model=EnhanceTextResponse,
    summary="AI Text Enhancement",
    description="Enhance text with regulatory context, EU GMP terminology, and professional phrasing.",
    tags=["AI Enhancement"],
)
async def enhance_text(request: EnhanceTextRequest):
    """
    Enhance text using AI with regulatory context.

    Takes user input text and enhances it with:
    - Regulatory compliance terminology
    - EU GMP specific phrasing
    - Professional SOP language
    - Context from uploaded files (if available)
    """
    try:
        improvements = []

        # Build enhancement prompt
        field_context = {
            "sopTitle": "SOP title - make concise, professional, regulatory-compliant",
            "shortDescription": "SOP description - expand with regulatory context, purpose, scope clarity",
            "annexTitle": "Annex title - clear, specific, professional",
        }

        context_info = request.context or {}
        enhancement_prompt = f"""
You are an EU GMP regulatory writing expert. Enhance the following text for a {request.field_type} field.

Original text: "{request.text}"

Context:
- SOP Title: {context_info.get('sop_title', 'N/A')}
- Department: {context_info.get('department', 'N/A')}
- Uploaded files: {', '.join(context_info.get('uploaded_files', [])) or 'None'}

Guidelines:
{field_context.get(request.field_type, 'Enhance for regulatory compliance and clarity')}

Enhanced text (return ONLY the improved text, no explanations):
"""

        # Use Letta/DeepSeek if available
        if letta_service:
            try:
                # 1. Query RAG for relevant regulatory terminology (Dual-DB Search)
                rag_results = letta_service.dual_db_search(
                    f"{request.text} {request.field_type} EU GMP regulatory terminology",
                    db1_top_k=3, db2_top_k=2
                )

                # 2. Extract context from RAG
                rag_context = ""
                if rag_results.get("db1_results"):
                    rag_context = "\n".join([r.get("text", "")[:300] for r in rag_results["db1_results"]])
                
                # 3. Augment prompt with RAG context
                final_prompt = enhancement_prompt
                if rag_context:
                    final_prompt += f"\n\nUse this regulatory reference for terminology:\n{rag_context}"
                
                # 4. Call Letta Assembler Agent (Uses DeepSeek Reasoner)
                enhanced = letta_service.send_message("assembler", final_prompt)
                
                if enhanced and len(enhanced.strip()) > len(request.text) * 0.5:
                    enhanced = enhanced.strip()
                    improvements.append("Enhanced via DeepSeek Reasoner")
                    improvements.append("Integrated RAG regulatory context")
                else:
                    raise ValueError("AI response empty or too short")

            except Exception as e:
                logger.warning(f"AI enhancement failed, using rule-based fallback: {e}")
                # Fallback to rule-based logic
                enhanced = request.text
                if request.field_type == "sopTitle":
                    if "SOP" not in enhanced:
                        enhanced = f"Standard Operating Procedure: {enhanced}"
                        improvements.append("Added SOP designation (Fallback)")
                elif request.field_type == "shortDescription":
                    if len(enhanced) < 200:
                        enhanced = f"{enhanced}\n\nThis procedure ensures EU GMP compliance and maintains pharmaceutical quality standards."
                        improvements.append("Added regulatory context (Fallback)")
        else:
            # Rule-based enhancement if Letta is disconnected
            enhanced = request.text
            if request.field_type == "sopTitle":
                if "SOP" not in enhanced:
                    enhanced = f"Standard Operating Procedure: {enhanced}"
                enhanced = f"{enhanced} - EU GMP Compliant"
                improvements.append("Rule-based formatting (Letta Offline)")
            elif request.field_type == "shortDescription":
                enhanced = f"{enhanced}\n\nThis procedure ensures EU GMP compliance and maintains pharmaceutical quality standards."
                improvements.append("Added template description (Letta Offline)")

        return EnhanceTextResponse(
            enhanced_text=enhanced,
            improvements=improvements if improvements else ["Text enhanced with regulatory compliance terminology"]
        )

    except Exception as e:
        logger.error(f"Text Enhancement Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Import and setup gap analyzer
sys.path.append(os.path.join(PROJECT_ROOT, "scripts"))
try:
    from sop_gap_analyzer import SOPGapAnalyzer

    GAP_ANALYZER_AVAILABLE = True
except ImportError:
    GAP_ANALYZER_AVAILABLE = False
    logger.warning("SOPGapAnalyzer not available")


class AnalyzeSOPRequest(BaseModel):
    sop_path: str


@app.post("/analyze-sop", dependencies=[Depends(verify_api_key)])
async def analyze_sop(request: AnalyzeSOPRequest):
    """Analyze an existing SOP for gaps against the standard checklist.

    ``sop_path`` is confined to the project's ``output`` directory to prevent
    arbitrary server-file reads (path traversal / LFI).
    """
    if not GAP_ANALYZER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Gap analyzer not available")

    # Confine the requested path to the allowed output directory.
    allowed_root = os.path.realpath(os.path.join(PROJECT_ROOT, "output"))
    requested = os.path.realpath(os.path.join(allowed_root, request.sop_path))
    if os.path.commonpath([allowed_root, requested]) != allowed_root:
        raise HTTPException(status_code=400, detail="sop_path must be within the output directory")
    if not os.path.isfile(requested):
        raise HTTPException(status_code=404, detail="SOP file not found")

    try:
        checklist_path = (
            Path(PROJECT_ROOT)
            / "CONTENT_CREATOR_FRAMEWORK"
            / "sop_standard_checklist.yaml"
        )
        analyzer = SOPGapAnalyzer(str(checklist_path))
        result = analyzer.analyze_sop(requested)
        return result
    except Exception as e:
        logger.error(f"Gap Analysis Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/facility-model")
def get_facility_model():
    """Get the extracted facility model"""
    model_path = Path(PROJECT_ROOT) / "data" / "facility_model.json"
    if not model_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Facility model not generated yet. Run layout_extractor.py first.",
        )

    import json

    with open(model_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Restrict CORS to explicitly-configured origins. A wildcard with
# allow_credentials=True lets any site make credentialed cross-origin calls,
# so the two are mutually exclusive here: set CORS_ALLOW_ORIGINS to a
# comma-separated allowlist (e.g. "https://qms.example.com") to enable
# credentialed requests; the "*" fallback runs without credentials.
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

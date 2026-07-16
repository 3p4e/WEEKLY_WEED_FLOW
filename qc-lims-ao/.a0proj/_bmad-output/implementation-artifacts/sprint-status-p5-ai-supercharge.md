---
# generated: 2026-05-31T12:07:15+02:00
# project: QC_LIMS_Ao
# project_key: qc_lims
# tracking_system: BMAD
# story_location: .a0proj/_bmad-output/implementation-artifacts/stories/
# stepsCompleted:
#   - step-01-discover-epics
#   - step-02-build-status
#   - step-03-generate-file
#   - step-04-validate-report
# spec: spec-p5-ai-supercharge.md
# commit: 72c0dee
---

# STATUS DEFINITIONS:
# ==================
# Epic Status:
#   - backlog: Epic not yet started
#   - in-progress: Epic actively being worked on
#   - done: All stories in epic completed
#
# Story Status:
#   - backlog: Story only exists in spec
#   - ready-for-dev: Story file created, ACs clarified
#   - in-progress: Developer actively working
#   - review: Ready for code review
#   - done: Completed, all tests passing
#
# Retrospective Status:
#   - optional: Can be completed but not required
#   - done: Retrospective has been completed

generated: 2026-05-31T12:07:15+02:00
project: QC_LIMS_Ao
project_key: qc_lims
tracking_system: BMAD
story_location: .a0proj/_bmad-output/implementation-artifacts/stories/

development_status:
  # Epic 5 — P5 AI Supercharge
  epic-5: in-progress

  # Task 1: Letta Service Layer Foundation
  5-1-letta-service-layer: review

  # Task 2: Create 5 Letta Agents on KVM4
  5-2-letta-agents: backlog

  # Task 3: SOP RAG Pipeline — Document Ingestion
  5-3-sop-rag-pipeline: backlog

  # Task 4: CAPA Assistant Integration
  5-4-capa-assistant: backlog

  # Task 5: COA Auto-Generator
  5-5-coa-auto-generator: backlog

  # Task 6: GMP Chat Widget (Frontend)
  5-6-gmp-chat-widget: backlog

  # Task 7: AI API Router
  5-7-ai-api-router: backlog

  # Task 8: SSH Tunnel Configuration
  5-8-ssh-tunnel-docs: backlog

  # Task 9: Document Ingestion Workflow
  5-9-ingestion-cli: backlog

  # Task 10: Testing & Validation
  5-10-testing-validation: backlog

  epic-5-retrospective: optional

# SPRINT PLAN — P5 AI Supercharge
# =================================

sprint_plan:
  name: "Sprint P5 — AI Supercharge"
  goal: "Deploy Letta-powered GMP compliance assistant with RAG, CAPA guidance, COA auto-generation, and embedded chat widget"
  start_date: 2026-05-31
  target_end_date: 2026-06-14
  velocity: 32

  stories:
    - id: 5-1
      key: 5-1-letta-service-layer
      title: "Letta Service Layer Foundation"
      description: "Create LettaService singleton, extend Settings with Letta/Qdrant/Voyage config, implement health checks"
      files:
        - backend/app/services/letta_service.py
        - backend/app/core/config.py
      estimate: 3
      priority: P0
      dependencies: []
      acceptance_criteria:
        - AC-1.1: Settings class extended with letta_base_url, letta_mcp_url, qdrant_url, voyage_api_key
        - AC-1.2: LettaService singleton with lazy init and thread-safe instance
        - AC-1.3: Health check method for Letta API, Qdrant, MCP
      branch: feature/p5-letta-service

    - id: 5-2
      key: 5-2-letta-agents
      title: "Create 5 Letta Agents on KVM4"
      description: "Create GMP Expert, SOP Writer, CAPA Manager, COA Generator, QMS Orchestrator agents via Letta API"
      estimate: 5
      priority: P0
      dependencies: [5-1]
      acceptance_criteria:
        - AC-2.1: All 5 agents created with correct system prompts
        - AC-2.2: Agents have memory blocks for facility context and RAG collections
        - AC-2.3: Agent IDs persisted in config for service layer consumption
      branch: feature/p5-letta-service

    - id: 5-3
      key: 5-3-sop-rag-pipeline
      title: "SOP RAG Pipeline — Document Ingestion"
      description: "DOCX/PDF extraction, section-aware chunking, Voyage-3 embedding, Qdrant upsert, CLI script"
      files:
        - scripts/ingest_sops.py
        - backend/app/services/sop_rag_service.py
      estimate: 5
      priority: P0
      dependencies: [5-1]
      acceptance_criteria:
        - AC-3.1: DOCX ingestion processes QCSOP docs without errors
        - AC-3.2: Chunks stored in Qdrant pp_qms_sops with metadata
        - AC-3.3: Semantic search returns relevant SOP sections
        - AC-3.4: Version tagging handles superseded docs correctly
      branch: feature/p5-sop-rag

    - id: 5-4
      key: 5-4-capa-assistant
      title: "CAPA Assistant Integration"
      description: "CAPAAgentService with Phase I/II suggestion methods, OOS API extensions, RAG over historical OOS"
      files:
        - backend/app/services/capa_agent_service.py
        - backend/app/api/oos.py
      estimate: 5
      priority: P1
      dependencies: [5-1, 5-2]
      acceptance_criteria:
        - AC-4.1: Phase I suggestions include all 5M categories
        - AC-4.2: Root cause suggestions reference historical OOS patterns
        - AC-4.3: Investigation form draft with QCSOP 019-A01/A02 structure
        - AC-4.4: AI suggestions logged in audit trail
      branch: feature/p5-capa-agent

    - id: 5-5
      key: 5-5-coa-auto-generator
      title: "COA Auto-Generator"
      description: "COAAutoGenerator service that drafts COA from spec + test results using Letta agent"
      files:
        - backend/app/services/coa_auto_generator.py
        - backend/app/api/coa.py
      estimate: 4
      priority: P1
      dependencies: [5-1, 5-2]
      acceptance_criteria:
        - AC-5.1: Draft COA generated from spec + results in <10s
        - AC-5.2: Output follows QCCoA 001 template structure
        - AC-5.3: Remarks suggested for borderline/out-of-trend results
        - AC-5.4: Generated drafts marked AI-ASSISTED pending human review
      branch: feature/p5-coa-generator

    - id: 5-6
      key: 5-6-gmp-chat-widget
      title: "GMP Chat Widget (Frontend)"
      description: "React chat widget with SSE streaming, source citations, quick actions, PDF export"
      files:
        - frontend/src/components/GMPChatWidget.tsx
        - frontend/src/services/aiService.ts
      estimate: 5
      priority: P1
      dependencies: [5-1, 5-7]
      acceptance_criteria:
        - AC-6.1: Widget mounts in all LIMS modules (floating button)
        - AC-6.2: Streaming responses display progressively
        - AC-6.3: Source citations link to SOP documents
        - AC-6.4: Chat exportable to PDF for audit trail
        - AC-6.5: Quick action buttons for context-specific queries
      branch: feature/p5-chat-widget

    - id: 5-7
      key: 5-7-ai-api-router
      title: "AI API Router"
      description: "FastAPI router for /ai/chat, /ai/query-gmp-expert, /ai/health with SSE streaming"
      files:
        - backend/app/api/ai.py
        - backend/app/models/chat.py
      estimate: 3
      priority: P1
      dependencies: [5-1]
      acceptance_criteria:
        - AC-7.1: Streaming chat endpoint with SSE
        - AC-7.2: Direct GMP Expert query endpoint
        - AC-7.3: Health check for Letta + Qdrant + MCP
      branch: feature/p5-chat-widget

    - id: 5-8
      key: 5-8-ssh-tunnel-docs
      title: "SSH Tunnel Configuration Documentation"
      description: "Document SSH tunnel setup for ports 8283, 6333, 6507 with health check verification"
      estimate: 1
      priority: P2
      dependencies: []
      acceptance_criteria:
        - AC-8.1: Tunnel command documented with all 3 ports
        - AC-8.2: Port mapping table in spec
        - AC-8.3: Health check endpoint verifies connectivity
      branch: docs/p5-ssh-tunnel

    - id: 5-9
      key: 5-9-ingestion-cli
      title: "Document Ingestion CLI"
      description: "CLI script for batch/full-folder/single-file ingestion with verify and sync modes"
      files:
        - scripts/ingest_sops.py
      estimate: 2
      priority: P2
      dependencies: [5-3]
      acceptance_criteria:
        - AC-9.1: Full folder ingestion supported
        - AC-9.2: Single document ingestion supported
        - AC-9.3: Verify mode checks collection consistency
        - AC-9.4: Sync mode detects new/modified files
      branch: feature/p5-sop-rag

    - id: 5-10
      key: 5-10-testing-validation
      title: "Testing & Validation"
      description: "Unit tests, integration tests, benchmarks for all P5 components"
      files:
        - backend/tests/test_ai_*.py
      estimate: 5
      priority: P1
      dependencies: [5-1, 5-2, 5-3, 5-4, 5-5, 5-6, 5-7]
      acceptance_criteria:
        - AC-10.1: Unit tests for Letta service (mocked)
        - AC-10.2: Integration tests with KVM4 services
        - AC-10.3: CAPA suggestion accuracy >80%
        - AC-10.4: RAG retrieval precision top-3
        - AC-10.5: COA generation <10s benchmark
      branch: feature/p5-testing

  dependencies:
    - from: 5-2
      to: 5-1
      type: hard
    - from: 5-3
      to: 5-1
      type: hard
    - from: 5-4
      to: 5-1
      type: hard
    - from: 5-4
      to: 5-2
      type: hard
    - from: 5-5
      to: 5-1
      type: hard
    - from: 5-5
      to: 5-2
      type: hard
    - from: 5-6
      to: 5-1
      type: hard
    - from: 5-6
      to: 5-7
      type: hard
    - from: 5-7
      to: 5-1
      type: hard
    - from: 5-9
      to: 5-3
      type: hard
    - from: 5-10
      to: 5-1
      type: hard
    - from: 5-10
      to: 5-2
      type: hard
    - from: 5-10
      to: 5-3
      type: hard
    - from: 5-10
      to: 5-4
      type: hard
    - from: 5-10
      to: 5-5
      type: hard
    - from: 5-10
      to: 5-6
      type: hard
    - from: 5-10
      to: 5-7
      type: hard

  risk_register:
    - risk: "SSH tunnel to KVM4 not operational"
      impact: high
      mitigation: "Health checks surface connectivity issues; implement mock mode for offline dev"
    - risk: "Letta agent prompt quality below threshold"
      impact: medium
      mitigation: "2-3 refinement cycles planned; benchmark after Task 2"
    - risk: "VoyageAI API rate limits during bulk ingestion"
      impact: medium
      mitigation: "Batch with 1s delay between requests; implement retry with backoff"
    - risk: "OOS RAG data privacy (anonymization)"
      impact: high
      mitigation: "Anonymize batch numbers and shift dates before embedding"

  architecture_ref: /a0/usr/projects/qc_lims/.a0proj/_bmad-output/planning-artifacts/architecture-qc_lims-p5-ai-supercharge.md
  summary:
    total_stories: 10
    total_points: 38
    p0_stories: 3
    p0_points: 13
    p1_stories: 5
    p1_points: 22
    p2_stories: 2
    p2_points: 3
    critical_path: [5-1, 5-2, 5-4, 5-5, 5-7, 5-6, 5-10]

---
story_key: 5-1-letta-service-layer
epic: 5
title: Letta Service Layer Foundation
status: done
startedAt: 2026-05-31T12:30:00+02:00
stepsCompleted: ["step-01-find-story", "step-02-load-context", "step-03-detect-continuation", "step-04-mark-in-progress", "step-05-implement-task", "step-06-author-tests", "step-07-run-validations", "step-08-validate-complete", "step-09-completion-gate", "step-10-communication"]
---

# Story 5.1: Letta Service Layer Foundation

## Description
Create the foundational service layer for Letta AI integration, including configuration settings, client singleton, and health checks for Letta API, Qdrant, and MCP services.

## Acceptance Criteria

- [x] AC-1.1: Settings class extended with letta_base_url, letta_mcp_url, qdrant_url, voyage_api_key
- [x] AC-1.2: LettaService singleton with lazy init and thread-safe instance
- [x] AC-1.3: Health check method for Letta API, Qdrant, MCP

## Tasks

### Task 1.1: Extend Settings
- [x] Extend `backend/app/core/config.py` with Letta/Qdrant/Voyage settings.

### Task 1.2: Create LettaService
- [x] Create `backend/app/services/letta_service.py` with singleton pattern.

### Task 1.3: Write Tests
- [x] Create `backend/tests/test_letta_service.py` with mocked Letta client.

### Task 1.4: Run Tests
- [x] Run full test suite, ensure all pass.

## Dev Agent Record

### Files Changed
- `backend/app/core/config.py` — extended with AI service settings (letta_base_url, letta_mcp_url, voyage_api_key)
- `backend/app/services/letta_service.py` — new LettaService class with singleton, health check, agent listing
- `backend/tests/test_letta_service.py` — 10 unit tests covering all 3 ACs (mocked Letta/Qdrant/MCP)

### Completion Notes
- All 10 tests pass (fixed QdrantService mock target: app.services.qdrant_service)
- AC-1.1: config.py lines 48-52 — all 4 fields added
- AC-1.2: get_letta_service() singleton + letta property lazy init — 3 tests verify
- AC-1.3: health_check(), health_check_mcp(), health_check_all() — 5 tests cover healthy, unreachable, aggregate, failure detection

### Decisions
- Mirrored QdrantService singleton pattern for consistency
- Used `letta_client` v1.12.0 (latest available)
- Health check returns structured dict, never raises unhandled exceptions
- MCP health check uses httpx with 5s timeout

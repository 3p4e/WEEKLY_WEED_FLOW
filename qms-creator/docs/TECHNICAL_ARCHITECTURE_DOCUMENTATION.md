# Cannabis EU GMP QMS Creator - Technical Architecture Documentation

**Document Version**: 2.0
**Classification**: GMP Controlled Document
**Date**: 2026-01-30
**Status**: Production Release

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Nine-Agent Orchestration System](#2-nine-agent-orchestration-system)
3. [Progressive Context Accumulation](#3-progressive-context-accumulation)
4. [Two-Phase Workflow Architecture](#4-two-phase-workflow-architecture)
5. [Database Architecture](#5-database-architecture)
6. [Quality Assurance Framework](#6-quality-assurance-framework)
7. [Design Philosophy](#7-design-philosophy)

---

## 1. Executive Overview

### 1.1 Platform Purpose

The Cannabis EU GMP QMS Creator is a pharmaceutical-grade document generation platform designed for cannabis facilities operating under European Good Manufacturing Practice (GMP) regulations. The system serves facilities navigating:

- **EudraLex Volume 4** - EU Guidelines for Good Manufacturing Practice
- **ICH Guidelines** - Q7 (API), Q8 (Development), Q9 (Risk Management), Q10 (PQS)
- **WHO GACP** - Good Agricultural and Collection Practices
- **MALMED Regulations** - North Macedonian Agency for Medicines and Medical Devices

### 1.2 Core Capabilities

| Capability | Description |
|------------|-------------|
| **Intelligent SOP Generation** | AI-powered creation of EU GMP compliant Standard Operating Procedures |
| **Dual-Database RAG** | Regulatory knowledge (DB1) + Operational examples (DB2) |
| **Nine-Agent Pipeline** | Specialized AI agents for each document section |
| **Quality Gates** | Multi-stage validation ensuring GMP compliance |
| **Bilingual Support** | English primary with Macedonian UI localization |

### 1.3 Regulatory Compliance Framework

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGULATORY HIERARCHY                          │
├─────────────────────────────────────────────────────────────────┤
│  Level 1: EU GMP (EudraLex Volume 4)                            │
│    └── Chapters 1-9: Core GMP Requirements                      │
│    └── Annex 7: Herbal Medicinal Products                       │
│    └── Annex 11: Computerised Systems                           │
│    └── Annex 15: Qualification and Validation                   │
├─────────────────────────────────────────────────────────────────┤
│  Level 2: ICH Guidelines                                         │
│    └── Q7: Good Manufacturing Practice for APIs                 │
│    └── Q9: Quality Risk Management                              │
│    └── Q10: Pharmaceutical Quality System                       │
├─────────────────────────────────────────────────────────────────┤
│  Level 3: WHO GACP                                               │
│    └── Medicinal Plant Cultivation Standards                    │
│    └── Collection and Processing Requirements                   │
├─────────────────────────────────────────────────────────────────┤
│  Level 4: National (MALMED)                                      │
│    └── North Macedonian GMP Implementation                      │
│    └── Local Registration Requirements                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Nine-Agent Orchestration System

### 2.1 Agent Architecture Overview

The platform employs nine specialized AI agents organized into a sequential pipeline. Each agent has distinct responsibilities, custom instructions, and quality criteria.

### 2.2 Agent Definitions

#### Agent 1: Metadata Collector (Interactive)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Document initialization and metadata capture |
| **Phase** | Content Development |
| **Input** | User form submission |
| **Output** | Structured metadata object |

**Custom Instructions:**
```
You are a GMP Document Control Specialist. Capture:
- Document title, code, version
- Department and facility type
- Author, reviewer, approver designations
- Effective date and review cycle
- Document classification (GMP Critical/Relevant/Administrative)
```

**Quality Criteria:**
- All mandatory fields populated
- Document code follows naming convention
- Valid department assignment
- Appropriate classification selected

---

#### Agent 2: Introduction Questionnaire (Interactive)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Gather purpose, scope, and regulatory context |
| **Phase** | Content Development |
| **Input** | Metadata + contextual questions |
| **Output** | Purpose/Scope specifications |

**Custom Instructions:**
```
You are an EU GMP Regulatory Specialist. Generate contextual questions about:
- Primary purpose and business need
- Regulatory drivers (EU GMP chapters, ICH sections)
- Scope boundaries (in/out of scope)
- Applicable areas, personnel, products
Search DB1 for relevant regulatory requirements.
```

**Quality Criteria:**
- Regulatory alignment identified
- Clear scope boundaries defined
- Applicable personnel specified
- Cross-references to related SOPs noted

---

#### Agent 3: Procedure Questionnaire (Interactive)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Capture detailed procedural requirements |
| **Phase** | Content Development |
| **Input** | Metadata + Purpose/Scope + questions |
| **Output** | Procedure specifications |

**Custom Instructions:**
```
You are a GMP Process Engineer. Gather:
- Step-by-step procedure requirements
- Equipment and materials needed
- Critical parameters and acceptance criteria
- Safety and PPE requirements
- In-process checks and decision points
Search DB2 for operational examples and templates.
```

**Quality Criteria:**
- Logical step sequence
- Measurable acceptance criteria
- Safety considerations addressed
- Equipment clearly identified

---

#### Agent 4: Compliance Analyzer (Automated)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Validate regulatory compliance |
| **Phase** | Content Development |
| **Input** | All previous agent outputs |
| **Output** | Compliance assessment report |

**Custom Instructions:**
```
You are an EU GMP Compliance Auditor. Analyze content against:
- EudraLex Volume 4 requirements
- ICH Q7/Q9/Q10 guidelines
- WHO GACP standards
- ALCOA+ data integrity principles
Flag gaps and recommend citations.
PRIMARY SOURCE: DB1 (Regulatory Knowledge Base)
```

**Quality Criteria:**
- All applicable regulations identified
- Specific clause citations provided
- Compliance gaps flagged
- Remediation recommendations included

---

#### Agent 5: RACI Generator (Automated)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Create responsibility matrix |
| **Phase** | Content Development |
| **Input** | Procedure steps + organizational context |
| **Output** | RACI matrix |

**Custom Instructions:**
```
You are a GMP Organizational Specialist. Generate RACI matrix:
- R (Responsible): Who performs the task
- A (Accountable): Who is ultimately answerable (ONE per activity)
- C (Consulted): Who provides input before execution
- I (Informed): Who needs notification of results
Ensure segregation of duties per EU GMP.
```

**Quality Criteria:**
- Each activity has exactly ONE Accountable
- Each activity has at least one Responsible
- QA independence maintained
- Segregation of duties enforced

---

#### Agent 6: QA Reviewer (Interactive)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Quality assurance review and approval |
| **Phase** | Quality Gate |
| **Input** | All generated content sections |
| **Output** | QA assessment with recommendations |

**Custom Instructions:**
```
You are a GMP Quality Assurance Manager. Review:
- Internal consistency across sections
- Regulatory compliance completeness
- Terminology consistency
- Cross-reference accuracy
Provide quality score (0-100) and specific recommendations.
```

**Quality Criteria:**
- Overall score >= 80 for approval
- No critical deficiencies
- All cross-references valid
- Consistent terminology throughout

---

#### Agent 7: Document Formatter (Automated)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Generate final formatted document |
| **Phase** | Template Formatting |
| **Input** | QA-approved content |
| **Output** | DOCX file with professional formatting |

**Custom Instructions:**
```
You are a GMP Document Formatter. Apply:
- Purely Plant corporate styling
- Professional cover page with signatures
- Table of contents generation
- Section numbering and formatting
- RACI matrix styling
- Approval page with signature blocks
```

**Quality Criteria:**
- Consistent heading hierarchy
- Proper table formatting
- All sections present
- Print-ready layout

---

#### Agent 8: Annex Questionnaire (Interactive)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Gather annex/appendix requirements |
| **Phase** | Template Formatting |
| **Input** | Main document + annex requests |
| **Output** | Annex specifications |

**Custom Instructions:**
```
You are a GMP Forms Specialist. For each requested annex:
- Determine form type (checklist, log, template)
- Identify required data fields
- Define validation rules
- Establish traceability requirements
Reference DB2 for operational form examples.
```

**Quality Criteria:**
- All requested annexes addressed
- Complete data field specifications
- GMP traceability maintained
- Standalone printable format

---

#### Agent 9: Annex Formatter (Automated)

| Attribute | Specification |
|-----------|---------------|
| **Role** | Generate formatted annexes |
| **Phase** | Template Formatting |
| **Input** | Annex specifications |
| **Output** | Formatted annexes appended to DOCX |

**Custom Instructions:**
```
You are a GMP Annex Formatter. Create:
- Standalone printable forms
- Signature and date fields
- Revision tracking blocks
- Instructions for completion
Ensure EU GMP documentation compliance.
```

**Quality Criteria:**
- Each annex standalone and printable
- All required fields present
- Clear completion instructions
- Proper labeling (Annex A, B, C...)

---

### 2.3 Agent Communication Protocol

```
┌─────────────────────────────────────────────────────────────────┐
│                 AGENT COMMUNICATION MATRIX                       │
├─────────┬─────────┬─────────┬─────────┬─────────────────────────┤
│ From/To │ Agent 2 │ Agent 3 │ Agent 4 │ Agent 5-9              │
├─────────┼─────────┼─────────┼─────────┼─────────────────────────┤
│ Agent 1 │ META    │ META    │ META    │ META (via pipeline)    │
│ Agent 2 │ -       │ SCOPE   │ SCOPE   │ SCOPE (via pipeline)   │
│ Agent 3 │ -       │ -       │ PROC    │ PROC (via pipeline)    │
│ Agent 4 │ -       │ -       │ -       │ COMPLIANCE             │
│ Agent 5 │ -       │ -       │ -       │ RACI                   │
└─────────┴─────────┴─────────┴─────────┴─────────────────────────┘

Legend:
META = Metadata Object
SCOPE = Purpose/Scope Specifications
PROC = Procedure Specifications
COMPLIANCE = Regulatory Assessment
RACI = Responsibility Matrix
```

---

## 3. Progressive Context Accumulation

### 3.1 Methodology Overview

Progressive Context Accumulation (PCA) is the core methodology enabling coherent document generation. User input from the dynamic questionnaire is sequentially refined through the agent pipeline, building comprehensive context from initial request to final output.

### 3.2 Context Flow Model

```
STAGE 1: INITIALIZATION
┌─────────────────────────────────────────────────────────────────┐
│  User Input (Metadata Form)                                      │
│  ├── SOP Title: "Raw Material Sampling Procedure"               │
│  ├── Document Code: "SOP-QC-001"                                │
│  ├── Department: "Quality Control"                              │
│  └── Classification: "GMP Critical"                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
STAGE 2: CONTEXT ENRICHMENT (Agent 2)
┌─────────────────────────────────────────────────────────────────┐
│  Accumulated Context                                             │
│  ├── [Metadata from Stage 1]                                    │
│  ├── Purpose: "Ensure representative sampling..."               │
│  ├── Regulatory Basis: "EU GMP Annex 8, ICH Q7 Section 7"      │
│  ├── Scope: "All incoming cannabis raw materials"               │
│  └── Applicable Areas: "Receiving, QC Laboratory"               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
STAGE 3: PROCEDURAL DETAIL (Agent 3)
┌─────────────────────────────────────────────────────────────────┐
│  Accumulated Context                                             │
│  ├── [All previous context]                                     │
│  ├── Procedure Steps: [1. Verify documentation, 2. Don PPE...] │
│  ├── Equipment: ["Sterile sampling tools", "Sample containers"]│
│  ├── Critical Parameters: ["Sample size: 10g minimum"]         │
│  └── Safety: ["Wear gloves", "Work in laminar flow hood"]      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
STAGE 4: COMPLIANCE VALIDATION (Agent 4)
┌─────────────────────────────────────────────────────────────────┐
│  Accumulated Context                                             │
│  ├── [All previous context]                                     │
│  ├── Regulatory Citations: ["EU GMP 6.11", "ICH Q7 7.3"]       │
│  ├── Compliance Score: 92/100                                   │
│  ├── Gaps Identified: ["Add temperature monitoring"]            │
│  └── Recommendations: ["Include chain of custody form"]         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
STAGE 5: RESPONSIBILITY ASSIGNMENT (Agent 5)
┌─────────────────────────────────────────────────────────────────┐
│  Accumulated Context                                             │
│  ├── [All previous context]                                     │
│  └── RACI Matrix:                                               │
│      ├── Sample Collection: R=QC Analyst, A=QC Manager         │
│      ├── Documentation: R=QC Analyst, A=QC Manager, I=QA       │
│      └── Release Decision: R=QC Manager, A=QA Manager          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
STAGE 6: QUALITY REVIEW (Agent 6)
┌─────────────────────────────────────────────────────────────────┐
│  Complete Document Context                                       │
│  ├── [All accumulated context - COMPLETE]                       │
│  ├── QA Score: 94/100                                           │
│  ├── Section Scores: {purpose: 95, procedure: 92, raci: 96}    │
│  └── Status: APPROVED FOR FORMATTING                            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Context Injection Points

| Agent | Context Received | Context Contributed |
|-------|------------------|---------------------|
| Agent 1 | None (initiator) | Metadata object |
| Agent 2 | Metadata | Purpose, scope, regulatory basis |
| Agent 3 | Metadata + Purpose/Scope | Procedure steps, equipment, parameters |
| Agent 4 | Full content | Compliance assessment, citations |
| Agent 5 | Full content | RACI matrix |
| Agent 6 | Full content + assessments | QA approval, recommendations |
| Agent 7 | QA-approved content | Formatted DOCX |
| Agent 8 | Main document | Annex specifications |
| Agent 9 | Annex specs | Formatted annexes |

### 3.4 RAG Context Enrichment

At each stage, agents query the dual-database RAG system:

```python
def enrich_context(agent_role: str, current_context: Dict) -> Dict:
    """
    Enrich context with RAG search results.

    DB1 Priority Topics: regulatory, definitions, compliance
    DB2 Priority Topics: procedure, forms, operational examples
    """
    # Build query from current context
    query = build_rag_query(agent_role, current_context)

    # Detect gap topics (areas with limited DB2 coverage)
    gap_info = detect_gap_topic(query, current_context['sop_name'])

    # Adjust weights based on agent role and gaps
    if gap_info:
        db1_weight = 0.8  # Prioritize regulatory guidance
        db2_weight = 0.2
    else:
        db1_weight = ROLE_WEIGHTS[agent_role]['db1']
        db2_weight = ROLE_WEIGHTS[agent_role]['db2']

    # Execute dual search
    results = dual_db_search(query, db1_weight, db2_weight)

    # Enrich passage metadata
    enriched_results = enrich_passages(results)

    return merge_context(current_context, enriched_results)
```

---

## 4. Two-Phase Workflow Architecture

### 4.1 Phase Separation Rationale

The workflow is divided into two distinct phases to enable:

1. **Independent Quality Review Cycles** - Content can be validated before formatting
2. **Specialized Agent Focus** - Content agents focus on accuracy; formatting agents on presentation
3. **Efficient Iteration** - Content changes don't require reformatting; formatting changes don't affect content
4. **Clear Accountability** - Distinct ownership for content vs. presentation quality

### 4.2 Phase 1: Content Development

**Focus**: Pharmaceutical accuracy, regulatory compliance, technical writing

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: CONTENT DEVELOPMENT                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │ Agent 1  │───▶│ Agent 2  │───▶│ Agent 3  │                   │
│  │ Metadata │    │ Intro Q  │    │ Proc Q   │                   │
│  │ (User)   │    │ (AI+User)│    │ (AI+User)│                   │
│  └──────────┘    └──────────┘    └──────────┘                   │
│                                       │                          │
│                                       ▼                          │
│                  ┌──────────┐    ┌──────────┐                   │
│                  │ Agent 5  │◀───│ Agent 4  │                   │
│                  │ RACI     │    │ Complian.│                   │
│                  │ (Auto)   │    │ (Auto)   │                   │
│                  └──────────┘    └──────────┘                   │
│                       │                                          │
│                       ▼                                          │
│              ┌────────────────┐                                  │
│              │    Agent 6     │                                  │
│              │   QA Review    │                                  │
│              │  (Interactive) │                                  │
│              └────────────────┘                                  │
│                       │                                          │
│                       ▼                                          │
│              ┌────────────────┐                                  │
│              │  QUALITY GATE  │                                  │
│              │  Score >= 80?  │                                  │
│              └────────────────┘                                  │
│                    │    │                                        │
│              YES ──┘    └── NO (Return to Agent 2-5)            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Phase 1 Outputs:**
- Validated metadata
- Purpose and scope sections
- Regulatory requirements section
- Procedure steps with parameters
- RACI responsibility matrix
- QA assessment report

### 4.3 Phase 2: Template Formatting

**Focus**: Document structure, professional presentation, final output

```
┌─────────────────────────────────────────────────────────────────┐
│                  PHASE 2: TEMPLATE FORMATTING                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                QA-APPROVED CONTENT                      │     │
│  │  (From Phase 1 Quality Gate)                           │     │
│  └────────────────────────────────────────────────────────┘     │
│                            │                                     │
│                            ▼                                     │
│                    ┌──────────────┐                              │
│                    │   Agent 7    │                              │
│                    │  Formatter   │                              │
│                    │   (Auto)     │                              │
│                    └──────────────┘                              │
│                            │                                     │
│                            ▼                                     │
│                    ┌──────────────┐                              │
│                    │  Main DOCX   │                              │
│                    │  Generated   │                              │
│                    └──────────────┘                              │
│                            │                                     │
│              ┌─────────────┴─────────────┐                      │
│              │   Annexes Requested?       │                      │
│              └─────────────┬─────────────┘                      │
│                    YES     │     NO                              │
│                      │     └─────────────────┐                  │
│                      ▼                       │                   │
│              ┌──────────────┐                │                   │
│              │   Agent 8    │                │                   │
│              │  Annex Q     │                │                   │
│              │ (Interactive)│                │                   │
│              └──────────────┘                │                   │
│                      │                       │                   │
│                      ▼                       │                   │
│              ┌──────────────┐                │                   │
│              │   Agent 9    │                │                   │
│              │ Annex Format │                │                   │
│              │   (Auto)     │                │                   │
│              └──────────────┘                │                   │
│                      │                       │                   │
│                      ▼                       ▼                   │
│              ┌────────────────────────────────┐                 │
│              │      FINAL DOCUMENT OUTPUT     │                 │
│              │  (Main SOP + Annexes in DOCX)  │                 │
│              └────────────────────────────────┘                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Phase 2 Outputs:**
- Professional DOCX with corporate styling
- Cover page with signature blocks
- Table of contents
- Formatted sections with proper numbering
- RACI matrix with professional styling
- Annexes (forms, checklists, templates)
- Approval page

### 4.4 Quality Gate Criteria

| Criterion | Threshold | Action if Failed |
|-----------|-----------|------------------|
| Overall QA Score | >= 80/100 | Return to content agents |
| Critical Deficiencies | 0 | Immediate remediation |
| Regulatory Citations | 100% valid | Return to Agent 4 |
| Cross-References | 100% valid | Return to Agent 6 |
| Terminology Consistency | >= 95% | Return to Agent 6 |

---

## 5. Database Architecture

### 5.1 Dual-Database Design Philosophy

The platform employs two complementary databases with distinct purposes:

- **DB1 (Regulatory Knowledge Base)**: Single source of truth for regulatory requirements
- **DB2 (Operational Context Store)**: Facility-specific data and session management

### 5.2 DB1: Regulatory Knowledge Base

#### 5.2.1 Purpose and Scope

DB1 serves as the authoritative source for:
- EudraLex Volume 4 (EU GMP Guidelines)
- ICH Q7/Q8/Q9/Q10 standards
- WHO GACP requirements
- MALMED national regulations
- Regulatory terminology and definitions

#### 5.2.2 Schema Design

```sql
-- DB1 SCHEMA: REGULATORY KNOWLEDGE BASE

-- Regulatory Bodies (EudraLex, ICH, WHO, MALMED)
CREATE TABLE regulatory_bodies (
    id UUID PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,      -- 'EUDRALEX', 'ICH', 'WHO', 'MALMED'
    name VARCHAR(255) NOT NULL,
    jurisdiction VARCHAR(100),
    website_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Regulatory Documents
CREATE TABLE regulatory_documents (
    id UUID PRIMARY KEY,
    body_id UUID REFERENCES regulatory_bodies(id),
    document_code VARCHAR(50) NOT NULL,    -- 'EU_GMP_CH4', 'ICH_Q7', etc.
    title VARCHAR(500) NOT NULL,
    version VARCHAR(20),
    effective_date DATE,
    document_type VARCHAR(50),             -- 'chapter', 'annex', 'guideline'
    full_text TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Regulatory Sections (Chapters, Articles, Clauses)
CREATE TABLE regulatory_sections (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES regulatory_documents(id),
    section_number VARCHAR(50) NOT NULL,   -- '4.1', '7.2.3', 'Annex 11.1'
    title VARCHAR(500),
    content TEXT NOT NULL,
    parent_section_id UUID REFERENCES regulatory_sections(id),
    hierarchy_level INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Regulatory Terms and Definitions
CREATE TABLE regulatory_terms (
    id UUID PRIMARY KEY,
    term VARCHAR(255) NOT NULL,
    definition TEXT NOT NULL,
    source_document_id UUID REFERENCES regulatory_documents(id),
    source_section VARCHAR(50),
    abbreviation VARCHAR(50),
    synonyms TEXT[],                       -- Array of alternative terms
    created_at TIMESTAMP DEFAULT NOW()
);

-- Regulatory Citations (for cross-referencing)
CREATE TABLE regulatory_citations (
    id UUID PRIMARY KEY,
    citing_section_id UUID REFERENCES regulatory_sections(id),
    cited_section_id UUID REFERENCES regulatory_sections(id),
    citation_type VARCHAR(50),             -- 'reference', 'supersedes', 'extends'
    citation_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector Embeddings for RAG Search
CREATE TABLE regulatory_embeddings (
    id UUID PRIMARY KEY,
    section_id UUID REFERENCES regulatory_sections(id),
    embedding_vector VECTOR(1536),         -- For nomic-embed-text
    chunk_text TEXT,
    chunk_index INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_reg_docs_body ON regulatory_documents(body_id);
CREATE INDEX idx_reg_sections_doc ON regulatory_sections(document_id);
CREATE INDEX idx_reg_sections_parent ON regulatory_sections(parent_section_id);
CREATE INDEX idx_reg_terms_term ON regulatory_terms(term);
CREATE INDEX idx_reg_embeddings_vector ON regulatory_embeddings
    USING ivfflat (embedding_vector vector_cosine_ops);
```

#### 5.2.3 Query Mechanisms

```python
class RegulatoryKnowledgeBase:
    """DB1 Query Interface for Regulatory Knowledge."""

    def search_by_citation(self, citation: str) -> List[RegulatorySection]:
        """
        Search for specific regulatory citation.
        Example: "EU GMP Chapter 4, Section 4.1"
        """
        pass

    def search_by_topic(self, topic: str, body: str = None) -> List[RegulatorySection]:
        """
        Semantic search for regulatory content by topic.
        Uses vector embeddings for similarity matching.
        """
        pass

    def get_definitions(self, terms: List[str]) -> Dict[str, RegulatoryTerm]:
        """
        Retrieve official regulatory definitions for terms.
        """
        pass

    def validate_citation(self, citation: str) -> ValidationResult:
        """
        Validate that a regulatory citation exists and is current.
        """
        pass

    def get_related_requirements(self, section_id: UUID) -> List[RegulatorySection]:
        """
        Find related regulatory requirements via citation graph.
        """
        pass
```

### 5.3 DB2: Operational Context Store

#### 5.3.1 Purpose and Scope

DB2 serves as the repository for:
- Facility-specific configurations
- Equipment and personnel databases
- Session and workflow state
- Audit trails
- Operational document templates
- Bilingual formatting rules

#### 5.3.2 Schema Design

```sql
-- DB2 SCHEMA: OPERATIONAL CONTEXT STORE

-- Facilities
CREATE TABLE facilities (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE,
    facility_type VARCHAR(100),            -- 'cultivation', 'processing', 'laboratory'
    address TEXT,
    gmp_license_number VARCHAR(100),
    license_expiry DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Departments
CREATE TABLE departments (
    id UUID PRIMARY KEY,
    facility_id UUID REFERENCES facilities(id),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20),
    manager_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Personnel
CREATE TABLE personnel (
    id UUID PRIMARY KEY,
    facility_id UUID REFERENCES facilities(id),
    department_id UUID REFERENCES departments(id),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    job_title VARCHAR(200),
    job_title_mk VARCHAR(200),             -- Macedonian translation
    email VARCHAR(255),
    qualifications TEXT[],
    training_status JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Equipment
CREATE TABLE equipment (
    id UUID PRIMARY KEY,
    facility_id UUID REFERENCES facilities(id),
    department_id UUID REFERENCES departments(id),
    name VARCHAR(255) NOT NULL,
    name_mk VARCHAR(255),                  -- Macedonian translation
    equipment_code VARCHAR(50),
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    serial_number VARCHAR(100),
    qualification_status VARCHAR(50),      -- 'qualified', 'pending', 'expired'
    last_calibration DATE,
    next_calibration DATE,
    location VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User Sessions
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    facility_id UUID REFERENCES facilities(id),
    session_token VARCHAR(500),
    language_preference VARCHAR(10) DEFAULT 'en',  -- 'en' or 'mk'
    started_at TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    metadata JSONB
);

-- Workflow States
CREATE TABLE workflow_states (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES user_sessions(id),
    workflow_type VARCHAR(50) NOT NULL,    -- 'sop_generation', 'annex_creation'
    current_agent INTEGER,
    current_phase VARCHAR(50),             -- 'content_development', 'template_formatting'
    status VARCHAR(50),                    -- 'in_progress', 'completed', 'failed'
    metadata JSONB,                        -- SOP title, code, etc.
    agent_responses JSONB,                 -- Accumulated context
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Audit Trail
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES user_sessions(id),
    workflow_id UUID REFERENCES workflow_states(id),
    action_type VARCHAR(100) NOT NULL,     -- 'agent_start', 'user_input', 'document_generated'
    action_details JSONB,
    performed_by UUID,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Document Templates (Entity QMS Examples)
CREATE TABLE document_templates (
    id UUID PRIMARY KEY,
    facility_id UUID REFERENCES facilities(id),
    template_type VARCHAR(100),            -- 'sop', 'form', 'checklist', 'log'
    category VARCHAR(100),                 -- 'production', 'qc_sampling', 'sanitation'
    title VARCHAR(500),
    title_mk VARCHAR(500),
    content TEXT,
    file_path VARCHAR(500),
    quality_score DECIMAL(3,1),
    regulatory_alignment DECIMAL(3,1),
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Template Embeddings for RAG Search
CREATE TABLE template_embeddings (
    id UUID PRIMARY KEY,
    template_id UUID REFERENCES document_templates(id),
    embedding_vector VECTOR(1536),
    chunk_text TEXT,
    chunk_index INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Bilingual Formatting Rules
CREATE TABLE formatting_rules (
    id UUID PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50),                 -- 'font', 'spacing', 'structure'
    language VARCHAR(10),                  -- 'en', 'mk', 'both'
    specification JSONB NOT NULL,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Default Formatting Rules Data
INSERT INTO formatting_rules (id, rule_name, rule_type, language, specification) VALUES
(gen_random_uuid(), 'macedonian_body_font', 'font', 'mk',
 '{"font_family": "Arial", "font_size_pt": 10.5, "style": "normal"}'),
(gen_random_uuid(), 'english_body_font', 'font', 'en',
 '{"font_family": "Arial", "font_size_pt": 11, "style": "italic"}'),
(gen_random_uuid(), 'parallel_text_structure', 'structure', 'both',
 '{"layout": "side_by_side", "primary_language": "mk", "secondary_language": "en", "separator": " / "}'),
(gen_random_uuid(), 'header_formatting', 'font', 'both',
 '{"font_family": "Arial", "font_size_pt": 14, "style": "bold", "color": "#1F4E79"}');

-- Indexes
CREATE INDEX idx_personnel_facility ON personnel(facility_id);
CREATE INDEX idx_equipment_facility ON equipment(facility_id);
CREATE INDEX idx_workflow_session ON workflow_states(session_id);
CREATE INDEX idx_audit_session ON audit_trail(session_id);
CREATE INDEX idx_audit_workflow ON audit_trail(workflow_id);
CREATE INDEX idx_templates_category ON document_templates(category);
CREATE INDEX idx_template_embeddings_vector ON template_embeddings
    USING ivfflat (embedding_vector vector_cosine_ops);
```

#### 5.3.3 Bilingual Formatting Specifications

```json
{
  "bilingual_document_rules": {
    "macedonian_text": {
      "font_family": "Arial",
      "font_size_range": {"min": 10, "max": 10.5},
      "font_style": "normal",
      "line_spacing": 1.15,
      "paragraph_spacing_after": 6
    },
    "english_text": {
      "font_family": "Arial",
      "font_size_range": {"min": 11, "max": 11.5},
      "font_style": "italic",
      "line_spacing": 1.15,
      "paragraph_spacing_after": 6
    },
    "parallel_presentation": {
      "layout_type": "inline",
      "separator": " / ",
      "primary_language": "macedonian",
      "secondary_language": "english"
    },
    "section_headers": {
      "bilingual": true,
      "format": "{mk_title} / {en_title}",
      "font_size": 14,
      "font_weight": "bold",
      "color": "#1F4E79"
    }
  }
}
```

---

## 6. Quality Assurance Framework

### 6.1 GMP Compliance Validation

The platform implements multi-layer validation aligned with EU GMP expectations:

#### 6.1.1 Validation Layers

| Layer | Focus | Agents Responsible |
|-------|-------|-------------------|
| **L1: Input Validation** | User input completeness and format | Agent 1, 2, 3 |
| **L2: Regulatory Validation** | Citation accuracy, requirement coverage | Agent 4 |
| **L3: Structural Validation** | RACI integrity, cross-references | Agent 5, 6 |
| **L4: Document Validation** | Format compliance, completeness | Agent 7, 9 |

#### 6.1.2 Compliance Scoring Model

```python
class ComplianceScorer:
    """
    Calculate GMP compliance score for generated documents.
    """

    WEIGHTS = {
        'regulatory_coverage': 0.30,    # All applicable regs cited
        'citation_accuracy': 0.20,      # Citations are valid
        'terminology_consistency': 0.15, # Consistent term usage
        'structural_completeness': 0.15, # All required sections
        'raci_integrity': 0.10,         # Valid RACI matrix
        'cross_reference_validity': 0.10 # Valid internal refs
    }

    def calculate_score(self, document: Document) -> ComplianceResult:
        scores = {
            'regulatory_coverage': self._score_regulatory_coverage(document),
            'citation_accuracy': self._score_citation_accuracy(document),
            'terminology_consistency': self._score_terminology(document),
            'structural_completeness': self._score_structure(document),
            'raci_integrity': self._score_raci(document),
            'cross_reference_validity': self._score_cross_refs(document)
        }

        weighted_score = sum(
            scores[key] * self.WEIGHTS[key]
            for key in scores
        )

        return ComplianceResult(
            overall_score=round(weighted_score, 1),
            component_scores=scores,
            passed=weighted_score >= 80,
            deficiencies=self._identify_deficiencies(scores)
        )
```

### 6.2 Audit Trail Requirements

Per EU GMP Annex 11 (Computerised Systems), the platform maintains complete audit trails:

```python
class AuditTrailEntry:
    """
    ALCOA+ compliant audit trail entry.
    """
    id: UUID
    timestamp: datetime           # Contemporaneous
    user_id: UUID                 # Attributable
    session_id: UUID
    workflow_id: UUID
    action_type: str              # Original action
    action_details: Dict          # Complete details
    previous_value: Optional[str] # For modifications
    new_value: Optional[str]
    ip_address: str
    user_agent: str
    checksum: str                 # Accurate/Enduring

    # ALCOA+ Compliance
    # A - Attributable: user_id, ip_address
    # L - Legible: structured action_details
    # C - Contemporaneous: timestamp auto-generated
    # O - Original: immutable once created
    # A - Accurate: checksum validation
    # + Complete: all fields required
    # + Consistent: standardized format
    # + Enduring: permanent storage
    # + Available: queryable via API
```

---

## 7. Design Philosophy

### 7.1 Guiding Principles

#### 7.1.1 Hide Complexity, Deliver Power

The platform abstracts regulatory complexity into an intuitive experience:

| User Sees | System Does |
|-----------|-------------|
| Simple questionnaire | Multi-agent AI orchestration |
| Plain language questions | RAG-enhanced context retrieval |
| Automatic suggestions | Dual-database semantic search |
| One-click generation | 9-agent sequential processing |
| Professional document | Complex DOCX formatting engine |

#### 7.1.2 Regulatory Requirements → Intuitive Experience

```
TRANSFORMATION PIPELINE

Complex Requirement:
"EU GMP 4.1: A comprehensive system of quality assurance documentation
should be established and maintained, incorporating GMP principles..."

                              │
                              ▼
                    ┌─────────────────┐
                    │  RAG Retrieval  │
                    │  + AI Analysis  │
                    └─────────────────┘
                              │
                              ▼
User-Facing Question:
"What is the primary purpose of this SOP?"
  Options:
  □ Ensure consistent process execution
  □ Meet regulatory compliance requirements
  □ Document quality control procedures
  □ Train personnel on procedures

                              │
                              ▼
                    ┌─────────────────┐
                    │ Context Accumul.│
                    │ + Validation    │
                    └─────────────────┘
                              │
                              ▼
Generated Content:
"## 1. Purpose
This SOP establishes the procedure for [X] in compliance with
EU GMP Chapter 4, Section 4.1 requirements for quality assurance
documentation. The procedure ensures..."
```

#### 7.1.3 Systematic Agent Orchestration

Quality is ensured through:

1. **Specialization**: Each agent masters one domain
2. **Sequential Refinement**: Context builds progressively
3. **Quality Gates**: Validation before progression
4. **Traceability**: Complete audit trail
5. **Iteration**: Failed validations trigger re-processing

### 7.2 Technical Excellence Standards

| Standard | Implementation |
|----------|----------------|
| **Separation of Concerns** | Content agents vs. formatting agents |
| **Single Responsibility** | One agent, one purpose |
| **DRY (Don't Repeat Yourself)** | Shared context, centralized validation |
| **SOLID Principles** | Extensible agent architecture |
| **12-Factor App** | Environment-based configuration |
| **GxP Compliance** | ALCOA+ data integrity |

---

*Document Classification: GMP Controlled Document*
*Review Cycle: Annual*
*Next Review: 2027-01-30*

# Architecture Diagrams - Cannabis EU GMP QMS Creator

**Document Version**: 1.0
**Date**: 2026-01-30

---

## Diagram 1: High-Level System Architecture

```mermaid
flowchart TB
    subgraph Frontend["Frontend Layer"]
        UI[React 19 UI<br/>TypeScript + TailwindCSS]
        I18N[i18n Layer<br/>EN / MK Toggle]
        WF[Workflow Components<br/>9-Agent Interface]
    end

    subgraph API["API Layer"]
        FAST[FastAPI Server<br/>REST Endpoints]
        AUTH[Authentication<br/>API Key + Session]
        RATE[Rate Limiter<br/>Request Throttling]
    end

    subgraph Orchestration["Agent Orchestration Layer"]
        LETTA[Letta/MemGPT Server<br/>Agent Management]

        subgraph Agents["Nine-Agent Pipeline"]
            A1[Agent 1<br/>Metadata]
            A2[Agent 2<br/>Intro Q]
            A3[Agent 3<br/>Proc Q]
            A4[Agent 4<br/>Compliance]
            A5[Agent 5<br/>RACI]
            A6[Agent 6<br/>QA Review]
            A7[Agent 7<br/>Formatter]
            A8[Agent 8<br/>Annex Q]
            A9[Agent 9<br/>Annex Fmt]
        end
    end

    subgraph Storage["Data Layer"]
        DB1[(DB1<br/>Regulatory KB<br/>47 docs)]
        DB2[(DB2<br/>Operational<br/>252 docs)]
        OLLAMA[Cloud Ollama<br/>Embeddings]
    end

    subgraph Output["Output Layer"]
        DOCX[DOCX Engine<br/>Document Generation]
        FILES[File Storage<br/>Generated SOPs]
    end

    UI --> FAST
    I18N --> UI
    WF --> UI

    FAST --> AUTH
    FAST --> RATE
    FAST --> LETTA

    LETTA --> A1
    A1 --> A2 --> A3 --> A4 --> A5 --> A6
    A6 --> A7
    A7 --> A8 --> A9

    A4 --> DB1
    A3 --> DB2
    A2 --> DB1
    A2 --> DB2

    DB1 --> OLLAMA
    DB2 --> OLLAMA

    A7 --> DOCX
    A9 --> DOCX
    DOCX --> FILES

    style Frontend fill:#E3F2FD,stroke:#1565C0
    style API fill:#FFF3E0,stroke:#EF6C00
    style Orchestration fill:#E8F5E9,stroke:#2E7D32
    style Storage fill:#F3E5F5,stroke:#7B1FA2
    style Output fill:#FFEBEE,stroke:#C62828
```

---

## Diagram 2: Complete Process Flow

```mermaid
flowchart TD
    START([User Login]) --> INIT[Initialize Session]
    INIT --> LANG{Select UI<br/>Language}
    LANG -->|English| EN_UI[English Interface]
    LANG -->|Macedonian| MK_UI[Macedonian Interface]
    EN_UI --> META
    MK_UI --> META

    subgraph Phase1["PHASE 1: Content Development"]
        META[Agent 1: Metadata Entry<br/>Title, Code, Department]
        META --> INTRO[Agent 2: Introduction Questions<br/>Purpose, Scope, Regulatory]
        INTRO --> PROC[Agent 3: Procedure Questions<br/>Steps, Equipment, Parameters]
        PROC --> COMP[Agent 4: Compliance Analysis<br/>Regulatory Validation]
        COMP --> RACI[Agent 5: RACI Generation<br/>Responsibility Matrix]
        RACI --> QA{Agent 6: QA Review<br/>Score >= 80?}
    end

    QA -->|No| REVISE[Revise Content]
    REVISE --> INTRO
    QA -->|Yes| APPROVE[Content Approved]

    subgraph Phase2["PHASE 2: Template Formatting"]
        APPROVE --> FORMAT[Agent 7: Document Formatting<br/>DOCX Generation]
        FORMAT --> ANNEX{Annexes<br/>Requested?}
        ANNEX -->|Yes| ANNEXQ[Agent 8: Annex Questions<br/>Form Requirements]
        ANNEXQ --> ANNEXF[Agent 9: Annex Formatting<br/>Generate Annexes]
        ANNEX -->|No| FINAL
        ANNEXF --> FINAL[Final Document]
    end

    FINAL --> DOWNLOAD[Download DOCX]
    DOWNLOAD --> AUDIT[Audit Trail Entry]
    AUDIT --> END([Complete])

    style Phase1 fill:#E8F5E9,stroke:#2E7D32
    style Phase2 fill:#E3F2FD,stroke:#1565C0
```

---

## Diagram 3: Agent Ecosystem - Internal Workflows

### 3A: Content Development Agents

```mermaid
flowchart LR
    subgraph Agent1["Agent 1: Metadata Collector"]
        A1_IN[User Form Input]
        A1_VAL{Validate<br/>Required Fields}
        A1_OUT[Metadata Object]
        A1_IN --> A1_VAL
        A1_VAL -->|Valid| A1_OUT
        A1_VAL -->|Invalid| A1_IN
    end

    subgraph Agent2["Agent 2: Introduction Questionnaire"]
        A2_IN[Metadata + Context]
        A2_RAG[RAG Search<br/>DB1 Priority]
        A2_GEN[Generate<br/>Questions]
        A2_USER[User Answers]
        A2_OUT[Purpose/Scope]
        A2_IN --> A2_RAG --> A2_GEN --> A2_USER --> A2_OUT
    end

    subgraph Agent3["Agent 3: Procedure Questionnaire"]
        A3_IN[Accumulated Context]
        A3_RAG[RAG Search<br/>DB2 Priority]
        A3_GEN[Generate<br/>Questions]
        A3_USER[User Answers]
        A3_OUT[Procedure Specs]
        A3_IN --> A3_RAG --> A3_GEN --> A3_USER --> A3_OUT
    end

    subgraph Agent4["Agent 4: Compliance Analyzer"]
        A4_IN[Full Content]
        A4_SEARCH[Search DB1<br/>Regulatory]
        A4_MATCH[Match<br/>Requirements]
        A4_CITE[Generate<br/>Citations]
        A4_GAP[Identify<br/>Gaps]
        A4_OUT[Compliance Report]
        A4_IN --> A4_SEARCH --> A4_MATCH --> A4_CITE --> A4_GAP --> A4_OUT
    end

    subgraph Agent5["Agent 5: RACI Generator"]
        A5_IN[Procedure Steps]
        A5_ROLES[Extract<br/>Roles]
        A5_MATRIX[Build<br/>Matrix]
        A5_VAL{Validate<br/>RACI Rules}
        A5_OUT[RACI Matrix]
        A5_IN --> A5_ROLES --> A5_MATRIX --> A5_VAL -->|Valid| A5_OUT
        A5_VAL -->|Invalid| A5_MATRIX
    end

    Agent1 --> Agent2 --> Agent3 --> Agent4 --> Agent5
```

### 3B: Quality and Formatting Agents

```mermaid
flowchart LR
    subgraph Agent6["Agent 6: QA Reviewer"]
        A6_IN[All Sections]
        A6_CONS[Check<br/>Consistency]
        A6_REG[Verify<br/>Citations]
        A6_XREF[Validate<br/>Cross-Refs]
        A6_SCORE[Calculate<br/>Score]
        A6_DEC{Score<br/>>= 80?}
        A6_PASS[Approved]
        A6_FAIL[Recommendations]
        A6_IN --> A6_CONS --> A6_REG --> A6_XREF --> A6_SCORE --> A6_DEC
        A6_DEC -->|Yes| A6_PASS
        A6_DEC -->|No| A6_FAIL
    end

    subgraph Agent7["Agent 7: Document Formatter"]
        A7_IN[Approved Content]
        A7_COVER[Generate<br/>Cover Page]
        A7_TOC[Build<br/>TOC]
        A7_SECT[Format<br/>Sections]
        A7_RACI[Style<br/>RACI]
        A7_APPR[Add<br/>Approval Page]
        A7_OUT[Main DOCX]
        A7_IN --> A7_COVER --> A7_TOC --> A7_SECT --> A7_RACI --> A7_APPR --> A7_OUT
    end

    subgraph Agent8["Agent 8: Annex Questionnaire"]
        A8_IN[Annex Request]
        A8_TYPE[Determine<br/>Type]
        A8_FIELDS[Define<br/>Fields]
        A8_USER[User Input]
        A8_OUT[Annex Specs]
        A8_IN --> A8_TYPE --> A8_FIELDS --> A8_USER --> A8_OUT
    end

    subgraph Agent9["Agent 9: Annex Formatter"]
        A9_IN[Annex Specs]
        A9_GEN[Generate<br/>Form]
        A9_SIG[Add<br/>Signatures]
        A9_INST[Add<br/>Instructions]
        A9_OUT[Formatted Annex]
        A9_IN --> A9_GEN --> A9_SIG --> A9_INST --> A9_OUT
    end

    Agent6 --> Agent7 --> Agent8 --> Agent9
```

### 3C: Agent Interconnectivity Map

```mermaid
flowchart TB
    subgraph ContentPhase["Content Development Phase"]
        A1((A1<br/>Meta))
        A2((A2<br/>Intro))
        A3((A3<br/>Proc))
        A4((A4<br/>Comp))
        A5((A5<br/>RACI))
    end

    subgraph QualityGate["Quality Gate"]
        A6((A6<br/>QA))
    end

    subgraph FormatPhase["Formatting Phase"]
        A7((A7<br/>Format))
        A8((A8<br/>AnnexQ))
        A9((A9<br/>AnnexF))
    end

    DB1[(DB1<br/>Regulatory)]
    DB2[(DB2<br/>Operational)]

    A1 -->|metadata| A2
    A2 -->|+purpose/scope| A3
    A3 -->|+procedure| A4
    A4 -->|+compliance| A5
    A5 -->|+raci| A6

    A6 -->|approved| A7
    A6 -.->|reject| A2

    A7 -->|main_doc| A8
    A8 -->|annex_specs| A9

    A2 <-->|search| DB1
    A2 <-->|search| DB2
    A3 <-->|search| DB2
    A4 <-->|search| DB1

    style ContentPhase fill:#E8F5E9
    style QualityGate fill:#FFF3E0
    style FormatPhase fill:#E3F2FD
```

---

## Diagram 4: Database Architecture

### 4A: DB1 Entity-Relationship Diagram

```mermaid
erDiagram
    REGULATORY_BODIES ||--o{ REGULATORY_DOCUMENTS : contains
    REGULATORY_BODIES {
        uuid id PK
        varchar code UK
        varchar name
        varchar jurisdiction
        varchar website_url
        timestamp created_at
    }

    REGULATORY_DOCUMENTS ||--o{ REGULATORY_SECTIONS : has
    REGULATORY_DOCUMENTS ||--o{ REGULATORY_TERMS : defines
    REGULATORY_DOCUMENTS {
        uuid id PK
        uuid body_id FK
        varchar document_code
        varchar title
        varchar version
        date effective_date
        varchar document_type
        text full_text
        timestamp created_at
    }

    REGULATORY_SECTIONS ||--o{ REGULATORY_SECTIONS : parent_of
    REGULATORY_SECTIONS ||--o{ REGULATORY_CITATIONS : cites
    REGULATORY_SECTIONS ||--o{ REGULATORY_CITATIONS : cited_by
    REGULATORY_SECTIONS ||--o{ REGULATORY_EMBEDDINGS : embedded
    REGULATORY_SECTIONS {
        uuid id PK
        uuid document_id FK
        varchar section_number
        varchar title
        text content
        uuid parent_section_id FK
        int hierarchy_level
        timestamp created_at
    }

    REGULATORY_TERMS {
        uuid id PK
        varchar term
        text definition
        uuid source_document_id FK
        varchar source_section
        varchar abbreviation
        text[] synonyms
        timestamp created_at
    }

    REGULATORY_CITATIONS {
        uuid id PK
        uuid citing_section_id FK
        uuid cited_section_id FK
        varchar citation_type
        text citation_text
        timestamp created_at
    }

    REGULATORY_EMBEDDINGS {
        uuid id PK
        uuid section_id FK
        vector embedding_vector
        text chunk_text
        int chunk_index
        jsonb metadata
        timestamp created_at
    }
```

### 4B: DB2 Entity-Relationship Diagram

```mermaid
erDiagram
    FACILITIES ||--o{ DEPARTMENTS : contains
    FACILITIES ||--o{ PERSONNEL : employs
    FACILITIES ||--o{ EQUIPMENT : owns
    FACILITIES ||--o{ DOCUMENT_TEMPLATES : stores
    FACILITIES {
        uuid id PK
        varchar name
        varchar code UK
        varchar facility_type
        text address
        varchar gmp_license_number
        date license_expiry
        timestamp created_at
    }

    DEPARTMENTS ||--o{ PERSONNEL : has
    DEPARTMENTS ||--o{ EQUIPMENT : uses
    DEPARTMENTS {
        uuid id PK
        uuid facility_id FK
        varchar name
        varchar code
        uuid manager_id
        timestamp created_at
    }

    PERSONNEL {
        uuid id PK
        uuid facility_id FK
        uuid department_id FK
        varchar first_name
        varchar last_name
        varchar job_title
        varchar job_title_mk
        varchar email
        text[] qualifications
        jsonb training_status
        timestamp created_at
    }

    EQUIPMENT {
        uuid id PK
        uuid facility_id FK
        uuid department_id FK
        varchar name
        varchar name_mk
        varchar equipment_code
        varchar manufacturer
        varchar model
        varchar serial_number
        varchar qualification_status
        date last_calibration
        date next_calibration
        varchar location
        timestamp created_at
    }

    USER_SESSIONS ||--o{ WORKFLOW_STATES : manages
    USER_SESSIONS ||--o{ AUDIT_TRAIL : logs
    USER_SESSIONS {
        uuid id PK
        uuid user_id
        uuid facility_id FK
        varchar session_token
        varchar language_preference
        timestamp started_at
        timestamp last_activity
        timestamp expires_at
        jsonb metadata
    }

    WORKFLOW_STATES ||--o{ AUDIT_TRAIL : tracked_by
    WORKFLOW_STATES {
        uuid id PK
        uuid session_id FK
        varchar workflow_type
        int current_agent
        varchar current_phase
        varchar status
        jsonb metadata
        jsonb agent_responses
        timestamp created_at
    }

    AUDIT_TRAIL {
        uuid id PK
        uuid session_id FK
        uuid workflow_id FK
        varchar action_type
        jsonb action_details
        uuid performed_by
        inet ip_address
        text user_agent
        timestamp created_at
    }

    DOCUMENT_TEMPLATES ||--o{ TEMPLATE_EMBEDDINGS : embedded
    DOCUMENT_TEMPLATES {
        uuid id PK
        uuid facility_id FK
        varchar template_type
        varchar category
        varchar title
        varchar title_mk
        text content
        varchar file_path
        decimal quality_score
        decimal regulatory_alignment
        text[] tags
        timestamp created_at
    }

    TEMPLATE_EMBEDDINGS {
        uuid id PK
        uuid template_id FK
        vector embedding_vector
        text chunk_text
        int chunk_index
        jsonb metadata
        timestamp created_at
    }

    FORMATTING_RULES {
        uuid id PK
        varchar rule_name
        varchar rule_type
        varchar language
        jsonb specification
        int priority
        timestamp created_at
    }
```

### 4C: Database Interaction Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Agent2 as Agent 2 (Intro)
    participant Agent3 as Agent 3 (Proc)
    participant Agent4 as Agent 4 (Comp)
    participant DB1 as DB1 (Regulatory)
    participant DB2 as DB2 (Operational)
    participant Ollama as Ollama Embeddings

    User->>API: Start SOP Generation
    API->>Agent2: Initialize with Metadata

    Note over Agent2,DB1: Regulatory Context Search
    Agent2->>Ollama: Embed query
    Ollama-->>Agent2: Query vector
    Agent2->>DB1: Vector search (regulatory)
    DB1-->>Agent2: Regulatory passages
    Agent2->>DB2: Vector search (examples)
    DB2-->>Agent2: Operational examples
    Agent2-->>User: Context-aware questions

    User->>Agent3: Submit answers
    Note over Agent3,DB2: Operational Examples Search
    Agent3->>Ollama: Embed query
    Ollama-->>Agent3: Query vector
    Agent3->>DB2: Vector search (priority)
    DB2-->>Agent3: Template examples
    Agent3-->>User: Procedure questions

    User->>Agent4: Submit procedure
    Note over Agent4,DB1: Compliance Validation
    Agent4->>DB1: Search regulatory requirements
    DB1-->>Agent4: Applicable regulations
    Agent4->>Agent4: Match & validate
    Agent4-->>API: Compliance report
```

---

## Diagram 5: Quality Assurance & Validation Workflow

```mermaid
flowchart TB
    subgraph Input["Input Validation (L1)"]
        IV1[Required Fields Check]
        IV2[Format Validation]
        IV3[Business Rules]
        IV1 --> IV2 --> IV3
    end

    subgraph Regulatory["Regulatory Validation (L2)"]
        RV1[Citation Accuracy]
        RV2[Requirement Coverage]
        RV3[Gap Detection]
        RV1 --> RV2 --> RV3
    end

    subgraph Structural["Structural Validation (L3)"]
        SV1[RACI Integrity]
        SV2[Cross-Reference Check]
        SV3[Terminology Consistency]
        SV1 --> SV2 --> SV3
    end

    subgraph Document["Document Validation (L4)"]
        DV1[Section Completeness]
        DV2[Format Compliance]
        DV3[Print Readiness]
        DV1 --> DV2 --> DV3
    end

    subgraph Scoring["Compliance Scoring"]
        SC1[Regulatory: 30%]
        SC2[Citation: 20%]
        SC3[Terminology: 15%]
        SC4[Structure: 15%]
        SC5[RACI: 10%]
        SC6[Cross-Ref: 10%]
        SC1 --> TOTAL
        SC2 --> TOTAL
        SC3 --> TOTAL
        SC4 --> TOTAL
        SC5 --> TOTAL
        SC6 --> TOTAL
        TOTAL[Total Score]
    end

    subgraph Decision["Quality Gate"]
        DEC{Score >= 80?}
        PASS[APPROVED<br/>Proceed to Formatting]
        FAIL[REJECTED<br/>Return for Revision]
        DEC -->|Yes| PASS
        DEC -->|No| FAIL
    end

    Input --> Regulatory --> Structural --> Document --> Scoring --> Decision

    style Input fill:#E3F2FD
    style Regulatory fill:#E8F5E9
    style Structural fill:#FFF3E0
    style Document fill:#F3E5F5
    style Scoring fill:#FFEBEE
    style Decision fill:#E0E0E0
```

---

## Diagram 6: User Interface Journey Map

```mermaid
journey
    title SOP Generation User Journey
    section Login & Setup
        Access Platform: 5: User
        Select Language (EN/MK): 5: User, System
        View Dashboard: 4: User
    section Phase 1 - Metadata
        Click "Create SOP": 5: User
        Enter Title & Code: 4: User
        Select Department: 4: User
        Choose Classification: 4: User
        Submit Metadata: 5: User, Agent1
    section Phase 1 - Questions
        View Contextual Questions: 4: Agent2
        Answer Purpose Questions: 3: User
        Answer Scope Questions: 3: User
        View Procedure Questions: 4: Agent3
        Enter Process Steps: 3: User
        Define Parameters: 3: User
        Submit All Answers: 5: User
    section Phase 1 - Automated
        Wait for Compliance Check: 2: Agent4
        Wait for RACI Generation: 2: Agent5
        View QA Score: 4: Agent6
        Review Recommendations: 4: User
        Approve or Revise: 5: User
    section Phase 2 - Generation
        Wait for Formatting: 2: Agent7
        View Generated Preview: 4: User
        Answer Annex Questions: 3: User, Agent8
        Wait for Annex Generation: 2: Agent9
        Download Final DOCX: 5: User
    section Complete
        View in Document Library: 4: User
        Export or Share: 5: User
```

### UI State Flow Diagram

```mermaid
stateDiagram-v2
    [*] --> Dashboard
    Dashboard --> CreateSOP: Click "Create New"

    state "Phase 1: Content" as Phase1 {
        [*] --> MetadataForm
        MetadataForm --> IntroQuestions: Submit
        IntroQuestions --> ProcedureQuestions: Next
        ProcedureQuestions --> AutoProcessing: Submit
        AutoProcessing --> QAReview: Complete
        QAReview --> [*]: Approved
        QAReview --> IntroQuestions: Revise
    }

    CreateSOP --> Phase1

    state "Phase 2: Format" as Phase2 {
        [*] --> Formatting
        Formatting --> AnnexQuestions: Has Annexes
        Formatting --> Preview: No Annexes
        AnnexQuestions --> AnnexFormatting: Submit
        AnnexFormatting --> Preview: Complete
        Preview --> Download: Approve
        Download --> [*]
    }

    Phase1 --> Phase2: Quality Gate Passed

    Phase2 --> DocumentLibrary: Complete
    DocumentLibrary --> Dashboard: Navigate

    state LanguageToggle {
        English --> Macedonian: Toggle
        Macedonian --> English: Toggle
    }

    note right of LanguageToggle
        UI-only toggle
        Documents always in English
    end note
```

---

## Color Scheme Reference

| Component | Color | Hex Code |
|-----------|-------|----------|
| Frontend Layer | Light Blue | #E3F2FD |
| API Layer | Light Orange | #FFF3E0 |
| Orchestration Layer | Light Green | #E8F5E9 |
| Storage Layer | Light Purple | #F3E5F5 |
| Output Layer | Light Red | #FFEBEE |
| Primary Accent | Purely Plant Blue | #1F4E79 |
| Secondary Accent | Purely Plant Green | #538135 |
| Neutral | Gray | #404040 |

---

*Generated for Cannabis EU GMP QMS Creator*
*Document Version: 1.0*

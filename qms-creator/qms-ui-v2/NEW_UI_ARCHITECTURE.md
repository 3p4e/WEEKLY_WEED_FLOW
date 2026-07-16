# New 9-Agent Interactive Workflow UI Architecture

## Overview

This document defines the complete redesign of the frontend UI to support the new 9-agent interactive workflow architecture for SOP generation.

---

## Core Principles

1. **Sequential Agent Flow** - Users progress through 9 distinct agent phases
2. **Interactive Questionnaires** - Each agent presents structured questions with multiple-choice options
3. **Context Accumulation** - Visual indication of how context builds through the workflow
4. **Decision-Making Interface** - Users select options, not write free-form text
5. **Progress Transparency** - Clear visualization of current agent, completed agents, pending agents

---

## User Journey Map

```
START
  ↓
[Agent 1: Metadata Input]
  ↓ (form submission)
[Agent 2: Introduction Questionnaire]
  ↓ (questionnaire answers)
[Agent 3: Procedure Questionnaire]
  ↓ (questionnaire answers)
[Agent 4: Compliance Integration] (automated)
  ↓
[Agent 5: RACI Generation] (automated with validation)
  ↓
[Agent 6: QA Review & Recommendations]
  ↓ (user approves/modifies)
[Agent 7: Document Formatting] (automated)
  ↓
[Agent 8: Annex Questionnaires] (if annexes specified)
  ↓
[Agent 9: Annex Formatting] (automated)
  ↓
COMPLETE - Download DOCX
```

---

## UI Components Architecture

### 1. Agent Progress Stepper

**Location:** Top of page (fixed)

**Design:**
- Horizontal stepper showing all 9 agents
- Current agent highlighted
- Completed agents show checkmark
- Pending agents grayed out
- Each step shows: Agent number, name, icon

**States:**
- `pending` - Gray, not clickable
- `in_progress` - Blue/cyan glow, animated
- `completed` - Green checkmark, clickable to review
- `skipped` - Yellow skip icon (for optional agents)

**Component Structure:**
```tsx
<AgentStepper
  agents={[
    { number: 1, name: "Metadata", status: "completed", icon: "📝" },
    { number: 2, name: "Introduction", status: "in_progress", icon: "📄" },
    { number: 3, name: "Procedure", status: "pending", icon: "⚙️" },
    // ... etc
  ]}
  currentAgent={2}
/>
```

---

### 2. Agent Phase Views

Each agent has a distinct view component:

#### 2.1 Agent 1: Metadata Form

**Component:** `MetadataFormView`

**Layout:**
- Clean form with labeled fields
- Real-time validation
- AI paraphrase button next to text fields
- Dynamic annex list builder
- Department dropdown with icons
- Auto-generated document code display

**Features:**
- Field-by-field validation
- Progress indicator (% complete)
- Save draft capability
- Paraphrase modal showing AI-enhanced version

---

#### 2.2 Agent 2/3/8: Questionnaire View

**Component:** `QuestionnaireView`

**Layout:**
- Left sidebar: Question navigator (mini progress)
- Main area: Current question card
- Right panel: RAG context sources (expandable)

**Question Card Design:**
```
┌─────────────────────────────────────────────┐
│ Question 3 of 15                            │
│ ─────────────────────────────────────────── │
│ What inspection frequency is appropriate?   │
│                                             │
│ ○ Daily                                     │
│ ○ Twice weekly (Recommended)               │
│ ○ Weekly                                    │
│ ○ Bi-weekly                                 │
│ ○ Monthly                                   │
│                                             │
│ [?] Why these options? (expands RAG context)│
│                                             │
│ [Previous]              [Next Question] →   │
└─────────────────────────────────────────────┘
```

**Features:**
- Single question per screen (no overwhelming lists)
- Options derived from RAG database queries
- "Why these options?" expandable showing DB1/DB2 sources
- Progress bar at top showing question N of M
- Previous/Next navigation
- Mark as "Review Later"
- Bulk selection mode (for experienced users)

---

#### 2.3 Agent 4/5: Automated Processing View

**Component:** `AutomatedProcessingView`

**Layout:**
- Center: Large animated spinner or progress animation
- Below: Status messages updating in real-time
- Bottom: Preview of generated content (as it appears)

**Design:**
```
┌─────────────────────────────────────────────┐
│          Agent 4: Compliance Integration    │
│                                             │
│              🔄 [animated spinner]          │
│                                             │
│  Analyzing procedure content...             │
│  ✓ Extracted 24 technical terms             │
│  ✓ Identified 5 cross-referenced documents  │
│  ○ Compiling definitions...                 │
│                                             │
│  ─────────────────────────────────────────  │
│  Generated Content Preview:                 │
│  ┌───────────────────────────────────────┐ │
│  │ 1.5 Abbreviations and Definitions     │ │
│  │                                       │ │
│  │ | Term | Definition |                │ │
│  │ |------|------------|                │ │
│  │ | GACP | Good Agricultural...        │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

#### 2.4 Agent 6: QA Review Interface

**Component:** `QAReviewInterface`

**Layout:** Split-panel design

**Left Panel: Document Preview**
- Formatted preview of complete SOP
- Sections expandable/collapsible
- Scroll to navigate
- Highlight areas with recommendations

**Right Panel: Review Recommendations**
```
┌─────────────────────────────────────────────┐
│ Quality Review Report                       │
│ Overall Score: 92/100  ⭐⭐⭐⭐⭐            │
│ ─────────────────────────────────────────── │
│ ✅ Regulatory Compliance: 100%              │
│ ✅ Internal Consistency: 95%                │
│ ⚠️  Completeness: 85%                       │
│ ─────────────────────────────────────────── │
│                                             │
│ 📌 Recommendations (3)                      │
│                                             │
│ 1. Section 3.2 missing acceptance criteria │
│    ○ Add specific cannabinoid ranges       │
│    ○ Add microbial limits                  │
│    ○ Skip (continue without)               │
│    [Apply]                                  │
│                                             │
│ 2. Cross-reference to QC_01.02 invalid     │
│    ○ Update to QC_01.03 (latest version)   │
│    ○ Remove reference                      │
│    [Apply]                                  │
│                                             │
│ [Accept All] [Modify Selections] [Approve]│
└─────────────────────────────────────────────┘
```

**Features:**
- Interactive recommendations with multiple choice fixes
- Preview changes before applying
- Quality score breakdown
- Approve and proceed to formatting

---

#### 2.5 Agent 7/9: Document Generation View

**Component:** `DocumentGenerationView`

**Layout:**
- Center: Progress bar with percentage
- Status: "Generating DOCX..." with file name
- Preview thumbnail of generated page
- Download button appears when complete

**Design:**
```
┌─────────────────────────────────────────────┐
│     Agent 7: Document Formatting            │
│                                             │
│  ████████████████░░░░░░  75%                │
│                                             │
│  Generating: QA_02.05_Document_Control.docx │
│                                             │
│  ✓ Applied Purely Plant theme               │
│  ✓ Formatted 9 sections                     │
│  ✓ Generated RACI matrix table              │
│  ○ Inserting headers and footers...         │
│                                             │
│  [Preview thumbnail once complete]          │
│                                             │
│  [⬇ Download SOP]  [📧 Email]  [✓ Complete]│
└─────────────────────────────────────────────┘
```

---

## Page Layout Structure

### Main CreateSOPPage

```tsx
<div className="create-sop-container">
  {/* Fixed header */}
  <AgentStepper currentAgent={currentAgentNumber} agents={agents} />

  {/* Main content area */}
  <div className="agent-phase-container">
    {currentPhase === 'metadata' && <MetadataFormView />}
    {currentPhase === 'questionnaire_intro' && <QuestionnaireView agent={2} />}
    {currentPhase === 'questionnaire_procedure' && <QuestionnaireView agent={3} />}
    {currentPhase === 'automated_compliance' && <AutomatedProcessingView agent={4} />}
    {currentPhase === 'automated_raci' && <AutomatedProcessingView agent={5} />}
    {currentPhase === 'qa_review' && <QAReviewInterface />}
    {currentPhase === 'formatting' && <DocumentGenerationView agent={7} />}
    {currentPhase === 'questionnaire_annex' && <QuestionnaireView agent={8} />}
    {currentPhase === 'annex_formatting' && <DocumentGenerationView agent={9} />}
  </div>
</div>
```

---

## State Management

### Zustand Store: `useWorkflowStore`

```typescript
interface WorkflowState {
  // Current phase
  currentAgent: number
  currentPhase: AgentPhase

  // Agent 1 data
  metadata: MetadataFormData

  // Agent 2 data
  introQuestions: QuestionnaireResponse[]

  // Agent 3 data
  procedureQuestions: QuestionnaireResponse[]

  // Agent 4/5 outputs (received from backend)
  complianceContent: GeneratedContent
  raciMatrix: RACIMatrix

  // Agent 6 data
  qaReview: QAReviewReport
  qaRecommendations: Recommendation[]
  userQASelections: QASelection[]

  // Agent 7 output
  sopDocxPath: string

  // Agent 8/9 data (per annex)
  annexQuestionnaires: Record<string, QuestionnaireResponse[]>
  annexDocxPaths: string[]

  // Actions
  setCurrentAgent: (agent: number) => void
  submitMetadata: (data: MetadataFormData) => void
  answerQuestion: (agentNum: number, questionId: string, answer: any) => void
  applyQARecommendation: (recId: string, selection: string) => void
  // ... etc
}
```

---

## API Integration

### New Endpoints Required

```typescript
// POST /api/workflow/start
// Initialize workflow, send metadata
// Returns: context_package, agent_2_questions

// POST /api/workflow/agent-2/submit
// Submit Agent 2 questionnaire answers
// Returns: agent_3_questions

// POST /api/workflow/agent-3/submit
// Submit Agent 3 questionnaire answers
// Triggers: Agent 4 (automated), Agent 5 (automated)
// Returns: SSE stream with Agent 4/5 progress

// GET /api/workflow/agent-6/review
// Get QA review report and recommendations
// Returns: QAReviewReport

// POST /api/workflow/agent-6/approve
// Submit QA selections and approve
// Triggers: Agent 7 (formatting)
// Returns: SSE stream with formatting progress

// POST /api/workflow/agent-8/annex/{annex_id}/submit
// Submit annex questionnaire
// Returns: formatted annex path

// GET /api/workflow/status
// Get current workflow status
```

---

## Theme Integration

Use existing theme system from `qms-ui-v2/src/themes/`

**Recommended:** Cyber Glass theme for modern glassmorphism look

**Key UI Elements:**
- Question cards: Frosted glass effect with border glow
- Progress stepper: Gradient animated borders
- Buttons: Neon accent colors (#00d9ff, #8b5cf6)
- Background: Deep space (#050510) with subtle grid
- Text: High contrast white/cyan on dark

---

## Implementation Priority

### Phase 1: Core Structure (Day 1-2)
1. Agent stepper component
2. MetadataFormView
3. Basic workflow state management
4. Navigation between agents

### Phase 2: Questionnaires (Day 3-4)
5. QuestionnaireView component
6. Question card design
7. RAG context panel
8. Progress tracking

### Phase 3: Automated Agents (Day 5)
9. AutomatedProcessingView
10. Real-time status updates
11. Content preview

### Phase 4: QA Review (Day 6-7)
12. QAReviewInterface
13. Split-panel layout
14. Recommendation interaction
15. Preview with highlights

### Phase 5: Document Generation (Day 8)
16. DocumentGenerationView
17. Download interface
18. Completion flow

---

## Success Criteria

✅ Users can complete full 9-agent workflow
✅ Each agent phase has distinct, intuitive UI
✅ Questionnaires present clear multiple-choice options
✅ RAG context is visible and understandable
✅ Automated agents show real-time progress
✅ QA review allows interactive improvements
✅ Final documents download successfully
✅ UI matches theme system (Cyber Glass)
✅ Mobile-responsive (tablet minimum)

---

**Document Version:** 1.0
**Date:** 2026-01-29
**Status:** Specification - Ready for Implementation

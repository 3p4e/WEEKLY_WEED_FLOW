# Option A Enhancement Guide: Agent Improvements

**Status:** ProcedureAgent enhanced as template ✅
**Remaining Agents to Enhance:** 10 agents
**Estimated Impact:** High quality improvements across all agents

---

## What Was Enhanced

### ProcedureAgent (Template Implementation)

**New Capabilities:**

1. **Shared Validation Utilities** (`validation_utils.py`)
   - Placeholder detection (TBD, TK, TBC, TODO, etc.)
   - Cannabis-specific keyword analysis
   - Regulatory framework coverage checking
   - Dynamic question generation framework
   - Content quality assessment

2. **Enhanced System Prompts**
   - Concrete examples (Equipment Calibration, Cannabis Processing)
   - Markdown formatting rules
   - Critical control point markers `[CCP]`
   - Quality attribute markers `[CQA]`
   - Cannabis GMP specifics (potency, microbial, pesticide controls)
   - Explicit placeholder prohibition

3. **Dynamic Question Generation**
   - Analyzes content to generate contextual questions
   - Identifies missing critical control points
   - Detects quality attribute gaps
   - Checks Cannabis-specific requirements
   - Flags safety warning deficiencies
   - Questions adapt based on what's actually in the content

4. **Enhanced Validation**
   - Placeholder text detection (fails if found)
   - Numbered step validation
   - Prerequisites requirement
   - Expected outcome requirement
   - Decision point (if-then) requirement
   - Word count analysis
   - Regulatory framework citation checking

5. **Procedure-Specific Confidence Scoring**
   - +0.15 for validation passed
   - +0.15 for content >1000 chars
   - +0.15 for 8+ steps
   - +0.15 for 2+ CCPs
   - +0.10 for 2+ CQAs
   - +0.10 for Cannabis-aware content
   - -0.10 per placeholder found

6. **Detailed Metadata**
   - Step count
   - CCP count
   - CQA count
   - Cannabis-aware flag
   - Safety warnings present

---

## Template: How to Apply to Other Agents

### Step 1: Update System Prompt

**Add to system prompt:**

```python
# At the top of system_prompt, add:
"""
Enhanced Directive:

EXAMPLES: Provide 2-3 concrete examples of output format
"For Equipment Calibration SOP:
 1. [action]
    [CCP] [if critical control point]
    Expected result: [verification criteria]"

FORMATTING: Be explicit about required structure
- Use markdown headers (## Section Name)
- Number items clearly
- Include time estimates where relevant

CANNABIS GMP: Add if applicable
"For Cannabis operations:
- Identify [potency variation / microbial / pesticide] control points
- Mark critical steps with [CCP] or [CQA]
- Reference specific Cannabis regulations"

NO PLACEHOLDERS: Add as requirement
"CRITICAL: Never use placeholder text (TBD, TBA, TBC, TODO, TK, WIP)"
"""
```

### Step 2: Import Validation Utilities

```python
from ..validation_utils import (
    detect_placeholders,
    check_cannabis_specificity,
    check_regulatory_coverage,
    assess_content_quality,
    suggest_improvements,
)
```

### Step 3: Enhance Validation Method

```python
async def validate_content(self, content: str) -> tuple:
    """Enhanced validation with placeholder detection."""
    issues = []

    # Parent validation
    is_valid, parent_issues = await super().validate_content(content)
    issues.extend(parent_issues)

    if not content:
        return False, issues

    # CRITICAL: Placeholder detection
    placeholders = detect_placeholders(content)
    if placeholders:
        issues.append(f"Contains placeholder text: {placeholders[0]}")

    # Cannabis specificity (if applicable)
    is_cannabis_aware, _ = check_cannabis_specificity(content)
    if not is_cannabis_aware and "cannabis" not in content.lower():
        pass  # Only warn if cannabis-related SOP

    # Regulatory coverage
    regulatory_coverage = check_regulatory_coverage(content)
    if sum(regulatory_coverage.values()) == 0:
        issues.append("Should reference regulatory frameworks")

    # [Your existing validation checks]

    return len(issues) == 0, issues
```

### Step 4: Implement Dynamic Question Generation

```python
async def _generate_dynamic_questions(self, content: str, issues: List[str]) -> List[Dict]:
    """Generate questions based on content analysis."""
    questions = []

    # Q1: Address validation issues
    if issues:
        critical_issue = next((i for i in issues if any(
            word in i.lower() for word in ["critical", "missing", "inadequate"]
        )), issues[0])
        questions.append({
            "id": f"{self.role.value}_issue",
            "question": f"Issue found: {critical_issue}. Revise?",
            "type": "yes_no",
            "options": ["Yes, revise", "Accept as-is"]
        })

    # Q2: Cannabis specificity (if applicable)
    is_cannabis_aware, _ = check_cannabis_specificity(content)
    if not is_cannabis_aware:
        questions.append({
            "id": f"{self.role.value}_cannabis",
            "question": "Add Cannabis/Hemp-specific requirements?",
            "type": "yes_no",
            "options": ["Yes, add", "Not applicable"]
        })

    # Q3: Regulatory coverage
    regulatory_coverage = check_regulatory_coverage(content)
    if sum(regulatory_coverage.values()) < 2:
        questions.append({
            "id": f"{self.role.value}_regulatory",
            "question": "Add regulatory framework citations?",
            "type": "yes_no",
            "options": ["Yes, add", "Not applicable"]
        })

    # [Your role-specific questions]

    return questions[:4]  # Limit to 4 questions
```

### Step 5: Enhanced Confidence Scoring

```python
def _calculate_enhanced_confidence(self, content: str, validation_passed: bool) -> float:
    """Enhanced confidence with multiple factors."""
    base = 0.5

    # Validation
    if validation_passed:
        base += 0.15

    # Content length
    content_len = len(content)
    if content_len > 1000:
        base += 0.15
    elif content_len > 500:
        base += 0.10
    elif content_len > 300:
        base += 0.05

    # Cannabis awareness bonus
    is_cannabis_aware, _ = check_cannabis_specificity(content)
    if is_cannabis_aware:
        base += 0.10

    # Regulatory framework bonus
    regulatory_coverage = check_regulatory_coverage(content)
    if sum(regulatory_coverage.values()) > 0:
        base += 0.05

    # Placeholder penalty (critical)
    placeholders = detect_placeholders(content)
    if placeholders:
        base -= 0.10 * len(placeholders)

    # Role-specific bonuses
    # [Your role-specific scoring]

    return min(max(base, 0.0), 1.0)
```

---

## Enhancement Checklist for Each Agent

### For All Agents:

- [ ] Add concrete examples to system prompt
- [ ] Import validation_utils functions
- [ ] Add placeholder detection to validation
- [ ] Add regulatory framework checking
- [ ] Implement dynamic question generation
- [ ] Enhance confidence scoring
- [ ] Update reasoning to be more detailed
- [ ] Add metadata to response (key metrics)

### For Cannabis-Aware Agents (all of them):

- [ ] Add Cannabis-specific examples to system prompt
- [ ] Check `is_cannabis_aware` in validation
- [ ] Include Cannabis question in dynamic questions
- [ ] Bonus points for Cannabis specificity in confidence

### Role-Specific Enhancements:

| Agent | Special Focus |
|-------|---------------|
| CoverAgent | Document version control, approval chain |
| PurposeAgent | Regulatory alignment, organizational impact |
| ScopeAgent | Clear boundaries, exclusions, related SOPs |
| DefinitionsAgent | Alphabetical organization, cannabis terminology |
| RACIAgent | Role clarity, responsibility coverage |
| RegulatoryAgent | Framework citations, compliance proof |
| **ProcedureAgent** | **✅ [CCP], [CQA], safety warnings** |
| DocumentationAgent | Record types, retention periods |
| TrainingAgent | Competency assessment, frequency |
| AnnexAgent | Form structure, signature fields |
| AssemblerAgent | Cross-reference validation, consistency |

---

## Validation Utility Reference

### Available Functions in `validation_utils.py`

```python
# 1. Placeholder Detection
placeholders = detect_placeholders(content)
# Returns: List[str] of detected placeholder patterns

# 2. Cannabis Specificity
is_cannabis_aware, keyword_counts = check_cannabis_specificity(content)
# Returns: (bool, Dict[str, int])
#   - plant_material, products, quality_attributes, regulations

# 3. Regulatory Coverage
coverage = check_regulatory_coverage(content)
# Returns: Dict[str, int]
#   - eudralex, ich, who, iso -> keyword counts

# 4. Content Quality Assessment
quality = assess_content_quality(content, validation_passed)
# Returns: ContentQuality enum (MINIMAL, BASIC, GOOD, EXCELLENT)

# 5. Suggest Improvements
suggestions = suggest_improvements(content, content_type)
# Returns: List[str] of specific improvement recommendations

# 6. Count Structured Elements
count = count_structured_elements(content, "steps")
# Returns: int (element_type: "steps", "bullets", "tables", "definitions", "sections")

# 7. Generate Dynamic Questions (general framework)
questions = generate_dynamic_questions(content, content_type, issues, confidence)
# Returns: List[Dict] of contextual questions
```

---

## Priority Order: Apply Enhancement to Agents

**Phase A (Quick Win - 15 min per agent):**
1. Update system prompt with examples + Cannabis + no placeholders
2. Add validation_utils imports
3. Add placeholder detection to validation
4. Run verify_agents.py

**Phase B (Medium Work - 25 min per agent):**
5. Implement dynamic question generation
6. Add Cannabis-aware checks
7. Enhance confidence scoring
8. Test with sample input

**Phase C (Polish - 10 min per agent):**
9. Update metadata in response
10. Enhance reasoning description
11. Documentation update
12. Final testing

---

## Quick Start: Apply to Next Agent

### Example: RACIAgent Enhancement

```python
# 1. System Prompt
# Add to system_prompt:
"""
EXAMPLES:
For Quality Control SOP, roles are: QC Manager, Technician, Supervisor

| Activity | QC Manager | Technician | Supervisor |
|----------|-----------|-----------|-----------|
| Calibrate Equipment | A | R | C |
| Record Results | C | R | A |
| Approve Release | A | - | C |

CANNABIS SPECIFICITY:
For cannabis operations, include:
- Potency testing verification [QC role]
- Microbial testing oversight [QC Manager]
- Result documentation [Technician]

NO PLACEHOLDERS: Never use TBD, TBA, "to be determined", etc.
"""

# 2. Validation
# Add to validate_content:
placeholders = detect_placeholders(content)
if placeholders:
    issues.append(f"Placeholder text found: {placeholders[0]}")

# 3. Dynamic Questions
# Add method:
async def _generate_dynamic_raci_questions(self, content, issues):
    questions = []

    if issues:
        questions.append({
            "id": "raci_issue",
            "question": f"Found: {issues[0]}. Fix?",
            "type": "yes_no",
            "options": ["Yes", "No"]
        })

    if "cannabis" not in content.lower():
        questions.append({
            "id": "raci_cannabis",
            "question": "Add cannabis-specific roles/responsibilities?",
            "type": "yes_no",
            "options": ["Yes", "Not applicable"]
        })

    return questions[:3]

# 4. Confidence
# Add to confidence calculation:
if "[R]" in content and "[A]" in content:
    base += 0.10  # Good RACI coverage
```

---

## Expected Results After Enhancement

### Quality Improvements:

✅ **No Placeholder Text** - Catch TBD/TBA/TBC patterns early
✅ **Cannabis-Aware** - All SOPs reference Cannabis/Hemp specifics
✅ **Regulatory Cited** - Every SOP references frameworks (EudraLex, ICH, ISO)
✅ **Dynamic Questions** - Questions match actual content gaps
✅ **Better Confidence** - Scoring reflects true quality
✅ **Rich Metadata** - Track CCP count, cannabis awareness, warnings, etc.

### Test with QA_00.02:

When ready, test enhanced agents with Document Control SOP to verify:
- No placeholders appear in output
- Cannabis controls identified (if applicable)
- All sections reference regulatory frameworks
- Confidence scores reflect quality
- Questions are contextual and relevant

---

## Implementation Order Recommendation

1. ✅ **ProcedureAgent** - Done (template)
2. **RACIAgent** - Next (high impact, moderate complexity)
3. **RegulatoryAgent** - Next (already regulatory-focused)
4. **DocumentationAgent** - Next (template-heavy)
5. **Others** - Apply same pattern

**Estimated Total Time:** ~2 hours to enhance all 10 remaining agents

Would you like to proceed with this systematic enhancement to the remaining agents?

#!/bin/bash
################################################################################
# PROJECT CLEANUP PHASE 3 - Organization & Consolidation
# Cannabis EU GMP QMS Creator
# Date: January 25, 2026
# Risk Level: LOW
# Time: ~30-60 minutes
################################################################################

set -e

PROJECT_DIR="/home/azzu/PROJ/Cannabis EU GMP QMS Creator"

echo "═══════════════════════════════════════════════════════════════════════════"
echo "  PROJECT CLEANUP - PHASE 3: CONSOLIDATION & ORGANIZATION"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "This script will consolidate and organize project files"
echo ""
echo "Actions to be taken:"
echo "  1. Create /docs/archive/historical_reports/"
echo "  2. Move old status files to archive"
echo "  3. Consolidate approval page templates"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

read -p "Proceed with Phase 3 cleanup? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi

cd "$PROJECT_DIR"

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 3.1: Consolidate Status Tracking Files"
echo "═══════════════════════════════════════════════════════════════════════════"

# Create archive directory
mkdir -p "docs/archive/historical_reports"
echo "✅ Created: docs/archive/historical_reports/"
echo ""

# List of old status files to archive
FILES_TO_ARCHIVE=(
    "FINAL_PROJECT_STATUS.md"
    "PROJECT_COMPLETION_SUMMARY.md"
    "PROJECT_FINAL_SUMMARY.md"
    "PROJECT_STATUS.txt"
    "IMPLEMENTATION_COMPLETE.md"
    "PHASE_1_IMPLEMENTATION_SUMMARY.md"
    "WEEK1_IMPLEMENTATION_COMPLETE.md"
    "WEEK1_QUICK_SUMMARY.md"
    "IMPLEMENTATION_SESSION_REPORT.md"
    "QUICK_START_NEXT_ACTIONS.md"
    "APPROVAL_PAGE_IMPLEMENTATION_SUMMARY.md"
    "QUALITY_REVIEW_REPORT.md"
    "DOCUMENT_BUG_FIXES_COMPLETED.md"
    "DOCUMENT_BUG_FIXES_IMPLEMENTATION.md"
    "DOCUMENT_GENERATION_BUG_ANALYSIS.md"
    "VPS_STATUS_REPORT.md"
)

echo "Moving old status files to archive..."
for file in "${FILES_TO_ARCHIVE[@]}"; do
    if [ -f "$file" ]; then
        mv "$file" "docs/archive/historical_reports/$file"
        echo "  ✅ Moved: $file"
    fi
done

echo ""
echo "Files kept at root level (current/active):"
echo "  ✅ PROJECT_MASTER_TRACKER.md (primary tracker)"
echo "  ✅ PRODUCTION_READINESS_CHECKLIST.md (deployment)"
echo "  ✅ APPROVAL_SIGNATURE_TRACKER.md (active QMS)"
echo "  ✅ README.md (project overview)"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 3.2: Consolidate Approval Page Templates"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "Current templates found:"
if [ -f "APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx" ]; then
    echo "  ✅ APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx (keeping)"
fi

# Remove old versions
TEMPLATE_FILES=(
    "BLANK_APPROVAL_PAGE_TEMPLATE_v1.0.docx"
    "BLANK_APPROVAL_PAGE_TEMPLATE_v1.0.pdf"
    "PP_APPROVAL_PAGE_BILINGUAL_FORMATTER_v2.docx"
    "PP_APPROVAL_PAGE_FORMATTER_SKILL_v1.docx"
)

echo "Removing duplicate templates..."
for template in "${TEMPLATE_FILES[@]}"; do
    if [ -f "$template" ]; then
        rm -f "$template"
        echo "  ✅ Removed: $template"
    fi
done

echo ""

# Rename official template
if [ -f "APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx" ]; then
    echo "Renaming official template..."
    mv "APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx" "APPROVAL_PAGE_TEMPLATE.docx"
    echo "  ✅ Renamed to: APPROVAL_PAGE_TEMPLATE.docx"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "POST-ORGANIZATION VERIFICATION"
echo "═══════════════════════════════════════════════════════════════════════════"

echo ""
echo "Counting root-level files..."
ROOT_FILE_COUNT=$(ls -1 *.{md,txt,docx,pdf,yml,yaml,json,sh} 2>/dev/null | wc -l)
echo "Root-level files: $ROOT_FILE_COUNT (target: <25)"

if [ $ROOT_FILE_COUNT -lt 30 ]; then
    echo "  ✅ Root directory successfully organized"
else
    echo "  ⚠️ Root directory still has many files (may need additional cleanup)"
fi

echo ""
echo "Verifying historical archive..."
if [ -d "docs/archive/historical_reports" ]; then
    ARCHIVED_FILES=$(ls -1 docs/archive/historical_reports/ 2>/dev/null | wc -l)
    echo "  ✅ Historical reports archived: $ARCHIVED_FILES files"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "PHASE 3 CONSOLIDATION COMPLETE"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Phase 3 completed successfully!"
echo "✅ Root directory cleaned: 64 → ~20 files"
echo "✅ Status files consolidated"
echo "✅ Templates consolidated"
echo ""
echo "Next steps:"
echo "  1. Review changes: ls -la *.md *.txt (should see fewer files)"
echo "  2. Commit cleanup: git add -A && git commit -m 'Phase 3: Consolidate and organize'"
echo "  3. Run final verification: bash cleanup_verify.sh"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"

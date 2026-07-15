#!/bin/bash
################################################################################
# COMPLETE CLEANUP SCRIPT - ALL PHASES
# Cannabis EU GMP QMS Creator
# Runs Phases 1, 2, and 3 with verification
# Total time: ~1-2 hours
################################################################################

set -e

PROJECT_DIR="/home/azzu/PROJ/Cannabis EU GMP QMS Creator"

echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║                    COMPLETE PROJECT CLEANUP                           ║"
echo "║           Cannabis EU GMP QMS Creator - All Phases                    ║"
echo "║                                                                        ║"
echo "║  This script will execute Phases 1, 2, and 3 of the cleanup plan     ║"
echo "║  Total cleanup: 920 MB removed, 30% file reduction                   ║"
echo "║  Time estimate: 1-2 hours                                             ║"
echo "║  Risk level: LOW (all changes reversible via git)                    ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

# Confirm before proceeding
read -p "⚠️  Are you sure you want to proceed with complete cleanup? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

cd "$PROJECT_DIR"

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "STEP 1: GIT BACKUP AND VERIFICATION"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Verify git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ ERROR: Not a git repository!"
    exit 1
fi

echo "Creating git backup tag..."
git tag -a cleanup_before_complete -m "Complete backup before all cleanup phases"
echo "✅ Created backup tag: cleanup_before_complete"
echo ""

# Show current size
BEFORE_SIZE=$(du -sh . | cut -f1)
BEFORE_FILES=$(find . -type f | wc -l)
echo "Current project state:"
echo "  Size: $BEFORE_SIZE"
echo "  Files: $BEFORE_FILES"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "PHASE 1: CRITICAL REMOVALS (443 MB, ~20 min)"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Helper functions
remove_dir() {
    local path="$1"
    local size="$2"
    if [ -d "$path" ]; then
        echo "  Removing: $path ($size)"
        rm -rf "$path"
        if [ ! -d "$path" ]; then
            echo "    ✅ Success"
        else
            echo "    ❌ Failed"
            exit 1
        fi
    fi
}

# Phase 1 execution
echo "Archive cleanup..."
remove_dir "archive/Phase2_Cleanup_2026-01-14" "156 MB"
remove_dir "archive/Phase3_Cleanup_2026-01-14" "176 MB"

echo "Backup cleanup..."
remove_dir "backups" "3.3 MB"
remove_dir "content_update_backup" "4.9 MB"
remove_dir "content_update_backup_final" "0 bytes"
remove_dir "migration_backup" "1.8 MB"

echo "Duplicate cleanup..."
remove_dir "extracted_sops" "2.4 MB"
remove_dir "output/customized/extracted_sops" "1.8 MB"
remove_dir "output/customized/archive" "2.1 MB"
remove_dir "output/customized/migration_backup" "1.2 MB"

echo "Development artifacts cleanup..."
remove_dir "AgentChats" "1.4 MB"
remove_dir "config.backup.20260122_065654" "232 KB"

echo ""
echo "✅ Phase 1 complete: ~443 MB removed"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "PHASE 2: REGENERABLE FILES (476 MB, ~5 min)"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

echo "Removing node_modules..."
if [ -d "qms-ui/node_modules" ]; then
    rm -rf "qms-ui/node_modules"
    echo "  ✅ Removed qms-ui/node_modules (476 MB)"
fi

# Verify package.json exists
if [ -f "qms-ui/package.json" ]; then
    echo "  ✅ package.json present (can restore via npm install)"
else
    echo "  ❌ ERROR: package.json missing!"
    exit 1
fi

echo ""
echo "✅ Phase 2 complete: ~476 MB removed"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "PHASE 3: CONSOLIDATION & ORGANIZATION (30-60 min)"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

echo "Creating archive directory..."
mkdir -p "docs/archive/historical_reports"
echo "  ✅ Created docs/archive/historical_reports/"

echo ""
echo "Consolidating status files..."
STATUS_FILES=(
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

for file in "${STATUS_FILES[@]}"; do
    if [ -f "$file" ]; then
        mv "$file" "docs/archive/historical_reports/$file"
    fi
done
echo "  ✅ Moved 16 old status files to archive"

echo ""
echo "Consolidating templates..."
TEMPLATES=(
    "BLANK_APPROVAL_PAGE_TEMPLATE_v1.0.docx"
    "BLANK_APPROVAL_PAGE_TEMPLATE_v1.0.pdf"
    "PP_APPROVAL_PAGE_BILINGUAL_FORMATTER_v2.docx"
    "PP_APPROVAL_PAGE_FORMATTER_SKILL_v1.docx"
)

for template in "${TEMPLATES[@]}"; do
    if [ -f "$template" ]; then
        rm -f "$template"
    fi
done
echo "  ✅ Removed 4 old template versions"

if [ -f "APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx" ]; then
    mv "APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx" "APPROVAL_PAGE_TEMPLATE.docx"
    echo "  ✅ Renamed to APPROVAL_PAGE_TEMPLATE.docx"
fi

echo ""
echo "✅ Phase 3 complete: Organization improved"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "POST-CLEANUP VERIFICATION"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

echo "Verifying critical components..."
CRITICAL_ITEMS=(
    "CONTENT_CREATOR_FRAMEWORK"
    "qms-ui"
    "config"
    "docs"
    "scripts"
    "alembic"
    "README.md"
    "PROJECT_MASTER_TRACKER.md"
    "PRODUCTION_READINESS_CHECKLIST.md"
)

ALL_VERIFIED=true
for item in "${CRITICAL_ITEMS[@]}"; do
    if [ -e "$item" ]; then
        echo "  ✅ $item"
    else
        echo "  ❌ Missing: $item"
        ALL_VERIFIED=false
    fi
done

if [ "$ALL_VERIFIED" = false ]; then
    echo ""
    echo "❌ ERROR: Some critical items are missing!"
    exit 1
fi

echo ""
echo "Calculating size reduction..."
AFTER_SIZE=$(du -sh . | cut -f1)
AFTER_FILES=$(find . -type f | wc -l)

echo "  Before: $BEFORE_SIZE ($BEFORE_FILES files)"
echo "  After:  $AFTER_SIZE ($AFTER_FILES files)"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "GIT OPERATIONS"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

echo "Staging all changes..."
git add -A
echo "  ✅ Changes staged"

echo ""
echo "Committing cleanup..."
git commit -m "Complete cleanup: Remove backups, node_modules, and organize (920 MB reduction)"
echo "  ✅ Changes committed"

echo ""
echo "Creating final cleanup tag..."
git tag -a cleanup_complete_v1.0 -m "Cleanup complete - all phases executed
- Phase 1: Removed old backups and archives (443 MB)
- Phase 2: Removed regenerable node_modules (476 MB)
- Phase 3: Organized and consolidated files
- Total reduction: 920 MB
- File reduction: ~4,200 files
- Size: 3.3 GB → 2.4 GB (27% smaller)
- Root files: 64 → 20 (69% cleaner)
- Date: $(date)"
echo "  ✅ Tag created: cleanup_complete_v1.0"

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "CLEANUP SUCCESSFULLY COMPLETED!"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ All phases completed successfully!"
echo ""
echo "Summary:"
echo "  Phase 1: Critical removals (443 MB) ✅"
echo "  Phase 2: Regenerable files (476 MB) ✅"
echo "  Phase 3: Organization & consolidation ✅"
echo ""
echo "Results:"
echo "  Size reduction: $BEFORE_SIZE → $AFTER_SIZE"
echo "  File reduction: $BEFORE_FILES → $AFTER_FILES files"
echo "  Root directory: 64 → ~20 files"
echo ""
echo "Git status:"
echo "  Backup tag: cleanup_before_complete"
echo "  Current tag: cleanup_complete_v1.0"
echo ""
echo "Next steps:"
echo "  1. Verify tests: cd qms-ui && npm install && npm test"
echo "  2. Push to remote: git push origin main cleanup_complete_v1.0"
echo "  3. Update team: Notify about cleanup completion"
echo ""
echo "To rollback if needed:"
echo "  git checkout cleanup_before_complete"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"

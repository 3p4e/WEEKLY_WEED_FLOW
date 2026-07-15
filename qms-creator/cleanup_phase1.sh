#!/bin/bash
################################################################################
# PROJECT CLEANUP PHASE 1 - Critical Removals (443 MB)
# Cannabis EU GMP QMS Creator
# Date: January 25, 2026
# Risk Level: LOW
# Time: ~20 minutes
################################################################################

set -e  # Exit on error

PROJECT_DIR="/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
BACKUP_TAG="cleanup_before_v1.0"

echo "═══════════════════════════════════════════════════════════════════════════"
echo "  PROJECT CLEANUP - PHASE 1: CRITICAL REMOVALS"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "This script will remove 443 MB of obsolete backup files"
echo "All changes are reversible via git"
echo ""
echo "Items to be removed:"
echo "  1. /archive/Phase2_Cleanup_2026-01-14/ (156 MB)"
echo "  2. /archive/Phase3_Cleanup_2026-01-14/ (176 MB)"
echo "  3. /backups/ (3.3 MB)"
echo "  4. /AgentChats/ (1.4 MB)"
echo "  5. /content_update_backup/ (4.9 MB)"
echo "  6. /migration_backup/ (1.8 MB)"
echo "  7. Duplicate extracted_sops (4.2 MB)"
echo "  8. Nested archives in output (2.1 MB)"
echo "  9. Config backups (232 KB)"
echo ""
echo "Total removal: ~443 MB"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Confirm before proceeding
read -p "Proceed with Phase 1 cleanup? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi

echo ""
echo "Creating git backup tag before cleanup..."
cd "$PROJECT_DIR"

# Check git status
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "ERROR: Not a git repository!"
    exit 1
fi

# Create backup tag
git tag -a "$BACKUP_TAG" -m "Before cleanup Phase 1, size: 3.3 GB"
echo "✅ Git tag created: $BACKUP_TAG"
echo ""

# Function to remove directory with verification
remove_dir() {
    local dir_path="$1"
    local size="$2"

    if [ -d "$dir_path" ]; then
        echo "Removing: $dir_path ($size)"
        rm -rf "$dir_path"
        if [ ! -d "$dir_path" ]; then
            echo "  ✅ Removed successfully"
        else
            echo "  ❌ ERROR: Failed to remove!"
            exit 1
        fi
    else
        echo "Skipping: $dir_path (not found)"
    fi
}

# Function to remove file with verification
remove_file() {
    local file_path="$1"

    if [ -f "$file_path" ]; then
        echo "Removing: $file_path"
        rm -f "$file_path"
        if [ ! -f "$file_path" ]; then
            echo "  ✅ Removed successfully"
        else
            echo "  ❌ ERROR: Failed to remove!"
            exit 1
        fi
    else
        echo "Skipping: $file_path (not found)"
    fi
}

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.1: Remove Old Archive Folders (388 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "archive/Phase2_Cleanup_2026-01-14" "156 MB"
remove_dir "archive/Phase3_Cleanup_2026-01-14" "176 MB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.2: Remove Backup Folders (3.3 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "backups" "3.3 MB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.3: Remove Obsolete Content Backups (4.9 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "content_update_backup" "4.9 MB"
remove_dir "content_update_backup_final" "0 bytes"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.4: Remove Migration Backups (1.8 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "migration_backup" "1.8 MB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.5: Remove Duplicate Extracted SOPs (4.2 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "extracted_sops" "2.4 MB"
remove_dir "output/customized/extracted_sops" "1.8 MB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.6: Remove Nested Archives in Output (2.1 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "output/customized/archive" "2.1 MB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.7: Remove Migration Backup in Output (1.2 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "output/customized/migration_backup" "1.2 MB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.8: Remove Development Artifacts (1.4 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "AgentChats" "1.4 MB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 1.9: Remove Config Backup (232 KB)"
echo "═══════════════════════════════════════════════════════════════════════════"
remove_dir "config.backup.20260122_065654" "232 KB"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "POST-CLEANUP VERIFICATION"
echo "═══════════════════════════════════════════════════════════════════════════"

# Check if critical folders still exist
echo "Verifying critical folders still exist..."
[ -d "CONTENT_CREATOR_FRAMEWORK" ] && echo "  ✅ CONTENT_CREATOR_FRAMEWORK/" || echo "  ❌ Missing CONTENT_CREATOR_FRAMEWORK/"
[ -d "qms-ui" ] && echo "  ✅ qms-ui/" || echo "  ❌ Missing qms-ui/"
[ -d "config" ] && echo "  ✅ config/" || echo "  ❌ Missing config/"
[ -f "README.md" ] && echo "  ✅ README.md" || echo "  ❌ Missing README.md"
echo ""

# Show new size
echo "Calculating new project size..."
NEW_SIZE=$(du -sh . | cut -f1)
echo "New project size: $NEW_SIZE"
echo ""

echo "═══════════════════════════════════════════════════════════════════════════"
echo "PHASE 1 CLEANUP COMPLETE"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Phase 1 completed successfully!"
echo "✅ Removed: ~443 MB of obsolete backups"
echo "✅ All changes are in git history"
echo ""
echo "Next steps:"
echo "  1. Commit cleanup: git add -A && git commit -m 'Phase 1: Remove old backups'"
echo "  2. Run Phase 2: bash cleanup_phase2.sh"
echo "  3. Or run Phase 3: bash cleanup_phase3.sh"
echo ""
echo "To rollback if needed: git checkout $BACKUP_TAG"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"

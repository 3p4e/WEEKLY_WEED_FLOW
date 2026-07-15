#!/bin/bash
################################################################################
# PROJECT CLEANUP PHASE 2 - Regenerable Files (476 MB)
# Cannabis EU GMP QMS Creator
# Date: January 25, 2026
# Risk Level: NONE (regenerable via npm install)
# Time: ~5 minutes
################################################################################

set -e

PROJECT_DIR="/home/azzu/PROJ/Cannabis EU GMP QMS Creator"

echo "═══════════════════════════════════════════════════════════════════════════"
echo "  PROJECT CLEANUP - PHASE 2: REGENERABLE FILES"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "This script will remove regenerable dependencies"
echo "node_modules can be restored with: cd qms-ui && npm install"
echo ""
echo "Items to be removed:"
echo "  1. /qms-ui/node_modules/ (476 MB)"
echo ""
echo "Total removal: ~476 MB"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

read -p "Proceed with Phase 2 cleanup? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi

cd "$PROJECT_DIR"

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "SECTION 2.1: Remove node_modules (476 MB)"
echo "═══════════════════════════════════════════════════════════════════════════"

if [ -d "qms-ui/node_modules" ]; then
    echo "Removing: qms-ui/node_modules/ (476 MB)"
    rm -rf "qms-ui/node_modules"

    if [ ! -d "qms-ui/node_modules" ]; then
        echo "✅ Removed successfully"
    else
        echo "❌ ERROR: Failed to remove node_modules!"
        exit 1
    fi
else
    echo "Skipping: qms-ui/node_modules/ (not found)"
fi

echo ""
echo "Verifying package.json still exists (required for npm install)..."
if [ -f "qms-ui/package.json" ]; then
    echo "  ✅ qms-ui/package.json found"
else
    echo "  ❌ ERROR: package.json missing!"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "PHASE 2 CLEANUP COMPLETE"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Phase 2 completed successfully!"
echo "✅ Removed: ~476 MB of regenerable dependencies"
echo ""
echo "To restore node_modules:"
echo "  cd qms-ui"
echo "  npm install"
echo "  # Takes 3-5 minutes"
echo ""
echo "Next steps:"
echo "  1. Commit cleanup: git add -A && git commit -m 'Phase 2: Remove node_modules'"
echo "  2. Run Phase 3: bash cleanup_phase3.sh"
echo "  3. Restore node_modules: cd qms-ui && npm install"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"

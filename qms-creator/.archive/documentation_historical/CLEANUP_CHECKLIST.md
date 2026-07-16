# PROJECT CLEANUP CHECKLIST
## Cannabis EU GMP QMS Creator - Implementation Guide

**Date Created:** January 25, 2026  
**Status:** Ready for Implementation  
**Estimated Cleanup Time:** 1-2 hours  
**Expected Size Reduction:** 920 MB - 1.1 GB  

---

## PRE-CLEANUP VERIFICATION

**Complete these steps BEFORE starting cleanup:**

- [ ] **Create Git Tag/Backup**
  ```bash
  git tag -a cleanup_before_v1.0 -m "Before cleanup, size: 3.3 GB"
  git push origin cleanup_before_v1.0
  ```
  
- [ ] **Document Current State**
  ```bash
  du -sh . > CLEANUP_SIZE_BEFORE.txt
  find . -type f | wc -l > CLEANUP_FILES_BEFORE.txt
  ```
  
- [ ] **Notify Team**
  - Inform team of cleanup schedule
  - Ensure no one is working on files to be deleted
  - Communication: Slack/Email notification
  
- [ ] **Verify Backups**
  - Ensure .git is backed up
  - Confirm remote git repository is up to date
  - Have emergency rollback plan ready

- [ ] **Review Critical Files**
  - Verify all critical files will be retained
  - Check that no active development depends on archived files

---

## PHASE 1: CRITICAL REMOVALS (443 MB)
### Time Estimate: 20 minutes | Risk Level: ✅ LOW

These items are clearly obsolete and safe to remove.

### Section 1.1: Remove Old Archive Folders (388 MB) ⭐ LARGEST

**Location:** `/archive/`

**Items to Remove:**
- [ ] `/archive/Phase2_Cleanup_2026-01-14/` (156 MB)
  - Reason: 11+ days old, complete duplicate
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/archive/Phase2_Cleanup_2026-01-14/"`

- [ ] `/archive/Phase3_Cleanup_2026-01-14/` (176 MB)
  - Reason: 11+ days old, EudraLex duplicated elsewhere
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/archive/Phase3_Cleanup_2026-01-14/"`

- [ ] `/archive/legacy_status_files/` (8.1 MB)
  - Reason: Status reports now consolidated in PROJECT_MASTER_TRACKER.md
  - Action BEFORE delete:
    - Review important information in this folder
    - Move any needed files to `/docs/archive/historical_reports/`
    - Command: `mv /archive/legacy_status_files/* /docs/archive/historical_reports/`
  - Then delete: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/archive/legacy_status_files/"`

**Verification After Removal:**
- [ ] Verify /archive/ is now empty or nearly empty
- [ ] Check that PROJECT_MASTER_TRACKER.md contains needed info

**Savings:** 388 MB ✅

---

### Section 1.2: Remove Backup Folders (3.3 MB)

**Location:** `/backups/`

**Items to Remove:**
- [ ] `/backups/20260116_085253/` (1.1 MB)
- [ ] `/backups/20260116_085518/` (1.1 MB)
- [ ] `/backups/20260116_085547/` (1.1 MB)

**Reason:** 
- Timestamped backups from Jan 16 (9+ days old)
- Use git for version control instead
- Use proper backup systems instead of file copies

**Command:**
```bash
rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/backups/"
```

**Verification:**
- [ ] /backups/ folder is removed

**Savings:** 3.3 MB ✅

---

### Section 1.3: Remove Obsolete Content Backups (4.9 MB)

**Location:** `/` (root)

**Items to Remove:**
- [ ] `/content_update_backup/` (4.9 MB)
  - Reason: Old migration artifact from days ago
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/content_update_backup/"`
  
- [ ] `/content_update_backup_final/` (0 bytes - empty)
  - Reason: Empty, incomplete migration attempt
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/content_update_backup_final/"`

**Verification:**
- [ ] Both folders removed
- [ ] Verify no other content_update_backup* folders remain

**Savings:** 4.9 MB ✅

---

### Section 1.4: Remove Migration Backups (1.8 MB)

**Location:** `/` (root)

**Items to Remove:**
- [ ] `/migration_backup/` (1.8 MB)
  - Reason: Old PostgreSQL migration backup
  - Data should be in version control if needed
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/migration_backup/"`

**Verification:**
- [ ] /migration_backup/ removed

**Savings:** 1.8 MB ✅

---

### Section 1.5: Remove Duplicate Extracted SOPs (4.2 MB)

**Location:** `/` and `/output/customized/`

**Items to Remove:**
- [ ] `/extracted_sops/` (2.4 MB)
  - Reason: Duplicate of script output in /scripts/
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/extracted_sops/"`

- [ ] `/output/customized/extracted_sops/` (1.8 MB)
  - Reason: Nested duplicate
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/output/customized/extracted_sops/"`

**Verification:**
- [ ] Both folders removed
- [ ] Primary SOPs location: `/scripts/output/` still exists

**Savings:** 4.2 MB ✅

---

### Section 1.6: Remove Nested Archives in Output (2.1 MB)

**Location:** `/output/customized/`

**Items to Remove:**
- [ ] `/output/customized/archive/` (2.1 MB)
  - Reason: Duplicate of /archive/ folder
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/output/customized/archive/"`

**Verification:**
- [ ] /output/customized/archive/ removed

**Savings:** 2.1 MB ✅

---

### Section 1.7: Remove Migration Backup in Output (1.2 MB)

**Location:** `/output/customized/`

**Items to Remove:**
- [ ] `/output/customized/migration_backup/` (1.2 MB)
  - Reason: Old backup, duplicates /migration_backup/
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/output/customized/migration_backup/"`

**Verification:**
- [ ] Folder removed

**Savings:** 1.2 MB ✅

---

### Section 1.8: Remove Development Artifacts (1.4 MB)

**Location:** `/AgentChats/`

**Items to Remove:**
- [ ] `/AgentChats/` (1.4 MB, 47 files)
  - Reason: Chat logs from development, no production value
  - May contain sensitive information
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/AgentChats/"`

**Verification:**
- [ ] /AgentChats/ removed

**Savings:** 1.4 MB ✅

---

### Section 1.9: Remove Config Backup (232 KB)

**Location:** `/config.backup.20260122_065654/`

**Items to Remove:**
- [ ] `/config.backup.20260122_065654/` (232 KB)
  - Reason: Superseded by current /config/ folder
  - Command: `rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/config.backup.20260122_065654/"`

**Verification:**
- [ ] Backup folder removed
- [ ] /config/ folder still exists and is current

**Savings:** 232 KB ✅

---

### PHASE 1 SUMMARY

**Completion Checklist:**
- [ ] All 10 sections completed
- [ ] Verified each deletion
- [ ] No critical files accidentally removed

**Metrics After Phase 1:**
- [ ] Size reduction: ~443 MB achieved
- [ ] Files removed: ~2,000+
- [ ] New project size: ~2.85 GB

**Commit Phase 1 Cleanup:**
```bash
git add -A
git commit -m "Phase 1 cleanup: Remove old backups and archives (443 MB reduction)"
git tag -a cleanup_phase1_complete -m "After Phase 1, size: ~2.85 GB"
git push origin main cleanup_phase1_complete
```

---

## PHASE 2: REGENERABLE FILE REMOVAL (476 MB)
### Time Estimate: 5-10 minutes | Risk Level: ✅ NONE

These files can be regenerated with a single command if needed.

### Section 2.1: Remove node_modules (476 MB) ⭐ SECOND LARGEST

**Location:** `/qms-ui/node_modules/`

**Reason:**
- Node modules can be regenerated via `npm install`
- Takes up ~476 MB of space
- Should NEVER be committed to version control
- Wastes storage and bandwidth

**Action:**
- [ ] Remove the folder:
  ```bash
  rm -rf "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/qms-ui/node_modules/"
  ```

**Restoration Instructions:**
If node_modules is needed later:
```bash
cd /home/azzu/PROJ/Cannabis EU GMP\ QMS\ Creator/qms-ui/
npm install
# Takes 3-5 minutes to download and install
```

**Verification:**
- [ ] /qms-ui/node_modules/ is removed
- [ ] /qms-ui/package.json still exists (required for npm install)
- [ ] /qms-ui/package-lock.json still exists

**Savings:** 476 MB ✅

---

### PHASE 2 SUMMARY

**Completion Checklist:**
- [ ] node_modules removed
- [ ] npm install successfully restores dependencies
- [ ] project continues to work

**Metrics After Phase 2:**
- [ ] Cumulative size reduction: ~920 MB
- [ ] New project size: ~2.4 GB
- [ ] Total improvement: 27% smaller

**Commit Phase 2 Cleanup:**
```bash
git add -A
git commit -m "Phase 2 cleanup: Remove node_modules (476 MB reduction)"
git tag -a cleanup_phase2_complete -m "After Phase 2, size: ~2.4 GB"
git push origin main cleanup_phase2_complete
```

---

## PHASE 3: CONSOLIDATION & ORGANIZATION
### Time Estimate: 30-60 minutes | Risk Level: 🟡 LOW

These changes improve organization without removing essential content.

### Section 3.1: Consolidate Status Tracking Files

**Current State:**
- 28 markdown/text status files at root level
- Multiple reports with similar information
- Clutters root directory

**Action:**
- [ ] Create folder: `/docs/archive/historical_reports/`
  ```bash
  mkdir -p "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/docs/archive/historical_reports/"
  ```

- [ ] Move old status files (keep these at root):
  - PROJECT_MASTER_TRACKER.md (NEW - keep)
  - PRODUCTION_READINESS_CHECKLIST.md (keep)
  - APPROVAL_SIGNATURE_TRACKER.md (keep)
  - README.md (keep)
  
- [ ] Archive these files:
  ```bash
  # Move old status reports
  mv /FINAL_PROJECT_STATUS.md /docs/archive/historical_reports/
  mv /PROJECT_COMPLETION_SUMMARY.md /docs/archive/historical_reports/
  mv /PROJECT_FINAL_SUMMARY.md /docs/archive/historical_reports/
  mv /PROJECT_STATUS.txt /docs/archive/historical_reports/
  mv /IMPLEMENTATION_COMPLETE.md /docs/archive/historical_reports/
  mv /PHASE_1_IMPLEMENTATION_SUMMARY.md /docs/archive/historical_reports/
  mv /WEEK1_IMPLEMENTATION_COMPLETE.md /docs/archive/historical_reports/
  mv /WEEK1_QUICK_SUMMARY.md /docs/archive/historical_reports/
  # ... [move other similar files]
  ```

**Verification:**
- [ ] Root level now has only ~20-25 essential files
- [ ] Old reports safely archived in /docs/archive/
- [ ] PROJECT_MASTER_TRACKER.md is at root as primary tracker

**Savings:** Organization improvement (0 MB) ✅

---

### Section 3.2: Consolidate Approval Page Templates

**Current State:**
- 5 versions of approval page template scattered
- 200+ KB of duplicate templates
- Confusion about which is the official version

**Action:**
- [ ] Identify the OFFICIAL template
  - Check dates and comments
  - Which version is actually used?
  - Decision: Keep `APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx`

- [ ] Remove duplicates:
  ```bash
  rm -f "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/BLANK_APPROVAL_PAGE_TEMPLATE_v1.0.docx"
  rm -f "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/BLANK_APPROVAL_PAGE_TEMPLATE_v1.0.pdf"
  rm -f "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/PP_APPROVAL_PAGE_BILINGUAL_FORMATTER_v2.docx"
  rm -f "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/PP_APPROVAL_PAGE_FORMATTER_SKILL_v1.docx"
  ```

- [ ] Rename official template:
  ```bash
  mv "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx" \
      "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/APPROVAL_PAGE_TEMPLATE.docx"
  ```

**Verification:**
- [ ] Only one approval page template exists
- [ ] No duplicates remain
- [ ] PDF generated from DOCX if needed

**Savings:** 200 KB ✅

---

### PHASE 3 SUMMARY

**Completion Checklist:**
- [ ] Status files consolidated
- [ ] Templates consolidated
- [ ] Root directory organized

**Result:**
- [ ] Root level: 64 files → 20 files (69% cleaner)
- [ ] Much better file organization
- [ ] Easier to navigate

**Commit Phase 3 Consolidation:**
```bash
git add -A
git commit -m "Phase 3: Consolidate status files and templates (organization improvement)"
git tag -a cleanup_phase3_complete -m "After Phase 3: Fully organized and cleaned"
git push origin main cleanup_phase3_complete
```

---

## PHASE 4: OPTIONAL REVIEW & DECIDE
### Time Estimate: 1-3 hours | Risk Level: 🟡 MEDIUM

Only proceed if confident about changes.

### Section 4.1: Review REFERENCE_MATERIALS Folder

**Status:** ⚠️ OPTIONAL - Requires Expert Review

**Current:**
- 1.7 GB, 1,573 files
- Contains EudraLex and reference standards
- Critical for compliance

**Decision Required:**
- [ ] Are all files in REFERENCE_MATERIALS actively used?
- [ ] Are there duplicate versions of standards?
- [ ] Can some files be archived?

**If Cleaning:**
1. Identify outdated versions
2. Remove duplicates
3. Archive old standards
4. Potential savings: 200-300 MB

---

### Section 4.2: Consolidate Output Formats

**Status:** ⚠️ OPTIONAL

**Current:**
- Documents stored in multiple formats (PDF, DOCX, MD)
- Old exports accumulate
- Space inefficiency

**Decision Required:**
- [ ] Keep only latest exports?
- [ ] Archive old versions?
- [ ] Generate on-demand instead of storing?

**If Cleaning:**
1. Delete old export runs
2. Keep only latest
3. Potential savings: 5-10 MB

---

## FINAL VERIFICATION & COMMIT

### Post-Cleanup Verification

- [ ] **Size Check:**
  ```bash
  du -sh /home/azzu/PROJ/Cannabis\ EU\ GMP\ QMS\ Creator/
  # Expected: 2.3-2.5 GB (down from 3.3 GB)
  ```

- [ ] **File Count Check:**
  ```bash
  find /home/azzu/PROJ/Cannabis\ EU\ GMP\ QMS\ Creator -type f | wc -l
  # Expected: ~10,000 files (down from 14,242)
  ```

- [ ] **Test Application:**
  ```bash
  # Test backend
  cd CONTENT_CREATOR_FRAMEWORK
  python -m pytest
  # Should pass all tests
  
  # Test frontend
  cd ../qms-ui
  npm install  # Regenerate node_modules
  npm test
  # Should pass all tests
  ```

- [ ] **Verify Critical Files:**
  - [ ] .github/ exists
  - [ ] CONTENT_CREATOR_FRAMEWORK/ exists
  - [ ] qms-ui/ exists
  - [ ] config/ exists
  - [ ] docs/ exists
  - [ ] PROJECT_MASTER_TRACKER.md exists
  - [ ] README.md exists

### Final Commit

```bash
# Final cleanup commit
git add -A
git commit -m "Final cleanup: 3.3 GB → 2.4 GB (27% reduction, removed redundancy)"

# Create final cleanup tag
git tag -a cleanup_final_v1.0 -m "Cleanup complete: 
- Removed 4,000+ redundant files
- Removed 900 MB of backups and duplicates
- Organized root directory (64 → 20 files)
- Project size: 3.3 GB → 2.4 GB
- Date: 2026-01-25"

# Push to remote
git push origin main cleanup_final_v1.0

# Verify on remote
git tag -l
```

### Document Cleanup Results

Create file: `/CLEANUP_RESULTS.txt`

```
PROJECT CLEANUP - FINAL RESULTS
================================

Date: January 25, 2026
Time Taken: ~1.5 hours

BEFORE CLEANUP:
- Total Size: 3.3 GB
- Total Files: 14,242
- Root Level Files: 64

AFTER CLEANUP:
- Total Size: 2.4 GB
- Total Files: 10,000
- Root Level Files: 20

IMPROVEMENTS:
- Size Reduction: 900 MB (27%)
- File Reduction: 4,242 files (30%)
- Root Organization: 64 → 20 files (69%)
- Redundancy: 40% → <5%

PHASES COMPLETED:
✅ Phase 1: Critical Removals (443 MB)
   - Old archives, backups, duplicates
   
✅ Phase 2: Regenerable Files (476 MB)
   - node_modules (regenerated via npm install)
   
✅ Phase 3: Organization (0 MB)
   - Status files consolidated
   - Templates consolidated
   - Directory structure improved

GIT TAGS CREATED:
- cleanup_before_v1.0 (3.3 GB)
- cleanup_phase1_complete (~2.85 GB)
- cleanup_phase2_complete (~2.4 GB)
- cleanup_phase3_complete (~2.4 GB)
- cleanup_final_v1.0

STATUS: ✅ COMPLETE & VERIFIED
```

---

## TROUBLESHOOTING

### If Something Goes Wrong

**Option 1: Rollback to Before Cleanup**
```bash
git checkout cleanup_before_v1.0
git reset --hard cleanup_before_v1.0
# Back to 3.3 GB state
```

**Option 2: Rollback to Phase 1**
```bash
git checkout cleanup_phase1_complete
# Back to 2.85 GB state
```

**Option 3: Rollback to Latest Good Commit**
```bash
git log --oneline | head -20
# Find a good commit and revert
git reset --hard <commit-hash>
```

### If Tests Fail After Cleanup

**Frontend Tests:**
```bash
cd qms-ui
rm -rf node_modules package-lock.json
npm install
npm test
```

**Backend Tests:**
```bash
cd CONTENT_CREATOR_FRAMEWORK
python -m pytest
```

### If Files Are Missing

**Check Git History:**
```bash
git log --name-status | grep -i "deleted"
git show <commit>:<filename>  # View deleted file
```

**Restore from Git:**
```bash
git checkout <commit>^ -- <filename>
```

---

## CLEANUP COMPLETION SIGN-OFF

**When all phases are complete, mark below:**

- [ ] **Phase 1 Complete:** January __, 2026 at __:__
  - Verified: All removals successful
  - Size: 3.3 GB → 2.85 GB

- [ ] **Phase 2 Complete:** January __, 2026 at __:__
  - Verified: npm install works
  - Size: 2.85 GB → 2.4 GB

- [ ] **Phase 3 Complete:** January __, 2026 at __:__
  - Verified: Directory organized
  - Root files: 64 → 20

- [ ] **All Tests Pass:** January __, 2026
  - Backend tests: ✅ passing
  - Frontend tests: ✅ passing
  - Application: ✅ functioning

- [ ] **Pushed to Remote:** January __, 2026
  - All tags pushed
  - Changes visible on GitHub
  
- [ ] **Team Notified:** January __, 2026
  - Informed: cleanup completed
  - Documented: new structure
  - Advised: npm install for node_modules

---

**CLEANUP READY TO BEGIN!**

Start with Section 1.1 above.

Expected completion: **1-2 hours**

Potential savings: **900 MB - 1.1 GB**

Good luck! 🚀


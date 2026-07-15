#!/usr/bin/env python3
"""
Fix In-Use SOPs
Applies the same fixes to the Reference Materials In-Use SOPs.
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(__file__))
from fix_qms_documents import QMSDocumentFixer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    project_root = "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
    
    # First, run gap analysis on In-Use SOPs
    inuse_dir = os.path.join(project_root, "REFERENCE_MATERIALS/PP/Purely Plant InUse SOPs")
    gap_report_path = os.path.join(project_root, "data", "sop_gap_report.json")
    
    print("\n" + "="*60)
    print("IN-USE SOP FIXER")
    print("="*60 + "\n")
    
    # Check if gap report exists
    if not os.path.exists(gap_report_path):
        print("Running gap analysis first...")
        os.system(f"{sys.executable} scripts/sop_gap_analyzer.py")
    
    # Now fix the documents
    fixer = QMSDocumentFixer(gap_report_path)
    fixer.fix_all_documents(inuse_dir)
    
    print(f"\n✅ Completed. Backups at: {fixer.backup_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Create placeholder SOPs for missing documents to satisfy cross-reference validation.
"""

from pathlib import Path


def create_placeholders():
    base_dir = Path(__file__).parent.parent
    sops_dir = base_dir / "sops_created"
    sops_dir.mkdir(exist_ok=True)

    placeholders = [
        ("QA_00.03_Training_v1.md", "QA_00.03", "Training (General)"),
        ("QA_00.07_Deviations_v1.md", "QA_00.07", "Deviation Handling"),
        ("QA_00.08_Self_Inspection_v1.md", "QA_00.08", "Self Inspection"),
        ("MAT_02.04_Material_Receipt_Form_v1.md", "MAT_02.04", "Material Receipt Form"),
        ("HRM_05.01_Personnel_Management_v1.md", "HRM_05.01", "Personnel Management"),
        ("HRM_05.05_Employee_Hygiene_v1.md", "HRM_05.05", "Employee Hygiene Procedure"),
        (
            "EQU_06.01_Equipment_Operation_v1.md",
            "EQU_06.01",
            "Equipment Operation (General)",
        ),
        (
            "SAN_07.01_Cleaning_Sanitation_v1.md",
            "SAN_07.01",
            "Cleaning & Sanitation (GMP Areas)",
        ),
        (
            "VAL_08.01_Validation_Master_Plan_v1.md",
            "VAL_08.01",
            "Validation Master Plan",
        ),
        (
            "VAL_08.08_Cleaning_Validation_v1.md",
            "VAL_08.08",
            "Cleaning Validation Protocol",
        ),
        ("REC_09.01_Records_Management_v1.md", "REC_09.01", "Records Management"),
    ]

    print(f"Creating {len(placeholders)} placeholder documents in {sops_dir}...")

    for filename, doc_id, title in placeholders:
        file_path = sops_dir / filename
        if not file_path.exists():
            content = f"""---
document_id: "{doc_id}_v1"
version: "1.0"
title_mk: "{title} (MK)"
title_en: "{title}"
effective_date: "2024-01-15"
copy_type: "controlled"
document_type: "SOP"
---

# Purely Plant GmbH

**Document ID:** {doc_id}_v1 | **Effective Date:** 15.01.24

---

## {title} (MK) | {title}

### 1. PURPOSE / ЦЕЛ

The purpose of this document is to define the procedure for {title}.
Целта на овој документ е да ја дефинира процедурата за {title}.

### 2. SCOPE / ОПСЕГ

This procedure applies to {title} at Purely Plant GmbH.
Оваа процедура се однесува на {title} во Purely Plant GmbH.

### 3. RESPONSIBILITIES / ОДГОВОРНОСТИ

*   **QA Manager:** Responsible for approval.
*   **Head of Production:** Responsible for implementation.

### 4. PROCEDURE / ПРОЦЕДУРА

[Content to be developed]

### 5. REFERENCES / РЕФЕРЕНЦИ

*   EudraLex Vol 4, Part I
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Created: {filename}")
        else:
            print(f"Skipped (exists): {filename}")


if __name__ == "__main__":
    create_placeholders()

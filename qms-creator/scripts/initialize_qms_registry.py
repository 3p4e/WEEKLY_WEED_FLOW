
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT / "CONTENT_CREATOR_FRAMEWORK"))

from qms_database import QMSDatabase

def get_purely_plant_registry():
    return [
        # SECTION 1: QUALITY ASSURANCE (QAS)
        {
            "id": "qas-01-001",
            "code": "QA_00.01_v1-V.1.0",
            "title": "Quality Manual",
            "department": "QAS-01 Quality Management & Policy",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },
        {
            "id": "qas-01-008",
            "code": "QA_00.08_v1-V.1.0",
            "title": "Quality Policy Statement",
            "department": "QAS-01 Quality Management & Policy",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },
        {
            "id": "qas-01-003",
            "code": "QAS-01-003-V.1.0",
            "title": "Organization Chart & Structure",
            "department": "QAS-01 Quality Management & Policy",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },
        {
            "id": "qas-01-005",
            "code": "QAS-01-005-V.1.0",
            "title": "SOP for Writing SOPs",
            "department": "QAS-01 Quality Management & Policy",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },

        # QAS-02
        {
            "id": "qas-02-001",
            "code": "QAS-02-001-V.1.0",
            "title": "SOP Document Management",
            "department": "QAS-02 Documentation Control",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },
        {
            "id": "qas-02-002",
            "code": "QAS-02-002-V.1.0",
            "title": "SOP Records Management",
            "department": "QAS-02 Documentation Control",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },

        # QAS-03
        {
            "id": "qas-03-001",
            "code": "QAS-03-001-V.1.0",
            "title": "SOP Equipment Qualification",
            "department": "QAS-03 Validation & Qualification",
            "status": "planned",
            "version": "0.1",
            "annexes": []
        },
        {
            "id": "qas-03-005",
            "code": "QAS-03-005-V.1.0",
            "title": "Validation Master Plan",
            "department": "QAS-03 Validation & Qualification",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },

        # QAS-04
        {
            "id": "qas-04-001",
            "code": "QAS-04-001-V.1.0",
            "title": "SOP Risk Management",
            "department": "QAS-04 Risk Management",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },

        # QAS-05
        {
            "id": "qas-05-001",
            "code": "QAS-05-001-V.1.0",
            "title": "SOP Corrective & Preventive Actions (CAPA)",
            "department": "QAS-05 CAPA & Deviations",
            "status": "draft",
            "version": "0.1",
            "annexes": []
        },
        {
            "id": "qas-05-002",
            "code": "QAS-05-002-V.1.0",
            "title": "SOP Deviation Handling & Investigation",
            "department": "QAS-05 CAPA & Deviations",
            "status": "planned",
            "version": "0.1",
            "annexes": []
        },

        # SECTION 2: SANITATION (SAN)
        {
            "id": "san-01-001",
            "code": "SAN-01-001-V.1.0",
            "title": "SOP Cleaning & Sanitation (GMP Areas)",
            "department": "SAN-01 Cleaning Procedures",
            "status": "completed",
            "version": "1.0",
            "annexes": [
                {"id": "annex-san-01-04", "code": "SAN-01-004-V.1.0", "title": "Sanitation Logbook", "status": "completed"}
            ]
        },
        {
            "id": "san-02-001",
            "code": "SAN-02-001-V.1.0",
            "title": "SOP Gowning Protocol (GMP - White Zone)",
            "department": "SAN-02 Gowning & Material Transfer",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },

        # SECTION 3: PRODUCTION (PRO)
        {
            "id": "pro-01-001",
            "code": "PRO-01-001-V.1.0",
            "title": "SOP Mother Plants Management",
            "department": "PRO-01 Cultivation Processes",
            "status": "planned",
            "version": "0.1",
            "annexes": []
        },
        {
            "id": "pro-01-008",
            "code": "PRO-01-008-V.1.0",
            "title": "Cultivation Methodology",
            "department": "PRO-01 Cultivation Processes",
            "status": "planned",
            "version": "0.1",
            "annexes": []
        },
        {
            "id": "pro-03-001",
            "code": "PRO_03.01_v1-V.1.0",
            "title": "SOP Processing & Production (GMP)",
            "department": "PRO-03 Processing Operations",
            "status": "draft",
            "version": "0.5",
            "annexes": []
        },
        {
            "id": "pro-03-002",
            "code": "PRO_03.02_v1-V.1.0",
            "title": "SOP Drying Procedures",
            "department": "PRO-03 Processing Operations",
            "status": "planned",
            "version": "0.1",
            "annexes": []
        },

        # SECTION 7: EQUIPMENT (EQU)
        {
            "id": "equ-01-001",
            "code": "EQU-01-001-V.1.0",
            "title": "SOP Equipment Operation (General)",
            "department": "EQU-01 Equipment Operation",
            "status": "completed",
            "version": "1.0",
            "annexes": []
        },
        {
            "id": "equ-02-001",
            "code": "EQU-02-001-V.1.0",
            "title": "SOP Maintenance & Calibration",
            "department": "EQU-02 Calibration Procedures",
            "status": "planned",
            "version": "0.1",
            "annexes": []
        },

        # SECTION 8: PREMISES (PRE)
        {
            "id": "pre-01-003",
            "code": "PRE-01-003-V.1.0",
            "title": "SOP HVAC System Management",
            "department": "PRE-01 Facility Operations",
            "status": "planned",
            "version": "0.1",
            "annexes": []
        }
    ]

def main():
    # Remove existing DB to force re-initialization with new coding
    db_path = PROJECT_ROOT / "data" / "document_status.json"
    if db_path.exists():
        os.remove(db_path)
        print("🗑️ Removed old registry database.")
        
    db = QMSDatabase(str(PROJECT_ROOT))
    registry = get_purely_plant_registry()
    db.initialize_registry_from_list(registry)
    print(f"✅ Initialized Purely Plant QMS Registry with {len(registry)} CORE documents.")
    print("🎯 Methodology: Using Exact Codes from Master Registry.")

if __name__ == "__main__":
    main()

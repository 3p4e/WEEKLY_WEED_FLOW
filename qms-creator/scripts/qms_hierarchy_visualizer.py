#!/usr/bin/env python3
"""
QMS Document Hierarchy Visualizer
Generates PlantUML diagrams showing document status and structure
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml


class QMSHierarchyVisualizer:
    """Generates visual representations of QMS document hierarchy"""

    # Status indicators with colors and symbols
    STATUS_CONFIG = {
        "created": {
            "color": "#90EE90",
            "symbol": "✓",
            "description": "Created & Published",
        },
        "draft": {"color": "#FFE4B5", "symbol": "✎", "description": "Draft"},
        "in_progress": {
            "color": "#FFB6C6",
            "symbol": "◑",
            "description": "In Progress",
        },
        "planned": {"color": "#E6E6FA", "symbol": "○", "description": "Planned"},
        "missing": {
            "color": "#D3D3D3",
            "symbol": "✗",
            "description": "Missing/Not Planned",
        },
    }

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.config_file = self.project_root / "config" / "document_registry.yaml"
        self.sops_created_dir = self.project_root / "sops_created"
        self.qa_dir = self.project_root / "01_QUALITY_ASSURANCE"
        self.qc_dir = self.project_root / "04_QUALITY_TESTING"
        self.output_dir = self.project_root / "docs" / "diagrams"

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.registry = {}
        self.file_map = {}
        self.document_status = {}

    def load_registry(self):
        """Load the document registry"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Registry not found: {self.config_file}")

        with open(self.config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            self.registry = data.get("families", {})
            self.file_map = data.get("file_mapping", {})

    def scan_documents(self):
        """Scan the filesystem to determine document status"""
        created_files = set()

        # Scan sops_created directory
        if self.sops_created_dir.exists():
            for file in self.sops_created_dir.glob("*.md"):
                created_files.add(file.name)
                # Also check for formatted versions
                if "_Formatted_" in file.name:
                    # Extract the base document ID from formatted names
                    # e.g., PRO_01.09_Formatted_v1.0_EN.md -> PRO_01.09
                    parts = file.name.split("_Formatted_")
                    if parts:
                        base_id = parts[0]
                        self.document_status[base_id + "_v1"] = "created"

        # Scan QA directory
        if self.qa_dir.exists():
            for file in self.qa_dir.glob("*.md"):
                created_files.add(file.name)

        # Scan QC directory
        if self.qc_dir.exists():
            for file in self.qc_dir.glob("*.md"):
                created_files.add(file.name)
                # Check for QC-01-001 files
                if file.name.startswith("QC-01-001"):
                    if "_A01_" in file.name:
                        self.document_status["QC_01.01_A01_v1"] = "created"
                    elif "_A02_" in file.name:
                        self.document_status["QC_01.01_A02_v1"] = "created"
                    elif "_A03_" in file.name:
                        self.document_status["QC_01.01_A03_v1"] = "created"
                    elif "_A04_" in file.name:
                        self.document_status["QC_01.01_A04_v1"] = "created"
                    elif "_A05_" in file.name:
                        self.document_status["QC_01.01_A05_v1"] = "created"
                    elif "Batch_Release" in file.name and "_A0" not in file.name:
                        self.document_status["QC_01.01_v1"] = "created"

        # Check for specific document patterns
        for file_name in created_files:
            # QA documents
            if file_name.startswith("QA_00"):
                if "Document_Control" in file_name and "_A0" not in file_name:
                    self.document_status["QA_00.02_v1"] = "created"
                elif "_A01_Document_Templates" in file_name:
                    self.document_status["QA_00.02_A01_v1"] = "created"
                elif "_A02_Approval_Matrix" in file_name:
                    self.document_status["QA_00.02_A02_v1"] = "created"
                elif "_A03_Change_Request" in file_name:
                    self.document_status["QA_00.02_A03_v1"] = "created"
                elif "_A04_Obsolete" in file_name:
                    self.document_status["QA_00.02_A04_v1"] = "created"
                elif "Quality_Manual" in file_name:
                    self.document_status["QA_00.01_v1"] = "created"
                elif "Training" in file_name and "03" in file_name:
                    self.document_status["QA_00.03_v1"] = "created"
                elif "Change_Control" in file_name and "_A0" not in file_name:
                    self.document_status["QA_00.05_v1"] = "created"
                elif "_A01_Change_Control_Request" in file_name:
                    self.document_status["QA_00.05_A01_v1"] = "created"
                elif "_A02_Risk_Assessment" in file_name:
                    self.document_status["QA_00.05_A02_v1"] = "created"
                elif "_A03_Impact_Assessment" in file_name:
                    self.document_status["QA_00.05_A03_v1"] = "created"
                elif "CAPA" in file_name and "_A0" not in file_name:
                    self.document_status["QA_00.06_v1"] = "created"
                elif "_A01_CAPA_Initiation" in file_name:
                    self.document_status["QA_00.06_A01_v1"] = "created"
                elif "_A02_CAPA_Action" in file_name:
                    self.document_status["QA_00.06_A02_v1"] = "created"
                elif "_A03_CAPA_Effectiveness" in file_name:
                    self.document_status["QA_00.06_A03_v1"] = "created"
                elif "Deviation" in file_name and "07" in file_name:
                    self.document_status["QA_00.07_v1"] = "created"
                elif "Self" in file_name and "08" in file_name:
                    self.document_status["QA_00.08_v1"] = "created"

            # QCS documents
            elif file_name.startswith("QCS"):
                if "OOS" in file_name or "OOx" in file_name:
                    self.document_status["QC_01.03_v1"] = "created"
                elif "SAM" in file_name or "Sampling" in file_name:
                    self.document_status["QC_01.02_v1"] = "created"
                elif "SPEC" in file_name or "Specifications" in file_name:
                    self.document_status["QC_01.04_v1"] = "created"
                elif "LAB" in file_name and "Organization" in file_name:
                    self.document_status["QC_01.05_v1"] = "created"
                elif "DOC" in file_name and "GDP" in file_name:
                    self.document_status["QC_01.06_v1"] = "created"
                elif "BRR" in file_name:
                    self.document_status["QCS_01.02_v1"] = "created"

            # PRO documents
            elif file_name.startswith("PRO"):
                if "CUR" in file_name or "Curing" in file_name:
                    self.document_status["PRO_01.09_v1"] = "created"
                elif "PHM" in file_name or "Plant_Health" in file_name:
                    self.document_status["PRO_01.10_v1"] = "created"
                elif "XXX" in file_name:
                    self.document_status["PRO_01.11_v1"] = "created"
                elif "TRN" in file_name or "Transportation" in file_name:
                    self.document_status["PRO_06.01_v1"] = "created"
                elif "DRY" in file_name and "FACI" in file_name:
                    self.document_status["PRO_03.03_v1"] = "created"
                elif "Drying" in file_name and "03.02" in file_name:
                    self.document_status["PRO_03.02_v1"] = "created"

            # Other documents
            elif "RES" in file_name and "PHE" in file_name:
                self.document_status["RES_10.01_v1"] = "created"
            elif "EQU" in file_name and "06.01" in file_name:
                self.document_status["EQU_06.01_v1"] = "created"
            elif "HRM" in file_name:
                if "05.01" in file_name:
                    self.document_status["HRM_05.01_v1"] = "created"
                elif "05.05" in file_name or "Hygiene" in file_name:
                    self.document_status["HRM_05.05_v1"] = "created"
            elif "MAT" in file_name and "02.04" in file_name:
                self.document_status["MAT_02.04_v1"] = "created"
            elif "SAN" in file_name and "07.01" in file_name:
                self.document_status["SAN_07.01_v1"] = "created"
            elif "REC" in file_name and "09.01" in file_name:
                self.document_status["REC_09.01_v1"] = "created"

        # Map remaining files to document IDs
        for file_path, doc_id in self.file_map.items():
            if doc_id not in self.document_status:
                file_name = Path(file_path).name
                if file_name in created_files:
                    self.document_status[doc_id] = "created"
                else:
                    self.document_status[doc_id] = "planned"

    def get_document_count_by_status(self) -> Dict[str, int]:
        """Count documents by status"""
        counts = {status: 0 for status in self.STATUS_CONFIG.keys()}

        total_docs = self._count_registry_documents()

        # Count created documents
        created_count = len(
            [s for s in self.document_status.values() if s == "created"]
        )
        counts["created"] = created_count

        # All remaining documents are planned
        counts["planned"] = total_docs - created_count

        # Make sure we don't have negative counts
        if counts["planned"] < 0:
            counts["planned"] = 0

        return counts

    def _count_registry_documents(self) -> int:
        """Count total documents in registry"""
        count = 0
        for family in self.registry.values():
            if isinstance(family, dict):
                sops = family.get("sops", {})
                if isinstance(sops, dict):
                    for sop_key, sop_val in sops.items():
                        if isinstance(sop_val, dict):
                            count += 1
                            annexes = sop_val.get("annexes", {})
                            if isinstance(annexes, dict):
                                count += len(annexes)
        return count

    def get_status_for_document(self, doc_id: str) -> str:
        """Get status for a specific document"""
        return self.document_status.get(doc_id, "planned")

    def generate_plantuml_diagram(self) -> str:
        """Generate PlantUML diagram of document hierarchy"""
        lines = [
            "@startmindmap",
            "title Cannabis EU GMP QMS Document Hierarchy",
            "* QMS Documents",
        ]

        for family_key in sorted(self.registry.keys()):
            if not isinstance(self.registry[family_key], dict):
                continue

            family = self.registry[family_key]
            family_name = family.get("name_en", family_key)

            lines.append(f"** {family_key}: {family_name}")

            sops = family.get("sops", {})
            if isinstance(sops, dict):
                for sop_key in sorted(sops.keys()):
                    sop = sops[sop_key]
                    if not isinstance(sop, dict):
                        continue

                    sop_title = sop.get("title_en", sop_key)
                    status = self.get_status_for_document(sop_key + "_v1")
                    status_symbol = self.STATUS_CONFIG[status]["symbol"]

                    lines.append(f"*** {status_symbol} {sop_key}: {sop_title}")

                    annexes = sop.get("annexes", {})
                    if isinstance(annexes, dict):
                        for annex_key in sorted(annexes.keys()):
                            annex = annexes[annex_key]
                            if isinstance(annex, dict):
                                annex_title = annex.get("title_en", annex_key)
                                annex_status = self.get_status_for_document(
                                    annex_key + "_v1"
                                )
                                annex_symbol = self.STATUS_CONFIG[annex_status][
                                    "symbol"
                                ]
                                lines.append(
                                    f"**** {annex_symbol} {annex_key}: {annex_title}"
                                )

        lines.append("@endmindmap")
        return "\n".join(lines)

    def generate_class_diagram(self) -> str:
        """Generate a class diagram showing document structure"""
        lines = [
            "@startuml QMS_Document_Structure",
            "!theme dark",
            "skinparam linetype ortho",
            "",
            'package "QMS Document Families" {',
        ]

        for family_key in sorted(self.registry.keys()):
            if not isinstance(self.registry[family_key], dict):
                continue

            family = self.registry[family_key]
            family_name = family.get("name_en", family_key)
            doc_count = len(
                [s for s in family.get("sops", {}).values() if isinstance(s, dict)]
            )

            lines.append(f"  class {family_key.replace('-', '_')} {{")
            lines.append(f"    {family_name}")
            lines.append(f"    ---")
            lines.append(f"    Documents: {doc_count}")
            lines.append(f"  }}")

        lines.append("}")
        lines.append("@enduml")
        return "\n".join(lines)

    def generate_detailed_status_diagram(self) -> str:
        """Generate detailed status diagram showing all documents with colors"""
        counts = self.get_document_count_by_status()

        lines = [
            "@startuml QMS_Document_Status_Detailed",
            "!theme dark",
            "",
            "title QMS Document Status Report",
            f"note right: Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        lines.append("legend right")
        for status, config in self.STATUS_CONFIG.items():
            lines.append(
                f"  |<{config['color']}> {config['symbol']} {config['description']} |"
            )
        lines.append("endlegend")
        lines.append("")

        lines.append("card Statistics {")
        lines.append(f"  **Total Documents**: {sum(counts.values())}")
        for status, count in counts.items():
            if count > 0:
                config = self.STATUS_CONFIG[status]
                lines.append(
                    f"  <{config['color']}> {config['symbol']} {config['description']}: {count}"
                )
        lines.append("}")

        lines.append("@enduml")
        return "\n".join(lines)

    def generate_family_status_overview(self) -> str:
        """Generate overview of each family's document status"""
        lines = [
            "@startuml QMS_Family_Status_Overview",
            "!theme dark",
            "skinparam backgroundColor #1a1a1a",
            "skinparam textBackgroundColor #222222",
            "",
            "title QMS Document Families - Status Overview",
            f"note right: Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        for family_key in sorted(self.registry.keys()):
            if not isinstance(self.registry[family_key], dict):
                continue

            family = self.registry[family_key]
            family_name = family.get("name_en", family_key)
            description = family.get("description", "")

            sops = family.get("sops", {})
            created_count = 0
            total_count = 0

            if isinstance(sops, dict):
                for sop_key, sop_val in sops.items():
                    if isinstance(sop_val, dict):
                        total_count += 1
                        status = self.get_status_for_document(sop_key + "_v1")
                        if status == "created":
                            created_count += 1

                        annexes = sop_val.get("annexes", {})
                        if isinstance(annexes, dict):
                            for annex_key in annexes.keys():
                                total_count += 1
                                annex_status = self.get_status_for_document(
                                    annex_key + "_v1"
                                )
                                if annex_status == "created":
                                    created_count += 1

            percentage = (created_count / total_count * 100) if total_count > 0 else 0

            lines.append(f"card {family_key} {{")
            lines.append(f"  **{family_name}**")
            lines.append(f"  ---")
            lines.append(f"  {description}")
            lines.append(f"  ---")
            lines.append(
                f"  Progress: {created_count}/{total_count} ({percentage:.0f}%)"
            )
            lines.append("}")
            lines.append("")

        lines.append("@enduml")
        return "\n".join(lines)

    def generate_summary_report(self) -> str:
        """Generate a text summary report"""
        counts = self.get_document_count_by_status()
        total = sum(counts.values())

        report = []
        report.append("=" * 70)
        report.append("QMS DOCUMENT HIERARCHY SUMMARY REPORT")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        report.append("OVERALL STATUS:")
        report.append("-" * 70)
        for status in ["created", "draft", "in_progress", "planned", "missing"]:
            count = counts.get(status, 0)
            config = self.STATUS_CONFIG[status]
            percentage = (count / total * 100) if total > 0 else 0
            report.append(
                f"  {config['symbol']} {config['description']:<25} {count:>3} ({percentage:>5.1f}%)"
            )

        report.append("-" * 70)
        report.append(f"  TOTAL DOCUMENTS: {total}")
        report.append("")

        report.append("DOCUMENT FAMILIES BREAKDOWN:")
        report.append("-" * 70)

        for family_key in sorted(self.registry.keys()):
            if not isinstance(self.registry[family_key], dict):
                continue

            family = self.registry[family_key]
            family_name = family.get("name_en", family_key)

            sops = family.get("sops", {})
            created_count = 0
            total_count = 0

            if isinstance(sops, dict):
                for sop_key, sop_val in sops.items():
                    if isinstance(sop_val, dict):
                        total_count += 1
                        status = self.get_status_for_document(sop_key + "_v1")
                        if status == "created":
                            created_count += 1

                        annexes = sop_val.get("annexes", {})
                        if isinstance(annexes, dict):
                            for annex_key in annexes.keys():
                                total_count += 1
                                annex_status = self.get_status_for_document(
                                    annex_key + "_v1"
                                )
                                if annex_status == "created":
                                    created_count += 1

            percentage = (created_count / total_count * 100) if total_count > 0 else 0
            report.append(f"  {family_key}: {family_name}")
            report.append(
                f"    Progress: {created_count}/{total_count} ({percentage:.0f}%)"
            )

        report.append("=" * 70)
        return "\n".join(report)

    def save_diagrams(self):
        """Save all diagrams to files"""
        diagrams = {
            "qms_hierarchy.puml": self.generate_plantuml_diagram(),
            "qms_family_status.puml": self.generate_family_status_overview(),
            "qms_document_status.puml": self.generate_detailed_status_diagram(),
            "qms_structure.puml": self.generate_class_diagram(),
        }

        for filename, content in diagrams.items():
            filepath = self.output_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✓ Saved: {filepath}")

        # Save summary report
        report_path = self.output_dir / "qms_status_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.generate_summary_report())
        print(f"✓ Saved: {report_path}")

        # Save metadata as JSON
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "document_counts": self.get_document_count_by_status(),
            "total_documents": sum(self.get_document_count_by_status().values()),
            "families": len(
                [f for f in self.registry.keys() if isinstance(self.registry[f], dict)]
            ),
        }

        metadata_path = self.output_dir / "qms_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        print(f"✓ Saved: {metadata_path}")


def main():
    """Main entry point"""
    project_root = Path(__file__).parent.parent

    print("=" * 70)
    print("QMS DOCUMENT HIERARCHY VISUALIZER")
    print("=" * 70)
    print()

    visualizer = QMSHierarchyVisualizer(str(project_root))

    print("Loading registry...")
    visualizer.load_registry()
    print(f"✓ Loaded {len(visualizer.registry)} document families")

    print("\nScanning filesystem...")
    visualizer.scan_documents()
    print(
        f"✓ Scanned documents - found {len(visualizer.document_status)} mapped documents"
    )

    print("\nGenerating diagrams...")
    visualizer.save_diagrams()

    print("\n" + visualizer.generate_summary_report())
    print()
    print(f"All diagrams saved to: {visualizer.output_dir}")
    print()
    print("To view the diagrams:")
    print("1. Open the .puml files in PlantUML Online (plant-uml.org)")
    print("2. Or use VSCode with PlantUML extension")
    print("3. Or convert with: plantuml filename.puml -o output_format png")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cross-Reference Validator for Cannabis EU GMP QMS Creator
Validates all document references, SOPs, forms, and equipment IDs across the QMS
"""

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

from document_id_generator import DocumentIDError, DocumentIDGenerator
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

console = Console()


class CrossReferenceValidator:
    """Validate cross-references across QMS documents."""

    def __init__(self, docs_dir: Path, registry_path: Path = None):
        """
        Initialize cross-reference validator.

        Args:
            docs_dir: Directory containing generated documents
            registry_path: Path to QMS document registry (optional)
        """
        self.docs_dir = docs_dir
        self.registry_path = registry_path

        # Patterns for different reference types
        self.id_gen = DocumentIDGenerator()
        self.patterns = {
            "sop": re.compile(
                r"([A-Z]{2,5}_\d{2}\.\d{2}(?:_A\d{2})?(?:_v\d+)?)"
            ),  # QC_02.01_A01_v1 or QC_02.01_A01
            "legacy_sop": re.compile(r"([A-Z]{3,4}-\d{2}-\d{3})"),  # QAS-01-001
            "form": re.compile(r"(FM-[A-Z]{3,4}-\d{3})"),  # FM-QAS-001
            "equipment": re.compile(r"(EQU-[A-Z]+-\d{3})"),  # EQU-DRYING-001
            "room": re.compile(r"(ROOM-\d{2})"),  # ROOM-01
            "section": re.compile(r"Section\s+(\d+\.?\d*)"),  # Section 4.2
        }

        # Storage for discovered references
        self.document_ids: Set[str] = set()
        self.form_ids: Set[str] = set()
        self.equipment_ids: Set[str] = set()
        self.room_ids: Set[str] = set()

        # Reference maps: doc -> [references it makes]
        self.sop_references: Dict[str, List[str]] = defaultdict(list)
        self.form_references: Dict[str, List[str]] = defaultdict(list)
        self.equipment_references: Dict[str, List[str]] = defaultdict(list)
        self.room_references: Dict[str, List[str]] = defaultdict(list)

        # Inverse maps: referenced -> [docs that reference it]
        self.referenced_by: Dict[str, List[str]] = defaultdict(list)

    def scan_all_documents(self) -> Dict:
        """Scan all documents and build reference database."""
        console.print(
            "\n[bold cyan]Scanning Documents for Cross-References[/bold cyan]"
        )
        console.print("=" * 80 + "\n")

        # Define relevant directories to scan
        relevant_dirs = ["01_QUALITY_ASSURANCE", "04_QUALITY_TESTING", "sops_created"]
        documents = []

        console.print(f"[debug] docs_dir: {self.docs_dir}")

        for rel_dir in relevant_dirs:
            target_dir = self.docs_dir / rel_dir
            console.print(
                f"[debug] Checking: {target_dir} (exists: {target_dir.exists()})"
            )
            if target_dir.exists():
                # Find all .md and .txt files, excluding backups
                for ext in ["*.md", "*.txt"]:
                    files = list(target_dir.rglob(ext))
                    console.print(
                        f"[debug] Found {len(files)} {ext} files in {rel_dir}"
                    )
                    for doc_path in files:
                        if (
                            ".backup." not in doc_path.name.lower()
                            and "backup" not in doc_path.name.lower()
                        ):
                            documents.append(doc_path)

        # Fallback if specific directories don't exist or are empty
        if not documents:
            all_docs = list(self.docs_dir.rglob("*.md")) + list(
                self.docs_dir.rglob("*.txt")
            )
            documents = [
                d
                for d in all_docs
                if "venv" not in str(d) and ".backup." not in d.name.lower()
            ]
        console.print(f"[cyan]Found {len(documents)} documents to scan[/cyan]\n")

        for doc_path in documents:
            self._scan_document(doc_path)

        # Build summary
        summary = {
            "total_documents": len(documents),
            "unique_sop_ids": len(self.document_ids),
            "unique_form_ids": len(self.form_ids),
            "unique_equipment_ids": len(self.equipment_ids),
            "unique_room_ids": len(self.room_ids),
            "total_sop_references": sum(
                len(refs) for refs in self.sop_references.values()
            ),
            "total_form_references": sum(
                len(refs) for refs in self.form_references.values()
            ),
            "documents_scanned": documents,
        }

        console.print("[bold green]✓ Scan complete![/bold green]\n")
        return summary

    def _scan_document(self, doc_path: Path):
        """Scan a single document for references."""
        try:
            with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Extract document ID from filename
            filename = doc_path.stem
            # Try hierarchical first, then legacy
            doc_id_match = self.patterns["sop"].search(filename)
            if not doc_id_match:
                doc_id_match = self.patterns["legacy_sop"].search(filename)

            doc_id = doc_id_match.group(1) if doc_id_match else filename

            # Normalize doc_id: if it's hierarchical and missing version, append _v1
            if doc_id_match and "_" in doc_id and "." in doc_id and "_v" not in doc_id:
                doc_id = f"{doc_id}_v1"

            # Store this document ID
            if doc_id_match:
                self.document_ids.add(doc_id)

            # Find all SOP references (Hierarchical)
            sop_refs = self.patterns["sop"].findall(content)
            for ref in sop_refs:
                # Normalize reference: append _v1 if missing
                if "_" in ref and "." in ref and "_v" not in ref:
                    ref = f"{ref}_v1"

                if ref != doc_id:  # Don't count self-references
                    self.sop_references[doc_id].append(ref)
                    self.referenced_by[ref].append(doc_id)

            # Find all legacy SOP references
            legacy_refs = self.patterns["legacy_sop"].findall(content)
            for ref in legacy_refs:
                if ref != doc_id:
                    self.sop_references[doc_id].append(ref)
                    self.referenced_by[ref].append(doc_id)

            # Find all form references
            form_refs = self.patterns["form"].findall(content)
            for ref in form_refs:
                self.form_ids.add(ref)
                self.form_references[doc_id].append(ref)

            # Find all equipment references
            eq_refs = self.patterns["equipment"].findall(content)
            for ref in eq_refs:
                self.equipment_ids.add(ref)
                self.equipment_references[doc_id].append(ref)

            # Find all room references
            room_refs = self.patterns["room"].findall(content)
            for ref in room_refs:
                self.room_ids.add(ref)
                self.room_references[doc_id].append(ref)

        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not scan {doc_path.name}: {e}[/yellow]"
            )

    def validate_references(self) -> Dict:
        """Validate all cross-references."""
        console.print("[bold cyan]Validating Cross-References[/bold cyan]")
        console.print("=" * 80 + "\n")

        validation_results = {
            "broken_sop_references": [],
            "broken_form_references": [],
            "broken_equipment_references": [],
            "broken_room_references": [],
            "orphaned_documents": [],
            "circular_references": [],
            "hierarchical_errors": [],
        }

        # Check SOP references
        console.print("[cyan]Checking SOP references...[/cyan]")
        for doc_id, refs in self.sop_references.items():
            for ref in refs:
                if ref not in self.document_ids:
                    validation_results["broken_sop_references"].append(
                        {"source": doc_id, "target": ref, "type": "SOP not found"}
                    )

        if validation_results["broken_sop_references"]:
            console.print(
                f"  [yellow]⚠ Found {len(validation_results['broken_sop_references'])} broken SOP references[/yellow]"
            )
        else:
            console.print("  [green]✓ All SOP references valid[/green]")

        # Hierarchical Validation (Parent-Child relationships)
        console.print("[cyan]Checking hierarchical integrity...[/cyan]")
        for doc_id in self.document_ids:
            if self.id_gen.is_valid(doc_id):
                try:
                    parsed = self.id_gen.parse(doc_id)
                    if parsed.annex is not None:
                        # This is an annex, check if parent SOP exists
                        parent_id = f"{parsed.department}_{parsed.family:02d}.{parsed.sop:02d}_v{parsed.version}"
                        if parent_id not in self.document_ids:
                            validation_results["hierarchical_errors"].append(
                                {
                                    "document": doc_id,
                                    "error": f"Parent SOP {parent_id} missing",
                                    "type": "Missing Parent",
                                }
                            )
                except DocumentIDError:
                    continue

        if validation_results["hierarchical_errors"]:
            console.print(
                f"  [yellow]⚠ Found {len(validation_results['hierarchical_errors'])} hierarchical integrity issues[/yellow]"
            )
        else:
            console.print("  [green]✓ Hierarchical integrity verified[/green]")

        # Check for orphaned documents (not referenced by anyone)
        console.print("[cyan]Checking for orphaned documents...[/cyan]")
        for doc_id in self.document_ids:
            if doc_id not in self.referenced_by or len(self.referenced_by[doc_id]) == 0:
                # Exclude master documents which aren't typically referenced
                if not doc_id.startswith("QAS-01-"):
                    validation_results["orphaned_documents"].append(doc_id)

        if validation_results["orphaned_documents"]:
            console.print(
                f"  [yellow]⚠ Found {len(validation_results['orphaned_documents'])} orphaned documents[/yellow]"
            )
        else:
            console.print("  [green]✓ No orphaned documents[/green]")

        # Check for circular references
        console.print("[cyan]Checking for circular references...[/cyan]")
        circular = self._find_circular_references()
        validation_results["circular_references"] = circular

        if circular:
            console.print(
                f"  [yellow]⚠ Found {len(circular)} circular reference chains[/yellow]"
            )
        else:
            console.print("  [green]✓ No circular references[/green]")

        console.print()
        return validation_results

    def _find_circular_references(self) -> List[List[str]]:
        """Find circular reference chains."""
        circular = []
        visited = set()

        def dfs(doc_id: str, path: List[str]) -> None:
            if doc_id in path:
                # Found a cycle
                cycle_start = path.index(doc_id)
                cycle = path[cycle_start:] + [doc_id]
                if cycle not in circular:
                    circular.append(cycle)
                return

            if doc_id in visited:
                return

            visited.add(doc_id)
            refs = self.sop_references.get(doc_id, [])

            for ref in refs:
                dfs(ref, path + [doc_id])

        for doc_id in self.document_ids:
            dfs(doc_id, [])

        return circular

    def generate_dependency_tree(self, root_doc: str = None) -> Tree:
        """Generate a visual dependency tree."""
        if not root_doc:
            # Use first master document as root
            master_docs = [d for d in self.document_ids if d.startswith("QAS-01-")]
            root_doc = master_docs[0] if master_docs else list(self.document_ids)[0]

        tree = Tree(f"[bold cyan]{root_doc}[/bold cyan] (Root Document)")
        self._build_tree_recursive(tree, root_doc, visited=set())
        return tree

    def _build_tree_recursive(
        self, tree: Tree, doc_id: str, visited: Set[str], depth: int = 0
    ):
        """Recursively build dependency tree."""
        if depth > 3 or doc_id in visited:  # Limit depth to prevent huge trees
            return

        visited.add(doc_id)
        refs = self.sop_references.get(doc_id, [])

        for ref in refs[:5]:  # Limit to 5 children per node
            exists = ref in self.document_ids
            color = "green" if exists else "red"
            branch = tree.add(f"[{color}]{ref}[/{color}]")

            if exists:
                self._build_tree_recursive(branch, ref, visited, depth + 1)

    def generate_html_report(self, output_path: Path, validation_results: Dict):
        """Generate HTML cross-reference validation report."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Cross-Reference Validation Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat-box {{
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-box.good {{
            background: #d4edda;
            border: 2px solid #28a745;
        }}
        .stat-box.warning {{
            background: #fff3cd;
            border: 2px solid #ffc107;
        }}
        .stat-box.error {{
            background: #f8d7da;
            border: 2px solid #dc3545;
        }}
        .stat-number {{
            font-size: 48px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 14px;
            text-transform: uppercase;
            color: #666;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .good {{ color: #28a745; }}
        .warning {{ color: #ffc107; }}
        .error {{ color: #dc3545; }}
        .reference-list {{
            list-style: none;
            padding: 0;
        }}
        .reference-list li {{
            padding: 5px 10px;
            margin: 5px 0;
            background: #f8f9fa;
            border-left: 4px solid #3498db;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 Cross-Reference Validation Report</h1>
        <p><strong>Generated:</strong> {self._get_timestamp()}</p>
        <p><strong>Cannabis EU GMP QMS Creator</strong> - Purely Plant GmbH</p>

        <div class="summary">
            <div class="stat-box good">
                <div class="stat-label">Total Documents</div>
                <div class="stat-number">{len(self.document_ids)}</div>
            </div>
            <div class="stat-box {"good" if len(validation_results["broken_sop_references"]) == 0 else "error"}">
                <div class="stat-label">Broken SOP References</div>
                <div class="stat-number">{len(validation_results["broken_sop_references"])}</div>
            </div>
            <div class="stat-box {"good" if len(validation_results["orphaned_documents"]) == 0 else "warning"}">
                <div class="stat-label">Orphaned Documents</div>
                <div class="stat-number">{len(validation_results["orphaned_documents"])}</div>
            </div>
            <div class="stat-box {"good" if len(validation_results["circular_references"]) == 0 else "warning"}">
                <div class="stat-label">Circular References</div>
                <div class="stat-number">{len(validation_results["circular_references"])}</div>
            </div>
        </div>

        <h2>📊 Reference Statistics</h2>
        <table>
            <tr>
                <th>Reference Type</th>
                <th>Unique IDs Found</th>
                <th>Total References</th>
            </tr>
            <tr>
                <td>SOP Documents</td>
                <td>{len(self.document_ids)}</td>
                <td>{sum(len(refs) for refs in self.sop_references.values())}</td>
            </tr>
            <tr>
                <td>Forms</td>
                <td>{len(self.form_ids)}</td>
                <td>{sum(len(refs) for refs in self.form_references.values())}</td>
            </tr>
            <tr>
                <td>Equipment</td>
                <td>{len(self.equipment_ids)}</td>
                <td>{sum(len(refs) for refs in self.equipment_references.values())}</td>
            </tr>
            <tr>
                <td>Rooms</td>
                <td>{len(self.room_ids)}</td>
                <td>{sum(len(refs) for refs in self.room_references.values())}</td>
            </tr>
        </table>
"""

        # Broken references section
        if validation_results["broken_sop_references"]:
            html += """
        <h2 class="error">⚠️ Broken SOP References</h2>
        <table>
            <tr>
                <th>Source Document</th>
                <th>Missing Reference</th>
                <th>Issue</th>
            </tr>
"""
            for ref in validation_results["broken_sop_references"][:20]:
                html += f"""
            <tr>
                <td>{ref["source"]}</td>
                <td class="error">{ref["target"]}</td>
                <td>{ref["type"]}</td>
            </tr>
"""
            html += "        </table>\n"

        # Orphaned documents section
        if validation_results["orphaned_documents"]:
            html += """
        <h2 class="warning">📄 Orphaned Documents (Not Referenced)</h2>
        <ul class="reference-list">
"""
            for doc in validation_results["orphaned_documents"][:20]:
                html += f"            <li>{doc}</li>\n"
            html += "        </ul>\n"

        # Most referenced documents
        html += """
        <h2>🔝 Most Referenced Documents</h2>
        <table>
            <tr>
                <th>Document ID</th>
                <th>Referenced By</th>
            </tr>
"""
        sorted_refs = sorted(
            self.referenced_by.items(), key=lambda x: len(x[1]), reverse=True
        )
        for doc_id, refs in sorted_refs[:10]:
            html += f"""
            <tr>
                <td><strong>{doc_id}</strong></td>
                <td>{len(refs)} documents</td>
            </tr>
"""
        html += "        </table>\n"

        html += """
        <div class="footer">
            <p>Cannabis EU GMP QMS Creator - Automation System v1.0</p>
            <p>Purely Plant GmbH - Skopje, North Macedonia</p>
        </div>
    </div>
</body>
</html>
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        console.print(
            f"\n[bold green]✓[/bold green] Report saved to: [cyan]{output_path}[/cyan]"
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def print_summary(self, validation_results: Dict):
        """Print validation summary."""
        console.print("\n" + "=" * 80)
        console.print("[bold cyan]Cross-Reference Validation Summary[/bold cyan]")
        console.print("=" * 80 + "\n")

        # Statistics table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Total SOP Documents", str(len(self.document_ids)))
        table.add_row("Total Forms Referenced", str(len(self.form_ids)))
        table.add_row("Total Equipment Referenced", str(len(self.equipment_ids)))
        table.add_row("Total Rooms Referenced", str(len(self.room_ids)))
        table.add_row(
            "Broken SOP References",
            str(len(validation_results["broken_sop_references"])),
        )
        table.add_row(
            "Orphaned Documents", str(len(validation_results["orphaned_documents"]))
        )
        table.add_row(
            "Circular Reference Chains",
            str(len(validation_results["circular_references"])),
        )

        console.print(table)
        console.print()

        # Print broken references details
        if validation_results["broken_sop_references"]:
            console.print("[bold red]Broken SOP References Details:[/bold red]")
            for ref in validation_results["broken_sop_references"][:20]:
                source = (
                    ref.get("source")
                    if isinstance(ref, dict)
                    else ref[0]
                    if isinstance(ref, tuple)
                    else "Unknown"
                )
                target = (
                    ref.get("target")
                    if isinstance(ref, dict)
                    else ref[1]
                    if isinstance(ref, tuple)
                    else str(ref)
                )
                console.print(
                    f"  • [yellow]{source}[/yellow] references non-existent [red]{target}[/red]"
                )

            if len(validation_results["broken_sop_references"]) > 20:
                console.print(
                    f"  ... and {len(validation_results['broken_sop_references']) - 20} more"
                )
            console.print()

        if validation_results["orphaned_documents"]:
            console.print(
                "[bold yellow]Orphaned Documents (Not referenced by any other SOP):[/bold yellow]"
            )
            for doc in sorted(list(validation_results["orphaned_documents"]))[:10]:
                console.print(f"  • {doc}")
            if len(validation_results["orphaned_documents"]) > 10:
                console.print(
                    f"  ... and {len(validation_results['orphaned_documents']) - 10} more"
                )
            console.print()


def main():
    """Main validation function."""
    console.print("\n[bold cyan]QMS Cross-Reference Validator[/bold cyan]")
    console.print("=" * 80 + "\n")

    # Get project root directory
    base_dir = Path(__file__).parent.parent

    # Try customized output first, then fallback to source dirs
    docs_dir = base_dir / "output" / "customized"
    if not docs_dir.exists():
        console.print(
            "[yellow]⚠ Output directory 'output/customized' not found. Scanning source directories instead.[/yellow]"
        )
        docs_dir = base_dir
    else:
        console.print(
            "[green]✓ Scanning customized documents in 'output/customized'[/green]"
        )

    # Create validator
    validator = CrossReferenceValidator(docs_dir)

    # Scan documents
    summary = validator.scan_all_documents()

    # Validate references
    validation_results = validator.validate_references()

    # Print summary
    validator.print_summary(validation_results)

    # Generate HTML report
    (base_dir / "output").mkdir(exist_ok=True)
    report_path = base_dir / "output" / "cross_reference_report.html"
    validator.generate_html_report(report_path, validation_results)

    console.print("[bold green]✓ Cross-reference validation complete![/bold green]\n")


if __name__ == "__main__":
    main()

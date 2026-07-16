#!/usr/bin/env python3
"""
Test Pipeline for SOP Document Generation
=========================================

Tests the complete document generation pipeline:
1. PDF generation from existing SOP markdown files
2. .docx approval page template generation
3. Integration testing of document formats

Usage:
    python3 test_pipeline.py --sop QA_00.06 --output test_output/
    python3 test_pipeline.py --all --output test_output/
"""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

    class Console:
        def print(self, *args, **kwargs):
            print(*args, **kwargs)

    console = Console()


class SOPTestPipeline:
    """Test pipeline for SOP document generation."""

    def __init__(self, base_dir: Path, output_dir: Path):
        self.base_dir = base_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Define test SOPs with their file paths
        self.test_sops = {
            "QA_00.02": {
                "name": "Document Control",
                "file": base_dir
                / "sops_created"
                / "QA_00.02_Document_Control_v1.0_EN.md",
                "dept": "QA",
                "sop_num": "002",
            },
            "QA_00.06": {
                "name": "CAPA System",
                "file": base_dir
                / "01_QUALITY_ASSURANCE"
                / "QA_00.06_CAPA_System_SOP_v1.0_EN.md",
                "dept": "QA",
                "sop_num": "006",
            },
            "QC_01.01": {
                "name": "Batch Release",
                "file": base_dir
                / "04_QUALITY_TESTING"
                / "QC_01.01_Batch_Release_v1.0_EN.md",
                "dept": "QC",
                "sop_num": "001",
            },
        }

        # Check which SOPs actually exist
        self.available_sops = {}
        for sop_id, sop_info in self.test_sops.items():
            if sop_info["file"].exists():
                self.available_sops[sop_id] = sop_info
            else:
                console.print(
                    f"[yellow]⚠  SOP not found: {sop_id} ({sop_info['file']})[/yellow]"
                )

    def print_header(self, title: str):
        """Print formatted header."""
        if RICH_AVAILABLE:
            console.print(
                Panel.fit(f"[bold cyan]{title}[/bold cyan]", border_style="cyan")
            )
        else:
            console.print(f"\n{'=' * 80}")
            console.print(f"{title}")
            console.print(f"{'=' * 80}\n")

    def print_success(self, message: str):
        """Print success message."""
        if RICH_AVAILABLE:
            console.print(f"[green]✓ {message}[/green]")
        else:
            console.print(f"✓ {message}")

    def print_error(self, message: str):
        """Print error message."""
        if RICH_AVAILABLE:
            console.print(f"[red]✗ {message}[/red]")
        else:
            console.print(f"✗ {message}")

    def print_info(self, message: str):
        """Print info message."""
        if RICH_AVAILABLE:
            console.print(f"[blue]→ {message}[/blue]")
        else:
            console.print(f"→ {message}")

    def generate_pdf(self, sop_file: Path, sop_id: str) -> bool:
        """Generate PDF from SOP markdown file."""
        try:
            output_pdf = self.output_dir / f"{sop_id}.pdf"

            # Run the PDF generator script
            cmd = [
                sys.executable,
                str(self.base_dir / "scripts" / "pdf_generator.py"),
                "--file",
                str(sop_file),
                "--output",
                str(self.output_dir),
            ]

            console.print(f"\nGenerating PDF for {sop_id}...")
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.base_dir
            )

            if result.returncode == 0:
                if output_pdf.exists():
                    size_kb = output_pdf.stat().st_size / 1024
                    self.print_success(
                        f"PDF generated: {output_pdf.name} ({size_kb:.1f} KB)"
                    )
                    return True
                else:
                    # Check if PDF was created with different name
                    alt_pdf = self.output_dir / f"{sop_file.stem}.pdf"
                    if alt_pdf.exists():
                        size_kb = alt_pdf.stat().st_size / 1024
                        self.print_success(
                            f"PDF generated: {alt_pdf.name} ({size_kb:.1f} KB)"
                        )
                        return True
                    else:
                        self.print_error("PDF file not created")
                        if result.stderr:
                            console.print(f"Stderr: {result.stderr[:500]}")
                        return False
            else:
                self.print_error(
                    f"PDF generation failed (exit code: {result.returncode})"
                )
                if result.stderr:
                    console.print(f"Stderr: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.print_error(f"Error generating PDF: {str(e)}")
            return False

    def generate_docx(self, sop_info: dict, sop_id: str) -> bool:
        """Generate .docx approval page template."""
        try:
            output_docx = self.output_dir / f"{sop_id}_approval_page.docx"

            # Run the DOCX generator script
            cmd = [
                sys.executable,
                str(self.base_dir / "scripts" / "purely_plant_docx_generator.py"),
                "--output",
                str(output_docx),
                "--dept",
                sop_info["dept"],
                "--sop-num",
                sop_info["sop_num"],
            ]

            console.print(f"\nGenerating .docx approval page for {sop_id}...")
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.base_dir
            )

            if result.returncode == 0:
                if output_docx.exists():
                    size_kb = output_docx.stat().st_size / 1024
                    self.print_success(
                        f".docx generated: {output_docx.name} ({size_kb:.1f} KB)"
                    )
                    return True
                else:
                    self.print_error(".docx file not created")
                    return False
            else:
                self.print_error(
                    f".docx generation failed (exit code: {result.returncode})"
                )
                if result.stderr:
                    console.print(f"Stderr: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.print_error(f"Error generating .docx: {str(e)}")
            return False

    def analyze_sop_content(self, sop_file: Path, sop_id: str) -> dict:
        """Analyze SOP content for basic validation."""
        try:
            with open(sop_file, "r", encoding="utf-8") as f:
                content = f.read()

            unresolved_placeholders = sorted(
                set(re.findall(r"\[([A-Z][A-Z0-9_\-\s]*?)\]", content))
            )

            analysis = {
                "file_size_kb": sop_file.stat().st_size / 1024,
                "line_count": len(content.splitlines()),
                "has_approval_table": "ОДОБРУВАЊЕ НА ДОКУМЕНТ" in content
                or "DOCUMENT APPROVAL" in content,
                "has_purpose_section": "1. PURPOSE" in content or "1. ЦЕЛ" in content,
                "has_procedure_section": "5. PROCEDURE" in content
                or "5. ПРОЦЕДУРА" in content,
                "has_references": "REFERENCES" in content or "РЕФЕРЕНЦИ" in content,
                "has_front_matter": content.strip().startswith("---"),
                "unresolved_placeholders": unresolved_placeholders,
                "unresolved_placeholders_count": len(unresolved_placeholders),
                "content_preview": content[:200].replace("\n", " ") + "...",
            }

            return analysis

        except Exception as e:
            self.print_error(f"Error analyzing SOP content: {str(e)}")
            return {}

    def test_single_sop(self, sop_id: str) -> dict:
        """Test a single SOP through the pipeline."""
        if sop_id not in self.available_sops:
            self.print_error(f"SOP {sop_id} not found or not available")
            return {"success": False, "error": "SOP not found"}

        sop_info = self.available_sops[sop_id]
        sop_file = sop_info["file"]

        self.print_header(f"Testing SOP: {sop_id} - {sop_info['name']}")
        self.print_info(f"Source file: {sop_file.relative_to(self.base_dir)}")

        # Analyze SOP content
        analysis = self.analyze_sop_content(sop_file, sop_id)
        if analysis:
            self.print_info(
                f"File size: {analysis['file_size_kb']:.1f} KB, Lines: {analysis['line_count']}"
            )
            if analysis["has_approval_table"]:
                self.print_success("Contains approval table")
            else:
                self.print_error("Missing approval table")

            if analysis["unresolved_placeholders_count"] == 0:
                self.print_success("No unresolved placeholders")
            else:
                self.print_error(
                    f"Unresolved placeholders: {analysis['unresolved_placeholders_count']}"
                )

        results = {
            "sop_id": sop_id,
            "sop_name": sop_info["name"],
            "source_file": str(sop_file),
            "pdf_generated": False,
            "docx_generated": False,
            "placeholders_ok": analysis.get("unresolved_placeholders_count", 0) == 0,
            "analysis": analysis,
        }

        # Generate PDF
        pdf_success = self.generate_pdf(sop_file, sop_id)
        results["pdf_generated"] = pdf_success

        # Generate .docx
        docx_success = self.generate_docx(sop_info, sop_id)
        results["docx_generated"] = docx_success

        # Overall success
        results["success"] = (pdf_success or docx_success) and results[
            "placeholders_ok"
        ]

        return results

    def test_all_sops(self) -> list:
        """Test all available SOPs."""
        results = []

        for sop_id in self.available_sops.keys():
            result = self.test_single_sop(sop_id)
            results.append(result)
            console.print("\n")  # Add spacing between tests

        return results

    def generate_summary_report(self, results: list):
        """Generate summary report of all tests."""
        self.print_header("TEST PIPELINE SUMMARY REPORT")

        if RICH_AVAILABLE:
            table = Table(title="SOP Generation Results")
            table.add_column("SOP ID", style="cyan")
            table.add_column("Name", style="magenta")
            table.add_column("PDF", justify="center")
            table.add_column(".docx", justify="center")
            table.add_column("Placeholders", justify="center")
            table.add_column("Status", justify="center")

            for result in results:
                sop_id = result["sop_id"]
                name = result["sop_name"]
                pdf_status = "✓" if result["pdf_generated"] else "✗"
                docx_status = "✓" if result["docx_generated"] else "✗"
                placeholders_status = "✓" if result["placeholders_ok"] else "✗"
                status = "✓" if result["success"] else "✗"

                pdf_style = "green" if result["pdf_generated"] else "red"
                docx_style = "green" if result["docx_generated"] else "red"
                placeholders_style = "green" if result["placeholders_ok"] else "red"
                status_style = "green" if result["success"] else "red"

                table.add_row(
                    sop_id,
                    name,
                    f"[{pdf_style}]{pdf_status}[/{pdf_style}]",
                    f"[{docx_style}]{docx_status}[/{docx_style}]",
                    f"[{placeholders_style}]{placeholders_status}[/{placeholders_style}]",
                    f"[{status_style}]{status}[/{status_style}]",
                )

            console.print(table)
        else:
            console.print("\nSOP Generation Results:")
            console.print("-" * 80)
            console.print(
                f"{'SOP ID':<10} {'Name':<25} {'PDF':<6} {'.docx':<6} {'PH':<6} {'Status':<6}"
            )
            console.print("-" * 80)

            for result in results:
                sop_id = result["sop_id"]
                name = (
                    result["sop_name"][:22] + "..."
                    if len(result["sop_name"]) > 22
                    else result["sop_name"]
                )
                pdf_status = "✓" if result["pdf_generated"] else "✗"
                docx_status = "✓" if result["docx_generated"] else "✗"
                placeholders_status = "✓" if result["placeholders_ok"] else "✗"
                status = "✓" if result["success"] else "✗"

                console.print(
                    f"{sop_id:<10} {name:<25} {pdf_status:<6} {docx_status:<6} {placeholders_status:<6} {status:<6}"
                )

        # Count statistics
        total = len(results)
        pdf_success = sum(1 for r in results if r["pdf_generated"])
        docx_success = sum(1 for r in results if r["docx_generated"])
        all_success = sum(1 for r in results if r["success"])

        console.print(f"\nStatistics:")
        console.print(f"  Total SOPs tested: {total}")
        console.print(f"  PDFs generated successfully: {pdf_success}/{total}")
        console.print(f"  .docx templates generated: {docx_success}/{total}")
        console.print(f"  Overall success rate: {all_success}/{total}")

        # Output directory info
        console.print(f"\nOutput directory: {self.output_dir.absolute()}")
        console.print("Generated files:")
        for file in self.output_dir.iterdir():
            if file.is_file():
                size_kb = file.stat().st_size / 1024
                console.print(f"  • {file.name} ({size_kb:.1f} KB)")

        # Recommendations
        console.print(f"\nRecommendations:")
        if pdf_success < total:
            console.print(
                "  • Check PDF generator script for errors with specific SOP formats"
            )
        if docx_success < total:
            console.print(
                "  • Verify .docx generator script dependencies (python-docx)"
            )

        # Save results to file
        report_file = self.output_dir / "test_report.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"SOP Generation Test Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Output directory: {self.output_dir}\n")
            f.write(f"\nResults:\n")
            f.write("-" * 80 + "\n")
            for result in results:
                f.write(f"SOP: {result['sop_id']} - {result['sop_name']}\n")
                f.write(f"  Source: {result['source_file']}\n")
                f.write(f"  PDF generated: {result['pdf_generated']}\n")
                f.write(f"  .docx generated: {result['docx_generated']}\n")
                f.write(f"  Success: {result['success']}\n")
                if result.get("analysis"):
                    f.write(
                        f"  File size: {result['analysis']['file_size_kb']:.1f} KB\n"
                    )
                    f.write(f"  Lines: {result['analysis']['line_count']}\n")
                f.write("\n")

        self.print_success(f"Detailed report saved to: {report_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Test SOP document generation pipeline"
    )
    parser.add_argument(
        "--sop", type=str, help="Test specific SOP (e.g., QA_00.06, QC_01.01)"
    )
    parser.add_argument("--all", action="store_true", help="Test all available SOPs")
    parser.add_argument(
        "--output",
        type=str,
        default="test_output",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available SOPs and exit"
    )

    args = parser.parse_args()

    # Get base directory
    base_dir = Path(__file__).parent
    output_dir = Path(args.output)

    # Create test pipeline
    pipeline = SOPTestPipeline(base_dir, output_dir)

    if args.list:
        console.print(f"\nAvailable SOPs for testing:")
        console.print("-" * 80)
        for sop_id, sop_info in pipeline.available_sops.items():
            console.print(
                f"{sop_id:<10} {sop_info['name']:<30} ({sop_info['file'].relative_to(base_dir)})"
            )
        console.print(f"\nTotal available: {len(pipeline.available_sops)}")
        return

    if not args.sop and not args.all:
        console.print(
            "[yellow]Please specify --sop <id> or --all to run tests[/yellow]"
        )
        console.print("Use --list to see available SOPs")
        return

    # Run tests
    if args.sop:
        if args.sop not in pipeline.available_sops:
            console.print(f"[red]Error: SOP '{args.sop}' not found[/red]")
            console.print(
                f"Available SOPs: {', '.join(pipeline.available_sops.keys())}"
            )
            sys.exit(1)

        result = pipeline.test_single_sop(args.sop)
        pipeline.generate_summary_report([result])

    elif args.all:
        if not pipeline.available_sops:
            console.print("[red]No SOPs found for testing[/red]")
            sys.exit(1)

        results = pipeline.test_all_sops()
        pipeline.generate_summary_report(results)

    console.print(f"\n[bold green]Test pipeline completed![/bold green]")


if __name__ == "__main__":
    main()

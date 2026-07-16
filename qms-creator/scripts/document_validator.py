#!/usr/bin/env python3
"""
Document Validator for Cannabis EU GMP QMS Creator
Validates documents before PDF/DOCX conversion to catch formatting errors early.

Author: Claude Code
Date: 2026-01-22
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@dataclass
class ValidationResult:
    """Result of document validation."""

    file_path: str
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, error: str):
        """Add an error to the validation result."""
        self.valid = False
        self.errors.append(error)

    def add_warning(self, warning: str):
        """Add a warning to the validation result."""
        self.warnings.append(warning)


class DocumentValidator:
    """Validates documents for formatting issues before conversion."""

    def __init__(self):
        """Initialize document validator."""
        self.base_dir = Path("/home/azzu/PROJ/Cannabis EU GMP QMS Creator")
        self.results: List[ValidationResult] = []

    def validate_content(self, content: str, file_path: str) -> ValidationResult:
        """
        Validate document content for common issues.

        Args:
            content: Document markdown/text content
            file_path: Path to the document file

        Returns:
            ValidationResult with any errors or warnings found
        """
        result = ValidationResult(file_path=file_path)

        # Check 1: Unresolved placeholders
        unresolved_placeholders = re.findall(r"\[([A-Z_]+)\]", content)
        if unresolved_placeholders:
            unique_placeholders = list(set(unresolved_placeholders))
            result.add_error(
                f"Unresolved placeholders found: {', '.join(unique_placeholders[:5])}"
                + (
                    f" ... and {len(unique_placeholders) - 5} more"
                    if len(unique_placeholders) > 5
                    else ""
                )
            )

        # Check 2: Duplicate titles
        h1_titles = re.findall(r"^#\s+([^\n]+)$", content, re.MULTILINE)
        h2_titles = re.findall(r"^##\s+([^\n]+)$", content, re.MULTILINE)
        all_titles = h1_titles + h2_titles

        if len(all_titles) != len(set(all_titles)):
            duplicate_titles = [t for t in set(all_titles) if all_titles.count(t) > 1]
            result.add_error(
                f"Duplicate titles detected: {duplicate_titles[0]}"
                + (
                    f" ... and {len(duplicate_titles) - 1} more"
                    if len(duplicate_titles) > 1
                    else ""
                )
            )

        # Check 3: Strange artifacts (raw metadata)
        if "noteId:" in content or "tags: []" in content:
            artifact_count = content.count("noteId:") + content.count("tags: []")
            result.add_error(
                f"Found {artifact_count} raw metadata artifacts (noteId/tags)"
            )

        # Check 4: Multiple approval sections
        approval_count = content.count("APPROVAL SIGNATURES") + content.count(
            "DOCUMENT APPROVAL"
        )
        if approval_count > 1:
            result.add_error(
                f"Multiple approval sections found ({approval_count}). "
                f"Should be exactly 1."
            )

        # Check 5: Empty sections
        empty_sections = re.findall(
            r"^#+\s+([^\n]+)\s*\n\s*(?=^#+|\Z)", content, re.MULTILINE
        )
        if empty_sections:
            result.add_warning(
                f"Empty sections found: {', '.join(empty_sections[:3])}"
                + (
                    f" ... and {len(empty_sections) - 3} more"
                    if len(empty_sections) > 3
                    else ""
                )
            )

        # Check 6: Missing document ID/metadata
        if not re.search(r"Document [ID|Code][:=]", content, re.IGNORECASE):
            result.add_warning("Document ID/Code not found in metadata")

        # Check 7: Check for very short content (might indicate parsing error)
        if len(content.strip()) < 500:
            result.add_warning(
                f"Document content is very short ({len(content)} chars). "
                f"May indicate parsing error."
            )

        # Check 8: Validate YAML frontmatter if present
        if content.strip().startswith("---"):
            yaml_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if yaml_match:
                yaml_content = yaml_match.group(1)
                # Check for required YAML fields
                required_fields = [
                    "document_id",
                    "version",
                    "title_en",
                    "effective_date",
                ]
                missing_fields = [f for f in required_fields if f not in yaml_content]
                if missing_fields:
                    result.add_error(
                        f"Missing YAML frontmatter fields: {', '.join(missing_fields)}"
                    )

        return result

    def validate_file(self, file_path: Path) -> ValidationResult:
        """
        Validate a single markdown file.

        Args:
            file_path: Path to the file to validate

        Returns:
            ValidationResult for the file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            result = self.validate_content(content, str(file_path))
            self.results.append(result)
            return result

        except Exception as e:
            result = ValidationResult(file_path=str(file_path))
            result.add_error(f"Failed to read file: {str(e)}")
            self.results.append(result)
            return result

    def validate_directory(self, dir_path: Path, pattern: str = "*.md") -> Dict:
        """
        Validate all markdown files in a directory.

        Args:
            dir_path: Directory to scan
            pattern: File pattern to match (default: *.md)

        Returns:
            Summary statistics
        """
        if not dir_path.exists():
            console.print(f"[red]✗ Directory not found: {dir_path}[/red]")
            return {}

        md_files = sorted(dir_path.glob(pattern))
        if not md_files:
            console.print(f"[yellow]⚠ No {pattern} files found in {dir_path}[/yellow]")
            return {}

        stats = {
            "total": len(md_files),
            "valid": 0,
            "invalid": 0,
            "warnings": 0,
            "errors": [],
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Validating {len(md_files)} files...", total=len(md_files)
            )

            for md_file in md_files:
                result = self.validate_file(md_file)

                if result.valid and not result.warnings:
                    stats["valid"] += 1
                else:
                    if not result.valid:
                        stats["invalid"] += 1
                    if result.warnings:
                        stats["warnings"] += 1

                    if result.errors or result.warnings:
                        stats["errors"].append(
                            {
                                "file": md_file.name,
                                "errors": result.errors,
                                "warnings": result.warnings,
                            }
                        )

                progress.update(task, advance=1)

        return stats

    def print_summary(self, stats: Dict):
        """Print validation summary."""
        if not stats:
            return

        console.print("\n" + "=" * 80)
        console.print("[bold cyan]Validation Summary[/bold cyan]")
        console.print("=" * 80 + "\n")

        # Summary table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")

        table.add_row("Total files", str(stats["total"]))
        table.add_row("[green]Valid[/green]", str(stats["valid"]))
        table.add_row("[yellow]With warnings[/yellow]", str(stats["warnings"]))
        table.add_row("[red]Invalid[/red]", str(stats["invalid"]))

        console.print(table)

        # Detailed errors
        if stats["errors"]:
            console.print("\n[bold yellow]Issues Found:[/bold yellow]")

            for issue in stats["errors"][:20]:  # Show first 20
                console.print(f"\n  📄 {issue['file']}")

                if issue["errors"]:
                    for error in issue["errors"]:
                        console.print(f"    [red]✗ {error}[/red]")

                if issue["warnings"]:
                    for warning in issue["warnings"]:
                        console.print(f"    [yellow]⚠ {warning}[/yellow]")

            if len(stats["errors"]) > 20:
                remaining = len(stats["errors"]) - 20
                console.print(f"\n  ... and {remaining} more files with issues")

        # Success summary
        if stats["valid"] == stats["total"]:
            console.print(
                f"\n[bold green]✓ All {stats['total']} documents passed validation![/bold green]\n"
            )
        else:
            console.print(
                f"\n[bold yellow]⚠ {stats['invalid']} document(s) need fixing before conversion[/bold yellow]\n"
            )


@click.command()
@click.option(
    "--scan", type=click.Path(exists=True), help="Scan directory for markdown files"
)
@click.option("--pattern", default="*.md", help="File pattern to match (default: *.md)")
@click.option("--file", type=click.Path(exists=True), help="Validate single file")
def main(scan: Optional[str], pattern: str, file: Optional[str]):
    """
    Validate QMS documents before PDF/DOCX conversion.

    Examples:
        # Validate single file
        python document_validator.py --file output/sops/QA_00.01_v1.0_EN.md

        # Scan entire directory
        python document_validator.py --scan output/sops

        # Scan with custom pattern
        python document_validator.py --scan output/sops --pattern "*_v1.0_EN.md"
    """
    validator = DocumentValidator()

    console.print(
        Panel(
            "[bold cyan]QMS Document Validator[/bold cyan]\n"
            "Validates documents for formatting issues before conversion",
            expand=False,
        )
    )

    if file:
        # Validate single file
        console.print(f"\n[cyan]Validating: {file}[/cyan]")
        result = validator.validate_file(Path(file))

        if result.valid and not result.warnings:
            console.print("[green]✓ Document is valid![/green]\n")
        else:
            if result.errors:
                console.print("[red]Errors:[/red]")
                for error in result.errors:
                    console.print(f"  • {error}")

            if result.warnings:
                console.print("[yellow]Warnings:[/yellow]")
                for warning in result.warnings:
                    console.print(f"  • {warning}")
            console.print()

    elif scan:
        # Scan directory
        console.print(f"\n[cyan]Scanning: {scan}[/cyan]")
        stats = validator.validate_directory(Path(scan), pattern)
        validator.print_summary(stats)

    else:
        # Default: scan output/sops
        default_dir = validator.base_dir / "output" / "sops"
        if default_dir.exists():
            console.print(f"\n[cyan]Scanning default directory: {default_dir}[/cyan]")
            stats = validator.validate_directory(default_dir, pattern)
            validator.print_summary(stats)
        else:
            console.print(
                f"[yellow]⚠ No default directory found: {default_dir}[/yellow]\n"
                f"Use --scan to specify a directory or --file to validate a single file"
            )


if __name__ == "__main__":
    main()

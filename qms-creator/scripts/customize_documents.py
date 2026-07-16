#!/usr/bin/env python3
"""
Document Customization Orchestrator for Cannabis EU GMP QMS Creator
Main script to automate placeholder replacement across all QMS documents
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Import our modules
sys.path.append(str(Path(__file__).parent))

from facility_config import load_facility_config
from placeholder_engine import PlaceholderEngine, process_template_file
from utils.template_scanner import TemplateScanner

console = Console()


class DocumentCustomizer:
    """Main document customization orchestrator."""

    def __init__(
        self, base_dir: Path, config_dir: Path = None, output_dir: Path = None
    ):
        """
        Initialize document customizer.

        Args:
            base_dir: Base project directory
            config_dir: Config directory (default: base_dir/config)
            output_dir: Output directory (default: base_dir/output/customized)
        """
        self.base_dir = base_dir
        self.config_dir = config_dir or base_dir / "config"
        self.output_dir = output_dir or base_dir / "output" / "customized"

        self.config = None
        self.scanner = None
        self.templates: List[Path] = []
        self.results: Dict[str, Any] = {}

    def load_configuration(self) -> bool:
        """Load and validate facility configuration."""
        console.print("\n[bold cyan]Loading facility configuration...[/bold cyan]")

        try:
            self.config = load_facility_config(self.config_dir)

            if not self.config._loaded:
                console.print("[bold red]✗[/bold red] Failed to load configuration")
                return False

            console.print(
                "[bold green]✓[/bold green] Configuration loaded successfully"
            )
            return True

        except Exception as e:
            console.print(f"[bold red]✗[/bold red] Error loading configuration: {e}")
            return False

    def scan_templates(self, category: str = None) -> int:
        """
        Scan for template files.

        Args:
            category: Optional category filter

        Returns:
            Number of templates found
        """
        console.print("\n[bold cyan]Scanning for templates...[/bold cyan]")

        self.scanner = TemplateScanner(self.base_dir)
        # Scan for both .txt and .md templates
        txt_templates = self.scanner.scan(file_pattern="*.txt")
        md_templates = self.scanner.scan(file_pattern="*.md")
        all_templates = sorted(list(set(txt_templates + md_templates)))

        if category:
            self.scanner.categorize()
            self.templates = self.scanner.get_templates_by_category(category)
            console.print(
                f"[bold green]✓[/bold green] Found {len(self.templates)} templates in category '{category}'"
            )
        else:
            self.templates = all_templates
            console.print(
                f"[bold green]✓[/bold green] Found {len(self.templates)} templates"
            )

        return len(self.templates)

    def customize_documents(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Customize all discovered templates.

        Args:
            dry_run: If True, don't write files (just simulate)

        Returns:
            Results dictionary with statistics
        """
        if not self.templates:
            console.print("[bold red]✗[/bold red] No templates to process")
            return {}

        console.print(
            f"\n[bold cyan]{'Simulating' if dry_run else 'Processing'} {len(self.templates)} templates...[/bold cyan]\n"
        )

        results = {
            "total": len(self.templates),
            "successful": 0,
            "failed": 0,
            "total_replacements": 0,
            "total_unresolved": 0,
            "unresolved_placeholders": set(),
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
                "[cyan]Customizing documents...", total=len(self.templates)
            )

            for template in self.templates:
                rel_path = template.relative_to(self.base_dir)

                # Calculate output path (preserve directory structure)
                output_path = self.output_dir / rel_path

                try:
                    if not dry_run:
                        success, stats = process_template_file(
                            template, output_path, self.config
                        )
                    else:
                        # Dry run: just process content without writing
                        with open(
                            template, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()
                        engine = PlaceholderEngine(self.config)
                        engine.process_content(content)
                        success = True
                        stats = engine.get_statistics()

                    if success:
                        results["successful"] += 1
                        results["total_replacements"] += stats.get(
                            "replacements_made", 0
                        )
                        results["total_unresolved"] += stats.get("unresolved_count", 0)
                        results["unresolved_placeholders"].update(
                            stats.get("unresolved_placeholders", [])
                        )
                    else:
                        results["failed"] += 1
                        results["errors"].append(
                            {
                                "file": str(rel_path),
                                "error": stats.get("error", "Unknown error"),
                            }
                        )

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({"file": str(rel_path), "error": str(e)})

                progress.update(task, advance=1)

        self.results = results
        return results

    def print_summary(self):
        """Print customization summary."""
        if not self.results:
            return

        console.print("\n" + "=" * 80)
        console.print("[bold cyan]Customization Summary[/bold cyan]")
        console.print("=" * 80 + "\n")

        # Success/failure table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Total templates", str(self.results["total"]))
        table.add_row("Successfully processed", str(self.results["successful"]))
        table.add_row("Failed", str(self.results["failed"]))
        table.add_row(
            "Total replacements made", str(self.results["total_replacements"])
        )
        table.add_row("Unresolved placeholders", str(self.results["total_unresolved"]))

        console.print(table)

        # Show unresolved placeholders
        if self.results["unresolved_placeholders"]:
            console.print("\n[bold yellow]⚠ Unresolved Placeholders:[/bold yellow]")
            for ph in sorted(self.results["unresolved_placeholders"])[
                :20
            ]:  # Show first 20
                console.print(f"  • [{ph}]")

            if len(self.results["unresolved_placeholders"]) > 20:
                remaining = len(self.results["unresolved_placeholders"]) - 20
                console.print(f"  ... and {remaining} more")

        # Show errors
        if self.results["errors"]:
            console.print("\n[bold red]✗ Errors:[/bold red]")
            for error in self.results["errors"][:10]:  # Show first 10
                console.print(f"  • {error['file']}: {error['error']}")

            if len(self.results["errors"]) > 10:
                remaining = len(self.results["errors"]) - 10
                console.print(f"  ... and {remaining} more errors")

        # Success message
        if self.results["successful"] > 0:
            console.print(
                f"\n[bold green]✓ Successfully customized {self.results['successful']} documents![/bold green]"
            )
            console.print(
                f"[bold green]  Output directory: {self.output_dir}[/bold green]\n"
            )


@click.command()
@click.option("--all", "process_all", is_flag=True, help="Process all templates")
@click.option(
    "--category",
    type=str,
    help="Process specific category (e.g., master_documents, quality_assurance)",
)
@click.option("--document", type=str, help="Process single document by name")
@click.option("--dry-run", is_flag=True, help="Simulate without writing files")
@click.option("--output", type=click.Path(), help="Custom output directory")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def main(process_all, category, document, dry_run, output, verbose):
    """
    Cannabis EU GMP QMS Document Customization Tool

    Automatically replaces placeholders in template documents with facility-specific data.

    Examples:

      # Process all documents
      python customize_documents.py --all

      # Process specific category
      python customize_documents.py --category master_documents

      # Dry run (simulate without writing)
      python customize_documents.py --all --dry-run

      # Process single document
      python customize_documents.py --document QAS-01-001_Quality_Manual_Template.txt
    """
    # Banner
    console.print(
        Panel.fit(
            "[bold cyan]Cannabis EU GMP QMS Creator[/bold cyan]\n"
            "[yellow]Document Customization Tool[/yellow]\n"
            f"[dim]Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            border_style="cyan",
        )
    )

    # Get base directory
    base_dir = Path(__file__).parent.parent

    # Custom output directory
    output_dir = None
    if output:
        output_dir = Path(output)

    # Initialize customizer
    customizer = DocumentCustomizer(base_dir, output_dir=output_dir)

    # Load configuration
    if not customizer.load_configuration():
        console.print("[bold red]Exiting due to configuration errors.[/bold red]")
        sys.exit(1)

    # Determine what to process
    if document:
        # Process single document
        console.print(f"\n[yellow]Searching for document: {document}[/yellow]")
        customizer.scan_templates()

        # Find matching template
        matching = [t for t in customizer.templates if document in t.name]

        if not matching:
            console.print(f"[bold red]✗ Document not found: {document}[/bold red]")
            sys.exit(1)

        customizer.templates = matching
        console.print(f"[green]✓ Found: {matching[0].name}[/green]")

    elif category:
        # Process category
        customizer.scan_templates(category)

        if not customizer.templates:
            console.print(
                f"[bold red]✗ No templates found in category: {category}[/bold red]"
            )
            sys.exit(1)

    elif process_all:
        # Process all templates
        customizer.scan_templates()

    else:
        # No option specified
        console.print(
            "[yellow]Please specify --all, --category, or --document[/yellow]"
        )
        console.print("Run with --help for usage information")
        sys.exit(0)

    # Show dry run notice
    if dry_run:
        console.print(
            "\n[bold yellow]⚠ DRY RUN MODE - No files will be written[/bold yellow]"
        )

    # Customize documents
    customizer.customize_documents(dry_run=dry_run)

    # Print summary
    customizer.print_summary()

    # Exit code based on results
    if customizer.results["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

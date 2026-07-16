#!/usr/bin/env python3
"""
Document Validation Tool for Cannabis EU GMP QMS Creator
Validates generated documents for completeness and generates HTML report
"""

import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import re
from datetime import datetime
from rich.console import Console

console = Console()


class DocumentValidator:
    """Validator for generated QMS documents."""

    def __init__(self, output_dir: Path):
        """Initialize validator with output directory."""
        self.output_dir = output_dir
        self.placeholder_pattern = re.compile(r'\[([A-Z][A-Z0-9_\-\s]+?)\]')
        self.results: Dict = {}

    def scan_documents(self) -> List[Path]:
        """Find all generated documents."""
        documents = list(self.output_dir.rglob('*.txt'))
        console.print(f"[cyan]Found {len(documents)} documents to validate[/cyan]")
        return documents

    def validate_document(self, doc_path: Path) -> Dict:
        """Validate a single document."""
        try:
            with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Find unfilled placeholders
            placeholders = self.placeholder_pattern.findall(content)
            unfilled = [p for p in placeholders if self._is_placeholder(p)]

            return {
                'path': doc_path,
                'size': len(content),
                'lines': content.count('\n'),
                'unfilled_placeholders': list(set(unfilled)),
                'unfilled_count': len(set(unfilled)),
                'status': 'complete' if not unfilled else 'incomplete'
            }

        except Exception as e:
            return {
                'path': doc_path,
                'error': str(e),
                'status': 'error'
            }

    def _is_placeholder(self, text: str) -> bool:
        """Check if text is actually an unfilled placeholder."""
        # Skip common non-placeholder brackets
        skip_patterns = [
            'ROOM-', 'EQU-', 'QAS-', 'SAN-', 'PRO-', 'SEC-', 'REC-', 'HR-', 'PRE-',
            'DATE', 'VERSION', 'XX', 'NN', 'YYYY', 'MM', 'DD'
        ]

        for pattern in skip_patterns:
            if pattern in text and len(text) < 20:
                return False

        return True

    def validate_all(self) -> Dict:
        """Validate all documents and generate summary."""
        documents = self.scan_documents()

        total_unfilled = set()
        complete_docs = []
        incomplete_docs = []
        error_docs = []

        for doc in documents:
            result = self.validate_document(doc)

            if result['status'] == 'complete':
                complete_docs.append(result)
            elif result['status'] == 'incomplete':
                incomplete_docs.append(result)
                total_unfilled.update(result.get('unfilled_placeholders', []))
            else:
                error_docs.append(result)

        self.results = {
            'total_documents': len(documents),
            'complete': len(complete_docs),
            'incomplete': len(incomplete_docs),
            'errors': len(error_docs),
            'total_unfilled': len(total_unfilled),
            'unfilled_placeholders': sorted(total_unfilled),
            'complete_docs': complete_docs,
            'incomplete_docs': incomplete_docs,
            'error_docs': error_docs,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        return self.results

    def generate_html_report(self, output_path: Path):
        """Generate HTML validation report."""
        if not self.results:
            return

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>QMS Document Validation Report</title>
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
        .stat-box.complete {{
            background: #d4edda;
            border: 2px solid #28a745;
        }}
        .stat-box.incomplete {{
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
        .placeholder-list {{
            background: #fff3cd;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #ffc107;
            margin: 20px 0;
        }}
        .placeholder-list ul {{
            column-count: 3;
            column-gap: 20px;
        }}
        .status-badge {{
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .status-complete {{
            background: #28a745;
            color: white;
        }}
        .status-incomplete {{
            background: #ffc107;
            color: black;
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
        <h1>🎯 QMS Document Validation Report</h1>
        <p><strong>Generated:</strong> {self.results['timestamp']}</p>
        <p><strong>Cannabis EU GMP QMS Creator</strong> - Purely Plant GmbH</p>

        <div class="summary">
            <div class="stat-box complete">
                <div class="stat-label">Complete Documents</div>
                <div class="stat-number">{self.results['complete']}</div>
            </div>
            <div class="stat-box incomplete">
                <div class="stat-label">Incomplete Documents</div>
                <div class="stat-number">{self.results['incomplete']}</div>
            </div>
            <div class="stat-box error">
                <div class="stat-label">Errors</div>
                <div class="stat-number">{self.results['errors']}</div>
            </div>
        </div>

        <h2>📊 Summary Statistics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Count</th>
                <th>Percentage</th>
            </tr>
            <tr>
                <td>Total Documents</td>
                <td>{self.results['total_documents']}</td>
                <td>100%</td>
            </tr>
            <tr>
                <td>Complete (No placeholders)</td>
                <td>{self.results['complete']}</td>
                <td>{self.results['complete']/max(self.results['total_documents'],1)*100:.1f}%</td>
            </tr>
            <tr>
                <td>Incomplete (Has placeholders)</td>
                <td>{self.results['incomplete']}</td>
                <td>{self.results['incomplete']/max(self.results['total_documents'],1)*100:.1f}%</td>
            </tr>
            <tr>
                <td>Total Unique Unfilled Placeholders</td>
                <td>{self.results['total_unfilled']}</td>
                <td>-</td>
            </tr>
        </table>
"""

        # Unfilled placeholders section
        if self.results['unfilled_placeholders']:
            html += f"""
        <h2>⚠️ Unfilled Placeholders ({self.results['total_unfilled']})</h2>
        <div class="placeholder-list">
            <p>The following placeholders were found across all documents:</p>
            <ul>
"""
            for ph in self.results['unfilled_placeholders']:
                html += f"                <li>[{ph}]</li>\n"

            html += """
            </ul>
        </div>
"""

        # Incomplete documents section
        if self.results['incomplete_docs']:
            html += """
        <h2>📄 Incomplete Documents</h2>
        <table>
            <tr>
                <th>Document</th>
                <th>Status</th>
                <th>Unfilled Placeholders</th>
            </tr>
"""
            for doc in self.results['incomplete_docs']:
                rel_path = doc['path'].relative_to(self.output_dir)
                html += f"""
            <tr>
                <td>{rel_path}</td>
                <td><span class="status-badge status-incomplete">Incomplete</span></td>
                <td>{doc['unfilled_count']}</td>
            </tr>
"""
            html += "        </table>\n"

        # Complete documents section
        if self.results['complete_docs']:
            html += f"""
        <h2>✅ Complete Documents ({len(self.results['complete_docs'])})</h2>
        <table>
            <tr>
                <th>Document</th>
                <th>Status</th>
                <th>Size</th>
            </tr>
"""
            for doc in self.results['complete_docs'][:10]:  # Show first 10
                rel_path = doc['path'].relative_to(self.output_dir)
                html += f"""
            <tr>
                <td>{rel_path}</td>
                <td><span class="status-badge status-complete">Complete</span></td>
                <td>{doc['lines']} lines</td>
            </tr>
"""
            html += "        </table>\n"

            if len(self.results['complete_docs']) > 10:
                html += f"        <p><em>... and {len(self.results['complete_docs']) - 10} more complete documents</em></p>\n"

        html += """
        <div class="footer">
            <p>Cannabis EU GMP QMS Creator - Automation System v1.0</p>
            <p>Purely Plant GmbH - Skopje, North Macedonia</p>
        </div>
    </div>
</body>
</html>
"""

        # Write HTML file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        console.print(f"\n[bold green]✓[/bold green] Validation report saved to: [cyan]{output_path}[/cyan]")


def main():
    """Main validation function."""
    console.print("\n[bold cyan]QMS Document Validation Tool[/bold cyan]")
    console.print("=" * 80 + "\n")

    # Get output directory
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / 'output' / 'customized'

    if not output_dir.exists():
        console.print("[bold red]✗[/bold red] Output directory not found. Run customize_documents.py first.")
        sys.exit(1)

    # Create validator
    validator = DocumentValidator(output_dir)

    # Validate all documents
    console.print("[cyan]Validating documents...[/cyan]\n")
    results = validator.validate_all()

    # Print summary
    console.print(f"\n[bold]Validation Summary:[/bold]")
    console.print(f"  Total documents: {results['total_documents']}")
    console.print(f"  [green]Complete: {results['complete']}[/green]")
    console.print(f"  [yellow]Incomplete: {results['incomplete']}[/yellow]")
    console.print(f"  [red]Errors: {results['errors']}[/red]")
    console.print(f"  [yellow]Total unfilled placeholders: {results['total_unfilled']}[/yellow]")

    # Generate HTML report
    report_path = base_dir / 'output' / 'validation_report.html'
    validator.generate_html_report(report_path)

    console.print(f"\n[bold green]✓ Validation complete![/bold green]\n")


if __name__ == "__main__":
    main()

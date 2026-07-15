#!/usr/bin/env python3
"""
Placeholder Scanner for Cannabis EU GMP QMS Creator
Scans all template files to discover unique placeholders
"""

import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, List
import yaml


def find_placeholders_in_file(file_path: Path) -> Set[str]:
    """Find all placeholders in a single file."""
    placeholders = set()

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Match [PLACEHOLDER] pattern - must be uppercase with underscores
        pattern = r'\[([A-Z][A-Z0-9_\-\s]*?)\]'
        matches = re.findall(pattern, content)

        for match in matches:
            # Clean up the placeholder
            placeholder = match.strip()
            # Skip if it's just a category marker or too short
            if len(placeholder) > 1 and not placeholder.isdigit():
                placeholders.add(placeholder)

    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return placeholders


def scan_templates(base_dir: Path) -> Dict[str, List[str]]:
    """Scan all template files and categorize placeholders."""

    all_placeholders = set()
    file_count = 0
    placeholder_sources = defaultdict(list)

    # Scan all .txt files in the project
    for txt_file in base_dir.rglob('*.txt'):
        # Skip output and venv directories
        if 'output' in txt_file.parts or 'venv' in txt_file.parts:
            continue

        placeholders = find_placeholders_in_file(txt_file)

        if placeholders:
            file_count += 1
            all_placeholders.update(placeholders)

            for placeholder in placeholders:
                rel_path = txt_file.relative_to(base_dir)
                placeholder_sources[placeholder].append(str(rel_path))

    print(f"\n{'='*80}")
    print(f"Placeholder Scan Results")
    print(f"{'='*80}\n")
    print(f"Files scanned: {file_count}")
    print(f"Unique placeholders found: {len(all_placeholders)}\n")

    # Categorize placeholders
    categories = {
        'facility': [],
        'personnel': [],
        'equipment': [],
        'dates': [],
        'locations': [],
        'operational': [],
        'contact': [],
        'regulatory': [],
        'other': []
    }

    for placeholder in sorted(all_placeholders):
        ph_lower = placeholder.lower()

        if any(k in ph_lower for k in ['facility', 'company', 'legal_entity', 'registration']):
            categories['facility'].append(placeholder)
        elif any(k in ph_lower for k in ['manager', 'name', 'qp', 'personnel', 'employee', 'staff', 'officer', 'responsible']):
            categories['personnel'].append(placeholder)
        elif any(k in ph_lower for k in ['equipment', 'machine', 'device', 'system', 'instrument', 'hvac', 'model', 'serial']):
            categories['equipment'].append(placeholder)
        elif any(k in ph_lower for k in ['date', 'effective', 'expiration', 'issue', 'revision', 'review']):
            categories['dates'].append(placeholder)
        elif any(k in ph_lower for k in ['location', 'address', 'room', 'area', 'city', 'region', 'latitude', 'longitude', 'site']):
            categories['locations'].append(placeholder)
        elif any(k in ph_lower for k in ['phone', 'email', 'contact', 'fax']):
            categories['contact'].append(placeholder)
        elif any(k in ph_lower for k in ['license', 'permit', 'regulatory', 'authority', 'ministry', 'inspection']):
            categories['regulatory'].append(placeholder)
        elif any(k in ph_lower for k in ['objective', 'target', 'metric', 'retention', 'operation', 'procedure', 'batch', 'product']):
            categories['operational'].append(placeholder)
        else:
            categories['other'].append(placeholder)

    # Print categorized placeholders
    for category, placeholders in categories.items():
        if placeholders:
            print(f"\n{category.upper()} ({len(placeholders)} placeholders):")
            print("-" * 80)
            for ph in sorted(placeholders):
                print(f"  [{ph}]")

    return {
        'all_placeholders': sorted(list(all_placeholders)),
        'categories': {k: v for k, v in categories.items() if v},
        'placeholder_sources': dict(placeholder_sources),
        'file_count': file_count
    }


def save_placeholder_report(results: Dict, output_path: Path):
    """Save placeholder scan results to YAML."""
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(results, f, default_flow_style=False, allow_unicode=True)

    print(f"\n{'='*80}")
    print(f"Placeholder report saved to: {output_path}")
    print(f"{'='*80}\n")


def main():
    """Main execution function."""
    # Get base directory
    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1])
    else:
        # Assume script is in scripts/ directory
        base_dir = Path(__file__).parent.parent

    print(f"Scanning templates in: {base_dir}")
    print(f"{'='*80}\n")

    # Scan templates
    results = scan_templates(base_dir)

    # Save results
    output_path = base_dir / 'config' / 'placeholder_scan_results.yaml'
    save_placeholder_report(results, output_path)

    # Print summary statistics
    print(f"Total unique placeholders: {len(results['all_placeholders'])}")
    print(f"Categories found: {len(results['categories'])}")
    print(f"\nNext steps:")
    print(f"1. Review {output_path}")
    print(f"2. Create facility_data.yaml based on these placeholders")
    print(f"3. Run setup_wizard.py to populate facility data")


if __name__ == '__main__':
    main()

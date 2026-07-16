#!/usr/bin/env python3
"""
Extract SOP-related conversations from Claude Desktop conversation history
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

def extract_sop_conversations(conversations_file: Path, output_dir: Path) -> None:
    """Extract conversations related to SOPs"""

    # SOP keywords to search for
    sop_keywords = [
        "batch release",
        "SOP-BRR-001",
        "plant health",
        "out-of-expected",
        "OOx investigation",
        "water quality",
        "transport",
        "logistics",
        "reagent storage",
        "memorandum control",
        "curing process",
        "equipment calibration",
        "HVAC",
        "AHU-5",
        "stability studies",
        "cultivation SOP",
        "phenotype selection",
        "R&D plant"
    ]

    print(f"Reading conversations from: {conversations_file}")
    print(f"Output directory: {output_dir}")
    print(f"\nSearching for SOP-related conversations...")

    try:
        with open(conversations_file, 'r', encoding='utf-8') as f:
            conversations = json.load(f)

        print(f"✓ Loaded {len(conversations)} conversations")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Extract relevant conversations
        sop_convos = []

        for conv in conversations:
            name = conv.get('name', '').lower()
            summary = conv.get('summary', '').lower()

            # Check if any SOP keyword matches
            for keyword in sop_keywords:
                if keyword.lower() in name or keyword.lower() in summary:
                    sop_convos.append({
                        'uuid': conv.get('uuid'),
                        'name': conv.get('name'),
                        'summary': conv.get('summary', '')[:500],  # First 500 chars
                        'created': conv.get('created_at'),
                        'updated': conv.get('updated_at'),
                        'keyword_matched': keyword
                    })
                    print(f"  ✓ Found: {conv.get('name')[:60]}... (keyword: {keyword})")
                    break

        # Save extracted conversations list
        output_file = output_dir / "sop_conversations_index.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(sop_convos, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Extracted {len(sop_convos)} SOP-related conversations")
        print(f"✓ Index saved to: {output_file}")

        # Print summary
        print("\n" + "="*80)
        print("SOP Conversations Summary")
        print("="*80)

        for i, conv in enumerate(sop_convos, 1):
            print(f"\n{i}. {conv['name']}")
            print(f"   UUID: {conv['uuid']}")
            print(f"   Keyword: {conv['keyword_matched']}")
            print(f"   Created: {conv['created']}")
            if conv['summary']:
                print(f"   Summary: {conv['summary'][:150]}...")

        return sop_convos

    except FileNotFoundError:
        print(f"✗ Error: File not found: {conversations_file}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"✗ Error: Invalid JSON in: {conversations_file}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Set paths
    project_root = Path(__file__).parent.parent
    conversations_file = project_root / "data-2026-01-13-11-16-07-batch-0000" / "conversations.json"
    output_dir = project_root / "extracted_sops"

    # Extract conversations
    sop_convos = extract_sop_conversations(conversations_file, output_dir)

    print(f"\n✓ Complete! Found {len(sop_convos)} SOP conversations")
    print(f"✓ Index file: {output_dir}/sop_conversations_index.json")

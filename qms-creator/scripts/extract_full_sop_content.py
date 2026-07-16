#!/usr/bin/env python3
"""
Extract full SOP content from identified conversations

This script takes the UUIDs from sop_conversations_index.json and extracts
the complete conversation content from the conversations.json file,
formatting each conversation into a readable markdown document.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import re
from datetime import datetime


def load_json_file(file_path: Path) -> dict:
    """Load and parse JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"✗ Error loading {file_path}: {e}")
        sys.exit(1)


def extract_conversation_by_uuid(conversations: List[dict], uuid: str) -> dict:
    """Find and return conversation matching UUID"""
    for conv in conversations:
        if conv.get('uuid') == uuid:
            return conv
    return None


def format_conversation_content(conversation: dict, sop_info: dict) -> str:
    """Format conversation into readable markdown document"""

    uuid = conversation.get('uuid', 'Unknown')
    name = conversation.get('name', 'Untitled')
    summary = conversation.get('summary', 'No summary available')
    created = conversation.get('created_at', 'Unknown')
    updated = conversation.get('updated_at', 'Unknown')

    # Get chat messages
    chat_messages = conversation.get('chat_messages', [])

    # Build markdown document
    content = []
    content.append("# SOP CONVERSATION EXTRACTION")
    content.append("")
    content.append(f"**Conversation Title:** {name}")
    content.append(f"**UUID:** {uuid}")
    content.append(f"**Keyword Matched:** {sop_info.get('keyword_matched', 'N/A')}")
    content.append(f"**Created:** {created}")
    content.append(f"**Last Updated:** {updated}")
    content.append("")
    content.append("---")
    content.append("")
    content.append("## CONVERSATION SUMMARY")
    content.append("")
    content.append(summary)
    content.append("")
    content.append("---")
    content.append("")
    content.append("## FULL CONVERSATION TRANSCRIPT")
    content.append("")

    # Extract messages
    message_count = 0
    for msg in chat_messages:
        message_count += 1
        sender = msg.get('sender', 'unknown')
        text = msg.get('text', '')
        created_at = msg.get('created_at', '')

        # Format sender
        if sender == 'human':
            content.append(f"### MESSAGE {message_count}: USER")
        else:
            content.append(f"### MESSAGE {message_count}: ASSISTANT (Claude)")

        content.append(f"*Time: {created_at}*")
        content.append("")

        # Add message text
        if text:
            content.append(text)
        else:
            content.append("*(No text content)*")

        content.append("")
        content.append("---")
        content.append("")

    # Add extraction metadata
    content.append("")
    content.append("## EXTRACTION METADATA")
    content.append("")
    content.append(f"- **Total Messages:** {message_count}")
    content.append(f"- **Conversation Length:** ~{len(json.dumps(conversation))} characters")
    content.append(f"- **Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append(f"- **Source:** Cannabis EU GMP QMS Creator / Conversation History")
    content.append("")
    content.append("---")
    content.append("")
    content.append("**NEXT STEPS:**")
    content.append("1. Review conversation content for SOP-relevant information")
    content.append("2. Extract key procedures, requirements, and technical details")
    content.append("3. Format into standardized SOP template (per QAS-00-002 Annex A01)")
    content.append("4. Add regulatory references and compliance requirements")
    content.append("5. Generate bilingual version if required")
    content.append("")

    return '\n'.join(content)


def extract_all_sop_conversations(
    conversations_file: Path,
    index_file: Path,
    output_dir: Path,
    prioritize_complete: bool = True
) -> None:
    """Extract all SOP conversations identified in index"""

    print(f"\n{'='*80}")
    print("SOP CONVERSATION CONTENT EXTRACTION")
    print(f"{'='*80}\n")

    # Load data
    print(f"Loading conversation index: {index_file}")
    sop_index = load_json_file(index_file)
    print(f"✓ Found {len(sop_index)} SOP conversations in index")

    print(f"\nLoading full conversation history: {conversations_file}")
    all_conversations = load_json_file(conversations_file)
    print(f"✓ Loaded {len(all_conversations)} total conversations")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")

    # Categorize SOPs
    fully_developed = []
    partially_developed = []

    for sop in sop_index:
        sop_name = sop.get('name', '').lower()
        # Heuristic: if summary is long and detailed, likely more complete
        summary_length = len(sop.get('summary', ''))

        # Known fully developed SOPs based on previous analysis
        fully_developed_keywords = [
            'batch release', 'sop-brr-001', 'plant health',
            'out-of-expected', 'oox', 'transport', 'logistics',
            'curing process', 'memorandum', 'reagent storage',
            'phenotype selection'
        ]

        is_fully_developed = any(kw in sop_name for kw in fully_developed_keywords)

        if is_fully_developed:
            fully_developed.append(sop)
        else:
            partially_developed.append(sop)

    print(f"\n{'='*80}")
    print("SOP CATEGORIZATION")
    print(f"{'='*80}")
    print(f"Fully Developed SOPs: {len(fully_developed)}")
    print(f"Partially Developed SOPs: {len(partially_developed)}")
    print(f"Total: {len(sop_index)}")

    # Process SOPs
    if prioritize_complete:
        print(f"\n⭐ PRIORITIZING FULLY DEVELOPED SOPs FIRST")
        sops_to_process = fully_developed + partially_developed
    else:
        sops_to_process = sop_index

    extracted_count = 0
    failed_count = 0

    print(f"\n{'='*80}")
    print("EXTRACTING CONVERSATION CONTENT")
    print(f"{'='*80}\n")

    for idx, sop_info in enumerate(sops_to_process, 1):
        uuid = sop_info.get('uuid')
        name = sop_info.get('name', 'Untitled')

        print(f"\n[{idx}/{len(sops_to_process)}] Processing: {name[:60]}...")
        print(f"    UUID: {uuid}")

        # Find conversation in full dataset
        conversation = extract_conversation_by_uuid(all_conversations, uuid)

        if conversation is None:
            print(f"    ✗ ERROR: Conversation not found in dataset")
            failed_count += 1
            continue

        # Format content
        try:
            formatted_content = format_conversation_content(conversation, sop_info)

            # Create safe filename
            safe_name = re.sub(r'[^\w\s-]', '', name)
            safe_name = re.sub(r'[-\s]+', '_', safe_name)
            safe_name = safe_name[:60]  # Limit filename length

            # Determine category
            category = "fully_developed" if sop_info in fully_developed else "partially_developed"

            # Create category subdirectory
            category_dir = output_dir / category
            category_dir.mkdir(exist_ok=True)

            # Output filename
            output_file = category_dir / f"{safe_name}_{uuid[:8]}.md"

            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(formatted_content)

            # Calculate size
            file_size = len(formatted_content)
            file_size_kb = file_size / 1024

            print(f"    ✓ Extracted: {file_size_kb:.1f} KB")
            print(f"    ✓ Saved to: {output_file.name}")

            extracted_count += 1

        except Exception as e:
            print(f"    ✗ ERROR: {e}")
            failed_count += 1

    # Summary
    print(f"\n{'='*80}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*80}")
    print(f"✓ Successfully extracted: {extracted_count} conversations")
    print(f"✗ Failed: {failed_count} conversations")
    print(f"\nOutput location: {output_dir}")
    print(f"  - Fully Developed SOPs: {output_dir}/fully_developed/")
    print(f"  - Partially Developed SOPs: {output_dir}/partially_developed/")
    print(f"\n{'='*80}")
    print("NEXT STEPS")
    print(f"{'='*80}")
    print("1. Review extracted conversations in output directory")
    print("2. Identify key SOP content and procedures")
    print("3. Format into standardized SOP templates (QAS-00-002 Annex A01)")
    print("4. Add regulatory compliance requirements")
    print("5. Generate professional .docx documents")
    print(f"{'='*80}\n")


def main():
    """Main execution"""
    # Set paths
    project_root = Path(__file__).parent.parent
    conversations_file = project_root / "data-2026-01-13-11-16-07-batch-0000" / "conversations.json"
    index_file = project_root / "extracted_sops" / "sop_conversations_index.json"
    output_dir = project_root / "extracted_sops" / "full_content"

    # Verify files exist
    if not conversations_file.exists():
        print(f"✗ Error: Conversations file not found: {conversations_file}")
        sys.exit(1)

    if not index_file.exists():
        print(f"✗ Error: Index file not found: {index_file}")
        print("   Run extract_sop_conversations.py first to generate index")
        sys.exit(1)

    # Extract
    extract_all_sop_conversations(
        conversations_file=conversations_file,
        index_file=index_file,
        output_dir=output_dir,
        prioritize_complete=True  # Extract fully developed SOPs first
    )


if __name__ == "__main__":
    main()

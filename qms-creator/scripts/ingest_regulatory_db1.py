#!/usr/bin/env python3
"""
Ingest Regulatory Documents into Letta DB1 Archive

Ingests all regulatory documents from 1stDataKnowledge folder into db1_regulatory archive.
Sources include: EudraLex, EMA, ICH, WHO, Ph.Eur., and other regulatory literature.

Usage:
    python scripts/ingest_regulatory_db1.py
    python scripts/ingest_regulatory_db1.py --recreate  # Recreate archive from scratch
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from CONTENT_CREATOR_FRAMEWORK.letta_service import LettaService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# Regulatory body mapping based on folder names
REGULATORY_BODY_MAP = {
    "eudralex": "EudraLex",
    "ema": "EMA",
    "ich": "ICH",
    "who": "WHO",
    "ph.eur.": "Ph.Eur.",
    "macedonian gmp": "National_GMP",
    "various literature": "Literature",
    "test weights": "Industry_Guidelines",
}


def get_regulatory_body(folder_name: str) -> str:
    """Map folder name to regulatory body tag."""
    lower_name = folder_name.lower()
    return REGULATORY_BODY_MAP.get(lower_name, "Regulatory")


def create_tag_fn(base_folder: Path):
    """Create a tagging function for regulatory documents."""

    def tag_fn(file_path: Path):
        """Generate tags for regulatory documents."""
        tags = ["database:db1", "type:regulatory"]

        # Get relative path from base folder
        try:
            rel_path = file_path.relative_to(base_folder)
            parts = rel_path.parts

            # First level folder is regulatory body
            if len(parts) >= 1:
                reg_body = get_regulatory_body(parts[0])
                tags.append(f"regulatory_body:{reg_body}")

                # Second level for sub-categorization (e.g., Part I, Annexes)
                if len(parts) >= 2 and parts[1] not in [file_path.name]:
                    sub_category = parts[1].replace(" ", "_").lower()
                    tags.append(f"section:{sub_category}")

            # Add file reference
            tags.append(f"file:{file_path.name}")

            # Detect document type from filename
            name_lower = file_path.stem.lower()
            if "annex" in name_lower:
                tags.append("doc_type:annex")
            elif "chapter" in name_lower or "chap" in name_lower:
                tags.append("doc_type:chapter")
            elif "guideline" in name_lower or "guide" in name_lower:
                tags.append("doc_type:guideline")
            elif "template" in name_lower:
                tags.append("doc_type:template")
            elif "checklist" in name_lower:
                tags.append("doc_type:checklist")
            else:
                tags.append("doc_type:document")

        except ValueError:
            tags.append(f"file:{file_path.name}")

        return tags

    return tag_fn


def main():
    parser = argparse.ArgumentParser(description="Ingest regulatory documents into DB1")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate the archive from scratch (deletes existing data)",
    )
    args = parser.parse_args()

    # Regulatory documents folder path
    regulatory_folder = PROJECT_ROOT / "Knowledgebase" / "1stDataKnowledge"

    if not regulatory_folder.exists():
        logger.error(f"Regulatory folder not found: {regulatory_folder}")
        sys.exit(1)

    # Count files
    all_files = list(regulatory_folder.glob("**/*"))
    doc_files = [f for f in all_files if f.is_file() and f.suffix.lower() in [".pdf", ".docx", ".doc", ".txt"]]

    logger.info("=" * 60)
    logger.info("DB1 REGULATORY DOCUMENT INGESTION")
    logger.info("=" * 60)
    logger.info(f"Source folder: {regulatory_folder}")
    logger.info(f"Total document files: {len(doc_files)}")
    logger.info("")

    # List subfolders
    subfolders = [d for d in regulatory_folder.iterdir() if d.is_dir()]
    for sf in sorted(subfolders):
        sf_files = list(sf.glob("**/*"))
        sf_docs = [f for f in sf_files if f.is_file() and f.suffix.lower() in [".pdf", ".docx", ".doc", ".txt"]]
        logger.info(f"  📁 {sf.name}: {len(sf_docs)} documents")
    logger.info("")

    # Initialize Letta service
    logger.info("Connecting to Letta server...")
    letta = LettaService()

    if args.recreate:
        # Recreate archive from scratch
        logger.info("=" * 60)
        logger.info("Recreating db1_regulatory archive with Ollama embeddings...")
        logger.info("=" * 60)
        letta.recreate_archive(
            "db1_regulatory",
            "Official EU GMP regulatory documents: EudraLex, EMA, ICH, WHO, Ph.Eur."
        )
    else:
        # Ensure archive exists
        letta.ensure_archives()

    # Ingest regulatory folder
    logger.info("=" * 60)
    logger.info("Ingesting regulatory documents into db1_regulatory...")
    logger.info("=" * 60)

    tag_fn = create_tag_fn(regulatory_folder)

    stats = letta.ingest_folder(
        archive_name="db1_regulatory",
        folder_path=str(regulatory_folder),
        tag_fn=tag_fn,
        recursive=True,
    )

    # Print results
    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total files found:     {stats.get('total', 0)}")
    logger.info(f"Files ingested:        {stats.get('ingested', 0)}")
    logger.info(f"Passages created:      {stats.get('passages', 0)}")
    logger.info(f"Files skipped:         {stats.get('skipped', 0)}")
    logger.info(f"Errors:                {stats.get('errors', 0)}")
    logger.info("=" * 60)

    if stats.get("errors", 0) > 0:
        logger.warning("Some files failed to ingest. Check logs above for details.")
        sys.exit(1)

    logger.info("All regulatory documents successfully ingested into Letta DB1 archive!")
    logger.info("")
    logger.info("You can now use the dual-database RAG search:")
    logger.info("  - DB1 (db1_regulatory): Official regulatory documents")
    logger.info("  - DB2 (db2_entity_qms): Entity operational examples")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Re-ingest Entity 1 into Letta DB2 Archive

Clears the existing db2_entity_qms archive and re-ingests all files from
the anonymized Entity 1 folder.

Usage:
    python scripts/reingest_entity_1.py
"""

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


def main():
    # Entity 1 folder path
    entity_1_folder = PROJECT_ROOT / "Knowledgebase" / "2ndDataKnowledge" / "Entity 1"

    if not entity_1_folder.exists():
        logger.error(f"Entity 1 folder not found: {entity_1_folder}")
        sys.exit(1)

    logger.info(f"Entity 1 folder: {entity_1_folder}")
    logger.info("=" * 60)

    # Initialize Letta service
    logger.info("Connecting to Letta server...")
    letta = LettaService()

    # Recreate DB2 archive with current embedding model (Ollama)
    logger.info("=" * 60)
    logger.info("Recreating db2_entity_qms archive with Ollama embeddings...")
    logger.info("=" * 60)
    letta.recreate_archive("db2_entity_qms", "Previous entity QMS documents (Entity 1 - anonymized)")

    # Ensure DB1 archive exists too (for dual search)
    letta.ensure_archives()

    # Re-ingest Entity 1 folder
    logger.info("=" * 60)
    logger.info("Re-ingesting Entity 1 folder into db2_entity_qms...")
    logger.info("=" * 60)

    def tag_fn(file_path: Path):
        """Generate tags for Entity 1 files."""
        tags = ["entity:entity_1", "source:entity_qms"]
        # Add folder-based tags
        rel_path = file_path.relative_to(entity_1_folder)
        if len(rel_path.parts) > 1:
            folder = rel_path.parts[0]
            tags.append(f"category:{folder.lower()}")
        return tags

    stats = letta.ingest_folder(
        archive_name="db2_entity_qms",
        folder_path=str(entity_1_folder),
        tag_fn=tag_fn,
        recursive=True,
    )

    # Print results
    logger.info("=" * 60)
    logger.info("RE-INGESTION COMPLETE")
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

    logger.info("All anonymized Entity 1 files successfully re-ingested into Letta DB2 archive!")


if __name__ == "__main__":
    main()

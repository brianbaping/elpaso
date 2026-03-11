"""Rebuild the Qdrant collection from scratch — drop, re-ingest all sources."""

import os
import subprocess
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.ingestion_tracker import IngestionTracker
from pipeline.logger import get_logger
from pipeline.store import VectorStore

import yaml

logger = get_logger("el_paso.rebuild")


def main():
    load_dotenv()

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    collection_name = config["qdrant"]["collection_name"]
    qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))

    store = VectorStore(collection_name=collection_name, host=qdrant_host, port=qdrant_port)
    tracker = IngestionTracker()

    # Drop collection
    logger.info(f"Dropping collection '{collection_name}'...")
    try:
        store.delete_collection()
        logger.info("  Collection dropped")
    except Exception:
        logger.info("  No existing collection to drop")

    # Clear ingestion state
    tracker.clear()
    logger.info("Ingestion state cleared")

    # Re-run all ingestion scripts
    scripts = [
        ("Confluence", "scripts/ingest_confluence.py"),
        ("GitHub Docs", "scripts/ingest_github_docs.py"),
        ("GitHub Code", "scripts/ingest_github_code.py"),
    ]

    python = sys.executable
    for name, script in scripts:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {name} ingestion...")
        logger.info(f"{'='*50}")
        result = subprocess.run(
            [python, script],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if result.returncode != 0:
            logger.error(f"{name} ingestion failed with exit code {result.returncode}")

    # Final status
    logger.info(f"\n{'='*50}")
    logger.info("Rebuild complete")
    try:
        store = VectorStore(collection_name=collection_name, host=qdrant_host, port=qdrant_port)
        info = store.collection_info()
        logger.info(f"Collection: {info['name']} | Points: {info['points_count']} | Status: {info['status']}")
    except Exception as e:
        logger.error(f"Could not read collection info: {e}")


if __name__ == "__main__":
    main()

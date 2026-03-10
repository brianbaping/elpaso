"""Ingest GitHub docs, issues, and PRs — fetch, chunk, embed, store in Qdrant."""

import os
import sys

import yaml
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.github_docs import GitHubDocsConnector
from connectors.github_issues import GitHubIssuesConnector
from pipeline.chunker import chunk_text
from pipeline.embedder import Embedder
from pipeline.store import VectorStore


def ingest_docs(connector, embedder, store, chunk_size, chunk_overlap):
    """Ingest README and /docs markdown files."""
    print("\n--- GitHub Docs ---")
    docs = connector.fetch_docs()
    print(f"Found {len(docs)} doc files across matching repos")

    total = 0
    errors = 0
    for doc in docs:
        try:
            chunks = chunk_text(doc.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            if not chunks:
                continue

            texts = [chunk.text for chunk in chunks]
            vectors = embedder.embed_batch(texts)
            store.ensure_collection(vector_size=len(vectors[0]))

            payloads = [
                {
                    "source_type": "github_docs",
                    "repo_name": doc.repo_name,
                    "repo_url": doc.repo_url,
                    "file_path": doc.file_path,
                    "heading_context": chunk.heading_context,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": len(chunks),
                    "text": chunk.text,
                }
                for chunk, _ in zip(chunks, vectors)
            ]

            count = store.upsert_chunks(vectors, payloads)
            total += count
            print(f"  [{doc.repo_name}/{doc.file_path}] → {count} chunks")
        except Exception as e:
            errors += 1
            print(f"  [{doc.repo_name}/{doc.file_path}] → ERROR: {e}")

    return total, errors


def ingest_issues_and_prs(connector, embedder, store, chunk_size, chunk_overlap):
    """Ingest issues and merged PRs."""
    print("\n--- GitHub Issues ---")
    issues = connector.fetch_issues()
    print(f"Found {len(issues)} issues across matching repos")

    print("\n--- GitHub PRs ---")
    prs = connector.fetch_merged_prs()
    print(f"Found {len(prs)} merged PRs across matching repos")

    all_items = issues + prs
    total = 0
    errors = 0

    for item in all_items:
        try:
            chunks = chunk_text(item.body, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            if not chunks:
                continue

            texts = [chunk.text for chunk in chunks]
            vectors = embedder.embed_batch(texts)
            store.ensure_collection(vector_size=len(vectors[0]))

            number_key = "issue_number" if item.source_type == "github_issue" else "pr_number"
            payloads = [
                {
                    "source_type": item.source_type,
                    "repo_name": item.repo_name,
                    "repo_url": item.repo_url,
                    number_key: item.number,
                    "title": item.title,
                    "author": item.author,
                    "last_modified": item.last_modified,
                    "heading_context": chunk.heading_context,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": len(chunks),
                    "text": chunk.text,
                }
                for chunk, _ in zip(chunks, vectors)
            ]

            count = store.upsert_chunks(vectors, payloads)
            total += count
            label = f"#{item.number}" if item.source_type == "github_issue" else f"PR#{item.number}"
            print(f"  [{item.repo_name} {label}] {item.title} → {count} chunks")
        except Exception as e:
            errors += 1
            print(f"  [{item.repo_name} #{item.number}] → ERROR: {e}")

    return total, errors


def main():
    load_dotenv()

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    github_token = os.environ.get("GITHUB_TOKEN")
    github_org = os.environ.get("GITHUB_ORG")
    if not all([github_token, github_org]):
        print("ERROR: Set GITHUB_TOKEN and GITHUB_ORG in .env")
        sys.exit(1)

    repo_prefix = config.get("github", {}).get("repo_prefix", "")
    lookback_months = config.get("github", {}).get("issue_lookback_months", 12)
    chunk_size = config.get("chunking", {}).get("chunk_size", 512)
    chunk_overlap = config.get("chunking", {}).get("chunk_overlap", 50)
    embed_model = config["embedding"]["model"]
    collection_name = config["qdrant"]["collection_name"]
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))

    docs_connector = GitHubDocsConnector(github_token, github_org, repo_prefix)
    issues_connector = GitHubIssuesConnector(github_token, github_org, repo_prefix, lookback_months)
    embedder = Embedder(model=embed_model, ollama_url=ollama_url)
    store = VectorStore(collection_name=collection_name, host=qdrant_host, port=qdrant_port)

    doc_chunks, doc_errors = ingest_docs(docs_connector, embedder, store, chunk_size, chunk_overlap)
    issue_chunks, issue_errors = ingest_issues_and_prs(issues_connector, embedder, store, chunk_size, chunk_overlap)

    total_chunks = doc_chunks + issue_chunks
    total_errors = doc_errors + issue_errors

    print(f"\nDone: {doc_chunks} doc chunks + {issue_chunks} issue/PR chunks = {total_chunks} total")
    if total_errors:
        print(f"  ({total_errors} items failed — see errors above)")

    info = store.collection_info()
    print(f"Collection: {info['name']} | Points: {info['points_count']} | Status: {info['status']}")


if __name__ == "__main__":
    main()

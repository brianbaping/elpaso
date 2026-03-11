# El Paso — Operations Runbook

## Prerequisites

- **Ollama** running with `qwen3:30b-a3b` and `nomic-embed-text` models
- **Qdrant** running via Docker (`docker compose up -d`)
- **Python venv** activated (`source .venv/bin/activate`)
- **`.env`** file with Confluence and GitHub credentials

## Running Ingestion

### Full Rebuild (from scratch)

Drops the collection, clears ingestion state, and re-ingests everything:

```bash
python scripts/rebuild_collection.py
```

This takes 60-90 minutes due to GitHub API rate limits.

### Incremental Ingestion (recommended)

Only processes new or changed content:

```bash
python scripts/ingest_confluence.py
python scripts/ingest_github_docs.py
python scripts/ingest_github_code.py
```

Each script tracks `last_modified` timestamps and content hashes in `ingestion_state.json`. Unchanged items are skipped automatically.

### Single Source Re-ingestion

To force a full re-ingest of one source without rebuilding everything:

```python
from pipeline.ingestion_tracker import IngestionTracker
tracker = IngestionTracker()
tracker.clear("confluence")  # or "github_docs", "github_code", "github_issue", "github_pr"
tracker.save()
```

Then re-run the corresponding script.

## Checking System Health

### Qdrant

```bash
# Collection status
python -c "
from pipeline.store import VectorStore
s = VectorStore()
print(s.collection_info())
"

# Docker container status
docker compose ps
docker compose logs --tail 20
```

### Ollama

```bash
# List models
ollama list

# Health check
curl http://localhost:11434/api/tags
```

### Smoke Test

```bash
python smoke_test.py
```

## Logs

Structured JSON logs are written to `logs/elpaso-YYYY-MM-DD.jsonl`. Each ingestion run logs:

- Source type, items processed/skipped/failed
- Duration
- Query execution (question, scope, result count, latency)

## Troubleshooting

### "Connection refused" on Qdrant
```bash
docker compose up -d
```

### "Model not found" on Ollama
```bash
ollama pull qwen3:30b-a3b
ollama pull nomic-embed-text
```

### Embedding 400 errors
Some content causes Ollama embedding failures (very long text, binary content). The embedder truncates at 30K chars and falls back to one-at-a-time embedding. These errors are logged but don't stop the ingestion.

### Stale/duplicate data
Run a full rebuild:
```bash
python scripts/rebuild_collection.py
```

### LLM timeout
Qwen3 30B can be slow on large prompts. The timeout is set to 300 seconds. If it consistently times out, consider reducing `top_k` in `config.yaml` to send fewer context chunks.

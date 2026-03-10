# El Paso

## Organizational Knowledge RAG System — Project Roadmap & Architecture Reference

---

## Executive Summary

El Paso is a locally-hosted RAG (Retrieval-Augmented Generation) system that ingests organizational knowledge from multiple sources — Confluence and GitHub repositories — and exposes that knowledge through an MCP (Model Context Protocol) server. The MCP server acts as an intelligent question-answering layer, allowing any AI host (Claude, Cursor, etc.) to query institutional knowledge with grounded, source-attributed answers.

The system is designed for a manufacturing-focused microservices environment built on C# / .NET, RabbitMQ, PostgreSQL, and Blazor. It prioritizes the shared contracts library and domain services as the primary knowledge sources, with Confluence providing process and project context.

---

## Architecture Overview

The system consists of four main layers:

1. **Ingestion Layer** — Connectors for each source that crawl and extract raw content on a weekly schedule
2. **Processing Layer** — Chunking, embedding, and storage into a vector database
3. **Retrieval & Synthesis Layer** — Query handling, semantic search, and LLM-powered answer generation
4. **MCP Server Layer** — Exposes intelligent Q&A tools to any AI host via the Model Context Protocol

---

## Recommended Technology Stack

| Component | Technology |
|---|---|
| Local LLM Runtime | Ollama with Qwen3 (30B-A3B MoE recommended) |
| Embedding Model | nomic-embed-text or mxbai-embed-large (via Ollama) |
| Vector Database | Qdrant (Docker container) |
| RAG Orchestration | LlamaIndex (Python) |
| Code Parser | Tree-sitter (C#, Java, TypeScript, Python grammars) |
| MCP Server | Python MCP SDK (official) |
| Pipeline Scheduler | cron / Windows Task Scheduler |
| Source APIs | Confluence REST API, GitHub REST API |

---

## Roadmap Overview

| Phase | Title | Summary |
|---|---|---|
| Phase 0 | Foundation & Infrastructure | Set up local infrastructure, validate toolchain, establish project skeleton |
| Phase 1 | Confluence Ingestion — End-to-End Pipeline | Build the full pipeline with Confluence as the first source. Validate chunking, embedding, storage, and basic retrieval. |
| Phase 2 | GitHub Ingestion — Docs & Issues | Index GitHub READMEs, PR descriptions, and issue text from the 20 target repositories. |
| Phase 3 | GitHub Ingestion — Source Code | Index C# source code using Tree-sitter, with class-level chunking and context headers for SOLID-pattern codebases. |
| Phase 4 | MCP Server — Intelligent Q&A | Build and expose the MCP server with synthesized, source-attributed answers. Connect to Claude and validate end-to-end. |
| Phase 5 | Hardening & Optimization | Query quality tuning, metadata filtering, scheduling automation, monitoring, and documentation. |

---

## Phase Details

### Phase 0 — Foundation & Infrastructure

Establish the local development environment and validate that all key components can communicate before any real data is processed. Failures here are cheap; failures in Phase 3 are expensive.

**Goals**

- Ollama running with Qwen3 model loaded and responding
- Qdrant running in Docker, accessible via Python client
- Embedding model validated (nomic-embed-text or mxbai-embed-large)
- Basic round-trip test: embed a sentence, store in Qdrant, query it back
- Project repository initialized with folder structure
- API credentials obtained and tested for Confluence and GitHub

**Key Deliverables**

- `docker-compose.yml` for Qdrant
- `requirements.txt` with pinned dependencies
- `config.yaml` / `.env` template for all API keys and endpoints
- `smoke_test.py` — validates the full local stack

**Decisions to Make**

- Qwen3 model variant — 30B-A3B MoE (recommended) vs smaller/larger
- Qdrant collection naming strategy
- Project language/runtime — Python 3.11+ recommended

---

### Phase 1 — Confluence Ingestion (End-to-End Pipeline)

Confluence is the most structured source and the best one to validate the full pipeline with. By the end of this phase, a Confluence page should be queryable via a Python script.

**Goals**

- Fetch all Confluence pages via REST API (handle pagination)
- Extract clean text (strip HTML/wiki markup)
- Chunk pages into semantically meaningful segments (~500 token target)
- Generate embeddings for each chunk
- Store chunks + embeddings + metadata in Qdrant
- Basic semantic search query returns relevant Confluence content

**Metadata to Capture Per Chunk**

- `source_type`: `'confluence'`
- `page_title`, `page_url`, `space_key`
- `last_modified` date
- `author` (optional)

**Key Deliverables**

- `connectors/confluence.py` — Confluence crawler
- `pipeline/chunker.py` — text chunking logic
- `pipeline/embedder.py` — embedding wrapper around Ollama
- `pipeline/store.py` — Qdrant upsert logic
- `scripts/ingest_confluence.py` — runnable ingestion script
- `scripts/query_test.py` — basic semantic search validation

**Notes**

Use LlamaIndex's ConfluenceReader if available for your version — it handles auth and pagination. Otherwise the REST API is straightforward. Handle rate limiting with exponential backoff.

---

### Phase 2 — GitHub Ingestion (Docs & Issues)

Index the prose layer of GitHub — READMEs, PR descriptions, issue text, and wiki pages if present. This gives the El Paso context about each repository's purpose and history without the complexity of code parsing.

**Goals**

- Enumerate all repos in the target GitHub organization (filtered to the 20 POC repos)
- Fetch and index README.md and any `/docs` folder content
- Fetch open and recently-closed issues (title + body + comments)
- Fetch merged PR descriptions (good source of 'why' context)
- Store with repository-scoped metadata

**Metadata to Capture Per Chunk**

- `source_type`: `'github_docs'` or `'github_issue'` or `'github_pr'`
- `repo_name`, `repo_url`
- `file_path` (for docs), `issue_number` or `pr_number`
- `title` (always included as context)

**Key Deliverables**

- `connectors/github_docs.py` — README and docs crawler
- `connectors/github_issues.py` — issues and PRs crawler
- `scripts/ingest_github_docs.py`

**Notes**

Use PyGithub or the GitHub REST API directly. Respect rate limits (5000 requests/hour authenticated). For the POC, limit issue history to issues updated in the last 12 months to keep volume manageable.

---

### Phase 3 — GitHub Ingestion (Source Code)

This is the most technically complex phase. Source code is the ground truth of the system, but it requires language-aware parsing to chunk meaningfully. The primary language is C# (~80%), with secondary support for Java, TypeScript, and Python.

**Goals**

- Parse C# source files using Tree-sitter, chunking at class/method boundaries
- Generate context headers for each code chunk (namespace, class, method signature)
- Handle interface → implementation stitching for SOLID-pattern codebases
- Priority-index the shared contracts library first
- Index remaining repos using the same pipeline
- Support secondary languages (Java, TypeScript, Python) with language-specific Tree-sitter grammars

**C# Chunking Strategy**

For each `.cs` file, Tree-sitter extracts the syntax tree. The recommended chunking approach:

- Chunk at the class level for small, focused classes (typical in 12-factor services)
- For larger classes, chunk at the method level with a context header prepended
- Context header format: `// Namespace: X / // Class: Y : IY / // Method: Z`
- Include the class constructor signature in method-level chunks where possible
- Capture interface definitions and link them to their implementations via metadata

**Metadata to Capture Per Chunk**

- `source_type`: `'github_code'`
- `repo_name`, `file_path`, `language`
- `namespace`, `class_name`, `method_name` (where applicable)
- `is_interface`: true/false
- `implements_interface` (for concrete classes)

**Key Deliverables**

- `connectors/github_code.py` — source file fetcher
- `pipeline/code_chunker.py` — Tree-sitter based chunker with language dispatch
- `pipeline/csharp_chunker.py` — C#-specific chunking logic
- `scripts/ingest_github_code.py`

**Notes**

Install tree-sitter and tree-sitter-c-sharp, tree-sitter-java, tree-sitter-typescript, tree-sitter-python via pip. Test the C# parser thoroughly against your actual codebase before committing to the chunking strategy — SOLID patterns with deep inheritance may require tuning.

---

### Phase 4 — MCP Server (Intelligent Q&A)

This is the payoff phase. The MCP server exposes the El Paso as an intelligent question-answering tool to any AI host. From Claude or Cursor's perspective, it looks like a knowledgeable colleague who understands your codebase, processes, and architecture.

**Goals**

- Implement MCP server using the official Python MCP SDK
- Expose a primary tool: `ask_el_paso(question: str)` → answer with sources
- Retrieval pipeline: embed question → semantic search Qdrant → retrieve top-k chunks → synthesize with Qwen3 → return answer + citations
- Optionally expose scoped tools: `ask_about_code()`, `ask_about_process()`
- Validate end-to-end from Claude Desktop or Claude.ai with MCP configured

**MCP Tool Design**

Primary tool signature:

- **Tool name**: `ask_el_paso`
- **Input**: `question` (string), `scope` (optional: `'code'` | `'docs'` | `'all'`)
- **Output**: answer (string) with inline source citations (filename, URL, or repo/file path)

**Synthesis Prompt Strategy**

The LLM synthesis prompt should instruct Qwen3 to: answer based only on the provided context chunks, cite sources for each claim, acknowledge when the context is insufficient, and avoid hallucinating details not present in the retrieved chunks.

**Key Deliverables**

- `mcp_server/server.py` — MCP server entry point
- `mcp_server/tools.py` — tool definitions and handlers
- `mcp_server/retriever.py` — Qdrant query + Qwen3 synthesis pipeline
- `mcp_server/prompts.py` — system and synthesis prompt templates
- README with MCP configuration instructions for Claude Desktop

**Notes**

Start with a single `ask_el_paso` tool and validate quality before adding scoped variants. Source attribution is critical — developers will not trust answers that don't tell them where the information came from.

---

### Phase 5 — Hardening & Optimization

With the full pipeline working, this phase focuses on reliability, answer quality, and operational maturity.

**Goals**

- Automate weekly ingestion via cron or Windows Task Scheduler
- Add incremental ingestion — only re-process changed content
- Tune chunk size and top-k retrieval based on observed answer quality
- Add metadata filtering to Qdrant queries (e.g., restrict to a specific repo or source type)
- Implement basic logging and error reporting for ingestion runs
- Document the system for team onboarding

**Quality Tuning Levers**

- **Chunk size** — smaller chunks = more precise retrieval; larger = more context per chunk
- **top-k** — how many chunks to retrieve (start with 5-8, tune based on answer coherence)
- **Embedding model** — swap out if retrieval quality is poor
- **Reranking** — add a cross-encoder reranker (e.g., ms-marco) for better chunk ranking
- **Hybrid search** — combine semantic + keyword search in Qdrant for better precision on code queries

**Key Deliverables**

- `scripts/run_weekly_ingest.py` — orchestrated ingestion of Confluence + GitHub sources
- Incremental ingest logic using `last_modified` timestamps
- Logging setup (structured logs to file)
- `OPERATIONS.md` — runbook for weekly maintenance
- `TEAM_GUIDE.md` — how to use the MCP server

---

## Future Phases (Post-POC)

| Phase | Title | Summary |
|---|---|---|
| Phase 6 | Microsoft Teams Integration | Index shared Teams channels to capture informal knowledge, decisions made in chat, and meeting notes. Requires Microsoft Graph API access. |
| Phase 7 | Scale to Full GitHub Organization | Expand beyond the 20 POC repositories to the full organization. May require chunking strategy tuning and Qdrant collection partitioning for performance. |
| Phase 8 | Real-time Webhooks | Replace weekly batch with event-driven updates via GitHub and Confluence webhooks. Reduces staleness from 7 days to near-real-time. |
| Phase 9 | Knowledge Graph Layer | Augment RAG with a graph database (e.g., Neo4j) to capture explicit relationships between entities — services, contracts, teams, and tickets. Enables richer cross-system queries. |

---

## Notes for Claude Code Engagement

When engaging Claude Code to implement any phase, provide the following context:

- This document as the architectural reference
- The specific phase and its goals as the scope
- Your actual Confluence/GitHub org URLs and project keys
- The target 20 repository names for GitHub ingestion
- Any local constraints (OS, network, available RAM for Ollama model selection)

**Suggested Claude Code prompt pattern per phase:**

> "I am building the El Paso RAG system described in [this document]. I am now working on Phase [N]: [Phase Title]. The project skeleton is at [path]. Please implement [specific goal from phase] following the architectural decisions outlined in the document."

**Key files to provide to Claude Code at the start of each session:**

- This roadmap document
- Current `requirements.txt`
- Current `config.yaml` or `.env` template
- Any existing connector or pipeline files already implemented

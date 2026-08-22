# Git for Research

> What if Git had been designed for research instead of source code?

A research-native version control system: typed artifacts (prose, LLM chat exports, PDFs, codebases), content-addressed immutable history, sentence-level semantic diff and 3-way merge, CRDT live collaboration, provenance as a first-class primitive, and version-aware retrieval. No LLM in any correctness path.

**Status: architecture locked, scaffold in place.** Docs live in [`docs/`](docs/):
- [`docs/architecture.md`](docs/architecture.md) — locked system architecture + diagram + layer boundaries
- [`docs/adr/`](docs/adr/) — 14 Architecture Decision Records (object-model, content-addressing, version-graph, diff, merge, crdt, backend, frontend, database, realtime-protocol, retrieval, provenance, deployment, ai-integration)
- [`docs/data-model.md`](docs/data-model.md) — exact schemas + core invariants
- [`docs/specs/`](docs/specs/) — API contract, realtime protocol, versioning/diff/merge/collaboration/provenance/retrieval/ingestion specs
- [`docs/planning/`](docs/planning/) — 12h execution plan, mvp/target/stretch, testing plan, failure playbook, ownership matrix
- [`docs/demo/`](docs/demo/) — demo script, judge Q&A

## Quick start
```bash
bash scripts/setup.sh        # venv, deps, model download, gr init
uvicorn backend.src.api.main:app --port 8377
# CLI: python -m backend.src.cli init|commit|log|branch|checkout|diff|merge|verify|ingest
```

## The 30-second story
Three layers, none an LLM wrapper:
1. **Object model** — typed, content-addressed DAG (SHA-256 blobs, merkle commits) over *canonicalized* research artifacts. One history for prose+chat+PDF+code.
2. **Semantic layer** — one deterministic alignment engine (LCS over sentence hashes for prose; tree-sitter for code) shared by diff, 3-way merge, and retrieval delta-indexing.
3. **Concurrency layer** — pycrdt (server) ↔ yjs (browser) CRDT live drafts that become immutable DAG commits; real conflicts surface at branch-merge as sentence-level conflict cards.

## Security posture (honest scope)
Protected: path traversal in ingestion (paths normalized+contained), blob tamper detection (`gr verify`), parameterized SQL only. Deliberately out of scope (per brief): auth (mock `X-User` header), untrusted-content sanitization beyond parser defensiveness, prompt-injection handling for imported docs (no LLM consumes them in correctness paths), WS authorization. Secrets: none required; no API keys needed to run.

## AI usage
Boilerplate (scaffolding, parsers, UI components, tests) is agent-generated under human-owned specs per ADR-14 + ownership-matrix.md. All algorithms are deterministic, human-reviewed, and covered by invariant tests.

# ReGit

> What if Git had been designed for research instead of source code?

A research-native version control system: typed artifacts (prose, LLM chat exports, PDFs, codebases), content-addressed immutable history, sentence-level semantic diff and 3-way merge, CRDT live collaboration, provenance as a first-class primitive, and version-aware retrieval. No LLM in any correctness path.

**Status: 4/4 pillars implemented, tested, live-verified.** Backend all-green (90 unit + 31 integration tests), React frontend integrated, live server E2E-verified. Docs live in [`docs/`](docs/):
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

## What was & wasn't completed

**Completed (all four mandatory pillars + stretch):**
- ✅ **Ingestion** — Markdown, ChatGPT (`conversations.json`), Claude export, PDF, codebase directory; structure-preserving canonical payloads, content-addressed dedup.
- ✅ **Versioning** — content-addressed immutable DAG (SHA-256 blobs + merkle commits), branches (mutable refs to immutable commits), merge-base (BFS LCA), **sentence-level semantic diff** (LCS over sentence hashes, move detection), **true 3-way prose merge** with Git-exact conflict semantics.
- ✅ **Concurrency** — pycrdt ↔ yjs CRDT live drafts per (artifact, branch), persisted op log, reconnect/dup/out-of-order convergence, live presence, commit-from-live to a DAG commit.
- ✅ **Retrieval** — per-kind chunkers, delta-reindex on commit (only changed chunks), hybrid FTS5 BM25 + Chroma kNN, version/`as_of_commit` provenance filter, cited results, offline after one-time model download.
- ✅ **Stretch** — 3-way prose merge **with conflict-resolution UI** (two branches editing the same sentence → one conflict card → resolve → 2-parent merge commit); provenance chain (claim→commit→artifact→source); time-travel query.

**Deliberately not completed (per brief / out of scope):**
- ❌ Full auth/user management — mock `X-User` header only.
- ❌ OCR, custom vector DB — text-extractable PDFs only; Chroma is embedded, not self-built.

## What we'd build next, given more time

ReGit's next chapter is treating research as a *claim graph*, not just a version tree. Today every claim carries its lineage ("this sentence derives from that chat turn, via this commit"), but it's read-only metadata. With more time we'd make that lineage *actionable*: (1) **cross-artifact propagation** — when a source PDF's extracted claim changes, automatically identify and flag every downstream doc that cited it, with a one-click "re-verify" diff; (2) **semantic merge at the claim level** — resolve conflicting claims by their *sources* (ours-cites-ChatGPT, theirs-cites-a-paper) rather than just their text, using provenance to suggest the higher-confidence side; (3) **agent branches** — let an LLM draft a hypothesis on its own branch and submit it for human merge review, so the CRDT lock + 3-way merge become the review boundary; and (4) **true historical rewind** on retrieval (literal byte-content of a section as of commit X, not just "claims introduced by X"). The invariants and one-spine design are already in place to carry these without rearchitecting.

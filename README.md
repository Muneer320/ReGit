# Git for Research

> **What if Git had been designed for research instead of source code?**

A research-native version control system. Treats research artifacts — Markdown/plaintext docs, ChatGPT & Claude chat exports, PDFs, and codebases — as **first-class immutable, versioned objects** with semantic diffing, three-way prose merge, CRDT-based concurrent editing, and **first-class research provenance**.

Built and judged in a **13-hour overnight hackathon**. See [`docs/`](docs/) for the full architecture, ADRs, data model, and specs.

---

## The problem it solves

Research lives fragmented across Google Docs, folders of PDFs, GitHub repos, and throwaway LLM conversations. There is no shared history, no diffing, no branching, and no way for collaborators to work on the same evolving body of knowledge without overwriting each other.

**Git solved this for code. Nobody solved it for research.**

The key insight: a research artifact is *not* a file tree. It's prose with meaning, chat threads with turn structure, PDFs with layout, and claims with provenance. Slapping a byte-diff on top of a Git repo loses exactly the information research depends on. This system is built for that — not "Git + an LLM wrapper."

---

## Core capabilities

| Pillar | What it does | Why it's technically real |
|---|---|---|
| **Ingestion** | Markdown, ChatGPT `conversations.json`, Claude exports, PDF text layers, codebases — each preserved in its native structure, **never flattened to a string** | Per-format canonicalizers emit typed payloads + provenance edges |
| **Versioning** | Content-addressed, append-only object store: SHA-256 typed blobs, merkle trees, immutable commits, mutable branch refs over an immutable DAG | `object_id == SHA256(canonical_content)`; DB triggers forbid UPDATE/DELETE |
| **Semantic diff** | Prose → sentence/paragraph LCS alignment; code → tree-sitter function-level; chat → message-level; PDF → per-page prose alignment | One deterministic alignment engine shared by diff, merge, and retrieval reindex |
| **Three-way merge** | Merge-base (LCA), per-sentence decision table, **first-class conflict records** + conflict-resolution UI | 3-way prose merge is the *one* deep stretch goal |
| **Concurrency** | pycrdt (server) ↔ Yjs (browser) CRDT over WebSocket; live presence; commit-from-live snapshots the CRDT text into a DAG commit | CRDT convergence is a property, not a promise — proof + persisted update log per room |
| **Retrieval** | Hybrid Chroma (MiniLM-L6-v2 embeddings) + SQLite FTS5, **delta-reindexed per commit**, filtered by version/provenance, returning cited hits | Retrieval understands research *history*, not just a snapshot |
| **Provenance** | First-class `claims` + `provenance_edges` + sentence lineage. Answers: *"where did this claim come from?"*, *"what was known at commit X?"*, *"which sources influenced this doc?"* | Provenance is a technical primitive, not metadata sprinkled on top |

---

## Why this is not "Git + an LLM wrapper"

- **No LLM in any correctness path.** Diff, merge, and retrieval are deterministic algorithms. (LLMs are an optional *ingestion/claim-extraction* accelerator, never a correctness dependency.) That fact is the anti-wrapper story.
- **Research-native object model.** Per-artifact-kind are semantic units (sentences, turns, functions), not lines.
- **One alignment engine, three payoffs** — diff, merge, and delta-reindex all consume the same tested primitive instead of three bolted-on heuristics.

---

## Architecture (one-line)

A single Python 3.11 / FastAPI process owns a content-addressed object store + per-type engines (diff/merge/ingestion/retrieval/provenance) + an in-process pycrdt CRDT relay + a static vanilla-JS client — everything embedded in one `data/` dir so the demo runs fully offline with `uvicorn` alone.

Full diagram + layer boundaries: [`docs/architecture.md`](docs/architecture.md)

```

┌────────────── Browser (vanilla JS, no build) ──────────────┐
│  yjs Y.Text · presence · diff view · conflicts · search    │
└────────────────────────┬───────────────────────────────────┘
                         │ REST / WebSocket
┌─────────────────────── ▼ ── FastAPI (one process) ─────────┐
│  api/  realtime/  core/{objects,versioning,diff,merge,     │
│        collaboration}  ingestion/  retrieval/  provenance/ │
└───────┬──────────────┬───────────────┬─────────────────────┘
        ▼              ▼               ▼
  data/objects/   data/meta.db     data/vectordb (Chroma)
   (zlib blobs)   (SQLite WAL)     (+ data/models MiniLM)
```

---

## Repository layout

```
backend/
  src/
    api/         REST endpoints
    core/        objects · versioning · diff · merge · collaboration
    ingestion/   markdown · chatgpt · claude · pdf · codebase
    retrieval/   chunkers · vector · fts5 · reindex · query
    provenance/  claims · edges · sentence lineage
    realtime/    pycrdt-websocket relay · awareness · commit-from-live
    db/ ws/
frontend/src/    static vanilla-JS client (no build step)
tests/           unit · integration · concurrency · adversarial
docs/            architecture · ADRs · data model · specs
scripts/         fixtures · demo setup
shared/          shared type definitions
```

---

## Documentation index

- [`docs/architecture.md`](docs/architecture.md) — locked architecture + diagram + layer boundaries
- [`docs/adr-*.md`](docs/adr-01-object-model.md) — 14 Architecture Decision Records
- [`docs/data-model.md`](docs/data-model.md) — exact schemas + core invariants
- Specs: [`versioning`](versioning-spec.md) · [`diff`](diff-spec.md) · [`merge`](merge-spec.md) · [`collaboration`](collaboration-spec.md) · [`provenance`](provenance-spec.md) · [`retrieval`](retrieval-spec.md) · [`ingestion`](ingestion-spec.md) · [`api-contract`](api-contract.md) · [`realtime-protocol`](realtime-protocol.md)
- Planning: [`12h-execution-plan`](12h-execution-plan.md) · [`mvp-target-stretch`](mvp-target-stretch.md)

> **Status:** architecture locked; engineering in progress. This is a hackathon build — expect the object store, alignment engine, and merge core to land first, with the collaboration layer and retrieval hard on their heels.

---

## License

MIT — see [`LICENSE`](LICENSE).
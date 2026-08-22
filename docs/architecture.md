# Architecture (LOCKED)

**One-paragraph form:** A Python 3.11 backend owns a content-addressed, append-only object store (SHA-256 typed blobs, merkle trees, 2-parent-capable commits, mutable branch refs over an immutable DAG). On top of it sit per-artifact-type engines: sentence/paragraph alignment diff for prose (custom LCS over normalized sentence hashes), tree-sitter function-level diff for code, message-level diff for canonical chat threads, structural diff for PDF text layers. The same alignment engine drives a 3-way prose merge with sentence-level conflict records (the ONE deep stretch, with a conflict-resolution UI). Live collaboration runs on pycrdt (server) ↔ yjs (browser) CRDT over WebSocket; committing a live draft snapshots the CRDT text into a DAG commit under a per-artifact lock. Retrieval is hybrid: Chroma (embedded, MiniLM-L6-v2 embeddings, delta-reindexed per commit by the diff engine) + SQLite FTS5, filtered by version/provenance metadata, returning cited hits. Everything lives in one `data/` dir; one FastAPI process serves REST + WS + static client.

## Diagram (supersedes the brief's reference: CRDT server integrated into backend; vector store embedded, not a separate service; sentence-index is a first-class store alongside the object store)

```
┌───────────────────────────── Browser (vanilla JS, no build) ─────────────────────────────┐
│  yjs Y.Text + y-websocket provider  │ presence UI │ diff view │ conflict cards │ search  │
└───────────────┬─────────────────────────────── REST / WS ───────────────────┬───────────┘
                │                                                             │
┌───────────────▼──────────────── FastAPI backend (one process) ──────────────▼───────────┐
│  api/        REST: artifacts, commits, branches, diff, merge, ingest, search            │
│  realtime/   WS: pycrdt-websocket relay + awareness, per-doc rooms, commit-from-live    │
│  core/objects      Blob/Tree/Commit/Branch — SHA-256 content addressing, append-only    │
│  core/versioning   DAG walk, merge-base (lowest common ancestor), refs, checkout        │
│  core/diff         align.py (prose LCS) · code_ts.py (tree-sitter) · chat.py · pdf.py   │
│  core/merge        three_way.py (prose sentence-level) · file-level for code/chat/pdf   │
│  core/collaboration pycrdt doc registry, per-artifact commit lock, snapshot→commit      │
│  ingestion/  md · chatgpt · claude · pdf · codebase  → canonical forms → blobs          │
│  retrieval/  chunkers per type · Chroma embedded · FTS5 · delta reindex · hybrid query  │
│  provenance/ claims, edges (source→artifact→version→commit→claim), sentence lineage   │
└───────┬──────────────────┬───────────────────────┬──────────────────────────────────────┘
        │                  │                       │
┌───────▼───────┐  ┌───────▼────────┐  ┌───────────▼────────────┐
│ data/objects/ │  │ data/meta.db   │  │ data/vectordb (Chroma) │
│ zlib blobs by │  │ SQLite WAL:    │  │ embedded, persistent   │
│ hash prefix   │  │ objects index, │  │ + data/models (MiniLM) │
└───────────────┘  │ commits, refs, │  └────────────────────────┘
                   │ sentence_index,│
                   │ chunks, claims,│
                   │ provenance_edge│
                   └────────────────┘
```

## Layer responsibilities & boundaries

1. **Object store (core/objects).** The ONLY writer of blobs/trees/commits. Content-addressed, dedup, zlib on disk, SQLite index. Triggers forbid UPDATE/DELETE on `objects`/`commits`.
2. **Versioning (core/versioning).** Refs, checkout, DAG traversal, merge-base (LCA on the commit DAG), branch create/fork. Never parses content — works on hashes and trees.
3. **Diff (core/diff).** Dispatches by artifact kind. Prose: paragraph split → sentence split → normalize+hash → LCS alignment → edited-vs-added/deleted via similarity ≥0.7. Code: tree-sitter function/class extraction, match by signature, token-stream compare, Myers line-diff inside changed function bodies only. Chat: align by message ordinal+role, compare text. PDF: page→paragraph blocks, then prose alignment per page. ALL diffs emit the same `SentenceChange`-style record list (see data-model.md).
4. **Merge (core/merge).** 3-way: base = merge-base commit's artifact content; align(base,ours)+align(base,theirs); per-sentence decision table; conflicts as first-class records; resolution → merge commit with 2 parents. Code/chat/pdf merge = file/message-level conflict detection + markers (per the brief's "merging OR surfacing conflicts" floor).
5. **Collaboration (core/collaboration + realtime).** One pycrdt `Doc` per (artifact, branch) draft. WS relay via pycrdt-websocket; awareness relay for presence. Commit-from-live: acquire per-artifact asyncio lock → `doc.get_text()` → canonicalize → commit → broadcast new head. Convergence guarantee = CRDT property + persisted update log per room (reconnect = state vector sync).
6. **Ingestion.** Each adapter produces a canonical typed payload + a `ResearchSource` row + provenance edge `source→artifact`. Never flatten: chat stays a message list, PDF keeps page structure, code stays a file tree.
7. **Retrieval.** Commit hook: diff(parent, child) → changed sentence ids → delete/upsert only affected chunks → Chroma + FTS5. Query: FTS5 prefilter/union + vector kNN → filter by branch/commit-ancestry/provenance → rerank (vector score, recency of introduction, source diversity) → hits carry `{artifact, commit introduced_in, sid_range, source}` citations.
8. **Provenance.** First-class tables (`claims`, `provenance_edges`) + sentence lineage in `sentence_index`. Answers: where did this claim come from (edge walk), what was known at commit X (ancestry-filtered chunks), which sources influenced artifact A (reverse edges).
9. **API/Frontend.** REST for everything durable; WS for live docs+presence. Frontend is static vanilla JS: two-pane editor, presence strip, diff view, conflict cards, search with citations.

## Why this shape (decisive points)

- **CRDT inside the backend process**, not a separate service: one process = no cross-service consistency story to defend; pycrdt and the DAG share the commit lock in-process.
- **Alignment engine shared by diff, merge, and delta reindex** — one deterministic primitive, tested once, pays three times. This is the technical spine Muneer owns.
- **Embedded everything** (SQLite, Chroma, vendored yjs): the demo runs with zero network, zero servers beyond `uvicorn`.
- **No LLM in any correctness path** — diff/merge/retrieval are deterministic algorithms; that's the anti-wrapper story.

## Build/scale boundaries (state to judges)

Single-node demo scale: ≤ few hundred artifacts, ≤50MB, ≤10 concurrent editors. Scale-up path named but not built: Postgres+pgvector for metadata/vectors, object store → S3-style, CRDT rooms → Redis-backed provider, tree-sitter grammars per language.

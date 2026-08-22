# Research Report (validation of the locked decisions — with sources)

## 1. CRDT landscape (decision: Yjs)

| Library | Algorithm | Maturity | Editor bindings | Notes |
|---------|-----------|----------|-----------------|-------|
| **Yjs** | YATA | Very high (~920K weekly downloads, 17K+ stars on npm/GitHub); used by Notion, Jupyter, Cargo | **y-prosemirror, y-tiptap (the only mature rich-text bindings), y-codemirror.next, y-monaco, y-quill** | Full ecosystem: y-websocket, y-webrtc, y-indexeddb, y-redis, Hocuspocus server, Liveblocks/PartyKit |
| Automerge | RGA | Medium (~85K downloads); Rust + JS bindings; local-first (Ink & Switch); Git-like change history | Weak (no first-class ProseMirror/TipTap binding) | Slower than Yjs in eg-walker benchmarks; change-hash history model **overlaps with our own commit DAG** (redundant for us) |
| eg-walker / Diamond Types | OT/CRDT hybrid | Research-grade (Gentle & Kleppmann 2024, arXiv:2409.14252); 7–10× faster than reference CRDTs on sequential traces | None | josephg ("CRDTs go brrr", 2024): "[Diamond] does almost none of [binary encoding, presence, editor bindings]" — not production-ready for a 13h build |
| OT (e.g., ShareJS/Firepad) | Operational Transform | Legacy | — | Requires central server + transform functions per op type; no convergence under arbitrary offline interleavings without careful transform composition; effectively superseded for greenfield |

**Why Yjs (technical, not popularity):**
1. The frontend editor is ProseMirror/TipTap (see ADR-08); `y-prosemirror` is the only mature CRDT↔ProseMirror binding. Automerge would force us to write an editor binding or a plain-text area — losing rich-text demo value.
2. Yjs's YATA delete/insert semantics + item-ids give us convergence under offline/reconnect/out-of-order — the exact scenarios in our concurrency tests.
3. Automerge's killer feature (versioned change history as hashed nodes) is *already our job* — a commit DAG. We deliberately separate: **CRDT = present state, Merkle DAG = durable history.** This is the architecture story, not an accident of library choice.
4. Known Yjs risks: update metadata abuse (bounded by our server validation), large-doc GC (we snapshot into commits, bounding doc size), and the y-prosemirror binding still being y-prosemirror@1 (stable since 2020, widely deployed).

## 2. Diff algorithms (decision: per-type registry)

- **Myers** (O(ND)): baseline for everything; implemented in `jsdiff` (npm `diff`, 130M weekly downloads, BSD-3) and Google's `diff-match-patch` (powers Google Docs, 2006–present, Apache-2). jsdiff provides `diffSentences`, `diffWords`, `diffLines`, `diffJson` — matching our per-type strategy needs with zero custom algorithm code for the *token-level* phase.
- **Patience / histogram**: better grouping for code sliders; jsdiff exposes `diffLines` with `newlineIsToken` options and `patienceDiff`. We use patience for code baseline.
- **Structural (AST) diff for code**: difftastic (Wilfred Hughes, MIT, 25.8k stars, 50+ languages via tree-sitter) proves the approach; diffsitter (tree-sitter AST diff) and mergiraf (tree-sitter AST **merge**) exist. We shell out to `difftastic` if the binary installs cleanly (30-min trial) → "structural vs line diff" toggle in demo; otherwise line+word highlight (always works).
- **Sentence-level alignment for prose**: LCS/alignment on sentence units with exact-match anchors + token-overlap similarity fallback (Jaccard) detects insert/delete/**move**/modify. Intra-sentence refinement via `diff-match-patch` (char-level) or jsdiff `diffWords`.
- **Reference**: "SemanticDiff" (vs-code/GitHub) and difftastic both validate that *users and judges understand "semantic" as structure-aware, formatting-insensitive diff* — that is the bar for our demo.

## 3. Three-way merge (decision: unit-level 3-way)

- Git: LCA merge base → diff(base→ours), diff(base→theirs) → apply; conflict iff both changed the same region differently; markers `<<<<<<<`/`=======`/`>>>>>>>`; recursive strategy merges multiple common ancestors (git docs; git-merge man page).
- For prose, line-granularity is the wrong unit (a sentence spans lines; a one-word edit inside a long paragraph is a whole-paragraph "conflict" under line diff). **Unit = sentence for prose, block/line for code, turn for chat, path for JSON** — same 3-way logic, artifact-appropriate units (see merge-spec.md).
- Auto-resolve: only identical-change-on-both-sides resolves automatically; everything else is a surfaced conflict (invariant 6: never silently discard).
- Deterministic demo: fixture documents where both branches edit the same sentence (prose) / same line (code) → guaranteed conflict; scripted via CLI flag.

## 4. Content addressing (decision: SHA-256 Merkle, git-shaped, research-flavored)

- Git's object model (blob/tree/commit, SHA-1 → we use SHA-256, no collision-dependence), content-addressed store, packfiles conceptually. Proven immutability + dedup properties.
- We adopt blob/tree/commit **for the content layer** and overlay the research semantic layer (Artifact, ArtifactVersion, Claim, ProvenanceEdge) in the metadata DB. Trees only for multi-file artifacts (codebases); single-document artifacts use a single-blob tree. This is the standard, defensible approach vs a bespoke hierarchy: correctness is inherited from the proven model while the differentiator lives in the semantic layer.

## 5. Provenance (decision: PROV-inspired first-class primitives)

- W3C PROV-DM (W3C Recommendation 2013): Entity / Activity / Agent + relations `wasDerivedFrom`, `wasGeneratedBy`, `used`, `wasInformedBy`. Canonical provenance model in research contexts; PROV-O is the RDF/OWL realization.
- We keep the PROV *shape* but simplify: our edge set is research-native (SOURCE_TO_ARTIFACT, ARTIFACT_TO_VERSION, VERSION_TO_COMMIT, COMMIT_TO_CLAIM, CLAIM_CITES_SOURCE, VERSION_DERIVED_FROM, CLAIM_IN_ARTIFACT). No RDF; typed rows in SQLite enable graph walks answering: "where did this claim come from", "what did we know at commit X", "which sources influenced this doc" (provenance-spec.md). Full PROV-O serialization = documented production path.

## 6. Retrieval (decision: hybrid BM25+vector+RRF, filters, graph; no chatbot)

- HyDE/naive-RAG criticism is well established; hybrid (BM25 + dense) with RRF fusion beats either alone (Qdrant blog, arXiv:2508.16757 review). Rerankers (cross-encoders, e.g., Cohere/Voyage rerank) add precision but add API dependency → we use RRF (deterministic, zero-API) and keep cross-encoder as documented production upgrade.
- Vector store maturity: pgvector (~4K stars, post-filter — known weakness with aggressive metadata filters), Qdrant (~9K stars, native hybrid sparse+dense, in-graph filtering), Chroma (~6K stars, prototyping), sqlite-vec (embedded HNSW, no server). For a zero-infra, single-machine, deterministic demo we chose **SQLite + FTS5 (BM25) + sqlite-vec**; the production path to pgvector is documented in ADR-11/ADR-09.
- Primary key insight: filters run **on version/provenance state** ("search only what we knew at commit X"), which is exactly what git-backed RAG cannot do. That is the whole retrieval story.

## 7. Ingestion formats (decision: per-type parsers, structure preserved)

- Markdown: `markdown-it` → block/heading/code structure (structure preserved as typed blocks, not flattened text).
- Plain text: paragraph + sentence segmentation.
- PDF: `pdf-parse` (text extraction) + page/section structure; OCR explicitly out of scope; fixture fallback.
- ChatGPT export: `conversations.json` — mapping_id/title/mapping tree, nodes with `message.author.role` (`user`/`assistant`/`system`/`tool`), content parts (text, code, multimodal), create_time, parent/children → reconstruct turn order + thread hierarchy.
- Claude export: different schema (JSONL conversation files; `type: "user"/"assistant"` message objects, `content` blocks with text/tool_use/tool_result, uuid, timestamps) — **separate parser, do not assume ChatGPT schema** (explicit requirement).
- Code: zip or git repo clone → file tree, language detection by extension → tree objects; optional per-file AST indexing for structural diff.
- All parsers emit a normalized `IngestedDocument` (typed blocks), preserving original metadata (source object hash, timestamps, roles) — never one flat string.

## 8. Stack validation summary

- Node 22 / npm 10 present on the build host (verified). better-sqlite3 embeds SQLite (no system sqlite3 needed). fastify + @fastify/websocket mature. vitest for tests. Vite + React + TipTap for frontend. yjs + y-prosemirror + y-protocols for collaboration. All MIT/Apache/BSD.
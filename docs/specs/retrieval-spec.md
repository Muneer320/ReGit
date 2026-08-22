# Retrieval Spec (LOCKED)

Owner: Amrit (integration), Muneer (filters). Implements ADR-11. NOT a RAG chatbot — no answer synthesis; cited evidence only.

## Pipeline (stages all visible in code and in the demo's printed trace)
1. **Parse query** → terms.
2. **Keyword leg:** FTS5 over `chunks_fts` (BM25 ranking).
3. **Vector leg:** Chroma kNN (MiniLM-L6-v2, cosine).
4. **Union + dedupe** by chunk_id.
5. **Version/provenance filter:** keep chunks on requested branch (default: any); if `as_of_commit` given, keep only chunks whose `introduced_in_commit` ∈ ancestors(as_of) minus chunks replaced before that commit (time-travel semantics).
6. **Rerank:** `score = 0.6*vector + 0.3*bm25_norm + 0.1*source_diversity` (distinct artifacts preferred).
7. **Cited result:** every hit carries `{artifact, title, branch, introduced_in_commit, sid_range, source{type,filename}}` — rendered as citation lines in UI and demo output.

## Indexing (delta reindex — the depth story)
On commit C of artifact A on branch B:
1. align(parent content, C content) → changed/added/deleted sids (ADR-04 engine).
2. Delete chunks of (A,B) containing deleted/edited sids; upsert chunks for added/edited sids.
3. New chunks: `introduced_in_commit=C`, `replaces=[old chunk ids]`.
4. FTS5 + Chroma updated transactionally-ish (Chroma upsert then FTS row; failures logged, index rebuildable).

## Chunking (per ADR-11 table)
md: heading sections ≤600 chars 10% overlap; chat: 1 message = 1 chunk; pdf: page paragraphs ≤800; code: tree-sitter function spans ≤120 lines.

## Demo query (scripted)
`POST /search {"query":"gradient descent instability","as_of_commit":X}` → results show citation metadata; then re-run without as_of → visibly different result set (newer claims included). <30s, deterministic on fixtures.

## Fallbacks
Embeddings unavailable → keyword-only mode (banner: "degraded: FTS5 only"). Chroma broken → rebuild from object store (`scripts/reindex.py`).

## Non-goals
No cross-encoder reranker, no query expansion, no LLM answers, no multi-workspace search.

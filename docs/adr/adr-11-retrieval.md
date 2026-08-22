# ADR-11: Retrieval

- **Status: LOCKED** · Owner: Amrit (pipeline integration) + Muneer (version/provenance filter semantics)

## Decision
**Hybrid retrieval: Chroma embedded (`PersistentClient(path=data/vectordb)`) + sentence-transformers `all-MiniLM-L6-v2` (local, 384-dim, offline; pre-downloaded to data/models at H0) + SQLite FTS5 keyword surface — fused, then filtered by version/provenance, then reranked, then returned WITH citations.**

Pipeline (the spec of record, ../specs/retrieval-spec.md):
`query → FTS5 keyword candidates ∪ vector kNN candidates → filter by branch/commit-ancestry/provenance → rerank (0.6 vector + 0.3 keyword + 0.1 source-diversity) → cited SearchResult[]`.

**Diff-fed delta reindex:** on commit C, the ADR-04 aligner computes changed sentence ids; only chunks containing changed sids are deleted+upserted. Never re-embed the corpus. Each chunk carries `{artifact_id, branch, introduced_in_commit, replaces_chunk_ids, sid_range}` — so every hit answers "where did this come from".

## Why (runner-up: pgvector)
Decisive tradeoff: pgvector is the honest production answer but requires a Postgres server we otherwise don't need (ADR-09). Chroma embedded = zero-ops, disk-backed, one `data/` dir. Qdrant-local rejected as one-more-dependency with no demo-visible gain.

## Chunking per type
| Type | Chunker | Size |
|---|---|---|
| Markdown | heading-section split, sentence-merged | ≤600 chars, 10% overlap; id = section path |
| Chat | 1 message = 1 chunk, `role:` prefix, thread metadata | variable |
| PDF | page → paragraph blocks | ≤800 chars |
| Code | tree-sitter function/class spans | ≤120 lines |

## NOT a RAG chatbot
There is no LLM answer synthesis. Retrieval returns *cited evidence with version+provenance context*. Time-travel query (optional H11 add-on) = ancestry-filtered chunks ("what did we know at commit X").

## Risks
MiniLM download fails at H0 → deterministic hash-embedding fallback (degraded, flagged). Chroma install weight → FTS5-only fallback still demos hybrid-lite.

## Reversibility
High: index is derived data — rebuildable from the object store at any time.

## Consequences
`backend/src/retrieval/{chunkers.py,index.py,query.py}`; `scripts/demo_search.py` prints cited JSON.

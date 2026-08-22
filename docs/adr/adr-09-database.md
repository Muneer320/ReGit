# ADR-09: Database / storage

- **Status: LOCKED** · Owner: Muneer (schema+triggers), AI (migrations)

## Decision
**Single SQLite `data/meta.db`** (`PRAGMA journal_mode=WAL, synchronous=FULL, foreign_keys=ON`) **+ filesystem blob store `data/objects/<2hex>/<rest>` (zlib) + embedded Chroma `data/vectordb/`.** One `data/` directory = the whole system state.

Immutability enforcement: `BEFORE UPDATE ON objects/commits → RAISE(ABORT)` triggers (same for DELETE) + only-INSERT public API + content addressing.

## Why (runner-up: Postgres + pgvector)
Decisive tradeoff: 13h, one machine, one process, demo corpus ≤ few hundred artifacts / ≤50MB. Postgres buys nothing demonstrable in the remaining hours and costs server ops + migration friction. SQLite WAL handles our concurrency (one uvicorn worker; writers serialize). README names Postgres+pgvector as the scale-up path so judges hear the call was deliberate. Chroma's own persistence is SQLite too — one storage story.

## Alternatives rejected
- Pure filesystem JSON: no transactional refs update, no FTS5.
- DuckDB: great analytics, wrong shape (OLAP) for op-log-ish writes.

## Tables (see data-model.md for exact DDL)
`objects, commits, commit_parents, refs, artifacts, branches, workspaces, workspace_members, merges, conflicts, crdt_ops, sources, claims, provenance_edges, chunks, sentence_index` + FTS5 virtual table `chunks_fts`.

## Risks
SQLite write contention if we later add workers — mitigated by single-worker uvicorn decision (ADR-07). Blob dir/meta.db divergence — `gr verify` cross-checks.

## Reversibility
Moderate-high: schema is small; SQLAlchemy-free hand SQL keeps the mental model explicit (a depth point), and pgvector migration is a documented path.

## Consequences
`backend/src/db/{schema.sql,db.py}`; trigger tests in tests/unit/test_immutability.py assert UPDATE/DELETE raise.

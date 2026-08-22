# ADR-02: Content Addressing

- **Status: LOCKED** · Owner: Muneer

## Context / Problem
Immutable history requires that identity = content. Also: dedup, tamper evidence, integrity verification.

## Alternatives
1. SHA-256 over raw bytes per artifact (naive).
2. SHA-256 over type-tagged, canonicalized content + Merkle commit chain.
3. UUIDs + separate hash column (identity != content).

## Decision
**(2).** `SHA256("gr-obj-v1" || kind || "\0" || canonical_bytes)` for blobs/trees; `SHA256("gr-commit-v1" || sorted(parents) || root_hash || artifact_id || message || author || author_date)` for commits.

## Why (runner-up: (1) raw-byte hashing)
Decisive tradeoff: raw-byte hashing makes two exports of the SAME chat conversation different objects (volatile message ids, timestamps, JSON key order) → phantom versions, broken dedup, lying diffs. Canonicalization-before-hash makes byte noise invisible while preserving integrity. (3) rejected: identity decoupled from content destroys tamper evidence — the whole point.

## Integrity mechanics
- On-disk: `data/objects/<first2>/<rest>` zlib-compressed; read path verifies hash on load (cheap at demo scale) behind a flag `GR_VERIFY_ON_READ=1`.
- `gr verify` walks the commit chain: recompute every commit hash from stored fields; any historical mutation breaks every descendant hash. This is a scripted, <30s judge demo.
- Dedup: identical canonical content stored once; re-importing the same PDF twice = zero new blobs.

## Risks
Canonicalization bugs create "same content, different hash" — mitigated by golden-fixture tests: fixture chat export parsed twice must yield identical blob id.

## Reversibility
High: hash scheme versioned by the `gr-obj-v1` tag; v2 can coexist.

## Consequences
- Ingest adapters own canonicalization; objects layer owns hashing.
- Commit hash includes `author_date`; demo scripts pin `GR_AUTHOR_DATE` (git does the same with committer date) for reproducible scripted hashes.

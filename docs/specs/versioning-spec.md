# Versioning Spec (LOCKED)

Scope: how artifacts acquire immutable history. Owner: Muneer. Implements ADR-01/02/03.

## Definitions
- **Artifact**: typed research object (md|txt|chat|pdf|codebase). Identity stable across versions.
- **Version** = a Commit on the artifact's DAG. Committing the SAME canonical content twice yields the same commit id (dedup) — no phantom versions.
- **Branch**: named mutable ref; `main` created at artifact creation. Fork = POST /branches at any commit.
- **Head**: branch's current commit. Checkout reads any commit without moving refs.

## Commit rules
1. Commit content = canonical artifact payload (per ingestion-spec canonical forms).
2. `parents`: [branch head] normally; [ours, theirs] for merge commits; [] for root.
3. `author_date`: wall clock, or `GR_AUTHOR_DATE` env for deterministic scripted runs (identity input — documented, like git).
4. Commit is written in one SQLite transaction: blob(s) → root hash → commit row → ref CAS update (`WHERE head = :expected`). CAS failure → 409, client reloads.

## DAG operations
- `history(artifact, branch)`: newest-first walk from head.
- `merge_base(c1, c2)`: BFS paint-down over `commit_parents`; first common ancestor; deterministic tie-break (lower height, then lower hash). Empty base when DAGs share no ancestor.
- `log --graph`: ASCII DAG renderer for the demo (2-parent merges visible).

## Integrity
- `gr verify`: recompute all blob/tree/commit hashes; report any mismatch (scripted, <30s).
- Immutability: SQL triggers (data-model.md DDL) + content addressing + append-only API.

## What versioning deliberately does NOT do
No rebase, no force-push, no history rewriting, no GC of unreferenced commits at demo scale. Say so if asked: research history must be unrewriteable.

## Per-kind notes
- md/txt: commit = one blob.
- chat: commit = one blob of canonical chat JSON (message list; volatile export ids excluded from identity).
- pdf: commit = one blob of page-structured text JSON `{pages: [{n, paragraphs}]}`.
- codebase: commit = tree of file blobs (paths relative, sorted).

## Tests (tests/unit/test_versioning.py)
identical content → same commit id; changed content → new id + parent link; branch fork at old commit; merge commit has 2 parents; trigger blocks UPDATE; `gr verify` clean after 20 random commits; merge_base on diamond DAG returns the true base.

# ADR-01: Object Model

- **Status: LOCKED** · Owner: Muneer · Supersedes flash draft §1

## Context
Research artifacts are heterogeneous typed entities (prose, chat threads, PDF text layers, code trees). Judges score versioning 35% and explicitly probe beyond "git wrapper".

## Problem
What is the fundamental unit of storage and history?

## Alternatives
1. Real git repos via subprocess/GitPython.
2. Homemade content-addressed DAG (git-inspired object model, stdlib).
3. Event-sourced op log only (no snapshots).

## Comparison
- (1) gives free merge-base/packfiles but: line-granular diff on prose; byte-identity on volatile chat JSON; no typed-artifact or provenance representation; "wrapped git" is the lowest-credibility answer on the 35% pillar.
- (2) ~300 LOC stdlib; full control of typed blobs, canonicalization before hashing, merkle commit fingerprints; we can explain every line on a whiteboard.
- (3) makes "state at commit X" expensive and muddles the commit abstraction judges expect.

## Decision
**(2) Homemade object model**, deliberately git-shaped but research-native:
- `Blob`: `id = SHA256("gr-obj-v1" || kind || "\0" || data)`, kind ∈ {md, txt, chat, pdf, code-file, tree}.
- `Tree`: hash over sorted `(path, blob_id)` pairs — snapshot fingerprint of an artifact set (used for codebases and workspace manifests).
- `Commit`: `SHA256("gr-commit-v1" || sorted(parent_ids) || tree_or_blob_id || artifact_id || message || author || author_date)`. 1 parent = normal; 2 parents = merge; 0 = root.
- `Branch`: mutable ref → commit id. The only mutable thing in the store.
- Canonicalization BEFORE hashing per artifact type (chats: volatile ids/timestamps excluded from identity; prose: exact text; code: exact bytes).

## Why
Typed artifacts + canonical identity + merkle fingerprints + a sidecar sentence index are exactly what git cannot represent; the model is small enough that Muneer can defend every field.

## Risks
Hand-rolled merge-base (LCA) bugs — mitigated by adversarial DAG tests. No packfiles — fine at demo scale.

## Reversibility
High: objects are serializable to git fast-export format if ever needed.

## Implementation consequences
- `backend/src/core/objects/{store.py,models.py}` own ALL writes; no other module writes blobs/commits.
- SQL triggers hard-block UPDATE/DELETE on `objects`,`commits`.
- Deterministic hashing requires `GR_AUTHOR_DATE` pin support.

# ADR-03: Version Graph

- **Status: LOCKED** · Owner: Muneer

## Context / Problem
How is history structured per artifact and per workspace? Linear per-artifact chains lose research's exploratory forking; a single global chain couples unrelated artifacts.

## Alternatives
1. One global DAG of workspace snapshots (git-style repo-wide commits).
2. Per-artifact commit DAGs + branches; workspace = named set of (artifact, branch) pointers.
3. Per-artifact linear versions only (no DAG).

## Decision
**(2) Per-artifact commit DAGs.** Each commit references exactly one `artifact_id`, 0–2 parents, and the artifact's root hash (blob for md/txt/chat/pdf; tree for codebase). `Workspace` = row set of `(artifact_id, branch_name, head_commit_id)`. Branch create = new ref at existing commit ("fork a research thread"). Merge = commit with 2 parents on the target artifact.

## Why (runner-up: (1) global DAG)
Decisive tradeoff: a global snapshot DAG entangles unrelated artifacts — branching your hypothesis doc would fork the PDFs and chats too, making merge-base noisy and provenance queries ambiguous. Per-artifact DAGs match the research mental model ("this document/thread has a history and forks"), keep merge-base computation trivially correct, and make per-artifact blame/lineage queries clean. Workspace-level "state at time T" is still answerable by composing per-artifact ancestry (what retrieval does). (3) rejected: can't represent the merge event — the single most interesting event in collaborative research.

## Merge-base algorithm
BFS from both head commits over the parent edges, first common ancestor wins; ties broken by lowest height then hash order (deterministic). Equivalent to git's paint-down-to-common for 2-parent DAGs. Root merge-base = empty base (everything is an add).

## Risks
Cross-artifact "the workspace changed" view is derived, not stored — accepted; workspace timeline = union of per-artifact commits ordered by author_date (display only).

## Reversibility
Moderate: migrating to a global DAG later would require a synthetic commit layer; not planned.

## Consequences
- `merge_base(c1, c2)` lives in `core/versioning/dag.py` with adversarial tests (diamond DAGs, criss-cross, root merge).
- Merge commits store BOTH parent ids; `gr log --graph` renders the DAG for the demo.

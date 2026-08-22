# ADR-05: Merge Algorithm (3-way, sentence-level for prose)

- **Status: LOCKED** · Owner: Muneer · This is the ONE deep stretch (engine + conflict UI)

## Context / Problem
Judges' first ask: a live merge conflict. Brief floor: "merging OR at minimum surfacing merge conflicts". We build both: deterministic auto-merge for clean cases + first-class conflict records + resolution UI.

## Decision
**Sentence-level 3-way merge for prose**, reusing the ADR-04 alignment engine:
1. base = artifact content at `merge_base(ours_head, theirs_head)`.
2. `align(base, ours)` and `align(base, theirs)` → per-base-sentence change sets.
3. Per-sentence decision table:
   - unchanged both → keep base
   - changed only in one side → take that side (auto-merge)
   - both changed to identical text → convergent, take it (auto-merge, NO conflict)
   - both changed differently → **Conflict record** `{sid, base_text, ours_text, theirs_text}`
   - insertions at same anchor from both sides → both kept, ordered ours-then-theirs, flagged `insert_conflict` for UI ordering
   - delete-vs-modify → conflict (never silently drop the modification) — invariant 6
4. Output: merged text skeleton + `conflicts[]`. Unresolved merge is persisted as a `Merge` row (state=pending).
5. Resolution: per conflict `accept_ours | accept_theirs | free_edit`; applying all resolutions → **merge commit with 2 parents**, `Merge.state=resolved`.

### Code/chat/pdf merge
File/message-level: changed on one side only → take it; changed both sides → conflict markers (`<<<<<<< ours / ======= / >>>>>>> theirs`) in the merged artifact + conflict records. No function-level code merge (out of scope, stated).

## Why (runner-up: git-style line-level diff3 for everything)
Decisive tradeoff: line-level 3-way on prose produces false conflicts on reflow and meaningless conflict regions that span partial sentences; sentence-level merge maps conflicts to *claims* — reviewable by a researcher and exactly the "non-trivial merge semantics" the 35% pillar rewards. diff3 runner-up is retained for code files (correct tool there). Custom word-level diff3 rejected: 3× the complexity for a marginal demo gain.

## Conflict representation
Conflicts are DB rows + embedded markers; the UI renders conflict cards (ours/theirs/base panes + actions). Merge result-as-commit keeps the DAG honest: a merge is a commit with 2 parents and a link to its `Merge` row.

## Risks
Alignment instability creating spurious conflicts — mitigated by the 0.7 similarity threshold + convergent-change rule + exact-fixture pytest contracts: (a) disjoint edits auto-merge clean, (b) same-sentence divergent edits → exactly 1 conflict, (c) same-sentence identical edits → 0 conflicts.

## Reversibility
Moderate: merge engine is a pure function `merge_prose(base, ours, theirs) -> MergeResult`; swappable.

## Consequences
- `core/merge/three_way.py` + `specs/merge-spec.md` decision table is the spec of record.
- Conflict UI (Amrit) consumes `GET /merge/:id` + `POST /merge/:id/resolve`.

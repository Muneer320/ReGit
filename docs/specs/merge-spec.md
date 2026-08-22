# Merge Spec (LOCKED)

Owner: Muneer. Implements ADR-05. The live merge conflict is judge-ask #1 — this spec's fixtures make it deterministic.

## 3-way prose merge — algorithm of record
```
base  = content(artifact, merge_base(ours_head, theirs_head))
A     = align(base, ours)      # ADR-04 engine
B     = align(base, theirs)
for each base sentence s:
    ca, cb = change(s) in A, change(s) in B
    if ca == none and cb == none:            keep base
    elif ca != none and cb == none:          take ours
    elif ca == none and cb != none:          take theirs
    elif text(ca) == text(cb):               take ours   # convergent — NOT a conflict
    else:                                    CONFLICT(s, base, ours, theirs)
    delete(s) in one side, modify(s) in other: CONFLICT  # never silently drop (invariant 6)
insertions at same anchor in both sides:      keep both (ours then theirs), mark insert_conflict
```
Output: `{merged_text, conflicts: [Conflict], state: clean|conflicts}`.

## Merge lifecycle
1. POST /merge → compute base (DAG) → run algorithm.
2. state=clean → write merge commit (parents=[ours_head, theirs_head]) immediately, advance ours_branch, Merge.state=resolved.
3. state=conflicts → persist Merge(pending) + Conflict rows; NO ref moves; UI renders conflict cards.
4. POST /merge/:id/resolve with per-conflict `ours|theirs|free(resolved_text)` → validate all resolved → compose final text → merge commit (2 parents) → advance branch → state=resolved.

## Code/chat/pdf merge (floor behavior)
Per file/message: one side changed → take it; both changed → git-style markers `<<<<<<< ours … ======= … >>>>>>> theirs` + Conflict rows (resolution = free edit of the marked region). This satisfies "merging OR surfacing conflicts" with real conflict records, not just markers.

## Test contracts (tests/unit/test_merge.py — exact)
- T1 disjoint edits (ours edits S1, theirs edits S3) → clean, both edits present.
- T2 same sentence, divergent text → exactly 1 conflict, correct triple.
- T3 same sentence, identical text → clean, no conflict (convergent).
- T4 delete-vs-modify → conflict.
- T5 both insert at same anchor → both kept, order ours-then-theirs.
- T6 criss-cross DAG: merge_base correct, merge still 3-way against the painted base.
- T7 resolve → result commit has exactly 2 parents; Merge state resolved; branch head advanced.
- T8 (adversarial) resolve with unresolved conflicts → 400; double resolve → 409.

## Determinism for the demo
Fixture set `fixtures/merge/{base,ours,theirs}.md` with both sides editing sentence 2 differently → exactly one scripted conflict card. Pinned `GR_AUTHOR_DATE` → reproducible merge commit hash.

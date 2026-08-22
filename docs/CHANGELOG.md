# ReGit Changelog

## 2026-08-22 — Versioning DAG layer + prose alignment spine (H1/H2/H4 reference implementation)

No specs were rewritten; these notes record spec-vs-code interpretations and
drift found while implementing `backend/src/core/objects/store.py` and
`backend/src/core/diff/align.py`. Review with Muneer.

**Spec drift / interpretations (code deviates in shape, not semantics):**

- **`Change.sid` vs `Change.span` naming.** `docs/data-model.md` Change record
  is `{sid|span, ...}`; `core/models.py` names the field `span`, while
  `diff-spec.md` and the `align.py` stub both say `sid`. `diff_prose()` emits
  dicts with key **`sid`** (diff-spec.md is the diff engine's spec of record).
  Recommend renaming `models.Change.span` → `sid` (or documenting the alias).
- **`refs` vs `branches` tables.** data-model.md DDL defines BOTH
  `refs(name, artifact_id, head)` and `branches(..., head_commit_id, created_at)`.
  `ObjectStore` treats `refs` as the operational CAS table (source of truth)
  and `branches` as a metadata mirror kept in sync in the same transaction.
  No drift in behavior; the duplication is spec-authored.
- **`merge_base` "height" definition.** adr-03 says "ties broken by lowest
  height then hash order" without defining height; implementation uses
  `height = dist_from(c1) + dist_from(c2)` (shortest BFS distances back to the
  two heads), final tie-break lower commit id (hash). Deterministic; verified
  on diamond and criss-cross DAGs.
- **`commit()` signature extends the stub.** Added keyword params
  `branch="main"`, `expected_head=None`, `kind=None` — required by
  api-contract.md (`{branch, content, message, base_commit?}` → stale base_commit
  is 409) and versioning-spec.md's "ref CAS update (WHERE head = :expected)".
  Callers with no `expected_head` get the read-inside-transaction CAS
  (serialized per artifact via `BEGIN IMMEDIATE`).
- **2-parent commits "must link a Merge row"** (data-model.md) is enforced at
  the merge service layer (merge-spec.md lifecycle), NOT in `ObjectStore.commit`
  — the store is a primitive and doesn't know about `merges`.
- **`diff_prose` sids are `para:sent` by default.** The full `artifact:para:sent`
  sid needs artifact context, which the primitive doesn't have; pass
  `artifact_id=` to compose it, otherwise the API layer must prefix.
- **"moved" detection.** Equal-hash sentence pairs whose paragraph offset
  differs from the modal offset of the whole alignment → `moved` (a uniform
  offset, e.g. a heading prepended, is NOT a move). Known limitation: a
  paragraph reorder that crosses an LCS anchor surfaces as delete+add for one
  of the swapped paragraphs (LCS is order-preserving; documented in align.py).
- **`split_paragraphs` canonicalizes** blocks (`.strip()`), so a trailing
  newline after the last paragraph is not part of paragraph identity.
- **`author_date` resolution** in `commit()`: explicit param > `GR_AUTHOR_DATE`
  env > wall clock; the resolved value is what lands in `commits.author_date`
  and what was hashed (hashutil.commit_id), so `verify()` stays exact.

**Added:** `ObjectStore.commit/merge_base/verify/history/head/create_branch/
advance_branch` (store.py); `align/diff_prose` (align.py); unit tests
`tests/unit/test_commit.py`, `tests/unit/test_align.py`; invariant test
`test_branch_is_mutable_ref_to_immutable_commit` turned green (real test,
not weakened). Baseline was 3 passed / 4 xfailed; now 35 passed / 3 xfailed.
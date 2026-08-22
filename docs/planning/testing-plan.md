# Testing Plan (LOCKED)

Disproportionate focus on the hard parts. Determinism everywhere: fixtures pinned, `GR_AUTHOR_DATE` pinned, exact-JSON assertions.

## Unit (tests/unit)
- **Objects/versioning:** same content→same id; edit→new id+parent; root/merge commit shapes; branch CAS conflict; trigger blocks UPDATE/DELETE; `gr verify` after 20 random commits; merge_base: diamond, criss-cross, shared-root, no-common-ancestor.
- **Diff (prose):** insert, delete, replace, sentence split, paragraph move, reflow-noise → zero changes, large doc (5k sentences < 2s). EXACT JSON on fixture pairs.
- **Diff (code):** body change, rename, add/remove function, comment-only change → no entry, formatting churn → no entry.
- **Merge:** T1–T8 from merge-spec.md (incl. convergent → no conflict; delete-vs-modify → conflict).
- **Ingest:** both chat schemas → canonical equality; re-export dedup; PDF pages; codebase tree; 422 on malformed.
- **Retrieval:** delta reindex touches only changed chunks; `introduced_in_commit` correct; FTS fallback works.

## Concurrency (tests/concurrency)
- Two simulated WS clients: concurrent inserts converge.
- Property test: recorded op log shuffled 50× → byte-identical final text (THE convergence proof).
- Disconnect/reconnect heal; duplicate op no-op; out-of-order safe; commit-during-edit lands next commit.

## Integration (tests/integration)
- Full API loop: ingest → commit → branch → divergent commits → merge (conflict) → resolve → 2-parent commit → diff → search.
- Provenance chain intact across branch+merge; "what was known at X" ancestry filter correct.
- Commit-from-live via WS control frame.

## Adversarial (tests/adversarial) — keyed to the 6 invariants
1. Tamper a blob file on disk → `gr verify` fails loudly.
2. Crafted pathological prose (all sentences near-identical) → merge doesn't crash, conflicts bounded.
3. 1000-op burst on one room → convergence + op log length sane.
4. Re-ingest corpus twice → blob count unchanged (dedup).
5. Resolve merge twice → 409; resolve with missing conflicts → 400.
6. Search with as_of = root commit → only root-era chunks.

## Performance smoke (measure, don't guess)
commit <100ms, prose diff 5k sentences <2s, merge <1s, search <500ms on demo corpus, WS echo <50ms. Log timings in milestone reports; only fix what's a demo risk.

## Gate
No feature is "done" without its tests green; H10 requires the FULL suite green before demo prep.

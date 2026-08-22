# Provenance Spec (LOCKED)

Owner: Muneer. Implements ADR-12.

## The chain (edges written mechanically at each step)
```
ResearchSource --imported_as--> Artifact --has_version--> ArtifactVersion(=Commit)
Commit --states--> Claim
Claim --derived_from--> (source | other artifact's version)   # via citing artifact's commit
```
- Ingest: adapter writes `ResearchSource` + `Artifact` + `imported_as` edge + `has_version` + `in_commit`.
- Commit: claims parsed from `claim: ...` sentinels → `states` edge from the new commit; `derived_from` edges to the source(s) of the artifact (and, for citation markers `[@artifact:art_x]`, to that artifact's current version).
- Merge: claims merge by normalized text identity; a claim present in either side survives with edges to BOTH commits' ancestry (never silently dropped).

## The three queries (API per api-contract.md; each <30s in demo)
1. **Where did this claim come from?** — `GET /provenance/claim/:id` → chain with content snippets: claim text ← commit ← artifact version ← source file (e.g., "ChatGPT export conversations.json, message 14, assistant").
2. **What was known at commit X?** — `GET /provenance/at/:commit/claims` → claims whose stating commit ∈ ancestors(X), with first-stated dates. This is the temporal-knowledge query.
3. **Which sources influenced artifact A?** — `GET /provenance/artifact/:id/sources` → distinct sources reachable from A's claims, with counts.

## Sentence lineage (automatic, no sentinels needed)
`sentence_index` rows (commit, artifact, sid, status, old_hash, new_hash, text) written by the diff engine on every commit give per-sentence "introduced/edited in commit C" — this powers both blame-lite and the chunk `introduced_in_commit` metadata in retrieval.

## Invariants tested
- Chain integrity across branch+merge (tests/integration/test_provenance.py): claim stated on branch B, merged into main → query from main returns the claim with its branch-origin commit.
- No orphan claims: every claim has ≥1 path to a source.
- Deleting an artifact does not delete sources or edges of OTHER artifacts.

## Non-goals
No visual graph explorer (next-build paragraph). No LLM claim extraction. No confidence scores.

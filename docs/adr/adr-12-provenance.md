# ADR-12: Provenance as a first-class primitive

- **Status: LOCKED** · Owner: Muneer (semantics) + AI (CRUD)

## Decision
**Provenance is modeled as typed edges in the DB, written at ingest/commit time, queryable by API — not as metadata strings.**

Chain: `ResearchSource →(imported_as) Artifact →(has_version) ArtifactVersion →(in_commit) Commit →(states) Claim →(derived_from) source artifact/version`.

Three required queries (each <30s provable):
1. "Where did this claim come from?" → walk edges claim→commit→artifact version→source; return the chain with content snippets.
2. "What was known at commit X?" → claims whose in_commit ∈ ancestors(X) (uses ADR-03 DAG walk).
3. "Which sources influenced artifact A?" → reverse edges from A's claims to sources.

## How claims are created (no LLM required for the core)
- **MVP:** claims are *declared* — markdown sentinel lines `claim: <text>` (and chat messages prefixed `claim:`) are parsed at ingest/commit into `Claim` rows linked to the current commit + artifact version. This is honest, deterministic, and demoable.
- Provenance-lite everywhere else: chunk metadata (`introduced_in_commit`, `replaces`, sid lineage via `sentence_index`) gives per-fragment origin in every search result.

## Why (runner-up: LLM-based claim extraction)
Decisive tradeoff: LLM extraction is nondeterministic, unsourced-by-construction, and unverifiable under judge questioning ("how do you KNOW this claim came from this chat?"). Sentinel-declared claims + sentence lineage give a mechanically checkable chain. LLM extraction is a named post-hackathon upgrade, never a correctness dependency.

## Why provenance-lite is in the core but the full graph is NOT the stretch
The stretch pick is the 3-way merge UI (ADR-05): it amplifies versioning (35%) and the #1 demo moment. The provenance graph's demo value is ~80% captured by cited search results + the three queries above; the visual graph explorer is the next-build paragraph.

## Risks
Sentinel convention feels artificial — mitigated by showing it working on real fixture docs and by the chunk-level lineage being fully automatic. Edge maintenance across merge: claims merge by text identity; conflicting claims both survive with their own edges (never silently dropped — invariant 6).

## Reversibility
High: edges are additive rows; a richer claim model can supersede sentinels without schema loss.

## Consequences
`backend/src/provenance/{claims.py,edges.py}`; ../specs/provenance-spec.md is the spec; tests assert chain integrity across branch+merge.

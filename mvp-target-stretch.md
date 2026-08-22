# Judging Reverse-Engineering + MVP/TARGET/STRETCH (LOCKED)

Every feature lists: what judges want / minimum / strong / killer demo, and its <30s proof.

## Versioning (35%)
- **Want:** a real VCS model — immutable content-addressed history, meaningful diffs, non-trivial merge.
- **Minimum:** commits + branch + line diff + conflict markers.
- **Strong:** typed artifacts, canonical identity, sentence-level diff, 3-way merge with conflict records, `gr verify` integrity walk.
- **Killer demo (<30s each):** (a) semantic diff of edited fixture — sentences aligned, move detected, reflow produces ZERO noise where git shows 40 changed lines; (b) merge conflict card with base/ours/theirs → resolve → DAG shows 2-parent commit; (c) `gr verify` recomputes the chain live.

## Concurrency (20%)
- **Want:** actual concurrent editing with convergence + presence, not a save button.
- **Minimum:** two tabs, last-writer-wins.
- **Strong:** CRDT with awareness, independent undo, commit-from-live, reconnect heal.
- **Killer demo:** kill the server mid-edit → restart → room rebuilt from op log, text intact; then property-test replay: shuffled op logs converge byte-identical, shown live.

## Ingestion (15%)
- **Want:** ≥3 types, structure preserved, ChatGPT≠Claude handled.
- **Minimum:** upload text files.
- **Strong:** 4 adapters → canonical forms; chat re-export dedups to same blob (byte noise, same identity — the canonicalization mic-drop); PDF page structure preserved.
- **Killer demo:** ingest ChatGPT + Claude + PDF + md in one call; show same-conversation-different-export → SAME commit id.

## Retrieval (15%)
- **Want:** corpus query beyond Ctrl-F; ideally history-aware.
- **Minimum:** keyword search.
- **Strong:** hybrid FTS+vector, per-type chunking, delta reindex on commit (only changed chunks re-embedded — shown live), cited results.
- **Killer demo:** same query with and without `as_of_commit` → visibly different result sets ("what did we know at X"); every hit shows introduced-in-commit + source.

## Stretch (10%) — ONE deep: 3-way prose merge w/ conflict UI
- Already core to our merge pillar; the stretch depth is the sentence-level decision table + conflict cards + resolution → merge commit. Provenance-lite (chunk lineage + 3 provenance queries) rides along free. We say: "full visual provenance graph = next build."

## Demo clarity (5%)
- 8-scene scripted narrative (demo-script.md), rehearsed twice, timed, with printed JSON the judges can read from the back row.

---

## MVP (must work even if everything goes wrong)
Ingest md+chatgpt+claude (3 types) · content-addressed commits + branches + history · prose sentence diff · 3-way merge with conflict records via CLI/API (UI optional) · keyword search · scripted demo via scripts if frontend dies.

## TARGET (expected at ~10h)
MVP + PDF + codebase ingest · tree-sitter code diff · live CRDT collab + presence + commit-from-live · conflict cards UI · hybrid retrieval with delta reindex + citations · provenance 3 queries · `gr verify`.

## STRETCH (only if core stable)
1. Time-travel query UI toggle (as_of_commit) — engine already supports it.
2. LLM one-line diff summary (labeled, decorative, ADR-14).
3. Second tree-sitter language.
Hard-capped list. If any stretch threatens MVP stability → cut immediately.

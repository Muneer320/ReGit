# ReGit — Complete Project Explainer (for mentors & judges)

> **One line:** ReGit is a research-native version control system — "what if Git had been designed for research instead of source code?"

This doc explains the whole project: the problem, the architecture, exactly how each piece works, what's done, and two worked walkthroughs you can run to show a mentor. **Read this before approaching; it's dense but complete.**

---

## 1. The problem we're solving

Research lives fragmented — a Google Doc here, a folder of PDFs there, a GitHub repo, and a dozen throwaway ChatGPT/Claude conversations that never get saved. There's no shared history, no diffing, no branching, no way for collaborators to work on the same evolving knowledge without overwriting each other.

**Git solved this for code. Nobody solved it for research.** The core insight: a research artifact is *not* a file tree. It's prose with meaning, chat threads with turn structure, PDFs with layout, and claims with provenance. Slapping Git on top destroys exactly the information research depends on.

**This is deliberately NOT "Git + an LLM wrapper."** No LLM is in any correctness path — diff, merge, and retrieval are deterministic algorithms. That's the anti-wrapper story judges care about.

---

## 2. The four pillars (all mandatory, each scored)

| Pillar | Weight | What we built |
|---|---|---|
| **Versioning engine** | 35% | Content-addressed immutable object store + commit DAG + branches + **semantic diff** + **3-way merge** |
| **Concurrency** | 20% | CRDT (pycrdt↔yjs) live editing, presence, commit-from-live |
| **Ingestion** | 15% | Markdown, ChatGPT, Claude, PDF, codebase — structure-preserving canonicalizers |
| **Retrieval** | 15% | Hybrid Chroma+FTS5, **delta-reindexed per commit**, version/provenance-aware |
| Stretch + demo | 15% | 3-way prose merge (stretch) + scripted live conflict & semantic diff |

---

## 3. Architecture (the whole system)

```
 Browser (React, vanilla-friendly)  -- userA / userB two tabs
      │  REST (REST)  +  WS /collaborate/:artifact_id?branch=&user=
      ▼
 FastAPI backend (ONE process, single uvicorn worker)
   ├─ core/objects     content-addressed blob store, commit DAG, branches, merge-base
   ├─ core/diff        align.py — THE shared primitive (sentence/paragraph LCS)
   ├─ core/merge       three_way.py — 3-way prose merge, conflict records
   ├─ core/collaboration  CRDT Doc registry, lock, commit-from-live
   ├─ ingestion/       per-format parsers -> canonical typed payloads
   ├─ retrieval/       chunkers, delta indexer, hybrid search
   └─ provenance/      claims + provenance edges
      │
      ▼
 data/  (one fully-offline dir)
   ├─ objects/   zlib blobs by SHA-256 prefix
   ├─ meta.db    SQLite WAL — objects/commits/refs/chunks/crdt_ops/conflicts
   └─ vectordb   Chroma (embedded) + MiniLM-L6-v2 models
```

**Why one process / embedded everything:** the demo runs fully offline with just `uvicorn`. No network, no separate servers — a judge can't get "the deployment is down" as an excuse. Scale-up path (Postgres, S3, Redis rooms) is documented but deliberately not built.

---

## 4. How the key pieces actually work

### 4a. Content-addressed object store (core/objects)
- Every blob's id = `SHA256(kind + content)`. Same content → same id → **automatic dedup**.
- Blobs are **immutable**: SQLite triggers `RAISE(ABORT)` on UPDATE/DELETE of `objects`/`commits`. Once written, nothing can silently change it.
- A **commit** references a root blob hash + its parents (0–2) → forms an immutable DAG. A **branch** is just a mutable ref pointing at an immutable commit.

### 4b. The alignment spine (core/diff/align.py) — our crown jewel
One deterministic algorithm feeds **three** systems:
1. **Diff** (semantic, not byte-diff)
2. **3-way merge**
3. **Retrieval delta-reindex**

How it works: paragraph split → sentence split → normalize (lowercase, strip punctuation) → hash each sentence → **LCS alignment over sentence-hash sequences**. Then:
- identical hash → `equal`
- similar text (`difflib` ratio ≥ 0.7, `autojunk=False`) → `edited`
- otherwise → `delete`/`insert`
- **move detection:** a sentence whose paragraph shifted relative to the *modal* offset is reported `moved`, not delete+insert. A uniform shift (e.g. prepending a heading) is correctly NOT flagged as a move.

### 4c. 3-way merge (core/merge/three_way.py)
`merge_base(base, ours, theirs)` → BFS LCA on the commit DAG. Then `align(base,ours)` + `align(base,theirs)`, per-sentence decision table:
- unchanged on both → keep base
- changed on one side only → take that side
- both changed identically → converge (no conflict)
- **both changed differently → Conflict record + git-style markers** (`<<<<<<< ours 0:1 … ======= … >>>>>>> theirs`)
- **delete-vs-modify → Conflict** (invariant: **merge never silently discards incompatible changes** — nothing is ever dropped)
- result = a NEW 2-parent commit

### 4d. Retrieval (core/retrieval) — the delta-reindex depth story
On every commit: `align(parent, child)` → only the **changed sentences' chunks** get deleted/upserted (`introduced_in_commit=C`, `replaces=[old ids]`). Not a full rebuild — a delta. Query = FTS5 BM25 ∪ Chroma kNN → dedupe → **version/provenance filter** → rerank (0.6×vector + 0.3×bm25 + 0.1×source-diversity) → **cited result** (artifact, commit, source). The `as_of_commit` filter gives the "what did we know at time X?" time-travel query.

### 4e. CRDT concurrency (in progress)
One pycrdt Doc per (artifact, branch). Live edits converge (CRDT guarantee). A `commit_request` control frame snapshots the live text under a per-artifact lock into an immutable DAG commit. Convergence + reconnect/dup/out-of-order handled via persisted op log — tested by applying the same ops shuffled and asserting byte-identical state.

---

## 5. What's DONE vs in progress

**✅ DONE (committed to `main`, tested):**
- Object store (content-addressing, immutability, dedup, commits, branches, merge-base)
- Alignment spine (align.py) + semantic diff
- **3-way prose merge** with conflict records + markers
- Ingestion: markdown, ChatGPT, Claude, PDF, codebase parsers
- Retrieval: chunkers, delta indexer, hybrid search, time-travel filter
- Full REST contract (`api-contract.md`)
- **Tests: 106 pass, 2 xfail** (the 2 xfail = CRDT + provenance-chain gates, in progress)

**🔄 IN PROGRESS:** CRDT live-collaboration layer (being built now)

---

## 6. Worked walkthrough #1 — The live merge conflict (THE #1 demo moment)

This is the scripted demo using `scripts/fixtures/merge/`. Both squads branched from `base.md`:

```
base:   "We observed loss spikes at lr=0.1 on the quadratic benchmark."
ours:   "We observed loss spikes at lr=0.1 ... and at lr=0.05 on deeper models."   (edit)
theirs: "We observed oscillations, not spikes, at lr=0.1 ..."                      (edit)
```

Both edited **sentence `0:1`** differently → the merge engine produces **exactly 1 Conflict record**:
```
<<<<<<< ours 0:1
We observed loss spikes at lr=0.1 on the quadratic benchmark and at lr=0.05 on deeper models.
=======
We observed oscillations, not spikes, at lr=0.1 on the quadratic benchmark.
>>>>>>> theirs
```
The two unaffected sentences auto-merge cleanly. The judge sees:
1. Two branches diverged on the same sentence.
2. The merge engine detects the conflict (it didn't silently pick one).
3. Resolve in the UI (accept ours / accept theirs / free-edit) → 2-parent merge commit.

---

## 7. Worked walkthrough #2 — Semantic diff + time-travel retrieval

**Semantic diff:** take a note and **reorder a paragraph** vs delete+re-add it. The align engine reports it as `moved` (same sentence, new position) — not a wall of red/green line deletions. A prepended heading is correctly NOT a move.

**Time-travel search:** `POST /search {"query":"gradient descent instability", "as_of_commit": X}` returns only claims introduced ≤ X with citations. Re-run **without** `as_of` → newer claims appear. The judge sees retrieval *respect history*, not a dumb vector search over a snapshot.

---

## 8. How to explain it in 30 / 60 / 90 seconds

- **30s:** "Git, but for research. Content-addressed immutable versions of prose/chat/PDFs, semantic diff, 3-way merge, live CRDT collaboration, and version-aware retrieval. No LLM in the correctness path — deterministic algorithms."
- **60s:** add the one-spine story: "One sentence-alignment algorithm powers diff, merge, and retrieval reindex — tested once, pays three times. The demo's live conflict shows it never silently drops a change."
- **90s:** add the anti-wrapper line + "everything runs offline in one process; judges can inspect the object model and the merge decision table."

---

## 9. Repo map (where things live)
```
backend/src/core/objects/   content-addressed store + DAG
backend/src/core/diff/      align.py (spine)
backend/src/core/merge/     three_way.py
backend/src/core/collaboration/  CRDT (in progress)
backend/src/ingestion/      parsers
backend/src/retrieval/      chunkers/indexer/service
backend/src/api/main.py     FastAPI REST + WS
docs/                       ADRs, specs, data-model, planning, demo, judge-qa
frontend/src/               React client (Amrit)
scripts/fixtures/           demo data (merge triple, chat/pdf exports)
tests/                      unit + integration + concurrency/adversarial
```
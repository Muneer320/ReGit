# Demo Script (LOCKED) — a technical story, not a dashboard tour

## §0 The 5 killer differentiators (anchor every scene)
1. **Canonical identity** — re-exported chat → SAME commit id (byte noise, semantic identity).
2. **One alignment engine** powers diff, merge, AND delta reindex (deterministic, no LLM).
3. **Sentence-level 3-way merge** with real conflict records — conflicts are claims, not line soup.
4. **CRDT-live drafts become immutable DAG commits** — two layers, each doing what it's good at.
5. **Retrieval knows history** — cited hits with introduced-in-commit + source; "what did we know at X" filter.

## Setup (pre-demo checklist)
Fresh `data/` via `scripts/reset_demo.sh`; server on :8377; two browser tabs logged as userA/userB; terminal with `gr` + scripts; `GR_AUTHOR_DATE` pinned; backup video cued.

## Scenes (5 minutes, rehearsed, each beat <30s provable)

**S1 Research (45s).** `gr ingest fixtures/` → ChatGPT export + Claude export + PDF + notes.md load as 4 typed artifacts. *Beat:* show chat artifact = message list with roles, NOT a string. Show the ChatGPT re-export (different ids/timestamps) → **same commit id**. "Canonical identity: byte noise, same object."

**S2 Versioning (30s).** Edit notes.md in tab A (change a claim sentence), commit with message. `gr log` → chain; `gr verify` → chain recomputed live. "Immutable, content-addressed, tamper-evident."

**S3 Semantic diff (45s).** `scripts/demo_semantic_diff.py` on the edit: sentences aligned, the edited claim shown as ONE edited sentence; reflowed paragraph → zero changes. Side-by-side: `git diff` on the same file shows line noise. Code diff on fixture: `renamed: compute_stats → compute_statistics`, one body modified — comment churn invisible. "No LLM. An alignment engine we own."

**S4 Branching (20s).** Fork `claims-review` branch at HEAD. Two research directions visible in branch list.

**S5 Merge conflict (60s, CLIMAX 1).** Tab A (main) edits sentence 2; tab B (claims-review) edits sentence 2 differently; both commit. POST /merge → **conflict card**: base/ours/theirs of THE SENTENCE. Resolve via free edit → merge commit → `gr log --graph` shows 2 parents. "Conflicts are claims, not line markers."

**S6 Collaboration (45s).** Both tabs on same artifact+branch: live co-typing, presence chips, colored carets, independent undo. `commit_request` from tab B → both histories update. "CRDT absorbs typing races; the DAG absorbs research disagreements."

**S7 Provenance (30s).** Click a claim in notes.md → chain: claim ← commit ← version ← "ChatGPT export, message 14, assistant". "Every claim is traceable — mechanically, not by an LLM's say-so."

**S8 Temporal retrieval (45s, CLIMAX 2).** Search "gradient descent instability" → cited hits (artifact, branch, introduced-in-commit, source). Toggle `as_of_commit` = last week's commit → result set visibly shrinks to what we knew then. "Retrieval that understands research history."

**Close (15s).** "Git was designed for code. We asked what it would look like designed for research: typed artifacts, canonical identity, sentence-level merge, provenance as a primitive, version-aware retrieval. Next build: the full visual provenance graph + multi-agent editing branches."

## Fallbacks (rehearsed)
Frontend dies → same scenes via `gr` CLI + scripts. WS dies → `scripts/replay_ops.py` convergence replay. Embeddings die → FTS5 mode banner. Everything dies → backup video + live `pytest` walk (the tests ARE the depth proof).

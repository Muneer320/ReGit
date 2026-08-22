# Git for Research — Architecture Decision Record (Locked)

**Context:** 13-hour overnight hackathon, 2 humans (Muneer = systems, Amrit = product/integration) + AI agents implementing. Win condition: demonstrated technical depth under the UI (versioning 35% / concurrency 20% / ingestion 15% / retrieval 15% / stretch 10% / demo 5%). Judges will FIRST ask for (1) a live merge conflict and (2) a live semantic diff — both are scripted, deterministic, and rehearsed before anything else is polished.

**The 30-second story for judges (anti "git+LLM wrapper"):**
Three layers, none of them an LLM wrapper:
1. **Object model** — a typed, content-addressed DAG (SHA-256 blobs, merkle commit hashes) over *normalized* research artifacts: prose docs, canonicalized chat threads (ChatGPT and Claude exports parsed differently, stored identically), PDF text layers, and codebases as file trees. One history for heterogeneous artifacts.
2. **Semantic layer** — one deterministic alignment engine (LCS-over-sentence-hashes for prose, tree-sitter CST for code) shared by **diff, merge, and retrieval delta-indexing**. No LLM anywhere in the diff/merge path.
3. **Concurrency layer** — Yjs CRDT (y-py on the server, Jupyter's production story) for live presence + editing + undo, whose drafts *become* versioned commits in the DAG.

---

## TL;DR decision table

| # | Decision | Winner | Runner-up | Decided by |
|---|---|---|---|---|
| 1 | Versioning primitive | **Homemade content-addressed DAG** (~300 LOC, stdlib) | Real git (subprocess/GitPython) | Typed artifact semantics + merkle snapshot fingerprints + demo credibility + the sentence-index sidecar git cannot represent |
| 2 | Concurrency | **Yjs** (server: `y-py` + `ypy-websocket`; browser: vendored `yjs` + `y-websocket` UMD) | Automerge (pyautomerge stale; no maintained Python binding for Automerge 2) | Only CRDT with a production-proven Python binding (Jupyter) + built-in awareness/presence + undo manager |
| 3a | Semantic diff — code | **tree-sitter** (`tree_sitter` + `tree_sitter_python` wheels) | stdlib `ast` | Stable function/class identifiers, comment+format handling, multi-language path, judge-recognizable |
| 3b | Semantic diff — prose | **Custom LCS alignment over normalized sentence hashes** (own code, ~80 LOC) | `difflib.SequenceMatcher` on sentence lists | Alignment is THE shared primitive for diff + merge + retrieval; owning it is defensible and deterministic |
| 4 | Retrieval | **Chroma** (`chromadb.PersistentClient`, embedded) + SQLite FTS5 hybrid | Qdrant local mode / pgvector | Zero-ops embedded persistence matches SQLite; one `data/` dir; pgvector needs a Postgres server we don't need |
| 5 | Storage | **SQLite** (WAL, append-only, triggers forbid UPDATE/DELETE on objects/commits) | Postgres + pgvector | 13 hours, single machine, one process; immutability enforced by content addressing + triggers, not by a server |
| 6 | Stack | **Python 3.11+ engine + FastAPI server + thin vanilla-JS browser client** (two-language split) | All-TypeScript/Node | Research artifacts (PDF, chat JSON, embeddings) skew Python; y-py neutralizes Node's CRDT advantage |
| 7 | Deep stretch | **3-way prose merge with conflict UI** | Provenance graph | Directly amplifies the 35% versioning pillar AND the #1 demo moment; reuses the sentence alignment engine; provenance-lite comes nearly free via chunk metadata |
| 8 | Embeddings | **sentence-transformers `all-MiniLM-L6-v2`** (local, offline) | OpenAI embeddings API | No API key/network dependence at demo time; deterministic |

---

## 1. Versioning primitive — HOMEMADE content-addressed DAG (git is the runner-up, deliberately)

**Recommendation:** A git-inspired but research-aware object store, ~300 lines of stdlib (`hashlib`, `sqlite3`, `zlib`):
- **Blob** = `SHA-256("gr-obj-v1" || kind || "\0" || data)` — content-addressed, deduped, stored at `data/objects/<2-hex>/<38-hex>` (zlib-compressed). `kind ∈ {artifact, tree, chat}`.
- **Tree** = hash over sorted `(path, blob_hash)` pairs — a snapshot fingerprint of the artifact set (merkle-style).
- **Commit** = `SHA-256("gr-commit-v1" || parent_ids || tree_hash || message || author || author_date)` — hash is a full-snapshot fingerprint; any tamper breaks the chain.
- **Refs** = named pointers (branch → commit id). Merge commit = 2 parents. No in-place mutation, ever.
- Determinism carve-out: commit hash includes `author_date`; demo scripts pin it (`GR_AUTHOR_DATE`) so scripted hashes are reproducible across runs (git does the same thing — committer date is in the hash).

**Runner-up:** real git via subprocess/GitPython. **Decisive tradeoff:** a git repo is a *file tree of bytes*; research artifacts are *typed entities*. "Just wrap git" fails the beyond-wrapper test for four concrete reasons:
1. **Line-granular diff** — git diffs prose line-by-line; paragraph reflow and wrapping produce noise, and git has no notion of "sentence S became sentence T".
2. **Chat exports byte-diff trivially** — ChatGPT/Claude JSON contains volatile fields (timestamps, ids, key order). Two identical conversations byte-differ → git sees a "new version". We need *canonical semantic forms* (Section 8) before hashing — git cannot do this.
3. **No entity for provenance** — "claim → source chat/PDF/commit" has no representation in git's object graph. Our DAG + chunk metadata model it natively.
4. **Demo credibility** — a homemade merkle DAG with typed objects, an append-only immutable store and an alignment sidecar *is* the "real version-control model" judges score. Wrapping git is the lowest-credibility answer on the 35% pillar.

A homemade DAG also lets the commit hash be the fingerprint of *snapshots across heterogeneous artifacts* (prose + chat + PDF + code in one history) — intentional difference from git, which we state explicitly when judges probe. We still model codebases as per-file blobs (we don't reinvent git's tree for code); one uniform DAG covers all kinds.

## 2. Concurrency layer — Yjs (y-py on server, Yjs in browser)

**Recommendation:** Yjs end-to-end.
- **Server**: `y-py` (official Python binding of Yjs — the CRDT powering JupyterLab real-time collaboration, blog.jupyter.org June 2021; jupyterlab PR #9785) + **`ypy-websocket`** (PyPI, maintained, "Websocket backend, written in Python" per the yjs README — implements the same sync protocol as the JS `y-websocket` server).
- **Browser**: vendored UMD bundles `yjs` (`y.min.js`, self-contained) + `y-websocket` provider (includes sync protocol + awareness) or `y-protocols` — *no CDN dependency at demo time*.
- **Editor binding**: we hand-write a minimal `<textarea> ↔ Y.Text` binding in ~60 LOC: map `beforeinput` events (`insertText` / `deleteContentBackward` / `insertFromPaste`) to `Y.Text` ops; apply remote changes via `text.observe` with caret preservation. This is a deliberate depth point ("we wrote the binding") and avoids CodeMirror + y-codemirror integration risk. (Runner-up: y-codemirror.next + CodeMirror 6 — nicer UX, more moving parts.)
- **Presence**: Yjs awareness protocol relayed by the server — each client publishes `{user, color, artifactId, cursor}`; a "who's viewing" strip + colored caret per user in each pane.
- **Undo**: `Y.UndoManager` per pane on the shared `Y.Text` (client-side, tracks own transactions; works across remote edits). Coarse undo/redo across time = `checkout` of an old commit (DAG read → restore).
- **Live editing → versioning**: each `(artifact, branch)` has a draft `Y.Doc`. **Commit = snapshot** — serialize `Y.Text.toString()` → canonical artifact text → blob → DAG commit. Commits are serialized per-doc (a per-doc lock) so CRDT convergence and commit snapshots don't race.
- **Conflict model (what judges see)**: CRDT auto-merges *typing* conflicts; real conflicts are surfaced at *branch-merge* time via the sentence-level 3-way merge (Sections 3/7). Two branches, both editing sentence S differently → conflict UI. This separation (CRDT = fine-grained live layer; DAG = coarse-grained version layer; prose merge = conflict layer) is the architecture story.

**Runners-up:** Automerge — the better CRDT paper story, but `pyautomerge` wraps Automerge 1.x and is stale, and there is no maintained Python binding for Automerge 2 (Rust); breaks our Python-core constraint. OT log — we'd own ordering + transform functions, and undo/presence are DIY; only a fallback if y-py wheels fail to install (mitigation: pin `y-py>=0.8` which ships wheels; rebuild-from-source needs Rust).

**Decisive tradeoff:** the language constraint (Python engine) is satisfiable *only* by Yjs among the three candidates, and Jupyter's production deployment of y-py is the maturity proof judges will accept.

## 3. Semantic diff — tree-sitter for code, LCS-over-sentence-hashes for prose

Both demos are deterministic: `scripts/demo_semantic_diff.py` diffs fixed fixtures and prints structured JSON + a side-by-side rendering. pytest asserts **exact** JSON output.

### 3a. Code: tree-sitter CST at function granularity
- **Stack**: `pip install tree-sitter tree-sitter-python` — official Python bindings (tree-sitter/py-tree-sitter) + precompiled grammar wheels (tree-sitter/tree-sitter-python); mature, no compilation. (`tree-sitter-languages` bundles many grammars if time permits a 2nd language.)
- **Algorithm** (not a full gumtree CST diff — that's a research project, not an hour-3 task):
  1. Parse both versions to CSTs.
  2. Extract `function_definition` / `class_definition` nodes (incl. nested) with byte spans, structural signatures (name + parameter list).
  3. Match functions by signature; for matched pairs, compare **token streams** (serialized node tokens, comments retained): equal → no diff entry; different → Myers line-diff of the *function body only*.
  4. Emit structured diff: `{kind: "modified"|"added"|"removed"|"renamed", name, hunks}`.
- **Why this is "semantic"**: unchanged function bodies produce zero noise; a rename survives as "renamed" via signature comparison; comments/formatting don't create phantom changes. Judges see function-level intent, not byte soup.
- **Runner-up:** stdlib `ast` — zero deps, but no robust spans across formatting/comment-only changes and no path to more languages. **Decisive:** `ast` can't distinguish "formatting churn" from "logic change" reliably; tree-sitter can, and it's the tool judges expect to hear named.

### 3b. Prose: two-level alignment, not byte diff
- **Pipeline**: paragraph split on blank lines → sentence tokenization (compact hand-rolled regex splitter, ~40 LOC; handles abbreviations crudely but deterministically) → normalize (lowercase, strip punctuation, collapse whitespace) → hash each sentence.
- **Alignment**: **custom Myers/LCS over the sentence-hash sequences** (own implementation, ~50 LOC, `autojunk`-free, deterministic). For aligned pairs with equal position but differing hashes, compute `difflib.SequenceMatcher.ratio()` on the raw sentences: **≥ 0.7 ⇒ status "edited"** (keeps lineage), else separate delete+insert.
- **Granularity**: two-level — paragraph-level alignment first, then sentence-level within changed paragraphs. Output per sentence: `{sid, status: unchanged|edited|added|deleted, old_text?, new_text?}`. `sid = artifact_id:para_idx:sent_idx` at a commit; changed sentences are recorded as `(old_sid, new_sid, status, commit_id)` pairs in the sentence index (this is the lineage feed for retrieval, Section 4).
- **Runner-up:** `difflib.SequenceMatcher` directly on sentence lists — works today, but has auto-junk quirks and, more importantly, tells judges "we called difflib". **Decisive tradeoff:** this alignment engine is shared infrastructure for diff **and** 3-way merge **and** retrieval delta-indexing — owning it (deterministic, unit-tested) is the single highest-ROI piece of code in the project. ~2 hours of work, pays for itself three times.

**Demo script contract:** fixtures `base.md → ours.md` (edit 1 sentence, add 1 sentence, delete 1) and `base.py → ours.py` (rename a function, change one body, add one) produce human-readable diffs in under a second, printed as JSON + markdown.

## 4. Retrieval — Chroma (embedded) + per-type chunking + diff-fed delta reindex

**Recommendation:** `chromadb.PersistentClient(path="data/vectordb")` — embedded, disk-backed, no server (documented client mode, chroma docs). Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~80MB, CPU-fast, offline, deterministic — **pre-download the model in hour 0** into `data/models/`; fallback: a deterministic hash-based embedding function if the download fails, flagged as degraded). Secondary surface: SQLite **FTS5** keyword search (built into SQLite) for exact-term queries — cheap hybrid retrieval.

**Runner-up:** Qdrant local mode (`qdrant-client[local]`) — genuinely good, one more dependency. pgvector — the honest production answer, but requires a Postgres server we otherwise don't need (see §5). **Decisive:** same zero-ops rationale as SQLite; one `data/` directory holding DAG + blobs + vector store + FTS index is maximally simple to demo and explain.

**Chunk strategy per artifact type** (chunk id encodes type + stable path):
| Artifact | Chunker | Chunk size |
|---|---|---|
| Markdown | split on `##`/`###` headings; inside section, merge sentences | ≤ ~600 chars, 10% overlap; chunk id = section path |
| Chat (canonical) | **1 message = 1 chunk**, text prefixed `user:`/`assistant:`; thread id in metadata | variable; fine for retrieval |
| PDF | pypdf page text → paragraph blocks (blank-line split) | ≤ ~800 chars |
| Code | **tree-sitter function/class spans** = chunks (docstring/comment header + body) | clamp ≤ ~120 lines |

**How semantic diff feeds retrieval** (the depth story):
- On every commit `C`, reuse the alignment engine: align(parent version, C version) → changed/added/deleted sentence ids.
- **Delta reindex**: delete only the chunks containing changed sentences; upsert new chunks. Never re-embed the whole corpus.
- Each chunk carries provenance metadata: `{artifact_id, branch, introduced_in_commit, replaces_chunk_ids, sid_range}`.
- Query results therefore show *where each hit came from* ("introduced in commit `a1b2…`, replaces chunk from `9f3e…`, artifact `hypothesis.md`, branch `claims-review`") — provenance-lite for free, and the ground for a time-travel query (optional hour-11 add-on: filter chunks by commit ancestry + `replaces` chain).

## 5. Storage + persistence — SQLite + content-addressed blob store

**Recommendation:** single SQLite database `data/meta.db` (`PRAGMA journal_mode=WAL`, `synchronous=FULL`) + blob directory `data/objects/` + Chroma dir `data/vectordb/`. Chroma's own persistence is SQLite-backed too — one `data/` story.

**Schema sketch** (append-only; triggers `BEFORE UPDATE/DELETE ON objects/commits RAISE(ABORT)` as a belt-and-braces enforcement of immutability):
```
objects(hash TEXT PK, kind TEXT, size INTEGER, data BLOB)
commits(id TEXT PK, parent_ids TEXT, tree_hash TEXT, message TEXT, author TEXT, author_date TEXT)
refs(name TEXT PK, commit_id TEXT)
tree_entries(commit_id TEXT, path TEXT, blob_hash TEXT)
sentence_index(commit_id TEXT, artifact_id TEXT, sid TEXT, status TEXT, old_hash TEXT, new_hash TEXT, text TEXT)
chunks(chunk_id TEXT PK, artifact_id TEXT, commit_id TEXT, introduced_in_commit TEXT, replaces TEXT, sid_range TEXT)
```

**Immutability guarantees (state these to judges):**
1. Content addressing — blob identity *is* its hash; a modified artifact produces a different hash, never an overwrite.
2. Merkle chain — commit hash covers parents + tree; any historical mutation invalidates every descendant hash (verifiable: `gr verify` walks the chain).
3. Append-only — only INSERTs via the public API; SQL triggers hard-block UPDATE/DELETE on `objects`/`commits`.
4. Durability — WAL + `synchronous=FULL` (fsync on commit).

**Runner-up:** Postgres (+pgvector). **Decisive tradeoff:** 13 hours, one machine, one process, demo-sized corpus (assumption: ≤ few hundred artifacts, ≤ ~50MB blobs). Postgres buys nothing we can demonstrate in the remaining hours and costs server ops + migration friction. (We name this tradeoff explicitly in the README — "SQLite because the demo is single-node; pgvector is the scale-up path" — so judges hear we made the call on purpose.)

## 6. Language / stack — Python core, thin vanilla-JS browser client

**Recommendation:** Python 3.11+ monorepo. Engine = pure stdlib (`hashlib`, `sqlite3`, `zlib`, `difflib`) + `fastapi`/`uvicorn`/`websockets` server. Client = ~200 LOC vanilla JS (two-pane editor, Yjs UMD, conflict cards) served as static files — no framework, no build step. Dependencies (all pip, all with wheels): `y-py`, `ypy-websocket`, `chromadb`, `sentence-transformers`, `pypdf`, `tree-sitter`, `tree-sitter-python`, `fastapi`, `uvicorn`, `pytest`.

**Runner-up:** all-TypeScript/Node — yjs is native, tree-sitter has node bindings, better-sqlite3 exists. **Decisive tradeoff:** three of the four pillars skew Python (PDF text extraction, chat-export parsing ergonomics, embeddings via sentence-transformers), the DAG core is stdlib-only Python (zero dependency risk at the critical hour), and y-py removes Node's only real advantage (CRDT). The two-language split is thin and static — no build toolchain to break at hour 9.

## 7. Deep stretch — 3-way prose merge with conflict UI (provenance graph is runner-up, deliberately)

**Pick: 3-way prose merge + conflict UI.** Justification:
1. It amplifies the **highest-weight pillar (versioning 35%)** and the **#1 judged moment (live merge conflict)** — our conflict demo stops being "git-style text markers" and becomes sentence-level accept/reject, which is exactly "non-trivial diff/merge" the brief demands.
2. It **reuses the sentence alignment engine** from §3b — merge = align(base, ours) + align(base, theirs) and decide per sentence. Marginal cost is ~2 hours, not a new subsystem.
3. Its demo is **deterministic by construction**: fixture base/ours/theirs where both branches edit the same sentence.

**Why NOT the provenance graph:** it decorates retrieval (15%) and risks rendering "a graph that shows nothing" if time runs out. We capture ~80% of its demo value for free via chunk metadata (`introduced_in_commit`, `replaces`) in every search result — and *that* is what we say in the stretch Q&A: "provenance-lite is in the core; a full claim→source graph is the next-build paragraph."

**Bound scope (deliverable in ~2.5h, hour 5 + hour 9):**
- Engine `merge_prose(base, ours, theirs)` → per-sentence decisions `{keep | ours | theirs | conflict}`: unchanged everywhere → keep; changed only in one side → take it; both changed to identical text → take (convergent); changed differently → **conflict**. Insertions at the same anchor → conflict list (both shown, ordered ours-then-theirs in the card).
- Conflict record: `{sid, base_text, ours_text, theirs_text}`. Output: merged text + `conflicts[]`.
- UI: conflict cards with accept-ours / accept-theirs / free-edit; applying all resolutions writes the merge commit (2 parents) and the DAG records it.
- Test contract: (a) ours edits S1, theirs edits S2 → auto-merge clean; (b) both edit S → exactly 1 conflict; (c) both edit S to the same text → convergent, no conflict.
- **Non-goals**: no word-level diff3, no prose merge for code (code merge = file-level conflict detection + git-style markers as fallback, per the brief's "merging OR at minimum surfacing merge conflicts"), no recursive merge.

## 8. Ingestion — 4 adapters → one canonical model ("parse differently, store identically")

- **ChatGPT `conversations.json`**: array of conversations; each has `mapping` (dict msg-id → `{parent, children, message:{author:{role}, content:{parts[], content_type}}}`). Linearize by finding the root node (`parent == null`) and walking `children` (branching handled by priority order). Extract text from `parts`; drop non-text parts.
- **Claude export** (zip of `.jsonl`): each line has `chat_messages[]` with `{role, content: [{type:"text", text}, {type:"tool_use",…}], timestamp}`. Extract `type=="text"` blocks; join per message.
- **Canonical schema** (shared storage form): `ChatMessage {role: user|assistant|system, author, ts|null, text, source: chatgpt|claude, source_id}` → canonical JSON (sorted keys; timestamps kept but *not* hashed into identity — identity = role+text sequence) → blob.
- **Markdown**: raw text, kind=md. **PDF**: `pypdf` text extraction per page (text-extractable assumption; no OCR). **Codebase**: walk git repo/zip → per-file blobs (path → blob) in the tree; primary diff language Python, line-diff fallback for others.
- Adapters are tolerant (defensive field lookups) because the judge's real files are unknown (assumption §10); fixtures in both real schemas ship in `fixtures/`.

## 9. Ruthless 13-hour timeline (lanes: A = Muneer + engine agent; B = Amrit + integration agent; both + agents otherwise)

**Every hour ends with a working artifact. If an hour slips, we cut its polish, never its artifact.**

| Hour | Lane A (engine) | Lane B (ingestion/integration) | Working artifact at hour's end |
|---|---|---|---|
| **H0** | Lock this ADR (30 min). Scaffold repo, `pyproject.toml`, deps install, pre-download embedding model → `data/models/`. `gr init` (SQLite schema + immutability triggers + object dirs). | Same repo: fixtures in both chat schemas + base/ours/theirs prose fixtures authored. | `pytest tests/test_objects.py` green; `gr init` yields valid append-only store; model file present |
| **H1** | Object store + trees + commit DAG + refs + `gr commit`/`gr log` CLI (stdlib only). | — | Commit fixture md → `gr log` shows chain; hash changes on edit; UPDATE/DELETE trigger test green |
| **H2** | Prose diff: sentence splitter + paragraph splitter + LCS alignment + diff JSON. | — | `scripts/demo_semantic_diff.py` prints aligned-sentence JSON for fixture pair; pytest asserts exact output |
| **H3** | Code diff: tree-sitter function extraction + token-stream comparison + structured JSON. | — | Demo diff of 2 fixture `.py` files: `modified: compute_stats()` etc., rename detected |
| **H4** | Branch + checkout + merge plumbing (base resolution, conflict state persistence, resolution apply) — CLI path. | **Ingest parsers**: md + chatgpt + claude + pdf + codebase; `gr ingest`; canonical chat schema tests. | `gr branch/checkout/merge` works on fixtures; `gr ingest` loads all 4 types; chatgpt+claude → same canonical schema |
| **H5** | **3-way prose merge engine** + pytest contracts (clean / conflict / convergent). | **Retrieval v1**: chunkers per type + Chroma index + FTS5. | Merge contracts green; `scripts/demo_search.py` returns top-k with metadata |
| **H6** | FastAPI server: commit / diff / branch / merge endpoints + scripted demo wiring. | **Delta reindex on commit** (diff → delete/upsert changed chunks, provenance metadata). | `curl`-able API; test: commit an edit → only changed chunk ids replaced, `introduced_in_commit` correct |
| **H7** | **Collab**: y-py draft docs + `ypy-websocket` relay; vendored Yjs client; hand-rolled textarea↔Y.Text binding; awareness presence strip + cursors. | UI shell: two-pane workspace, artifact list, commit button. | Two browser panes live-edit one md; presence shows userA + userB; refresh-safe |
| **H8** | **Commit-from-live** (Y.Text snapshot → DAG commit, per-doc lock) + `Y.UndoManager` per pane + branch-fork-from-live. | Search UI + FTS hybrid + provenance display in results. | Edit in pane A → commit → log; undo/redo independent per pane; search shows introduced-in-commit |
| **H9** | **Conflict UI**: fork branch → divergent edits → dry-run merge → conflict cards (accept ours/theirs/edit) → merge commit (2 parents). | Demo script E2E: ingest → branch → conflict → resolve → semantic diff → search. | Full loop demoable live; merge commit visible in `gr log` with 2 parents |
| **H10** | **Hardening**: WS reconnect, double-commit guard, concurrent-edit-then-commit race (lock), error paths. | E2E pytest over HTTP+WS with two simulated clients; README skeleton. | `pytest` full suite green incl. concurrency tests |
| **H11** | **Buffer**: fix whatever slipped. If green: optional add-ons in this order — (1) time-travel query (ancestry-filtered chunks), (2) LLM one-line diff summary (decorative, flagged as LLM), (3) 2nd tree-sitter language. | same | TBD, prioritized by bug list, never at the cost of H12/H13 |
| **H12** | **Demo prep**: scripted sequence (ingest 2+ types → branch → live conflict → resolution → live semantic diff → corpus query with provenance), timed rehearsal, screenshots. | same | Rehearsed, timed demo script with printed outputs |
| **H13** | README (decisions + tradeoffs), one-paragraph "what we'd build next", judge Q/A prep (defend every table row above), final `pytest` + smoke run. | same | Repo + README + demo green, team ready |

*(Divergence from the brief's coarse plan: retrieval moves earlier (H5–6) because delta-reindex depends on the diff engine (H2) — retrieval is off the critical path, the two mandated demos are on it; merge arrives at H5 so the conflict UI can land by H9.)*

## 10. Requirement ambiguities + assumptions NOT in the brief

1. **Demo environment** (assumption): the 5-min live demo runs on our machine, localhost, two browser tabs, Chromium available; network *optional* because JS libs are vendored and the embedding model is pre-downloaded (with deterministic hash-embedding fallback). If judges demand running on a fresh laptop, we ship `pip install -r requirements.txt` + fixture corpus — flagged, not solved.
2. **"Merging OR at minimum surfacing merge conflicts"** (ambiguity): we build both — auto-merge for clean cases, conflict surfacing + resolution UI for conflicting ones. Interpretation: the "OR" is a minimum bar, not a pick-one.
3. **"Concurrent context layer" scope** (assumption): means concurrent *editing + presence* in one workspace (CRDT), with conflicts demonstrated via concurrent branch merges. If judges intend two users committing the same branch simultaneously, our per-doc commit lock serializes and remains correct — but we do not demo that as a headline.
4. **Chat export formats** (assumption): judge's actual files unknown; we implement to the documented ChatGPT `conversations.json` and Claude `.jsonl` schemas with defensive parsing, and ship realistic sample exports in both schemas for the demo. Demo ingestion uses our fixtures unless the judge supplies files on the spot.
5. **PDFs are text-extractable** (assumption, stated in brief as out-of-scope OCR): we use `pypdf` extraction; a scrape (images-only) PDF just fails ingestion gracefully with a message.
6. **Corpus scale** (assumption): ≤ a few hundred artifacts, ≤ ~50MB total — single-process SQLite + Chroma is sound at this scale; we say so in the README.
7. **"Semantic diff" for prose** (interpretation): structure-aware sentence/paragraph alignment (our §3b), *not* an LLM paraphrasing the diff. LLM is decorative-only (optional hour-11 one-line summary, labeled as such).
8. **Code pillar depth** (assumption): codebase ingestion = file-tree walk into our DAG; semantic diff for Python only; other languages get line-diff fallback. Code merge = file-level conflict detection, not function-level merge.
9. **Mock users** (stated in brief): userA/userB ids, no auth. Presence and authorship keyed by mock ids.
10. **Undo scope** (assumption): CRDT undo (Y.UndoManager) within the live editor session + coarse undo by commit checkout. We do not build cross-session per-user op undo.
11. **Commit determinism** (assumption we introduce): `author_date` pinned via env for scripted demos so hashes are reproducible; real commits use wall clock.
12. **Embedding model availability** (assumption): hour-0 network allows one model download; if not, deterministic hash-embedding fallback keeps retrieval demoable (worse quality, still functional) — this is the only sanctioned quality degradation.

## 11. Starter implementation surface (agents start here)

**Repo layout:**
```
gr/            hashutil.py objects.py dag.py schemas.py diff_prose.py diff_code.py
               merge_prose.py retrieval.py server.py cli.py
gr/ingest/     md.py chatgpt.py claude.py pdf.py codebase.py
client/        index.html app.js vendor/(yjs.min.js, y-websocket.min.js)
fixtures/  scripts/  tests/
```
**Key function signatures (contracts for parallel work):**
```python
# objects/dag
put_blob(kind: str, data: bytes) -> str                 # sha256 type-tagged, dedup
commit(parents: list[str], tree: dict[str, str], message: str,
       author: str, author_date: str | None = None) -> str
# diff/merge (THE shared primitive)
align_sentences(old: list[str], new: list[str]) -> list[Op]   # Op = {type, old_i, new_i, sim}
diff_prose(base: str, new: str) -> list[SentenceChange]       # sid, status, old_text?, new_text?
diff_code(old_src: str, new_src: str) -> CodeDiff             # function-level entries
merge_prose(base: str, ours: str, theirs: str) -> MergeResult # decisions + conflicts[]
# retrieval
index_commit(commit_id: str)                                  # diff-fed delta reindex
search(q: str, k: int = 5) -> list[Hit]                       # Hit has provenance metadata
# server (FastAPI)
POST /api/ingest   POST /api/commit   GET /api/diff/{a}..{b}
GET  /api/merge/{b1}/{b2}   POST /api/merge/apply   GET /api/search?q=
WS   /ws/{workspace}        # yjs sync + awareness relay
```
**Demo script order (rehearsed at H12):** `gr ingest fixtures/` (≥2 types) → semantic diff (prose + code) → branch + divergent edits → **live merge conflict** (cards) → resolve → merge commit → corpus query showing provenance.

## 12. Risks and mitigations (know these before hour 1)

| Risk | Mitigation |
|---|---|
| `y-py` wheel unavailable on judge machine → source build needs Rust | Pin `y-py>=0.8` (wheels for manylinux/mac/win); degrade path: server-authoritative broadcast (no CRDT) still demos presence; do NOT burn more than 30 min on it |
| Embedding model download fails | Hash-embedding fallback (deterministic, flagged); pre-download at H0 |
| Chroma/onnxruntime install bloat | Isolate `requirements.txt`; install at H0; fallback: FTS5-only retrieval (keyword search still demos retrieval) |
| Network down at demo | All JS vendored, model cached, embeddings local — demo runs fully offline |
| Scope creep (3rd stretch, OCR, auth, polish) | Brief §3 hard bans; H11 buffer list is capped and ordered; merge UI is the only stretch |
| Diff/merge nondeterminism | Fixtures + pinned `author_date` + pytest asserting exact JSON; sentence ids derive from base positions |
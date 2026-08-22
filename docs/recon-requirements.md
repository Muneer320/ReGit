# RECON — Requirement Extraction (4 separated lists)

## A. ORGANIZER REQUIREMENTS (from the problem statement PDF — non-negotiable)

**A1. Four mandatory pillars (minimal level OK for eligibility):**
- A. Ingestion: ≥3 artifact types — Markdown/plaintext, LLM chat exports (ChatGPT `conversations.json` AND Claude-specific export schema — DO NOT assume identical schemas), PDFs (text-extractable; OCR is stretch). Codebases = 4th type, strongly encouraged. **Preserve structure; never flatten to one giant string.**
- B. Versioning core (35%): discrete commits per artifact; SEMANTIC human-readable diff (not byte diff); branching; merging OR at minimum surfacing merge conflicts.
- C. Concurrent context layer (20%): multiple users, same workspace, live presence + real conflict scenarios.
- D. Retrieval (15%): corpus query surface.

**A2. Evaluation weights:** versioning 35 | concurrency 20 | ingestion 15 | retrieval 15 | stretch 10 | demo 5.

**A3. Judges FIRST ask to see:** (1) a live merge conflict, (2) a live semantic diff. Both must be deterministic and scriptable.

**A4. Deliverables:** working repo + README; 5-min live demo (ingest ≥2 types, one branch/merge, one corpus query); one-paragraph next-build.

**A5. Out of scope (explicit):** full auth (mock users fine), production OCR, building a vector DB from scratch (use pgvector/Chroma/Qdrant), polished UI.

**A6. Stretch (pick max 1–2 deep):** 3-way prose merge w/ conflict UI; provenance graph; cross-artifact diff; blame; time-travel query; multi-agent editing.

## B. RESEARCH FINDINGS (validated this run, sources cited)

- B1. `y-py` is **abandoned** (repo archived: "This project is abandoned, please look at pycrdt"). Successor: **pycrdt** (Python bindings to Yrs, Rust port of Yjs; by David Brochart/QuantStack, built for Jupyter RTC). **Verified locally: pycrdt 0.14.3 pip-installs with wheels on this machine (Python 3.11.15).**
- B2. **pycrdt-websocket** (y-crdt org, async WebSocket connector, actively maintained, 267+ commits, updated 2026) is the server-side sync layer. Jupyter ecosystem (jupyter_ydoc, jupyverse) migrated y-py → pycrdt.
- B3. Browser side stays **yjs + y-websocket** (UMD vendored, no CDN) — pycrdt is wire-compatible with the yjs sync/awareness protocol (same Yrs/Yjs family).
- B4. tree-sitter Python bindings (`tree-sitter` 0.26.x) ship precompiled wheels for all major platforms; `tree-sitter-python` grammar ships wheels; `tree-sitter-languages` bundles many grammars. Mature, no compilation.
- B5. Chroma `PersistentClient` = embedded, disk-backed, SQLite-based — zero server ops. sentence-transformers `all-MiniLM-L6-v2` = 384-dim, ~80MB, CPU-viable, offline.
- B6. Local env: Python 3.11.15, SQLite 3.53.1 (FTS5 available), node+npm present, date 2026-08-22.

## C. ENGINEERING ASSUMPTIONS (ours, flagged — not in the organizer statement)

1. Demo runs on our machine, localhost, two browser tabs; network optional (JS vendored, embedding model pre-downloaded at H0; hash-embedding fallback if download fails).
2. "Merging OR at minimum surfacing conflicts" — we build BOTH: auto-merge for clean cases + conflict surfacing/resolution UI. The "OR" is a floor, not a choice.
3. "Concurrent context layer" = concurrent editing + presence in one workspace (CRDT live layer) PLUS conflict scenarios demonstrated at branch-merge time. Same-branch simultaneous commits are serialized by a per-artifact lock.
4. Chat exports: judge's real files unknown → defensive parsing of documented ChatGPT/Claude schemas + our own realistic fixtures in both schemas.
5. PDFs are text-extractable; image-only PDFs fail ingestion gracefully.
6. Corpus scale ≤ few hundred artifacts, ≤50MB — single-process SQLite+Chroma is sound; README names pgvector as the scale-up path.
7. "Semantic diff" for prose = structure-aware sentence/paragraph alignment, NOT an LLM paraphrase. LLM is decorative-only if used at all.
8. Code pillar: Python gets tree-sitter function-level diff; other languages get line-diff fallback. Code merge = file-level conflict surfacing.
9. Mock users (userA/userB), no auth; presence/authorship keyed by mock ids.
10. Commit determinism: `author_date` pinnable via env (`GR_AUTHOR_DATE`) so scripted demo hashes reproduce.
11. The hackathon's 13h timer start is controlled by the humans; real elapsed setup time is an OFFSET on this plan (see 12h-execution-plan.md §0).

## D. STRATEGIC DECISIONS (ours — what we deliberately will NOT do)

1. No full auth. Zero time.
2. No DIY vector DB. Chroma embedded, pinned.
3. No production OCR.
4. UI = functional only (vanilla JS, no build step). Judges score the engine.
5. Exactly ONE deep stretch: **3-way prose merge with conflict UI** (see adr-05, mvp-target-stretch.md). Provenance graph value is captured as provenance-lite in the retrieval metadata; the full claim→source graph is the next-build paragraph.
6. Versioning engine in Python stdlib-first; no abstraction towers before the first commit exists.
7. LLMs never in the diff/merge/versioning path (correctness + the anti-wrapper story). LLM allowed only as a flagged, decorative one-line diff summary IF H11 buffer is green.
8. The flash-authored `architecture-decision.md` is superseded by the docs/ ADR set in this repo. Key supersessions: y-py → **pycrdt** (y-py is abandoned); ypy-websocket → **pycrdt-websocket**.

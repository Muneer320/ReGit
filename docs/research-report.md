# Research Report — library/tool validation with maturity citations

Validated 2026-08-22 for this run. Purpose: justify the locked choices with real maturity evidence, not popularity.

## CRDT: pycrdt + pycrdt-websocket (CHOSEN)
- **pycrdt**: Python bindings to Yrs (Rust port of Yjs), by David Brochart (QuantStack) for JupyterLab RTC. Docs: y-crdt.github.io/pycrdt. **Verified locally: `pip install pycrdt` → 0.14.3, wheels OK on Python 3.11.**
- **pycrdt-websocket** (github.com/y-crdt/pycrdt-websocket): async WebSocket connector, actively maintained (commits into 2026), used by Jupyter ecosystem.
- **y-py is ABANDONED** — github.com/y-crdt/ypy is a public archive: "This project is abandoned, please look at pycrdt." Jupyter migrated y-py → pycrdt (jupyter_ydoc#194, jupyverse#359, jupyter-server/team-compass#55). This is why the flash draft's y-py choice is superseded.
- Yjs (browser): yjs.dev, mature, editor bindings ecosystem, binary sync protocol, awareness, offline editing, UndoManager. We vendor UMD builds.

## Rejected CRDT alternatives
- **Automerge**: automerge.org; Rust/JS only for v2; pyautomerge wraps stale 1.x. No Python path.
- **eg-walker / Diamond Types**: research-grade event-graph-walker CRDT (JS/Rust); no Python bindings; wrong risk profile.
- **Custom minimal CRDT / OT**: convergence proof obligation we cannot meet credibly in 13h.

## Diff/parse: tree-sitter (CHOSEN for code)
- py-tree-sitter 0.26.x: "no library dependencies, pre-compiled wheels for all major platforms" (official repo). tree-sitter-python ships wheels; tree-sitter-languages bundles grammars as wheels. Judge-recognizable, zero compile risk.
- Prose alignment: custom LCS over normalized sentence hashes (own code) — shared by diff/merge/reindex; difflib used only for similarity ratio within aligned pairs.

## Retrieval: Chroma embedded + FTS5 (CHOSEN)
- Chroma `PersistentClient`: embedded, disk-backed (SQLite-based), no server — matches single-`data/` story.
- sentence-transformers `all-MiniLM-L6-v2`: 384-dim, ~80MB, CPU-fast, offline-deterministic.
- FTS5: built into SQLite 3.53.1 (verified present).
- pgvector = honest production answer, requires Postgres server we don't need; named as scale-up path.

## PDF: pypdf (CHOSEN)
Pure-python, maintained, per-page text extraction; no OCR (per brief).

## Web: FastAPI + uvicorn (CHOSEN)
Async REST+WS one process; minimal boilerplate; AI-generable route shells.

## Versioning core: Python stdlib (CHOSEN)
hashlib/sqlite3/zlib only — zero dependency risk at the critical hour; fully whiteboard-able.

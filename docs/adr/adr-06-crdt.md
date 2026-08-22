# ADR-06: Concurrency — CRDT choice

- **Status: LOCKED** · Owner: Muneer · **SUPERSEDES flash draft (which chose abandoned y-py)**

## Context / Problem
20%-pillar: multiple users in one workspace, live presence, real conflict scenarios. Need convergent concurrent editing with a Python-core stack.

## Alternatives compared (real technical reasons, not popularity)
| Candidate | Verdict | Reason |
|---|---|---|
| **Yjs family via pycrdt** | **WINNER** | Only CRDT with a maintained, production-proven Python binding: pycrdt = bindings to Yrs (Rust port of Yjs), built for Jupyter RTC, wheels verified locally (0.14.3). yjs in browser is wire-compatible (same sync/awareness protocol). Built-in awareness (presence) + UndoManager. |
| y-py + ypy-websocket | Rejected | **y-py repo is archived/abandoned** ("please look at pycrdt"). Flash draft's choice; superseded. |
| Automerge | Rejected | Excellent CRDT (RGA, rich provenance of ops), but no maintained Python binding (pyautomerge wraps stale Automerge 1.x; Automerge 2 is Rust with no official py binding). Breaks the Python-core constraint. |
| eg-walker / Diamond Types | Rejected | Research-grade (event-graph walker; fast OT/CRDT hybrid), JS/Rust only, no Python path, immature bindings. Wrong risk profile for 13h. |
| OT (custom) | Rejected | We'd own transform functions, ordering, server-authoritative sequencing, DIY presence + undo. Highest correctness risk per hour spent; only justified if CRDT wheels fail (fallback: server-authoritative last-writer-wins broadcast demos presence only). |
| Custom minimal CRDT | Rejected | A sequence CRDT with tombstones is ~500 LOC + weeks of edge-case hunting (interleaving anomalies). We cannot prove convergence in 13h; judges asking "how do you know it converges?" get a proof obligation we can't meet. pycrdt inherits Yjs's years of convergence hardening. |

## Decision
**pycrdt 0.14.x on the server (one Doc per (artifact, branch) draft) + pycrdt-websocket as WS relay + vendored yjs/y-websocket UMD in the browser.**

- Presence: Yjs awareness protocol relayed server-side; clients publish `{user, color, artifact_id, cursor}`.
- Undo: `Y.UndoManager` client-side per pane (own-origin transactions); coarse undo = checkout of old commit.
- Commit-from-live: per-artifact asyncio lock → `Text` snapshot → canonicalize → DAG commit → broadcast new head. CRDT (fine-grained live) and DAG (coarse durable) layers are explicitly separated; real *conflicts* surface at branch-merge via ADR-05, not at typing time.

## Why
Decisive tradeoff vs Automerge/OT/custom: language constraint (Python engine) + convergence guarantee + presence/undo for free + Jupyter production pedigree judges accept. pycrdt being Yrs-based also means the server holds authoritative docs in Rust-speed memory.

## Risks
- pycrdt-websocket API drift (young lib) → pin versions at H0; keep a hand-rolled minimal sync fallback behind a flag.
- Textarea↔Y.Text binding bugs (caret jumps) → hand-rolled binding ~60 LOC with `beforeinput` mapping; worst case degrade to whole-doc replace ops.

## Reversibility
Moderate: the realtime protocol (../specs/realtime-protocol.md) isolates transport from the CRDT; swapping CRDT libs touches one module.

## Consequences
- `backend/src/core/collaboration/` + `backend/src/realtime/`; concurrency tests in tests/concurrency simulate 2 clients: concurrent inserts, disconnect/reconnect, out-of-order, duplicate ops.

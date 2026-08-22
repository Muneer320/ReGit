# Ownership Matrix (LOCKED)

**Muneer = Principal Systems Engineer. His work is HARD: distributed systems, algorithms, correctness. Amrit = Product & Integration: UI, flows, testing, demo. AI = boilerplate multiplier with explanation duty.**

| Subsystem | Muneer | Amrit | AI agents |
|---|---|---|---|
| Object store (blobs/trees/commits, hashing, triggers) | **OWN: design + core code + review** | — | schema.sql, CRUD plumbing, tests from spec |
| DAG (merge-base LCA, refs, checkout) | **OWN** | — | adversarial DAG fixtures, log renderer |
| Prose alignment engine (split/normalize/LCS/classify) | **OWN — the spine** | — | edge-case test corpus |
| Code diff (tree-sitter) | **OWN algorithm** | — | grammar wiring, fixture code pairs |
| Chat/PDF differs | review | — | **implement from diff-spec** |
| 3-way merge engine + decision table | **OWN** | — | T1–T8 test scaffolding |
| Merge/conflict resolution API flow | **OWN semantics** | conflict cards UI | endpoint plumbing |
| CRDT integration (pycrdt rooms, op log, commit lock) | **OWN** | — | WS plumbing, reconnect helpers |
| Realtime client binding (textarea↔Y.Text) | review | **OWN** | caret-preservation utils |
| Presence UI | — | **OWN** | components |
| Ingestion adapters (md/chatgpt/claude/pdf/code) | canonical-form review | **OWN flow** | **implement parsers + fixtures** |
| Retrieval (chunkers, delta reindex, hybrid query) | filter semantics review | **OWN integration** | **implement chunkers/index plumbing** |
| Provenance (claims, edges, 3 queries) | **OWN semantics** | UI display | edge/claim CRUD + queries from spec |
| Immutability + invariant tests | **OWN test design** | run/gate | implement per spec |
| E2E + concurrency + adversarial suites | test design (merge/CRDT) | **OWN execution** | implement |
| Frontend shell (workspace, panes, history, search, cards) | — | **OWN** | generate components from spec |
| Demo script + rehearsal + judge Q&A | technical answers | **OWN narrative** | backup video, screenshots |
| README + docs upkeep | ADR accuracy | **OWN** | boilerplate sections |

## Rules
- No agent code enters `backend/src/core/{objects,versioning,diff/align.py,merge}` without Muneer reading it against the spec.
- Agent report format per subsystem: {Implemented, Files, Tests, Known limitations, Potential bugs, Decisions, Human-review-needed}.
- Muneer must be able to whiteboard: hashing scheme, LCS alignment, merge decision table, merge-base BFS, CRDT convergence argument, delta reindex. If he can't → stop, simplify, document, test.

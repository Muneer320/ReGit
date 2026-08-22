# 12-Hour Execution Plan (LOCKED, with real-clock offset note)

## §0 CLOCK OFFSET — READ FIRST
This plan is written in **hackathon-relative hours H0–H12** (13h total incl. demo+submit buffer). The humans control the real 13h timer start. **Real time already elapsed in setup/restart is an OFFSET, not consumed plan hours**: H0 begins when Muneer/Amrit actually sit down with this repo. If the organizers' clock started earlier, compress by cutting, in order: (1) H11 buffer add-ons, (2) frontend polish, (3) PDF/codebase ingest depth — NEVER cut the two mandated demo moments or the invariant tests. Record the actual offset in the first milestone report.

## Critical path (the chain that cannot slip)
`objects+commits (H0–1) → prose alignment engine (H2) → 3-way merge (H4–5) → conflict UI + merge demo (H9) → demo rehearsal (H12)`. CRDT (H6–7) is near-critical (20% pillar); retrieval/provenance (H7–8) hang off the alignment engine but are parallelizable.

## Hourly plan (every hour ends with a working artifact; slip = cut polish, never the artifact)

| Hour | Muneer (engine) | Amrit (product/integration) | AI agents | Exit artifact |
|---|---|---|---|---|
| H0 | Review/lock docs (30min w/ Amrit); object store + commit DAG + refs start | Fixtures authored (merge triple, diff pairs, both chat schemas); setup script run; model pre-downloaded | Repo scaffold verify; requirements install; `gr init` (schema+triggers); CI-ish test runner | `pytest test_objects` green; fixtures on disk; model cached |
| H1 | Commit/branch/log/checkout CLI + CAS refs | Wire `gr` CLI UX; smoke script | API skeleton from api-contract.md | `gr commit/log/branch/checkout` on fixture md; hash changes on edit; trigger test green |
| H2 | **Prose alignment engine** (splitter+normalize+LCS+classify) + exact-JSON tests | Diff view mock data contract | Chat/pdf differ adapters (message/page level) | `demo_semantic_diff.py` prints aligned JSON; pytest exact-output green |
| H3 | tree-sitter code diff (function extraction, token compare, rename) | Diff UI: colored two-pane rendering | PDF text-layer differ | Code fixture diff: `modified: f()`, rename detected |
| H4 | Merge-base (LCA) + adversarial DAG tests; merge plumbing (pending state, CAS) | **Ingest adapters E2E** (4 types) + `gr ingest` | Ingest API wiring + provenance edge writes | `gr ingest` loads 4 types; chatgpt+claude → same canonical id; merge_base green on diamond/criss-cross |
| H5 | **3-way prose merge engine** + T1–T8 contract tests | **Retrieval v1:** chunkers + Chroma + FTS5 | FTS5+Chroma plumbing, chunk metadata | Merge contracts green; `demo_search.py` top-k with metadata |
| H6 | FastAPI endpoints hardening (commit/diff/branch/merge) | **Delta reindex on commit** (diff→delete/upsert chunks) | WS plumbing skeleton (rooms, pycrdt-websocket) | curl-able API; test: commit → only changed chunks reindexed, `introduced_in_commit` correct |
| H7 | **CRDT integration:** pycrdt rooms, persist-before-broadcast, op log | Two-pane editor + vendored yjs + textarea↔Y.Text binding + presence strip | Awareness relay, reconnect logic | Two tabs live-edit; presence userA/userB; refresh-safe |
| H8 | **Commit-from-live** (lock, snapshot→commit, broadcast) + UndoManager + fork-from-live | Search UI + citations + provenance display | `demo_search.py` trace mode; provenance API | Edit pane A → commit → log updates in pane B; search hits show commit+source |
| H9 | **Conflict UI backend flow** (pending merge→cards→resolve→2-parent commit) | Conflict cards UI + demo E2E wiring | E2E test: two simulated WS clients | FULL LOOP live: ingest→branch→conflict→resolve→diff→search |
| H10 | Hardening: WS reconnect, double-commit guard, races, `gr verify` | E2E pytest over HTTP+WS; README skeleton | Adversarial test suite run + fixes | Full pytest green incl. concurrency+adversarial |
| H11 | Buffer: fix slips. If green, in order: (1) time-travel query toggle, (2) LLM one-line summary (labeled), (3) 2nd tree-sitter lang | Same; demo dataset curation | Backup demo video recorded | Prioritized fixes only |
| H12 | **Demo rehearsal ×2, timed**; judge-QA drill (judge-qa.md) | Same + final README + next-build paragraph | Freeze: tag repo, requirements.lock | Rehearsed demo + repo + README; submission |

## Hard cut-offs (auto-downgrade on miss)
T+2h object/commit model works · T+4h prose diff exact-output green · T+6h merge contracts green · T+7h live collab two-tab demo · T+9h cited search + full loop · T+10h FEATURE FREEZE · T+11h bug fixes only · T+12h demo.

## Milestone report template (every hour, 2 minutes)
`STATUS {Working|Broken|Risky} · ahead/behind vs plan · critical path state · next 60min per person/agent · CUT / PROTECT list.`

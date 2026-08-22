# Amrit — Frontend / Product & Integration Brief (ReGit)

You own the **product surface, frontend client, and demo presentation**. Muneer builds the engine (object store, alignment, merge, CRDT); your job is to make it visible, usable, and demoable. This doc is exact — file paths, commands, contract references. Work in parallel with Muneer; you do NOT need to touch the versioning/diff/merge core.

**GitHub:** `Muneer320/ReGit` (you're a collaborator — accept the invite)
**Branch:** `main` — pull before you start, commit to `main` (short hackathon, no PR ceremony).

---
## 0. Environment — one time
```bash
cd ~/git-for-research   # the repo is ReGit; local checkout dir may still be ~/git-for-research
git pull origin main
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
All frontend code is **static vanilla JS** served by FastAPI — no framework, no npm build step.

## 1. What you build (frontend/ — ~6 surfaces)
All in `frontend/src/`. Structure per `docs/adr/adr-08-frontend.md`:
```
frontend/src/
  pages/       (workspace, editor, history, diff, conflicts, search)
  components/  (presence strip, diff view, conflict card, artifact list, ingest upload)
  lib/         (api.js — REST client · ws.js — yjs/WS client · ybinding.js — textarea↔Y.Text)
frontend/vendor/  (yjs UMD y.min.js + y-protocols + y-websocket — vendored, offline)
```
Static files served by the backend — confirm mount at `backend/src/api/main.py` (it should serve `frontend/` at `/`).

## 2. The 6 surfaces (functional, not pretty — judges score the engine)
| # | Surface | What it must do | REST it calls |
|---|---|---|---|
| 1 | **Workspace** | list artifacts, ingest upload (type dropdown), branch selector | `GET /api/artifacts/:id`, `POST /api/ingest`, `GET /api/branches?artifact_id=` |
| 2 | **Two-pane editor** | userA/userB tabs, presence strip, colored cursors, live CRDT sync | `WS /api/collaborate/:artifact_id?branch=&user=` |
| 3 | **History** | commit DAG list + checkout | `GET /api/artifacts/:id/history?branch=` |
| 4 | **Diff view** | sentence-level colored alignment (prose) | `GET /api/diff?artifact_id=&from=&to=` |
| 5 | **Conflict cards** | base/ours/theirs + accept-ours/theirs/free-edit | `POST /api/merge`, `POST /api/merge/:id/resolve` |
| 6 | **Search** | query → cited results (artifact, branch, commit, source) | `POST /api/search` |

Files already scaffolded: empty dirs at `frontend/src/{pages,components,lib}`. You fill them.

## 3. Exact contracts (from `docs/specs/api-contract.md` — read it fully)
- **Base URL:** `http://localhost:8377/api`. JSON in/out. Errors: `{error:{code,message}}`.
- **Mock auth:** send header `X-User: userA` or `X-User: userB` (that's how presence/concurrency demos work — two tabs, two different users).
- **Live editor (surface 2):** `WS /api/collaborate/:artifact_id?branch=&user=` — binary yjs sync + awareness frames. Control frame: send `{type:"commit_request", message}` → server commits the live doc under a lock → broadcasts `{type:"committed", commit_id}`.
- **Merge flow (surface 5, THE demo):** `POST /api/merge {artifact_id, ours_branch, theirs_branch}` → either `{state:"clean"}` (auto-commits) or `{state:"conflicts", conflicts:[...]}`. Then `POST /api/merge/:id/resolve {resolutions:[{conflict_id, resolution, resolved_text?}]}`.

Read these for full detail — they ARE the contract you code against:
- `docs/specs/api-contract.md`
- `docs/specs/realtime-protocol.md`
- `docs/adr/adr-08-frontend.md`

## 4. Vendoring yjs (offline requirement — do this FIRST)
Architecture.md's whole demo bet is "runs fully offline." Grab the UMD builds into `frontend/vendor/` once (from CDN, then commit):
```bash
# yjs, y-protocols, y-websocket UMD builds into frontend/vendor/
```
Verify offline: after wiring dev server, load the page with **network disabled** — it must still work. Do this early.

## 5. Integration order (your H0→ comparable to Muneer's)
1. `lib/api.js` — thin fetch wrapper for all REST endpoints (surfaces 1,3,4,5,6 throughout).
2. **Diff view (surface 4) + workspace (surface 1)** — highest demo value, no CRDT needed. Muneer's `align.py` + `three_way.py` are stubs right now; you can build the UI against the API contract and test with `scripts/fixtures/merge/*` once he lands the engine — or temporarily against mocked responses.
3. History + search (3, 6) — REST-only, cheap, high demo clarity.
4. **Two-pane editor (2)** — CRDT; needs `lib/ybinding.js` (textarea↔Y.Text). Coordinate with Muneer on when the WS endpoint is live.
5. **Conflict cards (5)** — THE live-merge demo. Use `scripts/fixtures/merge/{base,ours,theirs}.md`.
6. Demo narrative + UI state prep — prepare the exact 8-scene story from `docs/demo/demo-script.md`.

## 6. The demo moment you own
Judges ask for a **live merge conflict** first. Your job: have the two-pane editor open on two branches (base/ours/theirs notes) so when Muneer hits merge, the conflict cards render and you resolve live on screen. Rehearse this until it's a reflex.

## 7. Testing (your domain)
- E2E flows on your 6 surfaces against the live backend.
- **Failure reproduction** — tell Muneer exactly what breaks the UI when the backend isn't ready (mocked fallback).
- Regression: after each engine change, re-test diff + merge surfaces.

## 8. Demo fallback (you + Muneer)
If CRDT live editor fails → CLI/API demo (Muneer runs `python -m backend.src.cli`). If embeddings fail → BM25. If PDF parse fails → prepared text. The system must stay demoable if any one layer dies — know which fallback you're switching to.

## ⚠️ Definition of DONE for you
- [ ] 6 surfaces rendered against the real API
- [ ] Diff view + workspace working (no CRDT)
- [ ] Two-pane live editor converging across 2 tabs (2 users)
- [ ] Merge conflict renders as cards + resolves live
- [ ] Search returns cited results
- [ ] Offline check: page works with network disabled
- [ ] 8-scene demo narrative rehearsed

**Questions?** Ask in team chat. If the backend isn't up yet, build against the contract and mock responses — don't block on Muneer's engine.
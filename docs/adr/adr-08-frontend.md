# ADR-08: Frontend stack

- **Status: LOCKED (updated for React)** · Owner: Amrit + AI

## Decision (REVISED — supersedes the original vanilla-JS choice)
**React 18 + TypeScript + Vite.** Rationale update vs the original "vanilla JS, no build" call:
- The original ADR worried a build toolchain is "a top-3 failure source at hour 9." That assumed an unknown team (and conservatism on VPS limits). Our constraint now: **node 22 + npm 10 confirmed available**, Vite dev-server build verified working, and the client is **fully decoupled** from the engine via REST + WS contracts — so this is high-reversibility (per original ADR). Switching the client does NOT touch the engine.
- React's component model genuinely fits the surface count (6 screens) and the interactive states (live presence, conflict cards, two-pane editor, diff view, search). Amrit is faster componentizing than hand-rolling DOM.
- **CRDT goal unchanged:** the two-pane editor binds a `<textarea>`/contentEditable to `Y.Text` via the `yjs` lib (hand-written binding retained as a deliberate depth point — "we wrote the CRDT binding"). Vendored `yjs` + `y-websocket`.
- UI polish is still explicitly OUT of scope (judges score the engine). React buys maintainability, not decoration.

## Why (runner-up: vanilla JS + no build)
Decisive tradeoff: the original no-build approach minimized toolchain risk but cost velocity on interactive surfaces. With node+Vite proven on the target machine and the engine fully contract-decoupled, React is now lower-risk than it appears and higher-velocity. Keep the door open: if Vite becomes a problem at hour 9+, the API client (`src/lib/api.ts`) isolates backend access, and screens can be degraded to static rendering without losing the engine.

## Surfaces (functional, clear affordances)
1. Workspace: artifact list + ingest upload + branch selector.
2. Two-pane editor (userA / userB tabs) with presence strip + colored cursors [yjs Y.Text].
3. History pane: commit DAG list, checkout.
4. Diff view: sentence-level colored alignments (prose) + function-level entries (code).
5. Conflict cards: base/ours/theirs + accept-ours / accept-theirs / free-edit.
6. Search: query box → cited results (artifact, branch, introduced-in-commit, source).

## Stack details
- **Vite** dev server (port 5173) with proxy: `/api` → `http://localhost:8377`, `/ws` → `ws://localhost:8377` (FastAPI single worker).
- **`src/lib/api.ts`** — thin typed REST client; base `/api`; mock-auth `X-User` header; multipart ingest; WS lives in `src/lib/ws.ts`.
- Build target: `frontend/dist` (FastAPI can serve it at production; in dev use the Vite proxy).

## Risks
- Build toolchain on VPS (mitigated: node/npm verified, build green).
- Y.Text ↔ textarea binding edge cases — accepted; fallback apply-as-whole-doc ops.
- Client/backend mismatch if API shapes drift — mitigate by regenerating `api.ts` from `api-contract.md` + integration tests.

## Reversibility
**High.** The client talks only REST+WS contracts; the whole frontend can be replaced wholesale without touching the engine. This is why the React switch was cheap.

## Consequences
`frontend/src/{pages,components,lib}` + `frontend/vendor/` or npm `yjs`. Two-pane editor depends on the WS endpoint (issue #9/#6). Build/serve: `npm run dev` (dev proxy) or `npm run build` → serve `dist/`. Rebuild after any API shape change.
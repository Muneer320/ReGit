# ADR-08: Frontend stack

- **Status: LOCKED** · Owner: Amrit + AI

## Decision
**Vanilla JS + HTML + CSS, static files served by FastAPI. No framework, no build step.** Vendored UMD: `yjs` (`y.min.js`) + `y-websocket` + `y-protocols`. Hand-written `<textarea> ↔ Y.Text` binding (~60 LOC): map `beforeinput` (insertText/deleteContentBackward/insertFromPaste) → Y.Text ops; remote ops applied via `text.observe` with caret preservation.

## Why (runner-up: React + CodeMirror 6 + y-codemirror.next)
Decisive tradeoff: a build toolchain (npm install of hundreds of packages, bundler config) is a top-3 failure source at hour 9 and buys pixels, not points — UI polish is explicitly out of scope and judges score the engine. The hand-rolled binding is itself a depth point ("we wrote the CRDT binding"). CodeMirror runner-up stays available as an H11 cosmetic upgrade ONLY if the core is green.

## Surfaces (functional, clear affordances)
1. Workspace: artifact list + ingest upload + branch selector.
2. Two-pane editor (userA / userB tabs) with presence strip + colored cursors.
3. History pane: commit DAG list, checkout.
4. Diff view: sentence-level colored alignments (prose) + function-level entries (code).
5. Conflict cards: base/ours/theirs + accept-ours / accept-theirs / free-edit.
6. Search: query box → cited results (artifact, branch, introduced-in-commit, source).

## Risks
Textarea binding edge cases (selection, IME) — accepted; fallback: apply-as-whole-doc ops. No framework = more DOM code — AI generates components from spec.

## Reversibility
High: the client talks only REST+WS contracts; can be replaced wholesale later.

## Consequences
`frontend/src/{pages,components,lib}` + `frontend/vendor/` (yjs UMD vendored at H0 — verify by loading page with network disabled).

# Collaboration Spec (LOCKED)

Owner: Muneer (CRDT semantics), Amrit (presence/conflict UI). Implements ADR-06/10.

## Model — two layers, stated explicitly to judges
- **Live layer (CRDT):** fine-grained concurrent typing on a shared draft of (artifact, branch). Converges automatically; no "conflicts" at typing time — by design.
- **Version layer (DAG):** coarse-grained durable history. Real research *conflicts* are surfaced at branch-merge time (merge-spec.md), where they are semantic and reviewable.
This separation is the answer to "does the CRDT hide conflicts?": no — it absorbs character-level races so that branch-level conflicts stay meaningful.

## Presence
Awareness per room: `{user, color, cursor, artifact_id}`. UI: colored strip of active users + per-pane colored caret/selection. Mock users userA/userB.

## Editing
textarea↔Y.Text binding (beforeinput mapping; remote ops via observe with caret preservation). Undo: per-pane `Y.UndoManager` (own-origin). Cross-time undo = checkout.

## Commit-from-live
`commit_request` → per-artifact lock → snapshot → commit → broadcast `committed`. History pane updates live for both users. Branch-fork-from-live: POST /branches at current head; new branch gets its own room seeded from that commit's content.

## Consistency guarantees (testable)
- Convergence property test: 3 simulated clients, shuffled op delivery → identical final text.
- Disconnect/reconnect: B edits offline-ish (ops buffered client-side), A continues; reconnect → sync step heals; final states equal.
- Duplicate op: no-op. Out-of-order: safe.
- Commit during active editing: lock ensures the snapshot is a convergent point; ops arriving during commit apply to the doc and land in the NEXT commit (documented behavior).

## Scenarios the demo shows (each <30s)
1. Two tabs, same artifact+branch: live co-editing + presence + independent undo.
2. Fork → both branches edit the same sentence differently → merge → conflict card → resolve → 2-parent commit in DAG view.
3. Kill server mid-edit → restart → room rebuilt from head + op log; text intact.

## Non-goals
No per-character attribution view (blame-lite is post-hackathon), no multi-doc transactions, no CRDT for chat/PDF (prose docs + code files only in the live layer; other kinds version via ingest/commit).

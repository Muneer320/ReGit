# Realtime Protocol (LOCKED)

Wire: WebSocket, `/collaborate/:artifact_id?branch=X&user=userA`. Two frame classes: **binary yjs protocol frames** (sync + awareness + update) and **JSON control frames** (our layer). Server = authoritative room host (pycrdt Doc per room). Client = yjs Doc + y-websocket-style handshake implemented in vendored JS.

## Rooms
`room = f"{artifact_id}:{branch}"`. One pycrdt `Doc` + one `Text` ("content") per room, created lazily from branch head content, destroyed after 60s idle.

## Connection lifecycle
1. Client connects with `user` param (mock auth; presence identity).
2. **Sync step 1:** client sends `SYNC_STEP1` (state vector). Server replies `SYNC_STEP2` (missing updates) then its `SYNC_STEP1`; client replies with its missing updates. Standard yjs two-step — reconnect-safe by construction.
3. Server sends `AWARENESS` snapshot of current room users; client publishes its own awareness `{user, color, cursor}`.
4. Steady state: edits → binary `UPDATE` frames both directions; awareness heartbeats every 5s; stale awareness evicted after 30s.

## Server handling of an UPDATE frame
1. Validate room exists + frame decodes. Drop invalid (log + close 4003).
2. **Persist:** INSERT INTO crdt_ops (append-only op log, per-room monotonic `seq` for debugging).
3. Apply to authoritative pycrdt Doc (idempotent — duplicates are no-ops; out-of-order safe by CRDT).
4. Broadcast binary update to all OTHER room connections.
5. Ack not required (yjs protocol has no per-op ack; state-vector resync heals loss on reconnect).

## JSON control frames (our layer)
- C→S `{type:"commit_request", message}` → server acquires per-artifact lock, snapshots Text → canonicalize → DAG commit (parents=[branch head]) → moves branch ref → broadcasts S→C `{type:"committed", commit_id, author, message}` to ALL room clients (UIs refresh history pane).
- C→S `{type:"presence_ping"}` → awareness refresh.
- S→C `{type:"error", code, message}`.

## Guarantees (what we tell judges)
- **Convergence:** any set of clients that exchange the full op set reach byte-identical Text — CRDT property, not our ordering. Property test: shuffle recorded op log, replay, assert equality.
- **No lost ops:** persisted before broadcast; crash → room rebuilt from branch head + op-log replay.
- **Duplicate/out-of-order:** harmless (idempotent, order-independent application).
- **Clock:** no wall-clock dependence for correctness; `seq` and `received_at` are observability only.

## Failure behavior
- WS drop: client y-websocket reconnects with backoff → sync step 1 heals state.
- Server restart: rooms cold; first client triggers rebuild from `branch head + ops log replay` (deterministic).
- Commit race (two commit_requests): lock serializes; second commit's parent is the first's result — both succeed, order visible in history.

## Demo fallback
Realtime dead → `scripts/replay_ops.py <room>` deterministically replays a recorded op log into a doc and prints final text + convergence hash. This is the scripted offline-convergence demo.

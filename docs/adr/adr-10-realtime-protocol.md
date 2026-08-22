# ADR-10: Realtime protocol

- **Status: LOCKED** · Owner: Muneer · Full wire spec in ../specs/realtime-protocol.md

## Decision
**WebSocket per (workspace) room, yjs sync protocol (state-vector exchange + binary update messages) via pycrdt-websocket on the server and y-websocket in the browser, plus awareness messages for presence. Server persists every update to `crdt_ops` (append-only op log per (artifact,branch)) before broadcasting.**

Client A op → server {validate room+doc, persist op, apply to authoritative pycrdt Doc, broadcast} → Client B. Reconnect = client sends state vector → server sends missing updates (standard yjs sync step 1/2). Duplicate/out-of-order ops are harmless by CRDT construction (idempotent, commutative application).

## Why (runner-up: custom JSON op protocol over WS)
Decisive tradeoff: a custom protocol makes convergence OUR proof obligation ("how do you know out-of-order ops converge?" — we couldn't answer credibly in 13h). The yjs protocol gives a mathematically-grounded answer plus free awareness/presence framing. JSON-vs-binary: yjs binary encoding is compact and both ends already speak it; hand-rolling JSON ops buys debuggability but costs the convergence story — wrong trade.

## Why server-persist-before-broadcast
Op log = crash recovery + the "offline CRDT replay" demo fallback (deterministic re-application of the log if realtime dies live). Ordering: server assigns monotonic `seq` per room for display/debug; CRDT correctness never depends on seq.

## Risks
pycrdt-websocket room management API drift → pin at H0, wrap in our own thin `RoomRegistry`. Awareness floods at many clients → demo caps at 2–3 users.

## Reversibility
Moderate: protocol spec is documented standalone; a different CRDT could speak the same room/persist/broadcast shell.

## Consequences
`backend/src/realtime/ws.py` + `specs/realtime-protocol.md` message catalog; tests/concurrency replays recorded op logs.

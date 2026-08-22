"""FastAPI WebSocket endpoint: /collaborate/:artifact_id?branch=&user=

Implements realtime-protocol.md's wire contract on pycrdt 0.14.x primitives
(verified API — see CHANGELOG for why pycrdt-websocket 0.16.x is not used):

- Binary frames, yjs protocol: [SYNC=0][subtype][len][payload] and
  [AWARENESS=1][len][payload].
  * SYNC_STEP1 (client state vector)  -> server replies SYNC_STEP2 (missing
    update) — reconnect/state-vector sync by construction.
  * SYNC_STEP2 / SYNC_UPDATE          -> persist to crdt_ops, apply to the
    authoritative room Doc (idempotent), relay the raw frame to other clients.
  * AWARENESS                         -> relay verbatim + record presence.
- JSON control frames: `{type:"commit_request", message}` -> commit-from-live
  under the per-artifact lock -> broadcast `{type:"committed", ...}` to ALL
  room clients; `{type:"presence_ping"}` -> awareness refresh.
- Invalid frames: dropped and the connection closed with 4003 (spec).

Server -> client on join: sync step1 (our state), JSON presence snapshot, and
each known user's last raw awareness frame (verbatim replay).
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import suppress

from fastapi import WebSocket, WebSocketDisconnect
from pycrdt import (
    Decoder,
    YMessageType,
    YSyncMessageType,
    create_sync_message,
    handle_sync_message,
    read_message,
)

from ..core.collaboration.ops import update_digest
from ..core.collaboration.rooms import CollabHub, LiveRoom, commit_live
from ..core.objects.store import ObjectStore

log = logging.getLogger("realtime.ws")

# An empty yjs update (varuint-0 payload) carries nothing; never logged/relayed.
_EMPTY = (b"", b"\x00\x00")


# ---------------------------------------------------------------------------
# app.state accessors (mirror api/main.get_store; adr-07: single worker)
# ---------------------------------------------------------------------------
def _store_from_app(app) -> ObjectStore:
    store = getattr(app.state, "store", None)
    if store is None:
        store = ObjectStore(os.environ.get("GR_API_DATA_DIR", "data"))
        app.state.store = store
    return store


def _hub_from_app(app) -> CollabHub:
    hub = getattr(app.state, "collab_hub", None)
    if hub is None:
        hub = CollabHub(_store_from_app(app))
        app.state.collab_hub = hub
    return hub


# ---------------------------------------------------------------------------
# crdt_ops persistence (append-only, content-addressed op id -> dedup by PK)
# ---------------------------------------------------------------------------
def persist_op(store: ObjectStore, room_key: str, update: bytes,
               client_id: str, received_at: str | None = None) -> str | None:
    """INSERT the update into crdt_ops (dedup: same update can never be logged
    twice — op id is the update's content address). Returns op id or None."""
    if update in _EMPTY:
        return None
    op_id = "op_" + update_digest(update)[:26]
    from datetime import UTC, datetime

    stamp = received_at or datetime.now(UTC).isoformat()
    with store._tx() as db:
        if db.execute("SELECT 1 FROM crdt_ops WHERE id=?", (op_id,)).fetchone():
            return None
        seq = db.execute(
            "SELECT COALESCE(MAX(seq),0)+1 FROM crdt_ops WHERE room=?", (room_key,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO crdt_ops(id, room, seq, client_id, op, received_at) "
            "VALUES (?,?,?,?,?,?)",
            (op_id, room_key, seq, client_id, update, stamp),
        )
    return op_id


# ---------------------------------------------------------------------------
# awareness payload parsing (best-effort; frames relayed verbatim regardless)
# ---------------------------------------------------------------------------
def _parse_awareness_payload(payload: bytes) -> list[tuple[int, dict]]:
    """yjs awareness update: [n][(clientId, clock, state_json)...]. Return
    [(client_id, {user,color,cursor,...})]; empty on malformed input."""
    out: list[tuple[int, dict]] = []
    try:
        dec = Decoder(payload)
        n = dec.read_var_uint()
        for _ in range(n):
            cid = dec.read_var_uint()
            dec.read_var_uint()  # clock
            raw = dec.read_message()
            state = json.loads(raw.decode("utf-8")) if raw else {}
            out.append((cid, state))
    except Exception:
        return []
    return out


# ---------------------------------------------------------------------------
# broadcast helpers
# ---------------------------------------------------------------------------
async def _broadcast_bytes(room: LiveRoom, sender: WebSocket, frame: bytes) -> None:
    for user, ws in list(room.clients.items()):
        if ws is sender:
            continue
        try:
            await ws.send_bytes(frame)
        except Exception:
            log.exception("broadcast_bytes failed to %s (dropping peer)", user)
            room.clients.pop(user, None)  # dead peer; yjs reconnect heals


async def _broadcast_json(room: LiveRoom, sender: WebSocket, payload: dict) -> None:
    frame = json.dumps(payload)
    for user, ws in list(room.clients.items()):
        if ws is sender:
            continue
        try:
            await ws.send_text(frame)
        except Exception:
            room.clients.pop(user, None)


async def _broadcast_json_all(room: LiveRoom, payload: dict) -> None:
    frame = json.dumps(payload)
    for user, ws in list(room.clients.items()):
        try:
            await ws.send_text(frame)
        except Exception:
            room.clients.pop(user, None)


# ---------------------------------------------------------------------------
# frame handling
# ---------------------------------------------------------------------------
async def _on_binary(hub: CollabHub, room: LiveRoom, store: ObjectStore,
                     ws: WebSocket, frame: bytes, user: str) -> bool:
    """Handle one binary yjs frame. Returns False when the frame is invalid
    (caller should close 4003 per realtime-protocol.md)."""
    if not frame:
        return False
    mtype = frame[0]
    try:
        if mtype == YMessageType.SYNC:
            subtype = frame[1]
            if subtype == YSyncMessageType.SYNC_STEP1:
                # client sent its state vector -> reply with exactly the
                # missing update (reconnect-safe by construction).
                reply = handle_sync_message(frame[1:], room.doc)
                if reply is not None:
                    await ws.send_bytes(reply)
                return True
            if subtype in (YSyncMessageType.SYNC_STEP2, YSyncMessageType.SYNC_UPDATE):
                update = read_message(frame[2:])
                if update not in _EMPTY:
                    new = room.apply_update(update, client_id=user)
                    if new and store is not None:
                        persist_op(store, room.room, update, user)
                    # relay the raw frame to the OTHER clients (spec: broadcast
                    # binary update after persist+apply).
                    await _broadcast_bytes(room, ws, frame)
                return True
            return False  # unknown sync subtype -> 4003
        if mtype == YMessageType.AWARENESS:
            payload = read_message(frame[1:])
            for _cid, state in _parse_awareness_payload(payload):
                room.set_awareness(
                    str(state.get("user", user)),
                    {"user": state.get("user", user), "color": state.get("color"),
                     "cursor": state.get("cursor")},
                    frame=frame,
                )
            await _broadcast_bytes(room, ws, frame)
            await _broadcast_json(room, ws, {"type": "presence",
                                             "users": room.awareness_snapshot()})
            return True
        return False
    except Exception:
        log.exception("invalid yjs frame in room %s", room.room)
        return False


async def _on_text(hub: CollabHub, room: LiveRoom, store: ObjectStore,
                   ws: WebSocket, text: str, user: str) -> None:
    """JSON control frames (our layer, realtime-protocol.md)."""
    try:
        payload = json.loads(text)
    except ValueError:
        await ws.send_text(json.dumps({"type": "error", "code": "INVALID_JSON",
                                       "message": "control frame must be JSON"}))
        return
    kind = payload.get("type")
    if kind == "commit_request":
        message = str(payload.get("message") or "")
        try:
            cid = await commit_live(hub, store, room, user, message)
        except Exception as exc:
            log.exception("commit_request failed in %s", room.room)
            await ws.send_text(json.dumps({"type": "error", "code": "COMMIT_FAILED",
                                           "message": str(exc)}))
            return
        await _broadcast_json_all(room, {"type": "committed", "commit_id": cid,
                                         "author": user, "message": message})
    elif kind == "presence_ping":
        room.touch_awareness(user)
        await ws.send_text(json.dumps({"type": "presence",
                                       "users": room.awareness_snapshot()}))
    else:
        await ws.send_text(json.dumps({"type": "error", "code": "UNKNOWN_FRAME",
                                       "message": f"unknown control frame {kind!r}"}))


# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------
async def collaborate(websocket: WebSocket, artifact_id: str,
                      branch: str = "main", user: str = "anonymous") -> None:
    """WS /collaborate/:artifact_id?branch=&user= (registered in api/main.py)."""
    store = _store_from_app(websocket.app)
    hub = _hub_from_app(websocket.app)
    try:
        await websocket.accept()
    except Exception:
        return
    room = await hub.get_room(artifact_id, branch, store)
    room.join(user, websocket)
    try:
        # 0. presence change to the room's OTHER clients (join notification)
        await _broadcast_json(room, websocket,
                              {"type": "presence", "users": room.awareness_snapshot()})
        # 1. our sync step1 (client replies with its missing updates)
        await websocket.send_bytes(create_sync_message(room.doc))
        # 2. JSON presence snapshot for the joining pane
        await websocket.send_text(json.dumps(
            {"type": "presence", "users": room.awareness_snapshot()}))
        # 3. verbatim replay of each known user's last awareness frame
        for frame in list(room.awareness_frames.values()):
            try:
                await websocket.send_bytes(frame)
            except Exception:
                break
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if "bytes" in msg:
                ok = await _on_binary(hub, room, store, websocket, msg["bytes"], user)
                if not ok:
                    await websocket.close(code=4003)  # spec: drop invalid, close 4003
                    break
            elif "text" in msg:
                await _on_text(hub, room, store, websocket, msg["text"], user)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("collaborate connection error for %s", room.room)
    finally:
        room.leave(user)
        room.evict_stale_awareness(hub.awareness_ttl)
        hub.cleanup_idle_rooms()
        # presence removal broadcast (best-effort; peers may already be gone)
        with suppress(Exception):
            await _broadcast_json(room, websocket, {"type": "presence",
                                                    "users": room.awareness_snapshot()})
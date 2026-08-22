"""Live collaboration room registry (collaboration-spec.md, ADR-06/10).

One authoritative pycrdt `Doc` per (artifact_id, branch) — `room = f"{a}:{b}"`.
The server is the room host: it applies every persisted update, serves the yjs
sync handshake, and is the single writer of branch commits (commit-from-live
under a per-artifact asyncio lock, so concurrent commit_requests serialize and
the second commit's parent is the first's result — realtime-protocol.md).

Rebuild on restart: room is seeded from the branch head content, then the
crdt_ops op log for the room is replayed (deterministic).
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

import pycrdt

from ..objects.store import ObjectStore
from .ops import OpLog, replay_text

TEXT_KEY = "content"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def pinned_author_date(store: ObjectStore, parents: list[str]) -> str:
    """Mirror of api/main._pinned_date so commit-from-live is deterministic.

    GR_AUTHOR_DATE env > first parent's author_date > wall clock. author_date
    is part of commit identity (hashutil.commit_id), so identical
    (parents, text, message, author) commits hash identically.
    """
    env = os.environ.get("GR_AUTHOR_DATE")
    if env:
        return env
    if parents:
        row = store.db.execute(
            "SELECT author_date FROM commits WHERE id=?", (parents[0],)
        ).fetchone()
        if row and row[0]:
            return row[0]
    return datetime.now(UTC).isoformat()


class LiveRoom:
    """One (artifact_id, branch) draft: authoritative Doc + Text + awareness.

    Threading: the hub serializes room creation; all other mutations happen on
    the asyncio loop that services the websocket (single uvicorn worker per
    adr-07). The Text API here is the *server's* — clients edit through yjs
    updates (`apply_update`), the server canonicalizes via `set_text`.
    """

    def __init__(self, artifact_id: str, branch: str, state: bytes | None = None) -> None:
        self.artifact_id = artifact_id
        self.branch = branch
        self.room = f"{artifact_id}:{branch}"
        self.doc = pycrdt.Doc()
        self._text = pycrdt.Text()
        self.doc[TEXT_KEY] = self._text
        if state:  # restore from a serialized snapshot (deserialize path)
            self.doc.apply_update(state)
        self.op_log = OpLog(self.room)
        # awareness: user -> {user, color, cursor, artifact_id, last_seen}
        self.awareness: dict[str, dict] = {}
        # last raw yjs awareness frame per user (replayed to newcomers verbatim)
        self.awareness_frames: dict[str, bytes] = {}
        # connected websocket per user (presence + broadcast bookkeeping)
        self.clients: dict[str, Any] = {}
        self.last_active = time.monotonic()

    # --- text (server side) --------------------------------------------------
    def text(self) -> str:
        return str(self._text)

    def set_text(self, value: str) -> None:
        """Canonicalize the doc text (seed from head, server-side snapshot)."""
        with self.doc.transaction():
            self._text.clear()
            if value:
                self._text.insert(0, value)
        self.touch()

    # --- updates (client -> server) ------------------------------------------
    def apply_update(self, update: bytes, client_id: str = "anonymous") -> bool:
        """Apply one client update to the authoritative doc.

        Idempotent: yjs apply of an already-applied update is a no-op, so
        duplicates / out-of-order frames are harmless (realtime-protocol.md).
        Returns True when the update was new to the room's op log.
        """
        rec = self.op_log.append(update, client_id=client_id)
        if update not in (b"", b"\x00\x00"):
            self.doc.apply_update(update)
        self.touch()
        return rec is not None

    # --- state serialize / deserialize ---------------------------------------
    def state_bytes(self) -> bytes:
        """Full snapshot update — everything needed to rebuild this doc."""
        return self.doc.get_update()

    def snapshot_update(self, state_vector: bytes | None = None) -> bytes:
        """Update from a client state vector (missing content only), or full."""
        if state_vector is None:
            return self.doc.get_update()
        return self.doc.get_update(state_vector)

    def convergence_hash(self) -> str:
        """sha256 of the room text — deterministic convergence handle."""
        return _text_digest(self.text())

    # --- awareness (presence) -------------------------------------------------
    def set_awareness(self, user: str, payload: dict, frame: bytes | None = None) -> None:
        self.awareness[user] = {
            "user": user,
            "color": payload.get("color"),
            "cursor": payload.get("cursor"),
            "artifact_id": self.artifact_id,
            "last_seen": time.monotonic(),
        }
        if frame is not None:
            self.awareness_frames[user] = frame
        self.touch()

    def touch_awareness(self, user: str) -> None:
        rec = self.awareness.get(user)
        if rec is not None:
            rec["last_seen"] = time.monotonic()

    def awareness_snapshot(self) -> list[dict]:
        """Deterministic (sorted-by-user) presence snapshot for the UI."""
        out = [
            {k: v for k, v in rec.items() if k != "last_seen"}
            for rec in self.awareness.values()
        ]
        return sorted(out, key=lambda r: r["user"])

    def evict_stale_awareness(self, ttl: float = 30.0) -> None:
        """realtime-protocol.md: stale awareness evicted after 30s."""
        now = time.monotonic()
        for user in [u for u, rec in self.awareness.items()
                     if now - rec["last_seen"] > ttl]:
            self.awareness.pop(user, None)
            self.awareness_frames.pop(user, None)

    # --- lifecycle -------------------------------------------------------------
    def touch(self) -> None:
        self.last_active = time.monotonic()

    def join(self, user: str, websocket: object) -> None:
        self.clients[user] = websocket
        self.touch()

    def leave(self, user: str) -> None:
        self.clients.pop(user, None)
        self.touch()

    def idled(self, ttl: float) -> bool:
        return not self.clients and (time.monotonic() - self.last_active) > ttl


def _text_digest(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


class CollabHub:
    """Doc registry: one LiveRoom per (artifact_id, branch) + per-artifact lock.

    `artifact_lock(aid)` serializes commit-from-live for one artifact so two
    commit_requests never race the branch ref (spec: "lock serializes; second
    commit's parent is the first's result").
    """

    def __init__(self, store: ObjectStore | None = None,
                 room_idle_ttl: float = 60.0, awareness_ttl: float = 30.0) -> None:
        self.store = store
        self.room_idle_ttl = room_idle_ttl
        self.awareness_ttl = awareness_ttl
        self._rooms: dict[str, LiveRoom] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    @staticmethod
    def room_key(artifact_id: str, branch: str) -> str:
        return f"{artifact_id}:{branch}"

    def artifact_lock(self, artifact_id: str) -> asyncio.Lock:
        lock = self._locks.get(artifact_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[artifact_id] = lock
        return lock

    async def get_room(self, artifact_id: str, branch: str,
                       store: ObjectStore | None = None) -> LiveRoom:
        """Get-or-create the room, seeding from branch head + op-log replay."""
        store = store or self.store
        key = self.room_key(artifact_id, branch)
        async with self._registry_lock:
            self.cleanup_idle_rooms()
            room = self._rooms.get(key)
            if room is None:
                room = LiveRoom(artifact_id, branch)
                self._rooms[key] = room
                if store is not None:
                    self._seed(room, store)
            room.touch()
            return room

    def _seed(self, room: LiveRoom, store: ObjectStore) -> None:
        """Rebuild: branch head content as base state, then replay op log.

        Head content is *base state*, not an op — the convergence invariant
        (data-model.md) is exercised on the op log itself; the seed just gives
        the draft its persisted starting point. Identical text results whether
        the head blob or the op log changed first: ops apply idempotently.
        """
        head = store.head(room.branch, room.artifact_id)
        seed = ""
        if head is not None:
            row = store.db.execute(
                "SELECT root_hash FROM commits WHERE id=?", (head,)
            ).fetchone()
            if row is not None:
                try:
                    seed = store.get_blob(row[0]).decode("utf-8", "replace")
                except KeyError:
                    seed = ""
        if seed:
            room.set_text(seed)
        for (op,) in store.db.execute(
            "SELECT op FROM crdt_ops WHERE room=? ORDER BY seq", (room.room,)
        ).fetchall():
            room.apply_update(bytes(op))

    def active_rooms(self) -> list[str]:
        return sorted(self._rooms)

    def cleanup_idle_rooms(self) -> None:
        """Drop empty rooms idle past the TTL (spec: destroyed after 60s idle).

        Checked on every join/disconnect; a production process may also call it
        on a timer. Deterministic and side-effect free for tests.
        """
        for key in [k for k, r in self._rooms.items() if r.idled(self.room_idle_ttl)]:
            self._rooms.pop(key, None)

    def drop_room(self, artifact_id: str, branch: str) -> None:
        self._rooms.pop(self.room_key(artifact_id, branch), None)


async def commit_live(hub: CollabHub, store: ObjectStore, room: LiveRoom,
                      author: str, message: str) -> str:
    """Commit-from-live (realtime-protocol.md), fully serialized per artifact.

    Lock -> snapshot Text -> canonicalize (put_blob, content-addressed) ->
    DAG commit with parents=[branch head] and CAS ref move. A failure raises
    and touches nothing (store.commit is one transaction); ops arriving during
    the commit land in the NEXT commit by design (collaboration-spec.md).
    """
    async with hub.artifact_lock(room.artifact_id):
        text = room.text()
        kind = _artifact_kind(store, room.artifact_id)
        head = store.head(room.branch, room.artifact_id)
        parents = [head] if head else []
        root_hash = store.put_blob(kind, text.encode("utf-8"))
        author_date = pinned_author_date(store, parents)
        return store.commit(
            parents, root_hash, room.artifact_id, message, author,
            branch=room.branch, expected_head=parents[0] if parents else None,
            kind=kind, author_date=author_date,
        )


def _artifact_kind(store: ObjectStore, artifact_id: str) -> str:
    """Live layer is prose-only (spec non-goals); unknown artifacts default to md."""
    row = store.db.execute(
        "SELECT kind FROM artifacts WHERE id=?", (artifact_id,)
    ).fetchone()
    return row[0] if row else "md"


def rebuild_room_text(store: ObjectStore, artifact_id: str, branch: str) -> str:
    """Deterministic offline rebuild (demo fallback): head seed + op-log replay.

    Pure function used by scripts/replay-style tooling and tests: no room
    object, no network — just the store.
    """
    head = store.head(branch, artifact_id)
    seed = ""
    if head is not None:
        row = store.db.execute(
            "SELECT root_hash FROM commits WHERE id=?", (head,)
        ).fetchone()
        if row is not None:
            try:
                seed = store.get_blob(row[0]).decode("utf-8", "replace")
            except KeyError:
                seed = ""
    updates = [
        bytes(op)
        for (op,) in store.db.execute(
            "SELECT op FROM crdt_ops WHERE room=? ORDER BY seq",
            (CollabHub.room_key(artifact_id, branch),),
        ).fetchall()
    ]
    return replay_text(updates, seed=seed)
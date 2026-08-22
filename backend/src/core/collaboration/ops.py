"""Deterministic CRDT op model (realtime-protocol.md, data-model.md CRDTOperation).

One yjs update (raw bytes, no wire envelope) is one op. Ops are content-addressed
(op_ + sha256(update)[:26]) so identical updates can never be recorded twice —
the persisted op log is a *set* of unique updates, which is what makes the
convergence replay clean ("applying the log in ANY order to an empty doc
converges to the same state"; `seq` never gates correctness).

Everything here is pure Python over pycrdt 0.14.x primitives — no LLM, no
wall-clock dependence, deterministic given the same update bytes:

- `OpLog.append`        : dedup by update digest (replay of an applied op = None).
- `OpLog.missing_ops`   : state-vector sync — exactly the logged ops not covered
                          by a client's state vector (reconnect path).
- `OpLog.missing_update`: merged update of exactly those ops.
- `replay_text`         : deterministic convergence (order/dup-insensitive).
- `convergence_digest`  : sha256 of the converged text (the demo "convergence
                          hash"; byte-identical across orders).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

import pycrdt

# The yjs "empty update" marker (varuint-0 payload). Guarded everywhere: it
# carries no content and must never become an op.
_EMPTY_UPDATES = (b"", b"\x00\x00")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def update_digest(update: bytes) -> str:
    """Content address of an op: the same update bytes always map to one op."""
    return hashlib.sha256(update).hexdigest()


def op_id_for(update: bytes) -> str:
    """Deterministic op id (data-model.md: id `op_*`)."""
    return "op_" + update_digest(update)[:26]


def parse_state_vector(state: bytes) -> dict[int, int]:
    """Decode a yjs state vector to {client_id: clock}.

    yjs sync encoding: varuint clientCount, then (varuint clientId,
    varuint clock) pairs. An empty / unparseable input is treated as a
    client that has NOTHING (returned {}) — safe: reconnect over-sends, and
    yjs apply is idempotent (realtime-protocol.md).
    """
    if not state:
        return {}
    try:
        dec = pycrdt.Decoder(state)
        n = dec.read_var_uint()
        out: dict[int, int] = {}
        for _ in range(n):
            client = dec.read_var_uint()
            clock = dec.read_var_uint()
            out[client] = max(out.get(client, 0), clock)
        return out
    except Exception:
        # Unparseable state vector: assume the client has nothing -> over-send.
        return {}


def update_state_vector(update: bytes) -> dict[int, int]:
    """The state vector implied by one update (max clock per producing client)."""
    if update in _EMPTY_UPDATES:
        return {}
    try:
        return parse_state_vector(pycrdt.get_state(update))
    except Exception:
        # get_state can raise on malformed bytes; treat as unknown -> callers
        # MUST over-send (safe direction), never silently drop.
        return {}


@dataclass(frozen=True)
class OpRecord:
    op_id: str
    room: str
    seq: int          # per-room monotonic, debug only (data-model.md)
    client_id: str    # mock user per realtime-protocol.md presence identity
    update: bytes     # raw yjs update (no wire envelope)
    received_at: str

    # -- persistence adapters (crdt_ops table, schema.sql) -------------------
    @staticmethod
    def from_row(row: tuple) -> OpRecord:
        return OpRecord(row[0], row[1], row[2], row[3], bytes(row[4]), row[5])

    def row(self) -> tuple:
        return (self.op_id, self.room, self.seq, self.client_id, self.update, self.received_at)


class OpLog:
    """In-memory mirror of the persisted op set for one room.

    Correctness never depends on this mirror (the crdt_ops table is the source
    of truth across restarts); it exists so convergence checks, dedup decisions
    and reconnect state-vector math run without touching the store.
    """

    def __init__(self, room: str) -> None:
        self.room = room
        self._seq: list[OpRecord] = []
        self._by_digest: dict[str, OpRecord] = {}

    # --- mutation -----------------------------------------------------------
    def append(
        self,
        update: bytes,
        client_id: str = "anonymous",
        received_at: str | None = None,
    ) -> OpRecord | None:
        """Record one update. Returns None when it is a duplicate (no-op).

        Dedup by content address: replaying an already-applied op neither
        mutates the CRDT nor grows the log (convergence invariant holds).
        """
        if update in _EMPTY_UPDATES:
            return None
        digest = update_digest(update)
        if digest in self._by_digest:
            return None
        rec = OpRecord(
            op_id=op_id_for(update),
            room=self.room,
            seq=len(self._seq) + 1,
            client_id=client_id,
            update=update,
            received_at=received_at or _now_iso(),
        )
        self._by_digest[digest] = rec
        self._seq.append(rec)
        return rec

    def __len__(self) -> int:
        return len(self._seq)

    def __iter__(self):
        return iter(self._seq)

    def all(self) -> list[OpRecord]:
        return list(self._seq)

    # --- state-vector sync (reconnect: send exactly the missing ops) --------
    def missing_ops(self, state_vector: bytes) -> list[OpRecord]:
        """Logged ops NOT fully contained in the client's state vector.

        An op is redundant iff every (client, clock) in its own state vector is
        covered by the client's vector. Updates with an unparseable/empty state
        vector are treated as missing (over-send — yjs apply is idempotent, so
        a redundant op is harmless; a dropped-needed op is not).
        """
        have = parse_state_vector(state_vector)
        missing: list[OpRecord] = []
        for rec in self._seq:
            st = update_state_vector(rec.update)
            if not st:
                missing.append(rec)  # conservative: can't prove it is covered
            elif any(have.get(c, 0) < clk for c, clk in st.items()):
                missing.append(rec)
        return missing

    def missing_update(self, state_vector: bytes) -> bytes:
        """One merged update of exactly the missing ops (empty bytes if none)."""
        ops = self.missing_ops(state_vector)
        if not ops:
            return b""
        return pycrdt.merge_updates(*[o.update for o in ops])

    # --- convergence --------------------------------------------------------
    def replay_text(self, seed: str = "") -> str:
        """Replay the log onto a FRESH doc and return the deterministic text."""
        return replay_text([o.update for o in self._seq], seed=seed)

    def convergence_digest(self, seed: str = "") -> str:
        return convergence_digest([o.update for o in self._seq], seed=seed)

    # --- persistence adapters ------------------------------------------------
    @staticmethod
    def load_rows(rows: list[tuple]) -> OpLog:
        """Rebuild an in-memory log from crdt_ops rows (room rebuilt on restart)."""
        log = OpLog(rows[0][1] if rows else "")
        for row in rows:
            rec = OpRecord.from_row(row)
            log._by_digest[update_digest(rec.update)] = rec
            log._seq.append(rec)
        return log


def replay_text(updates: list[bytes], seed: str = "") -> str:
    """Deterministic convergence: apply `updates` to an empty doc (optionally
    over a seeded base string) in ANY order and return the resulting text.

    yjs/Yrs apply is idempotent and order-independent, so this function is the
    executable statement of data-model.md's convergence invariant.
    """
    doc = pycrdt.Doc()
    text = pycrdt.Text()
    doc["content"] = text
    if seed:
        with doc.transaction():
            text.insert(0, seed)
    for update in updates:
        if update in _EMPTY_UPDATES:
            continue
        doc.apply_update(update)  # duplicates/out-of-order are safe by CRDT
    return str(text)


def convergence_digest(updates: list[bytes], seed: str = "") -> str:
    """sha256 of the converged text — identical for every delivery order."""
    return hashlib.sha256(replay_text(updates, seed=seed).encode()).hexdigest()
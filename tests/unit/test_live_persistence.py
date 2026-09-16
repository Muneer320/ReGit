import asyncio

import pytest

from backend.src.core.collaboration.rooms import CollabHub, LiveRoom, commit_live, persist_room
from backend.src.core.objects.store import ObjectStore, RefConflictError


def setup_store(tmp_path):
    store = ObjectStore(str(tmp_path))
    store.db.execute("INSERT INTO artifacts(id,kind,title) VALUES ('notes','md','Notes')")
    blob = store.put_blob('md', b'Initial research.')
    root = store.commit([], blob, 'notes', 'root', 'test', kind='md')
    return store, root


def test_pending_draft_keeps_crdt_identity_across_room_restart(tmp_path):
    store, _ = setup_store(tmp_path)

    async def scenario():
        room = await CollabHub(store).get_room('notes', 'main')
        room.set_text('Pending draft.\nclaim: A preserved finding.')
        persist_room(store, room)
        peer = LiveRoom('notes', 'main', state=room.doc.get_update())
        recovered = await CollabHub(store).get_room('notes', 'main')
        assert recovered.doc.get_state() == room.doc.get_state()
        assert recovered.text() == room.text()
        peer.set_text('Updated after reconnect.')
        recovered.apply_update(peer.doc.get_update())
        assert recovered.text() == 'Updated after reconnect.'
        cid = await commit_live(CollabHub(store), store, recovered, 'test', 'Save recovered draft')
        reopened = await CollabHub(store).get_room('notes', 'main')
        assert reopened.text() == 'Updated after reconnect.'
        assert reopened.base_commit == cid
    asyncio.run(scenario())


def test_live_commit_captures_claims_and_rejects_an_external_advance(tmp_path):
    store, root = setup_store(tmp_path)

    async def scenario():
        hub = CollabHub(store)
        room = await hub.get_room('notes', 'main')
        room.set_text('claim: New live evidence.')
        cid = await commit_live(hub, store, room, 'test', 'Save evidence')
        assert store.db.execute('SELECT text FROM claims WHERE commit_id=?', (cid,)).fetchone()[0] == 'New live evidence.'
        room.set_text('Uncommitted collaboration.')
        persist_room(store, room)
        newer_blob = store.put_blob('md', b'A newer REST edit.')
        newer = store.commit([cid], newer_blob, 'notes', 'REST edit', 'test', expected_head=cid, kind='md')
        with pytest.raises(RefConflictError):
            await commit_live(hub, store, room, 'test', 'Stale live commit')
        assert store.head('main', 'notes') == newer
        reopened = await CollabHub(store).get_room('notes', 'main')
        assert reopened.text() == 'Uncommitted collaboration.'
        assert reopened.base_commit == cid
    asyncio.run(scenario())


def test_clean_rebase_keeps_old_crdt_tombstones_for_reconnecting_peers(tmp_path):
    store, root = setup_store(tmp_path)

    async def scenario():
        room = await CollabHub(store).get_room('notes', 'main')
        peer = LiveRoom('notes', 'main', state=room.doc.get_update())
        blob = store.put_blob('md', b'Revised committed text.')
        store.commit([root], blob, 'notes', 'REST edit', 'test', expected_head=root, kind='md')
        reopened = await CollabHub(store).get_room('notes', 'main')
        peer.apply_update(reopened.doc.get_update())
        assert peer.text() == 'Revised committed text.'
        reopened.apply_update(peer.doc.get_update())
        assert reopened.text() == 'Revised committed text.'
    asyncio.run(scenario())


@pytest.mark.parametrize('subtype', [1, 2])
def test_empty_sync_reply_is_a_valid_handshake_frame(tmp_path, subtype):
    from unittest.mock import AsyncMock
    from backend.src.realtime.ws import _on_binary

    store, _ = setup_store(tmp_path)

    async def scenario():
        hub = CollabHub(store)
        room = await hub.get_room('notes', 'main')
        assert await _on_binary(hub, room, store, AsyncMock(), bytes([0, subtype, 2, 0, 0]), 'userA')
        assert room.text() == 'Initial research.'
    asyncio.run(scenario())


def test_explicit_reset_preserves_crdt_identity_and_does_not_create_a_commit(tmp_path):
    import json
    from unittest.mock import AsyncMock
    import pycrdt
    from backend.src.realtime.ws import _on_text

    store, root = setup_store(tmp_path)

    async def scenario():
        hub = CollabHub(store)
        room = await hub.get_room('notes', 'main')
        room.set_text('Pending discarded draft.')
        peer = LiveRoom('notes', 'main', state=room.doc.get_update())
        socket = AsyncMock()
        room.clients['userA'] = socket
        await _on_text(hub, room, store, socket, json.dumps({'type': 'reset_request'}), 'userA')
        update = socket.send_bytes.call_args.args[0]
        pycrdt.handle_sync_message(update[1:], peer.doc)
        assert peer.text() == 'Initial research.'
        assert room.base_commit == root and store.head('main', 'notes') == root
    asyncio.run(scenario())

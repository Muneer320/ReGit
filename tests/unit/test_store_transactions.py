from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.src.core.objects.store import ObjectStore, RefConflictError


def test_nested_transaction_rolls_back_index_and_recovers_disk_blob(tmp_path):
    store = ObjectStore(str(tmp_path))
    with pytest.raises(RuntimeError):
        with store._tx():
            blob = store.put_blob('txt', b'rollback fixture')
            store.commit([], blob, 'one', 'root', 'test')
            raise RuntimeError('abort the outer operation')
    assert store.head('main', 'one') is None
    assert store.db.execute('SELECT count(*) FROM objects').fetchone()[0] == 0
    assert store.put_blob('txt', b'rollback fixture') == blob
    assert store.db.execute('SELECT count(*) FROM objects').fetchone()[0] == 1
    assert store.get_blob(blob, verify=True) == b'rollback fixture'


def test_concurrent_blob_and_commit_writes_share_connection_safely(tmp_path):
    store = ObjectStore(str(tmp_path))

    def write(index):
        blob = store.put_blob('txt', b'shared content')
        return store.commit([], blob, f'art_{index}', 'root', 'test')

    with ThreadPoolExecutor(max_workers=8) as pool:
        commits = list(pool.map(write, range(24)))
    assert len(set(commits)) == 24
    assert store.db.execute('SELECT count(*) FROM objects').fetchone()[0] == 1
    assert store.db.execute('SELECT count(*) FROM commits').fetchone()[0] == 24


def test_parent_branch_and_ref_cannot_cross_artifact_boundaries(tmp_path):
    store = ObjectStore(str(tmp_path))
    blob = store.put_blob('txt', b'content')
    root = store.commit([], blob, 'one', 'root', 'test')
    with pytest.raises(ValueError):
        store.commit([root], blob, 'two', 'bad parent', 'test')
    with pytest.raises(ValueError):
        store.create_branch('foreign', 'two', root)
    store.commit([], blob, 'two', 'root', 'test')
    with pytest.raises(ValueError):
        store.advance_branch('main', 'two', root)
    with pytest.raises(RefConflictError):
        store.commit([root], blob, 'one', 'missing branch', 'test', branch='deleted', expected_head=root)

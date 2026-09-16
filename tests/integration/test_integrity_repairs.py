"""Regression checks for deletion, paths and concurrent merge requests."""
import pytest


def create(client, text='Base sentence.'):
    response = client.post('/api/artifacts', json={'kind': 'md', 'title': 'notes.md', 'content': text})
    assert response.status_code == 201
    return response.json()['artifact_id'], response.json()['root_commit_id']


def commit(client, artifact, branch, text):
    response = client.post(f'/api/artifacts/{artifact}/commit', json={
        'branch': branch, 'content': text, 'message': f'edit {branch}',
    })
    assert response.status_code == 201
    return response.json()['commit_id']


def conflicted(client):
    artifact, root = create(client)
    assert client.post('/api/branches', json={'artifact_id': artifact, 'name': 'feature', 'from_commit': root}).status_code == 201
    ours = commit(client, artifact, 'main', 'Our replacement.')
    commit(client, artifact, 'feature', 'Their replacement.')
    response = client.post('/api/merge', json={'artifact_id': artifact, 'ours_branch': 'main', 'theirs_branch': 'feature'})
    assert response.status_code == 201
    assert response.json()['state'] == 'conflicts'
    return artifact, ours, response.json()


def test_deleted_artifact_stays_out_of_workspace(client):
    artifact, _ = create(client)
    assert client.delete(f'/api/artifacts/{artifact}').status_code == 204
    assert artifact not in {item['id'] for item in client.get('/api/artifacts').json()}
    assert client.get(f'/api/artifacts/{artifact}').status_code == 404


@pytest.mark.parametrize('path', ['../outside', r'notes\..\outside', '/absolute', r'C:\outside', '\\server\share', 'bad\x00name'])
def test_repository_paths_reject_escape_and_nul(client, path):
    artifact, _ = create(client)
    response = client.post(f'/api/artifacts/{artifact}/folders', json={'path': path})
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'BAD_PATH'


def test_repository_paths_normalize_windows_separators(client):
    artifact, _ = create(client)
    response = client.post(f'/api/artifacts/{artifact}/folders', json={'path': r'notes\nested'})
    assert response.status_code == 201
    assert response.json()['path'] == 'notes/nested'


def test_empty_free_resolution_deletes_conflicting_text(client):
    artifact, _, merge = conflicted(client)
    response = client.post('/api/merge/' + merge['merge_id'] + '/resolve', json={
        'resolutions': [{'conflict_id': item['id'], 'resolution': 'free', 'resolved_text': ''} for item in merge['conflicts']],
    })
    assert response.status_code == 200, response.text
    checkout = client.post('/api/checkout', json={'artifact_id': artifact}).json()
    assert checkout['content'].strip() == ''


def test_pending_merge_rejects_a_moved_target(client):
    artifact, _, merge = conflicted(client)
    advanced = commit(client, artifact, 'main', 'A newer edit that must survive.')
    response = client.post('/api/merge/' + merge['merge_id'] + '/resolve', json={
        'resolutions': [{'conflict_id': item['id'], 'resolution': 'ours'} for item in merge['conflicts']],
    })
    assert response.status_code == 409
    assert client.app.state.store.head('main', artifact) == advanced
    assert client.app.state.store.head(None, artifact) is None


def test_resolution_advances_requested_branch_when_an_alias_shares_its_head(client):
    artifact, ours, merge = conflicted(client)
    client.post('/api/branches', json={'artifact_id': artifact, 'name': 'alias', 'from_commit': ours})
    response = client.post('/api/merge/' + merge['merge_id'] + '/resolve', json={
        'resolutions': [{'conflict_id': item['id'], 'resolution': 'ours'} for item in merge['conflicts']],
    })
    assert response.status_code == 200
    assert client.app.state.store.head('main', artifact) == response.json()['result_commit_id']
    assert client.app.state.store.head('alias', artifact) == ours


def test_clean_merge_cannot_overwrite_a_concurrent_commit(client, monkeypatch):
    artifact, root = create(client, 'First sentence.\n\nSecond sentence.')
    client.post('/api/branches', json={'artifact_id': artifact, 'name': 'feature', 'from_commit': root})
    ours = commit(client, artifact, 'main', 'Changed first.\n\nSecond sentence.')
    commit(client, artifact, 'feature', 'First sentence.\n\nChanged second.')
    store = client.app.state.store
    original = store.commit
    advanced = []

    def racing_commit(*args, **kwargs):
        newer = store.put_blob('md', b'A concurrent edit.')
        advanced.append(original([ours], newer, artifact, 'concurrent edit', 'other', expected_head=ours))
        return original(*args, **kwargs)

    monkeypatch.setattr(store, 'commit', racing_commit)
    response = client.post('/api/merge', json={'artifact_id': artifact, 'ours_branch': 'main', 'theirs_branch': 'feature'})
    assert response.status_code == 409, response.text
    assert store.head('main', artifact) == advanced[0]


def test_checkout_and_diff_cannot_mix_commits_from_other_artifacts(client):
    artifact, root = create(client, 'First artifact.')
    _, other_root = create(client, 'Other artifact.')
    assert client.post('/api/checkout', json={'artifact_id': artifact, 'commit': other_root}).status_code == 404
    assert client.get('/api/diff', params={'artifact_id': artifact, 'from': root, 'to': other_root}).status_code == 404
    assert client.post('/api/branches', json={'artifact_id': artifact, 'name': 'foreign', 'from_commit': other_root}).status_code == 400


def test_rest_commits_capture_updated_claims_without_duplicate_rows(client):
    artifact, root = create(client, 'claim: Initial evidence.')
    later = commit(client, artifact, 'main', 'claim: Updated evidence.')
    earlier = client.get(f'/api/provenance/at/{root}/claims').json()
    current = client.get(f'/api/provenance/at/{later}/claims').json()
    assert [claim['text'] for claim in earlier] == ['Initial evidence.']
    assert {claim['text'] for claim in current} == {'Initial evidence.', 'Updated evidence.'}
    assert len(current) == 2


def test_chat_diff_reports_message_changes(client):
    import json
    before = {'version': 1, 'kind': 'chat', 'messages': [{'ord': 0, 'role': 'assistant', 'text': 'Original answer.'}]}
    created = client.post('/api/artifacts', json={'kind': 'chat', 'title': 'Conversation', 'content': json.dumps(before)}).json()
    aid, root = created['artifact_id'], created['root_commit_id']
    after = {'version': 1, 'kind': 'chat', 'messages': [{'ord': 0, 'role': 'assistant', 'text': 'Revised answer.'}]}
    latest = commit(client, aid, 'main', json.dumps(after))
    response = client.get('/api/diff', params={'artifact_id': aid, 'from': root, 'to': latest})
    assert response.status_code == 200, response.text
    assert response.json()['kind'] == 'chat'
    changes = response.json()['changes']
    assert any(item.get('old_text') == 'Original answer.' for item in changes)
    assert any(item.get('new_text') == 'Revised answer.' for item in changes)


def test_historical_search_restores_overwritten_text_and_hides_deleted_artifacts(client):
    artifact, root = create(client, 'The original zephyr finding.')
    updated = commit(client, artifact, 'main', 'A replacement cobalt conclusion.')
    assert client.post('/api/search', json={'query': 'zephyr'}).json()['results'] == []
    old = client.post('/api/search', json={'query': 'zephyr', 'as_of_commit': root}).json()['results']
    assert len(old) == 1 and old[0]['text'] == 'The original zephyr finding.'
    assert old[0]['introduced_in_commit'] == root
    assert client.post('/api/search', json={'query': 'zephyr', 'as_of_commit': updated}).json()['results'] == []
    assert client.post('/api/search', json={'query': 'cobalt'}).json()['results']
    client.delete(f'/api/artifacts/{artifact}')
    assert client.post('/api/search', json={'query': 'cobalt'}).json()['results'] == []

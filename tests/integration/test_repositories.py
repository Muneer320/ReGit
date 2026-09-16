"""Repository snapshots retain exact files and isolate branch mutations."""
import pytest


def repository(client, name='Research'):
    response = client.post('/api/repositories', json={'name': name})
    assert response.status_code == 201, response.text
    return response.json()


def change(snapshot, path, **extra):
    return {'path': path, 'base_commit': snapshot['commit_id'], 'branch': snapshot['branch'],
            'message': 'Update ' + path, **extra}


def upload(client, snapshot, files, folder='', file_type='auto'):
    return client.post('/api/repositories/' + snapshot['id'] + '/files',
                       data={'path': folder, 'branch': snapshot['branch'], 'base_commit': snapshot['commit_id'],
                             'message': 'Upload sources', 'file_type': file_type},
                       files=[('files', (name, content, 'application/octet-stream')) for name, content in files])


def test_multiple_repositories_nested_files_versions_and_exact_download(client):
    original = repository(client)
    other = repository(client, 'Independent')
    rid = original['id']
    response = client.post(f'/api/repositories/{rid}/folders', json=change(original, 'notes/experiments'))
    assert response.status_code == 201, response.text
    folder = response.json()
    response = upload(client, folder, [('results.md', b'# Results\n\nFirst result.'), ('config.json', b'{"rate":0.1}'), ('image.png', b'\x89PNG\x00\xff')], 'notes/experiments')
    assert response.status_code == 201, response.text
    uploaded = response.json()
    entries = {entry['path']: entry for entry in uploaded['entries']}
    assert entries['notes']['type'] == 'folder'
    assert entries['notes/experiments/config.json']['kind'] == 'txt', 'Ordinary JSON is not a chat export.'
    assert entries['notes/experiments/image.png']['kind'] == 'binary'
    assert client.get(f'/api/repositories/{other["id"]}').json()['entries'] == []
    assert len(client.get('/api/repositories').json()) == 2
    path = 'notes/experiments/results.md'
    edited = client.patch(f'/api/repositories/{rid}/file', json=change(uploaded, path, content='# Results\n\nSecond result.'))
    assert edited.status_code == 200, edited.text
    assert client.get(f'/api/repositories/{rid}/file', params={'path': path}).content == b'# Results\n\nSecond result.'
    assert client.get(f'/api/repositories/{rid}/file', params={'path': path, 'commit': uploaded['commit_id']}).content == b'# Results\n\nFirst result.'
    assert client.get(f'/api/repositories/{rid}', params={'commit': original['commit_id']}).json()['entries'] == []
    assert len(client.get(f'/api/repositories/{rid}/history').json()) == 4
    deleted = client.request('DELETE', f'/api/repositories/{rid}/entry', json=change(edited.json(), 'notes'))
    assert deleted.status_code == 200 and deleted.json()['entries'] == []
    assert client.get(f'/api/repositories/{rid}/file', params={'path': path}).status_code == 404
    assert client.get(f'/api/repositories/{rid}/file', params={'path': path, 'commit': uploaded['commit_id']}).status_code == 200


def test_branch_snapshot_and_stale_writer_protection(client):
    start = repository(client)
    uploaded = upload(client, start, [('notes.txt', b'Common base.')]).json()
    rid = start['id']
    branch = client.post(f'/api/repositories/{rid}/branches', json={'name': 'experiment', 'from_commit': uploaded['commit_id']})
    assert branch.status_code == 201
    edited = client.patch(f'/api/repositories/{rid}/file', json=change(branch.json(), 'notes.txt', content='Feature version.'))
    assert edited.status_code == 200, edited.text
    assert client.get(f'/api/repositories/{rid}/file', params={'path': 'notes.txt', 'branch': 'main'}).content == b'Common base.'
    assert client.get(f'/api/repositories/{rid}/file', params={'path': 'notes.txt', 'branch': 'experiment'}).content == b'Feature version.'
    stale = client.patch(f'/api/repositories/{rid}/file', json=change(branch.json(), 'notes.txt', content='Stale version.'))
    assert stale.status_code == 409
    assert client.get(f'/api/repositories/{rid}', params={'branch': 'experiment'}).json()['commit_id'] == edited.json()['commit_id']


def test_failed_batch_rolls_back_tree_source_and_child_commits(client):
    start = repository(client)
    store = client.app.state.store
    before = {table: store.db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ['sources', 'artifacts', 'commits', 'objects']}
    failed = upload(client, start, [('good.pdf', b'not a PDF')], file_type='pdf')
    assert failed.status_code == 422
    # The first text file writes blobs and metadata before the second fails.
    failed = upload(client, start, [('good.md', b'Valid text.'), ('bad.pdf', b'not a PDF')])
    assert failed.status_code == 422
    assert {table: store.db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in before} == before
    assert client.get('/api/repositories/' + start['id']).json()['commit_id'] == start['commit_id']
    retry = upload(client, start, [('good.md', b'Valid text.')])
    assert retry.status_code == 201, retry.text


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:\\absolute', 'folder/../../escape', 'nul\x00path'])
def test_paths_and_file_folder_collisions(client, path):
    start = repository(client)
    response = client.post('/api/repositories/' + start['id'] + '/folders', json=change(start, path))
    assert response.status_code == 400


def test_snapshot_ownership_collisions_and_repository_deletion(client):
    start, other = repository(client), repository(client)
    rid = start['id']
    assert client.get(f'/api/repositories/{rid}', params={'commit': other['commit_id']}).status_code == 404
    uploaded = upload(client, start, [('file.txt', b'Original')]).json()
    collision = client.post(f'/api/repositories/{rid}/folders', json=change(uploaded, 'file.txt/nested'))
    assert collision.status_code == 409
    duplicate = upload(client, uploaded, [('same.txt', b'one'), ('same.txt', b'two')])
    assert duplicate.status_code == 409
    assert client.delete(f'/api/repositories/{rid}').status_code == 204
    assert rid not in {item['id'] for item in client.get('/api/repositories').json()}
    assert client.get(f'/api/repositories/{rid}').status_code == 404


def test_activity_uses_real_commits_and_keeps_repositories_out_of_artifact_listing(client):
    assert client.get('/api/activity').json() == []
    created = repository(client, 'Actual activity')
    activity = client.get('/api/activity').json()
    assert len(activity) == 1
    assert activity[0]['commit_id'] == created['commit_id']
    assert activity[0]['title'] == 'Actual activity'
    assert client.get('/api/artifacts').json() == []
    client.delete('/api/repositories/' + created['id'])
    assert client.get('/api/activity').json() == []


def test_live_file_publication_is_explicit_versioned_and_branch_local(client):
    start = upload(client, repository(client), [('notes.md', b'Original finding.')]).json()
    rid = start['id']
    branch = client.post(f'/api/repositories/{rid}/branches', json={'name': 'experiment', 'from_commit': start['commit_id']}).json()
    prepared = client.post(f'/api/repositories/{rid}/file/live', json=change(branch, 'notes.md')).json()
    assert prepared['branch'].endswith('/experiment')
    saved = client.post('/api/artifacts/' + prepared['artifact_id'] + '/commit', json={
        'branch': prepared['branch'], 'base_commit': prepared['commit_id'],
        'content': 'A saved live finding.', 'message': 'Save live draft',
    })
    assert saved.status_code == 201, saved.text
    assert client.get(f'/api/repositories/{rid}/file', params={'path': 'notes.md', 'branch': 'experiment'}).content == b'Original finding.'
    published = client.post(f'/api/repositories/{rid}/file/publish', json=change(branch, 'notes.md'))
    assert published.status_code == 200, published.text
    assert client.get(f'/api/repositories/{rid}/file', params={'path': 'notes.md', 'branch': 'experiment'}).content == b'A saved live finding.'
    assert client.get(f'/api/repositories/{rid}/file', params={'path': 'notes.md', 'branch': 'main'}).content == b'Original finding.'
    assert client.get(f'/api/repositories/{rid}/file', params={'path': 'notes.md', 'commit': start['commit_id']}).content == b'Original finding.'
    duplicate = client.post(f'/api/repositories/{rid}/file/publish', json=change(published.json(), 'notes.md'))
    assert duplicate.status_code == 409 and duplicate.json()['error']['code'] == 'NO_NEW_COMMIT'

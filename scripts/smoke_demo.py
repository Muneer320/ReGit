"""Exercise the local repository/research demo using synthetic data only."""
import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8377')
    parser.add_argument('--state-out', type=Path)
    parser.add_argument('--verify-state', type=Path)
    parser.add_argument('--live', action='store_true', help='Also test real WebSockets; requires the project dependencies.')
    args = parser.parse_args()
    assert urlparse(args.base_url).hostname in ('127.0.0.1', 'localhost'), 'Use a local demo endpoint.'
    base = args.base_url.rstrip('/')

    def http(path, body=None, method=None, status=200, content_type='application/json'):
        payload = json.dumps(body).encode() if body is not None and not isinstance(body, bytes) else body
        request = Request(base + '/api' + path, data=payload, method=method,
                          headers={'Content-Type': content_type, 'X-User': 'smoke'})
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            assert response.status == status, (path, response.status, data.decode(errors='replace'))
            return data

    def api(path, body=None, method=None, status=200):
        data = http(path, body, method, status)
        return json.loads(data) if data else None

    def change(snapshot, path, **extra):
        return {'path': path, 'base_commit': snapshot['commit_id'], 'branch': snapshot['branch'], 'message': 'Synthetic smoke update', **extra}

    def verify(state):
        rid = state['repository_id']
        assert http(f'/repositories/{rid}/file?' + urlencode({'path': 'notes/nested/finding.md'})).decode() == state['current_text']
        assert http(f'/repositories/{rid}/file?' + urlencode({'path': 'notes/nested/finding.md', 'commit': state['uploaded_commit']})).decode() == state['original_text']
        assert http(f'/repositories/{rid}/file?' + urlencode({'path': 'notes/nested/finding.md', 'branch': 'experiment'})).decode() == 'Feature branch finding.'
        assert len(api(f'/repositories/{rid}/history')) >= 4

    def live(aid, expected, commit=False, edit=None):
        import pycrdt
        import websockets.sync.client as websocket

        doc = pycrdt.Doc()
        doc['content'] = pycrdt.Text()
        socket = websocket.connect(base.replace('http://', 'ws://').replace('https://', 'wss://') + f'/api/collaborate/{aid}?user=smoke&branch=main')
        socket.send(pycrdt.create_sync_message(doc))

        def pump(until_text=None, until_commit=False):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                message = socket.recv(timeout=5)
                if isinstance(message, bytes) and message[0] == 0:
                    reply = pycrdt.handle_sync_message(message[1:], doc)
                    if reply is not None:
                        socket.send(reply)
                elif isinstance(message, str):
                    payload = json.loads(message)
                    assert payload.get('type') != 'error', payload
                    if until_commit and payload.get('type') == 'committed':
                        return payload['commit_id']
                if until_text is not None and str(doc['content']) == until_text:
                    return
            raise AssertionError('Collaboration did not converge before the deadline.')

        try:
            pump(until_text=expected)
            if edit is not None:
                with doc.transaction():
                    doc['content'].clear()
                    doc['content'].insert(0, edit)
                socket.send(pycrdt.create_update_message(doc.get_update()))
            if commit:
                socket.send(json.dumps({'type': 'commit_request', 'message': 'Synthetic live save'}))
                return pump(until_commit=True)
        finally:
            socket.close()

    for attempt in range(30):
        try:
            api('/health')
            break
        except (URLError, OSError, AssertionError):
            if attempt == 29:
                raise
            time.sleep(1)
    if args.verify_state:
        state = json.loads(args.verify_state.read_text(encoding='utf-8'))
        verify(state)
        if args.live and state.get('live_artifact_id'):
            cid = live(state['live_artifact_id'], state['pending_live_text'], commit=True)
            assert api('/checkout', {'artifact_id': state['live_artifact_id']})['content'] == state['pending_live_text']
            assert any(claim['text'] == 'Shared smoke evidence.' for claim in api(f'/provenance/at/{cid}/claims'))
        print('Restart verification passed: repository history, branch bytes and pending live draft retained.')
        return

    prefix = 'smoke-' + uuid.uuid4().hex[:10]
    repository = api('/repositories', {'name': prefix}, status=201)
    other = api('/repositories', {'name': prefix + '-other'}, status=201)
    rid = repository['id']
    folder = api(f'/repositories/{rid}/folders', change(repository, 'notes/nested'), status=201)
    original = '# Findings\n\nOriginal zephyr café evidence.'
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in {'path': 'notes/nested', 'branch': 'main', 'base_commit': folder['commit_id'], 'message': 'Upload smoke fixtures'}.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    for name, data in [('finding.md', original.encode()), ('config.json', b'{"rate":0.1}'), ('image.png', b'\x89PNG\x00\xff')]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    uploaded = json.loads(http(f'/repositories/{rid}/files', b''.join(parts), status=201, content_type='multipart/form-data; boundary=' + boundary))
    current = '# Findings\n\nRevised cobalt evidence.'
    edited = api(f'/repositories/{rid}/file', change(uploaded, 'notes/nested/finding.md', content=current), 'PATCH')
    stale = api(f'/repositories/{rid}/file', change(uploaded, 'notes/nested/finding.md', content='Stale'), 'PATCH', status=409)
    assert stale['error']['code'] == 'REF_CONFLICT'
    branch = api(f'/repositories/{rid}/branches', {'name': 'experiment', 'from_commit': edited['commit_id']}, status=201)
    api(f'/repositories/{rid}/file', change(branch, 'notes/nested/finding.md', content='Feature branch finding.'), 'PATCH')
    assert api(f'/repositories/{other["id"]}')['entries'] == []
    state = {'repository_id': rid, 'uploaded_commit': uploaded['commit_id'], 'original_text': original, 'current_text': current}
    verify(state)

    art = api('/artifacts', {'kind': 'md', 'title': prefix, 'content': 'Base sentence.\nclaim: Initial smoke evidence.'}, status=201)
    aid, root = art['artifact_id'], art['root_commit_id']
    api('/branches', {'artifact_id': aid, 'name': 'feature', 'from_commit': root}, status=201)
    ours = api(f'/artifacts/{aid}/commit', {'branch': 'main', 'content': 'Our replacement.\nclaim: Shared smoke evidence.', 'message': 'Our finding'}, status=201)['commit_id']
    theirs = api(f'/artifacts/{aid}/commit', {'branch': 'feature', 'content': 'Their replacement.', 'message': 'Their finding'}, status=201)['commit_id']
    assert api('/diff?' + urlencode({'artifact_id': aid, 'from': root, 'to': ours}))['changes']
    merged = api('/merge', {'artifact_id': aid, 'ours_branch': 'main', 'theirs_branch': 'feature'}, status=201)
    if merged['state'] == 'conflicts':
        merged = api('/merge/' + merged['merge_id'] + '/resolve', {'resolutions': [{'conflict_id': conflict['id'], 'resolution': 'ours'} for conflict in merged['conflicts']]})
    result = merged['result_commit_id']
    history = api(f'/artifacts/{aid}/history')
    assert set(history[0]['parents']) == {ours, theirs}
    assert any(claim['text'] == 'Shared smoke evidence.' for claim in api(f'/provenance/at/{result}/claims'))
    assert api('/search', {'query': 'Initial', 'as_of_commit': root})['results']
    if args.live:
        checkout = api('/checkout', {'artifact_id': aid})['content']
        pending = checkout + '\nPending collaboration survives restart.'
        live(aid, checkout, edit=pending)
        state.update(live_artifact_id=aid, pending_live_text=pending)
    if args.state_out:
        args.state_out.write_text(json.dumps(state, indent=2), encoding='utf-8')
    print('Demo smoke passed: repositories, folders, typed uploads, history, branch isolation, stale writes, prose diff/merge, claims and historical search.')
    if args.live:
        print('Real WebSocket sync/update passed; pending draft retained for restart verification.')


if __name__ == '__main__':
    main()
